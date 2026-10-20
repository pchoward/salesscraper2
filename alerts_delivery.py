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
   plans events from this scrape, using that route's own state file.
3. ``POST /v1/internal/deliveries`` (HMAC-signed): the hits to email. The
   Worker records every event id it has emailed, so a retried request never
   sends twice.
4. The Worker's answer is written back to the route's state.

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

from notification_engine import MAX_DIGEST_WATCHES, _hash, empty_state, evaluate, load_state, save_state

logger = logging.getLogger("alerts_delivery")

DEFAULT_STATE_DIR = "alerts_state"
MANIFEST = "manifest.json"
MIN_SECRET_LENGTH = 32
MAX_ROUTES = 1000
MAX_RULES = 25
CHUNK = 100
TIMEOUT = 30
MAX_RESPONSE = 2 * 1024 * 1024

_ROUTE_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_PARTS = {"Decks", "Wheels", "Trucks", "Bearings"}
_TEXT = {"brand": 60, "name": 80, "note": 80}
_WIDTHS = ("width", "min_width", "max_width", "back_in_stock_width")
_FLAGS = ("alert_on_drop", "alert_on_low", "alert_on_stock")
_ALLOWED = {"id", "part", *_TEXT, *_WIDTHS, "max_price", *_FLAGS}
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


def _clean_rule(rule):
    """Schema v1 check, the same limits as worker/src/rules.js. None if invalid."""
    if not isinstance(rule, dict) or set(rule) - _ALLOWED:
        return None
    clean = {}
    part = rule.get("part", "Decks")
    if part not in _PARTS:
        return None
    clean["part"] = part
    for field, limit in _TEXT.items():
        value = rule.get(field)
        if value is None:
            continue
        if not isinstance(value, str) or not value.strip() or len(value) > limit or re.search(r"[\x00-\x1f\x7f<>]", value):
            return None
        clean[field] = value.strip()
    if "brand" not in clean and "name" not in clean:
        return None
    for field in _WIDTHS:
        value = rule.get(field)
        if value is None:
            continue
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not 5 <= value <= 12 or part != "Decks":
            return None
        clean[field] = value
    price = rule.get("max_price")
    if price is not None:
        if isinstance(price, bool) or not isinstance(price, (int, float)) or not 0 < price <= 2000:
            return None
        clean["max_price"] = price
    for field in _FLAGS:
        value = rule.get(field)
        if value is None:
            continue
        if type(value) is not bool:
            return None
        if value:
            clean[field] = True
    rule_id = rule.get("id")
    if rule_id is not None:
        if not isinstance(rule_id, str) or not re.fullmatch(r"r_[0-9a-f]{24}", rule_id):
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


def _plan_route(state, route_id, rules, scrape):
    routed = [dict(rule, owner_id=route_id, recipient_id=route_id) for rule in rules]
    state, hits = evaluate(
        state,
        routed,
        scrape["catalog"],
        scrape["history"],
        scrape["failed_keys"],
        scrape["previous"],
        scrape["stock_evidence"],
        scrape["skip_urls"],
        scrape["day"],
        owner_id=route_id,
        recipient_id=route_id,
    )
    hits.sort(key=lambda hit: (min(state["events"][eid]["date"] for eid in hit["event_ids"]), min(hit["event_ids"])))
    return state, hits[:MAX_DIGEST_WATCHES]


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
            if hits:
                planned.append((route_id, path, state, hits, ids))
        _write_manifest(state_dir, known)

        deliveries = [
            {
                "route_id": route_id,
                "delivery_id": _hash(sorted(ids)),
                "hits": [
                    {"event_ids": hit["event_ids"], "reasons": hit["reasons"], "note": hit.get("note") or "", "item": _public_item(hit["item"])}
                    for hit in hits
                ],
            }
            for route_id, _path, _state, hits, ids in planned
        ]
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
        for (route_id, path, state, hits, ids), delivery in zip(planned, deliveries):
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
