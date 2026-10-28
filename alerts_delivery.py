"""Email verified subscribers' alerts through the alerts Worker. Off by default.

Runs after the owner's own notifications and never touches them. It is a
no-op unless ``ALERTS_DELIVERY_ENABLED`` is ``1`` or ``true``. Then
``ALERTS_API_URL`` (https) and ``ALERTS_HMAC_SECRET`` (32+ characters) are
required; anything missing or unsafe skips delivery and logs only the setting
names (fail closed).

Each run:

1. ``GET /v1/internal/routes`` (HMAC-signed): verified subscribers' rules,
   keyed by an opaque route id. No email addresses ever reach this job.
2. For each route, the existing engine (``notification_engine.evaluate``)
   plans events from this scrape, using that route's own state file. Search
   rules match brand/name words; product watches match one listing by its
   identity key (``history_identity.listing_identity``), never by name.
3. A route with a ``digest`` rule also gets today's general deals section:
   new listings, meaningful price drops, and new tracked lows from stores
   that scraped cleanly, capped at ``MAX_DIGEST_ITEMS``, once per day.
4. ``POST /v1/internal/deliveries`` (HMAC-signed): one email per route. The
   Worker records every event id it has emailed (one id per digest day), so
   a retried request never sends twice.
5. The Worker's answer is written back to the route's state.

State is one engine journal per route under ``ALERTS_STATE_DIR`` (default
``alerts_state/``), restored and saved by the Actions cache and never
committed. It holds hashes only. If the directory is lost, delivery refuses to
start until ``ALERTS_ALLOW_BOOTSTRAP=1``; if one known route's file is lost,
that route is skipped. Either way a lost journal cannot cause repeat emails.

The API contract is in docs/alerts-api.md; setup is in docs/alerts-backend.md.
"""

import copy
import fcntl
import hashlib
import hmac
import json
import logging
import os
import re
import secrets
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit

from filters import item_passes_filters, normalize_url
from history import all_time_low_status
from history_identity import listing_identity
from notification_engine import MAX_DIGEST_WATCHES, _hash, empty_state, evaluate, load_state, save_state
from report import build_digest, compare_catalogs
from watchlist import _width_of

logger = logging.getLogger("alerts_delivery")

DEFAULT_STATE_DIR = "alerts_state"
MANIFEST = "manifest.json"
MIN_SECRET_LENGTH = 32
MAX_ROUTES = 1000
MAX_RULES = 25
CHUNK = 100
TIMEOUT = 30
MAX_RESPONSE = 2 * 1024 * 1024

# The general digest. One section a day per subscriber, at most this many
# listings (worker/src/internal.js MAX_DIGEST_ITEMS); the email links to the
# site for the rest.
MAX_DIGEST_ITEMS = 30
DIGEST_EVENTS = ("new", "drop", "low")
# A store category whose "new" listings are mostly a re-listing, not news:
# no earlier rows at all, or more than REBASELINE_SHARE of today's rows and
# more than REBASELINE_MIN of them. Its new listings are left out that day
# (drops and lows still count). See docs/alerts-backend.md.
REBASELINE_MIN = 20
REBASELINE_SHARE = 0.5

_ROUTE_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_RULE_ID_RE = re.compile(r"r_[0-9a-f]{24}")
_PARTS = {"Decks", "Wheels", "Trucks", "Bearings"}
_CATALOG_PARTS = ("Decks", "Trucks", "Wheels", "Bearings", "Sneakers", "Accessories", "Completes", "Protection")
# worker/src/email.js STORE_HOSTS: the only hosts a watch may name.
STORE_HOSTS = frozenset({
    "www.zumiez.com", "www.skatewarehouse.com", "shop.ccs.com", "www.tactics.com",
    "tgmskateboards.com", "www.tgmskateboards.com",
    "www.skatedeluxe.com", "muirskate.com", "www.muirskate.com",
})
_TEXT = {"brand": 60, "name": 80, "note": 80, "label": 120}
_WIDTHS = ("width", "min_width", "max_width", "back_in_stock_width")
_FLAGS = ("alert_on_drop", "alert_on_low", "alert_on_stock")
_ALLOWED = {
    "search": {"id", "kind", "part", "brand", "name", "note", *_WIDTHS, "max_price", *_FLAGS},
    "watch": {"id", "kind", "product_url", "product_key", "label", "note", "max_price", *_FLAGS},
    "digest": {"id", "kind", "parts", "events", "min_width", "max_width", "max_price", "note"},
}
# What the engine sees as a watched listing's part. Watches match by identity
# only, so the engine's part check must not depend on the listing's real part
# (which may be unknown on a day the listing is missing).
_WATCH_PART = "Watched listing"
_ITEM_FIELDS = ("name", "store", "part", "url", "price_new", "price_old")
# Worker status -> engine journal status.
_STATUS = {
    "sent": "delivered",
    "duplicate": "delivered",
    "inactive": "delivered",  # the route is gone; drop its events
    "deferred": "pending",
    "failed": "pending",
    "uncertain": "uncertain",
}


class Config:
    def __init__(self, enabled, api_url, secret, state_dir, allow_bootstrap, problems):
        self.enabled = enabled
        self.api_url = api_url
        self.secret = secret
        self.state_dir = state_dir
        self.allow_bootstrap = allow_bootstrap
        self.problems = problems


def load_config(env=None):
    env = os.environ if env is None else env
    enabled = str(env.get("ALERTS_DELIVERY_ENABLED") or "").strip().lower() in {"1", "true"}
    api_url = str(env.get("ALERTS_API_URL") or "").strip().rstrip("/")
    secret = str(env.get("ALERTS_HMAC_SECRET") or "").strip()
    problems = []
    if enabled:
        parts = urlsplit(api_url)
        if parts.scheme != "https" or not parts.netloc or parts.path not in ("", "/") or parts.query:
            problems.append("ALERTS_API_URL")
        if len(secret) < MIN_SECRET_LENGTH:
            problems.append("ALERTS_HMAC_SECRET")
    return Config(
        enabled=enabled,
        api_url=api_url,
        secret=secret,
        state_dir=Path(env.get("ALERTS_STATE_DIR") or DEFAULT_STATE_DIR),
        allow_bootstrap=str(env.get("ALERTS_ALLOW_BOOTSTRAP") or "") == "1",
        problems=problems,
    )


def signature(secret, method, path_and_query, timestamp, nonce, body):
    """Same canonical string as worker/src/crypto.js internalSignature."""
    body_bytes = body if isinstance(body, bytes) else str(body or "").encode("utf-8")
    canonical = "\n".join(
        ["v1", method.upper(), path_and_query, str(timestamp), nonce, hashlib.sha256(body_bytes).hexdigest()]
    )
    return "v1=" + hmac.new(secret.encode("utf-8"), canonical.encode("utf-8"), hashlib.sha256).hexdigest()


def _urllib_transport(method, url, headers, body):
    request = urllib.request.Request(url, data=body or None, method=method, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            return response.status, response.read(MAX_RESPONSE + 1)
    except urllib.error.HTTPError as error:
        return error.code, error.read(MAX_RESPONSE + 1)


class ApiError(Exception):
    """The Worker could not be reached or answered with an error."""


def _call(config, method, path, payload=None, transport=None, now=None):
    body = b"" if payload is None else json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    timestamp = int(now if now is not None else time.time())
    nonce = secrets.token_urlsafe(18)
    headers = {
        "X-SkateDeals-Timestamp": str(timestamp),
        "X-SkateDeals-Nonce": nonce,
        "X-SkateDeals-Signature": signature(config.secret, method, path, timestamp, nonce, body),
        "Accept": "application/json",
        "User-Agent": "skatedeals-alerts-delivery/1",
    }
    if payload is not None:
        headers["Content-Type"] = "application/json"
    try:
        status, raw = (transport or _urllib_transport)(method, config.api_url + path, headers, body)
    except Exception as exc:
        raise ApiError(type(exc).__name__) from None
    if status != 200 or len(raw) > MAX_RESPONSE:
        raise ApiError(f"HTTP {status}")
    try:
        return json.loads(raw.decode("utf-8"))
    except ValueError:
        raise ApiError("invalid JSON") from None


def _text(rule, clean, field):
    value = rule.get(field)
    if value is None:
        return True
    if not isinstance(value, str) or not value.strip() or len(value) > _TEXT[field] or re.search(r"[\x00-\x1f\x7f<>]", value):
        return False
    clean[field] = value.strip()
    return True


def _number(value, low, high, low_inclusive=True):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    return (low <= value if low_inclusive else low < value) and value <= high


def _numbers(rule, clean, fields, decks):
    for field in fields:
        value = rule.get(field)
        if value is None:
            continue
        if not _number(value, 5, 12) or not decks:
            return False
        clean[field] = value
    price = rule.get("max_price")
    if price is not None:
        if not _number(price, 0, 2000, low_inclusive=False):
            return False
        clean["max_price"] = price
    return True


def _flags(rule, clean):
    for field in _FLAGS:
        value = rule.get(field)
        if value is None:
            continue
        if type(value) is not bool:
            return False
        if value:
            clean[field] = True
    return True


def _choices(rule, clean, field, allowed):
    value = rule.get(field)
    if value is None:
        return True
    if not isinstance(value, list) or not value or len(set(value)) != len(value) or not set(value) <= set(allowed):
        return False
    clean[field] = [entry for entry in allowed if entry in value]
    return True


def watch_key(url):
    """The product a watch names: ``listing_identity``'s key, or None if not a tracked store page."""
    if not isinstance(url, str) or len(url) > 500 or normalize_url(url) != url:
        return None
    parts = urlsplit(url)
    if parts.scheme != "https" or parts.hostname not in STORE_HOSTS or parts.username or parts.password or parts.fragment:
        return None
    return listing_identity(url)["key"]


def _clean_rule(rule):
    """Schema v1 check, the same limits as worker/src/rules.js. None if invalid."""
    if not isinstance(rule, dict):
        return None
    kind = rule.get("kind", "search")
    if kind not in _ALLOWED or set(rule) - _ALLOWED[kind]:
        return None
    clean = {} if kind == "search" else {"kind": kind}
    if kind == "search":
        part = rule.get("part", "Decks")
        if part not in _PARTS:
            return None
        clean["part"] = part
        if not all(_text(rule, clean, field) for field in ("brand", "name", "note")):
            return None
        if "brand" not in clean and "name" not in clean:
            return None
        if not _numbers(rule, clean, _WIDTHS, part == "Decks") or not _flags(rule, clean):
            return None
    elif kind == "watch":
        key = watch_key(rule.get("product_url"))
        # The Worker derives the same key; a disagreement means the two
        # sides drifted, and a watch must never guess which listing it means.
        if key is None or rule.get("product_key", key) != key:
            return None
        clean["product_url"] = rule["product_url"]
        clean["product_key"] = key
        if not all(_text(rule, clean, field) for field in ("label", "note")):
            return None
        if not _numbers(rule, clean, (), False) or not _flags(rule, clean):
            return None
        if "max_price" not in clean and not any(field in clean for field in _FLAGS):
            clean["alert_on_drop"] = True
    else:
        if not _choices(rule, clean, "parts", _CATALOG_PARTS) or not _choices(rule, clean, "events", DIGEST_EVENTS):
            return None
        decks = "parts" not in clean or "Decks" in clean["parts"]
        if not _numbers(rule, clean, ("min_width", "max_width"), decks) or not _text(rule, clean, "note"):
            return None
    rule_id = rule.get("id")
    if rule_id is not None:
        if not isinstance(rule_id, str) or not _RULE_ID_RE.fullmatch(rule_id):
            return None
        clean["id"] = rule_id
    return clean


def parse_routes(payload):
    """Validated ``{route_id: [rule, ...]}``. Raises ValueError on a bad shape."""
    if not isinstance(payload, dict) or payload.get("version") != 1 or not isinstance(payload.get("routes"), list):
        raise ValueError("unsupported routes response")
    if len(payload["routes"]) > MAX_ROUTES:
        raise ValueError("too many routes")
    routes = {}
    dropped = 0
    for route in payload["routes"]:
        route_id = route.get("route_id") if isinstance(route, dict) else None
        rules = route.get("rules") if isinstance(route, dict) else None
        if not isinstance(route_id, str) or not _ROUTE_RE.fullmatch(route_id) or route_id in routes:
            raise ValueError("invalid route id")
        if not isinstance(rules, list) or len(rules) > MAX_RULES:
            raise ValueError("invalid rule list")
        clean = [rule for rule in (_clean_rule(rule) for rule in rules) if rule is not None]
        dropped += len(rules) - len(clean)
        if clean:
            routes[route_id] = clean
    if dropped:
        logger.warning("Subscriber alerts: %s invalid rules ignored", dropped)
    return routes


def _route_file(state_dir, route_id):
    return state_dir / f"{_hash(route_id)}.json"


def _read_manifest(state_dir):
    path = state_dir / MANIFEST
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("version") != 1 or not isinstance(data.get("routes"), list):
        raise ValueError("Unsupported alerts manifest")
    if not all(isinstance(key, str) and re.fullmatch(r"[0-9a-f]{64}", key) for key in data["routes"]):
        raise ValueError("Malformed alerts manifest")
    return set(data["routes"])


def _write_manifest(state_dir, known):
    path = state_dir / MANIFEST
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps({"version": 1, "routes": sorted(known)}, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _public_item(item):
    out = {}
    for field in _ITEM_FIELDS:
        value = item.get(field)
        if value not in (None, ""):
            out[field] = str(value)
    return out


def _evaluate(state, owner, rules, view):
    routed = [dict(rule, owner_id=owner, recipient_id=owner) for rule in rules]
    return evaluate(
        state,
        routed,
        view["catalog"],
        view["history"],
        view["failed_keys"],
        view["previous"],
        view["stock_evidence"],
        view["skip_urls"],
        view["day"],
        owner_id=owner,
        recipient_id=owner,
    )


def _canonical_url(url, key):
    """A stable, real URL for a watched product: Shopify's /products/<handle>, else the URL itself."""
    if key.startswith("shopify:"):
        return f"https://{urlsplit(url).hostname}/products/{key.rsplit(':', 1)[1]}"
    return key


def _watch_view(watches, scrape):
    """The scrape as the engine should see a route's product watches.

    Every listing whose identity key is watched appears under one canonical
    URL, so the engine's per-product state survives Shopify URL churn, and
    under a fixed part, so the engine's part check cannot hide it. Nothing
    else is visible. ``real`` maps a canonical URL back to today's listing.
    """
    canonical = {rule["product_key"]: _canonical_url(rule["product_url"], rule["product_key"]) for rule in watches}

    def remap(url):
        if not canonical:
            return None  # most routes have no watches; skip the per-listing work
        url = normalize_url(url)
        return canonical.get(listing_identity(url)["key"]) if url else None

    def rows(catalog, real=None):
        view = {}
        for category, items in (catalog or {}).items():
            for item in items or []:
                url = remap(item.get("url")) if isinstance(item, dict) else None
                if not url or (real is not None and url in real):
                    continue
                if real is not None:
                    real[url] = item
                view.setdefault(category, []).append(dict(item, url=url, part=_WATCH_PART))
        # Categories with no watched listing still count as scanned, so a
        # verified out-of-stock check can re-arm a watch.
        for category in catalog or {}:
            view.setdefault(category, [])
        return view

    real = {}
    catalog = rows(scrape["catalog"], real)
    history = scrape["history"] or {}
    view_history = {url: history[normalize_url(item.get("url"))] for url, item in real.items()
                    if normalize_url(item.get("url")) in history}
    evidence = {remap(url): status for url, status in (scrape["stock_evidence"] or {}).items() if remap(url)}
    view = dict(
        scrape,
        catalog=catalog,
        previous=rows(scrape["previous"]),
        history=view_history,
        stock_evidence=evidence,
        skip_urls=tuple(filter(None, (remap(url) for url in scrape["skip_urls"]))),
    )
    return view, real


def watch_alias(route_id):
    """The engine owner id for a route's watches: fixed length, never the route id itself."""
    return "w_" + _hash(route_id)[:40]


def _plan_route(state, route_id, rules, scrape):
    """Engine hits for a route's search rules and product watches, newest-first capped."""
    searches = [rule for rule in rules if rule.get("kind", "search") == "search"]
    watches = [rule for rule in rules if rule.get("kind") == "watch"]
    state, hits = _evaluate(state, route_id, searches, scrape)
    # Watches keep their engine records under their own alias, so removing
    # every search rule never clears a watch's state, and the other way round.
    # Always evaluated, even with no watches, so removed watches are forgotten.
    view, real = _watch_view(watches, scrape)
    engine_watches = [
        {key: value for key, value in dict(rule, product_url=_canonical_url(rule["product_url"], rule["product_key"]),
                                           part=_WATCH_PART).items()
         if key not in {"kind", "product_key", "label"}}
        for rule in watches
    ]
    state, watch_hits = _evaluate(state, watch_alias(route_id), engine_watches, view)
    for hit in watch_hits:
        listing = real.get(hit["item"]["url"]) or {}
        hit["item"] = dict(hit["item"], url=listing.get("url", hit["item"]["url"]), part=listing.get("part", ""))
    hits = hits + watch_hits
    hits.sort(key=lambda hit: (min(state["events"][eid]["date"] for eid in hit["event_ids"]), min(hit["event_ids"])))
    return state, hits[:MAX_DIGEST_WATCHES]


def _price(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number and number >= 0 else None


def digest_candidates(catalog, previous, history, failed_keys=(), skip_urls=()):
    """Today's general deals, best first: ``[{kind, item, price_before?}]``.

    Uses the owner digest's own rules (``report.compare_catalogs`` and
    ``build_digest``: listing filters, and a drop is at least $2 or 5% under
    the previous sale price). Only stores that scraped cleanly count, carried
    listings never do, and nothing is new without a previous scrape.
    """
    if not previous:
        return []
    failed = set(failed_keys or ())
    skip = {normalize_url(url) for url in skip_urls or ()}
    entries = {}
    for category, diffs in compare_catalogs(previous, catalog, failed).items():
        if category in failed:
            continue
        found = build_digest({category: diffs}, failed)
        rows = len((catalog or {}).get(category) or [])
        news = found.new_items
        if not (previous.get(category) or []) or (len(news) > REBASELINE_MIN and len(news) > rows * REBASELINE_SHARE):
            logger.info("Digest: %s new listings in one category treated as a re-listing", len(news))
            news = []
        for item in news:
            entries[normalize_url(item.get("url"))] = {"kind": "new", "item": item}
        for change in found.drops:
            item = change.get("item") or {}
            entries[normalize_url(item.get("url"))] = {"kind": "drop", "item": item, "price_before": change.get("old")}
    prior = {normalize_url(item.get("url")): _price(item.get("price_new"))
             for items in previous.values() for item in items or [] if isinstance(item, dict)}
    for category, items in (catalog or {}).items():
        if category in failed:
            continue
        for item in items or []:
            url = normalize_url(item.get("url")) if isinstance(item, dict) else ""
            before = prior.get(url)
            if not url or before is None or not item_passes_filters(item):
                continue
            status = all_time_low_status(item, history or {})
            # Newly at the low: it was above the tracked low in the previous scrape.
            if status.get("flagged") and before > float(status["low"]) + 0.001:
                entries[url] = {"kind": "low", "item": item, "price_before": before}
    for url in skip:
        entries.pop(url, None)

    def rank(entry):
        item = entry["item"]
        now = _price(item.get("price_new")) or 0
        was = _price(entry.get("price_before") or item.get("price_old")) or now
        off = (was - now) / was if was else 0
        return ({"low": 0, "drop": 1, "new": 2}[entry["kind"]], -off, str(item.get("name") or ""))

    return sorted(entries.values(), key=rank)


def _digest_matches(rule, entry):
    item = entry["item"]
    if entry["kind"] not in rule.get("events", DIGEST_EVENTS):
        return False
    if "parts" in rule and item.get("part") not in rule["parts"]:
        return False
    price = _price(item.get("price_new"))
    if "max_price" in rule and (price is None or price > rule["max_price"]):
        return False
    if item.get("part") == "Decks" and ("min_width" in rule or "max_width" in rule):
        width = _width_of(item)
        if width is None or width < rule.get("min_width", 0) - 1e-9 or width > rule.get("max_width", 99) + 1e-9:
            return False
    return True


def _digest_section(route_id, rules, candidates, day):
    """The digest payload for one route, or None (no digest rule, or nothing today)."""
    rule = next((rule for rule in rules if rule.get("kind") == "digest"), None)
    if rule is None:
        return None
    chosen = [entry for entry in candidates if _digest_matches(rule, entry)]
    if not chosen:
        return None
    items = []
    for entry in chosen[:MAX_DIGEST_ITEMS]:
        row = {"kind": entry["kind"], "item": _public_item(entry["item"])}
        if entry.get("price_before") not in (None, ""):
            row["price_before"] = str(entry["price_before"])
        items.append(row)
    # One id per subscriber and day: the Worker sends a day's digest once.
    return {"event_id": _hash(["digest", route_id, str(day)[:10]]), "total": len(chosen), "items": items}


def deliver_subscriber_alerts(catalog, history, failed_keys=(), previous=None, stock_evidence=None,
                              skip_urls=(), day=None, env=None, transport=None, now=None):
    """Run one delivery pass. Never raises. Returns a summary of counts only."""
    summary = {"status": "disabled", "routes": 0, "deliveries": 0, "results": {}}
    try:
        config = load_config(env)
        if not config.enabled:
            return summary
        if config.problems:
            logger.error("Subscriber alerts not configured (%s); delivery skipped", ", ".join(config.problems))
            summary["status"] = "misconfigured"
            return summary
        return _deliver(config, catalog, history, failed_keys, previous, stock_evidence, skip_urls, day, transport, now, summary)
    except Exception as exc:
        logger.error("Subscriber alerts failed (%s); delivery skipped", type(exc).__name__)
        summary["status"] = "error"
        return summary


def _deliver(config, catalog, history, failed_keys, previous, stock_evidence, skip_urls, day, transport, now, summary):
    state_dir = config.state_dir
    if not (state_dir / MANIFEST).exists():
        if not config.allow_bootstrap:
            logger.error("Subscriber alert state missing; set ALERTS_ALLOW_BOOTSTRAP=1 once to start (delivery skipped)")
            summary["status"] = "state_missing"
            return summary
        state_dir.mkdir(parents=True, exist_ok=True)
        _write_manifest(state_dir, set())
    with open(state_dir / ".lock", "a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        known = _read_manifest(state_dir)
        try:
            routes = parse_routes(_call(config, "GET", "/v1/internal/routes", transport=transport, now=now))
        except (ApiError, ValueError) as exc:
            logger.error("Subscriber alert routes unavailable (%s); delivery skipped", exc)
            summary["status"] = "api_unavailable"
            return summary
        summary["routes"] = len(routes)

        # A subscriber who left: forget their journal.
        active = {_hash(route_id) for route_id in routes}
        for key in sorted(known - active):
            path = state_dir / f"{key}.json"
            if path.exists():
                path.unlink()
        known &= active

        scrape = {
            "catalog": catalog or {},
            "history": history or {},
            "failed_keys": tuple(failed_keys or ()),
            "previous": previous,
            "stock_evidence": stock_evidence,
            "skip_urls": tuple(skip_urls or ()),
            "day": day,
        }
        candidates = []
        if any(rule.get("kind") == "digest" for rules in routes.values() for rule in rules):
            candidates = digest_candidates(scrape["catalog"], scrape["previous"], scrape["history"],
                                           scrape["failed_keys"], scrape["skip_urls"])
        planned = []
        for route_id in sorted(routes):
            key = _hash(route_id)
            path = _route_file(state_dir, route_id)
            if key in known and not path.exists():
                logger.warning("A subscriber's alert journal is missing; that subscriber is skipped")
                continue
            state = load_state(path) if path.exists() else empty_state()
            state, hits = _plan_route(state, route_id, routes[route_id], scrape)
            ids = [eid for hit in hits for eid in hit["event_ids"]]
            for eid in ids:
                state["events"][eid]["status"] = "sending"
            save_state(path, state)  # journal first; nothing is sent if this fails
            known.add(key)
            digest = _digest_section(route_id, routes[route_id], candidates, day)
            if hits or digest:
                planned.append((route_id, path, state, hits, ids, digest))
        _write_manifest(state_dir, known)

        deliveries = []
        for route_id, _path, _state, hits, ids, digest in planned:
            delivery = {
                "route_id": route_id,
                "delivery_id": _hash(sorted(ids + ([digest["event_id"]] if digest else []))),
                "hits": [
                    {"event_ids": hit["event_ids"], "reasons": hit["reasons"], "note": hit.get("note") or "", "item": _public_item(hit["item"])}
                    for hit in hits
                ],
            }
            if digest:
                delivery["digest"] = digest
            deliveries.append(delivery)
        summary["deliveries"] = len(deliveries)
        results = {}
        for start in range(0, len(deliveries), CHUNK):
            chunk = deliveries[start : start + CHUNK]
            try:
                answer = _call(config, "POST", "/v1/internal/deliveries", {"version": 1, "deliveries": chunk}, transport, now)
                for row in answer.get("results") or []:
                    if isinstance(row, dict) and row.get("status") in _STATUS:
                        results[row.get("delivery_id")] = row["status"]
            except ApiError as exc:
                # The Worker dedups per event, so leaving these pending is safe.
                logger.error("Subscriber alert delivery request failed (%s); events stay queued", exc)

        counts = {}
        for (route_id, path, state, hits, ids, _digest), delivery in zip(planned, deliveries):
            outcome = results.get(delivery["delivery_id"], "failed")
            counts[outcome] = counts.get(outcome, 0) + 1
            status = _STATUS[outcome]
            state = copy.deepcopy(state)
            for eid in ids:
                state["events"][eid]["status"] = status
                if status == "uncertain":
                    state["records"][state["events"][eid]["record"]]["blocked"] = True
            save_state(path, state)
        summary["results"] = counts
        summary["status"] = "ok"
        logger.info("Subscriber alerts: %s routes, %s deliveries, results %s", summary["routes"], summary["deliveries"], counts)
        return summary
