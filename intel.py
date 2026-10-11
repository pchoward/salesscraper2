"""Deals intelligence beyond the count tiles.

A genuinely good discount is at least 30% off the original price and within
$2 or 5% of the lowest tracked price. The low uses the same bar as the
all-time-low badge: 3 observations spanning 7 days. A first-day price is not
a real low, and a deep discount that is well above the tracked low is not
counted as good.
"""

from filters import percent_off_value
from history import all_time_low_status

GOOD_MIN_PERCENT = 30.0
GOOD_NEAR_DOLLARS = 2.0
GOOD_NEAR_RATIO = 0.05
GOOD_DEFINITION = (
    "A good discount is at least 30% off the original price and within $2 or 5% "
    "of the lowest tracked price. The low only counts after 3 observations spanning "
    "7 days, so a brand-new price is not treated as a real low."
)


def _price(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _usd(item):
    return str((item or {}).get("currency") or "USD").upper() in {"", "USD"}


def is_good_deal(item, history):
    """True for a deep discount sitting on or near a qualified all-time low."""
    if not isinstance(item, dict) or not _usd(item):
        return False
    percent = percent_off_value(item.get("price_new"), item.get("price_old"))
    if percent is None or percent < GOOD_MIN_PERCENT - 1e-9:
        return False
    status = all_time_low_status(item, history if isinstance(history, dict) else {})
    if status.get("observations", 0) < 3 or status.get("span_days", 0) < 7:
        return False
    low = _price(status.get("low"))
    current = _price(item.get("price_new"))
    if low is None or current is None or low <= 0:
        return False
    gap = current - low
    if gap <= GOOD_NEAR_DOLLARS + 1e-9:
        return True
    return gap / low <= GOOD_NEAR_RATIO + 1e-12


def _name(item):
    return str((item or {}).get("name") or "").strip()


def intelligence_summary(items, history, new_items=None, drops=None, limit=8):
    """Headline numbers for the strip and the deals-intelligence panel.

    Never raises. ``limit`` caps the new-deal and biggest-drop lists.
    """
    empty = {
        "new_deals": [],
        "new_count": 0,
        "by_store": [],
        "discount_leader": None,
        "biggest_drops": [],
        "good_by_store": [],
        "good_leader": None,
        "good_count": 0,
        "definition": GOOD_DEFINITION,
    }
    try:
        history = history if isinstance(history, dict) else {}
        by_store = {}
        good_bucket = {}
        good_count = 0
        for item in items or []:
            if not isinstance(item, dict) or not _usd(item):
                continue
            store = item.get("store") or "Unknown"
            percent = percent_off_value(item.get("price_new"), item.get("price_old"))
            if percent is not None:
                by_store.setdefault(store, []).append(percent)
            if is_good_deal(item, history):
                good_count += 1
                slot = good_bucket.setdefault(store, [])
                slot.append(percent if percent is not None else 0.0)

        averages = []
        for store, values in by_store.items():
            if not values:
                continue
            averages.append(
                {"store": store, "average": sum(values) / len(values), "count": len(values)}
            )
        averages.sort(key=lambda row: (-row["average"], row["store"]))

        good_rows = []
        for store, values in good_bucket.items():
            good_rows.append(
                {
                    "store": store,
                    "count": len(values),
                    "average": sum(values) / len(values) if values else 0.0,
                }
            )
        good_rows.sort(key=lambda row: (-row["count"], -row["average"], row["store"]))

        newest = []
        for item in new_items or []:
            if not isinstance(item, dict):
                continue
            price = _price(item.get("price_new"))
            newest.append(
                {
                    "name": _name(item),
                    "store": item.get("store") or "",
                    "price": price,
                    "url": item.get("url") or "",
                }
            )

        biggest = []
        for change in drops or []:
            if not isinstance(change, dict):
                continue
            item = change.get("item") if isinstance(change.get("item"), dict) else {}
            delta = _price(change.get("delta"))
            if delta is None:
                continue
            biggest.append(
                {
                    "name": _name(item) or str(change.get("name") or ""),
                    "store": item.get("store") or "",
                    "delta": delta,
                    "price": _price(change.get("new") if change.get("new") is not None else item.get("price_new")),
                    "url": item.get("url") or change.get("url") or "",
                }
            )
        biggest.sort(key=lambda row: (-row["delta"], row["name"]))

        return {
            "new_deals": newest[:limit],
            "new_count": len(newest),
            "by_store": averages,
            "discount_leader": averages[0] if averages else None,
            "biggest_drops": biggest[:limit],
            "good_by_store": good_rows,
            "good_leader": good_rows[0] if good_rows else None,
            "good_count": good_count,
            "definition": GOOD_DEFINITION,
        }
    except Exception:
        return empty
