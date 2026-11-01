"""Deck wheelbase from product pages, read once per listing.

Sale listings never show wheelbase; product pages often do (probed
2026-10-30: Tactics, Skate Warehouse, CCS, SoCal and most Deathgear decks).
The Shopify feed stores (TGM, Kinetic, SPoT, Exodus) already get it from the
description they download, and Zumiez and SPoT pages do not state it.

Each deck is read once. A value is saved on its price-history row
(``wheelbase``), which the page already uses; a page that states none is
marked ``wheelbase_checked`` and tried again after ``RECHECK_DAYS``. So after
the first runs only new decks cost a request. Requests are spaced per store
(SoCal's robots.txt asks for 5 seconds) and capped per run.
"""

import datetime
import json
import logging
import time
import urllib.request
from urllib.parse import urlsplit

from bs4 import BeautifulSoup

from dimensions import extract_specs
from filters import normalize_url

logger = logging.getLogger("stores.details")

# Store -> seconds between its requests.
STORES = {"Tactics": 1.5, "SkateWarehouse": 1.5, "CCS": 1.0, "SoCal": 5.0, "Deathgear": 1.5}
PARTS = ("Decks", "Completes")
MAX_PAGES = 120
RECHECK_DAYS = 30
_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


def _get(url, accept, timeout=30):
    request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT, "Accept": accept})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read().decode("utf-8", "replace")
    except Exception as exc:
        logger.warning("Wheelbase page fetch failed for %s: %s", url, exc)
        return None


def page_text(store, url, fetch=_get):
    """Plain text of a deck's details, or None when it cannot be read."""
    if store == "CCS":
        parts = urlsplit(url)
        handle = parts.path.rstrip("/").rsplit("/", 1)[-1]
        body = fetch(f"https://{parts.hostname}/products/{handle}.js", "application/json")
        if body is None:
            return None
        try:
            html = json.loads(body).get("description") or ""
        except (ValueError, AttributeError):
            return None
        return BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
    html = fetch(url, "text/html")
    if html is None:
        return None
    soup = BeautifulSoup(html, "html.parser")
    for node in soup(["script", "style", "noscript"]):
        node.decompose()
    return soup.get_text(" ", strip=True)


def _due(entry, today):
    checked = str(entry.get("wheelbase_checked") or "")[:10]
    try:
        last = datetime.date.fromisoformat(checked)
    except ValueError:
        return True
    return (today - last).days >= RECHECK_DAYS


def pending(current_data, history, skip_keys=(), today=None):
    """``[(store, url, item, entry)]`` decks still without a known wheelbase, store by store in turn."""
    today = today or datetime.date.today()
    skip = {str(key) for key in skip_keys or ()}
    queues = {}
    for key, items in (current_data or {}).items():
        if key in skip or not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict) or item.get("part") not in PARTS or item.get("store") not in STORES:
                continue
            url = normalize_url(item.get("url"))
            entry = history.get(url) if url else None
            if not isinstance(entry, dict) or entry.get("wheelbase") not in (None, ""):
                continue
            if item.get("wheelbase") not in (None, "") or not _due(entry, today):
                continue
            queues.setdefault(item["store"], []).append((item["store"], url, item, entry))
    # Round-robin, so one large store cannot use the whole budget.
    ordered = []
    while any(queues.values()):
        for store in list(queues):
            if queues[store]:
                ordered.append(queues[store].pop(0))
    return ordered


def fill_wheelbases(current_data, history, skip_keys=(), today=None, fetch=_get, sleep=time.sleep, limit=MAX_PAGES):
    """Read pending deck pages and save what they state. Returns ``(read, found)``."""
    today = today or datetime.date.today()
    if isinstance(today, str):
        today = datetime.date.fromisoformat(today[:10])
    queue = pending(current_data, history, skip_keys, today)[:limit]
    last_request = {}
    read = found = 0
    for store, url, item, entry in queue:
        wait = STORES[store] - (time.monotonic() - last_request.get(store, -1e9))
        if wait > 0:
            sleep(wait)
        text = page_text(store, url, fetch)
        last_request[store] = time.monotonic()
        if text is None:
            continue  # try again next run
        read += 1
        entry["wheelbase_checked"] = today.isoformat()
        from product_specs import enrich
        if item.get('width') in (None, '') and not item.get('widths'):
            enriched = enrich(dict(item), text)
            if enriched.get('width') is not None:
                item['width'] = enriched['width']
                item['widths'] = enriched['widths']
                if entry.get('width') in (None, ''):
                    entry['width'] = item['width']
                    entry['widths'] = item['widths']
        specs = extract_specs(item.get("name") or "", text)
        if specs["wheelbase"] is not None:
            for target in (entry, item):
                target["wheelbase"] = specs["wheelbase"]
                if specs["wheelbases"]:
                    target["wheelbases"] = specs["wheelbases"]
            found += 1
    if queue:
        logger.info("Wheelbase: read %s of %s deck pages, %s stated one", read, len(queue), found)
    return read, found
