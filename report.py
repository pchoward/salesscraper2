"""Catalog diff and the HTML report entry point.

``build_digest`` is the same split the page and the email use. ``notify.py``
does not re-decide what counts as new or a drop. The page itself is built in
``page.py``.
"""

import logging

from history import price_trend, summarize_entry

logger = logging.getLogger("report")

from filters import (
    is_meaningful_drop,
    item_passes_filters,
    normalize_product_name,
    normalize_url,
    passes_filters,
    percent_off_value,
)


def _price(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def compare_catalogs(prev, curr, failed_keys=None):
    """Diff two catalogs.

    New rows and price drops must pass ``passes_filters``. A price drop is a
    decrease of at least $2 or 5% versus the previous sale price (not MSRP).
    Removals are recorded only when that key was scraped successfully and the
    previous item still passes the filters.
    """
    failed_keys = set(failed_keys or [])
    changes = {}

    for site, items in (curr or {}).items():
        prev_map = {}
        for previous in (prev or {}).get(site, []):
            url = normalize_url(previous.get("url"))
            if url:
                prev_map[url] = previous

        diffs = []
        current_urls = set()
        for item in items or []:
            if not item_passes_filters(item):
                continue
            url = normalize_url(item.get("url"))
            if not url:
                continue
            current_urls.add(url)
            previous = prev_map.get(url)
            if not previous or not item_passes_filters(previous):
                diffs.append({"type": "new", "item": item})
                continue
            old_price = _price(previous.get("price_new"))
            new_price = _price(item.get("price_new"))
            if not is_meaningful_drop(old_price, new_price):
                continue
            delta = old_price - new_price
            percent = (delta / old_price) * 100 if old_price else 0
            diffs.append(
                {
                    "type": "price_drop",
                    "url": url,
                    "name": item.get("name"),
                    "old": previous.get("price_new"),
                    "new": item.get("price_new"),
                    "delta": round(delta, 2),
                    "percent_vs_prior": round(percent, 1),
                    "item": item,
                }
            )

        if site not in failed_keys:
            for url, previous in prev_map.items():
                if url in current_urls or not item_passes_filters(previous):
                    continue
                diffs.append({"type": "removed", "item": previous})

        if diffs:
            changes[site] = diffs
    return changes


def get_price_stats(url, history):
    history = history or {}
    entry = None
    if isinstance(history, dict):
        entry = history.get(url) or history.get(normalize_url(url))
    empty = {"lowest": None, "is_lowest": False, "trend": "stable", "history_days": 0}
    if not isinstance(entry, dict):
        return empty
    summary = summarize_entry(entry)
    prices = summary["prices"]
    if not prices and summary.get("all_time_low") is None:
        return empty
    current = prices[max(prices)] if prices else None
    lowest = summary.get("all_time_low")
    is_lowest = current is not None and lowest is not None and current <= lowest
    return {
        "lowest": lowest,
        "is_lowest": is_lowest,
        "trend": price_trend(entry),
        "history_days": summary["observation_count"],
    }


def _discount_class(price_new, price_old):
    percent = percent_off_value(price_new, price_old)
    if percent is None:
        return "low"
    if percent >= 40:
        return "high"
    if percent >= 25:
        return "medium"
    return "low"


def _money(value):
    amount = _price(value)
    if amount is None:
        return "N/A"
    return f"${amount:.2f}"


def _drop_label(change):
    delta = change.get("delta")
    percent = change.get("percent_vs_prior")
    if delta is None or percent is None:
        old_price = _price(change.get("old"))
        new_price = _price(change.get("new"))
        if old_price is None or new_price is None or old_price <= 0:
            return "N/A"
        delta = old_price - new_price
        percent = (delta / old_price) * 100
    return f"−${delta:.2f} (−{percent:.1f}% vs prior sale)"


def _display_name(item):
    return normalize_product_name((item or {}).get("name", ""))


def _split_changes(changes, failed_keys):
    failed_keys = set(failed_keys or [])
    new_items = []
    drops = []
    removed = []
    for site, site_changes in (changes or {}).items():
        for change in site_changes:
            kind = change.get("type")
            if kind == "new":
                item = change.get("item") or {}
                if item_passes_filters(item):
                    new_items.append(item)
            elif kind in ("price_drop", "price_change"):
                item = change.get("item") or {}
                name = item.get("name") or change.get("name")
                part = item.get("part") or ""
                url = item.get("url") or change.get("url") or ""
                price_new = item.get("price_new", change.get("new"))
                price_old = item.get("price_old")
                if not passes_filters(name, part, url, price_new, price_old):
                    continue
                if not is_meaningful_drop(change.get("old"), change.get("new")):
                    continue
                drops.append(change)
            elif kind == "removed" and site not in failed_keys:
                item = change.get("item") or {}
                if item_passes_filters(item):
                    removed.append((site, item))
    return new_items, drops, removed


class Digest:
    """New listings, meaningful sale-price drops, and successful-scrape removals.

    ``warnings`` are broken-store alerts. They are not part of the catalog
    diff; ``pipeline.decorate_digest`` attaches them, along with all-time
    lows, cross-store groups, watchlist hits, and site-wide sale ages.
    """

    def __init__(
        self,
        new_items=None,
        drops=None,
        removed=None,
        warnings=None,
        all_time_lows=None,
        cross_store=None,
    ):
        self.new_items = list(new_items or [])
        self.drops = list(drops or [])
        self.removed = list(removed or [])
        self.warnings = list(warnings or [])
        self.all_time_lows = list(all_time_lows or [])
        self.cross_store = list(cross_store or [])


def build_digest(changes, failed_keys=None):
    """Split a catalog diff the same way the HTML report does.

    New rows and price drops already passed ``passes_filters`` and the
    meaningful-drop rule inside ``compare_catalogs`` / ``_split_changes``.
    Removals are included only for keys that scraped successfully.
    """
    new_items, drops, removed = _split_changes(changes, failed_keys)
    return Digest(new_items, drops, removed)


def build_report_html(data, changes, price_history=None, failed_keys=None, generated_at=None, digest=None):
    """Render the static report. Failures are logged by the caller."""
    from page import render_page

    return render_page(
        data,
        changes,
        price_history=price_history,
        failed_keys=failed_keys,
        generated_at=generated_at,
        digest=digest,
    )
