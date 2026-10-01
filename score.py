"""Deterministic deal score.

Deal score (0-100) = discount + lowest + recent drop + popular size.

* Discount is the percent off the original price, capped at 50. A missing
  original price adds 0.
* Lowest tracked price adds 25 when the sale price is at the all-time low,
  18 when it is within $1 or 3% above that low, and 10 when it is within $2
  or 5%. This part stays 0 until the listing has at least 3 observations
  spanning 7 days (the same bar as the all-time-low badge).
* A meaningful drop versus the previous sale price ($2 or 5%) adds 8 points
  plus 1 point per 5% of that drop, up to 15. A smaller day-to-day dip, with
  no meaningful drop, adds 4.
* A deck from 8.25" to 8.75" wide adds 10. Other widths and other parts add 0.

Hot means 70 or above.
"""

from filters import is_meaningful_drop, percent_off_value
from history import all_time_low_status, price_trend

DISCOUNT_CAP = 50
LOW_AT = 25
LOW_NEAR = 18
LOW_CLOSE = 10
DROP_BASE = 8
DROP_CAP = 15
DROP_TREND = 4
SIZE_POINTS = 10
POPULAR_MIN = 8.25
POPULAR_MAX = 8.75
HOT_AT = 70

FORMULA = (
    "Deal score (0-100) = discount + lowest + recent drop + popular size. "
    "Discount is the percent off the original price, capped at 50. "
    "Lowest tracked price adds 25 when the sale price is at the all-time low, "
    "18 when it is within $1 or 3% above that low, and 10 when it is within $2 or 5%. "
    "That part stays 0 until the listing has at least 3 observations spanning 7 days. "
    "A meaningful drop versus the previous sale price ($2 or 5%) adds 8 points plus 1 point "
    "per 5% of that drop, up to 15. A smaller day-to-day dip adds 4. "
    "A deck from 8.25\" to 8.75\" adds 10. "
    "Hot means 70 or above."
)


def _half_up(value):
    if value <= 0:
        return 0
    return int(value + 0.5)


def _price(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _discount_points(item):
    percent = percent_off_value(item.get("price_new"), item.get("price_old"))
    if percent is None or percent <= 0:
        return 0
    return min(DISCOUNT_CAP, _half_up(percent))


def _lowest_points(item, history):
    status = all_time_low_status(item, history or {})
    if status["observations"] < 3 or status["span_days"] < 7:
        return 0
    low = status.get("low")
    current = _price(item.get("price_new"))
    if low is None or current is None or low <= 0:
        return 0
    if current <= low + 1e-9:
        return LOW_AT
    gap = current - low
    if gap <= 1 or gap / low <= 0.03:
        return LOW_NEAR
    if gap <= 2 or gap / low <= 0.05:
        return LOW_CLOSE
    return 0


def _drop_points(item, history, drop):
    if isinstance(drop, dict) and is_meaningful_drop(drop.get("old"), drop.get("new")):
        try:
            percent = float(drop.get("percent_vs_prior"))
        except (TypeError, ValueError):
            percent = 0.0
        if percent < 0:
            percent = 0.0
        return min(DROP_CAP, DROP_BASE + int(percent // 5))
    url = item.get("url")
    entry = None
    if isinstance(history, dict) and url:
        entry = history.get(url)
    if price_trend(entry) == "down":
        return DROP_TREND
    return 0


def _size_points(item, width):
    if (item.get("part") or "") != "Decks":
        return 0
    if width is None:
        return 0
    if POPULAR_MIN - 1e-9 <= float(width) <= POPULAR_MAX + 1e-9:
        return SIZE_POINTS
    return 0


def _tooltip(parts, score, hot):
    lowest = parts["lowest"]
    if lowest == LOW_AT:
        lowest_text = f"{lowest} (at the low)"
    elif lowest == LOW_NEAR:
        lowest_text = f"{lowest} (within $1 or 3%)"
    elif lowest == LOW_CLOSE:
        lowest_text = f"{lowest} (within $2 or 5%)"
    else:
        lowest_text = "0"
    hot_text = " Hot." if hot else ""
    return (
        f"{score}/100. Discount {parts['discount']} of {DISCOUNT_CAP}. "
        f"Lowest tracked price {lowest_text}. "
        f"Recent drop {parts['drop']}. "
        f"Popular size {parts['size']} (deck {POPULAR_MIN:g}-{POPULAR_MAX:g}). "
        f"Hot at {HOT_AT} or above.{hot_text} {FORMULA}"
    )


def deal_score(item, history=None, drop=None, width=None):
    """Return score, hot flag, part points, and a tooltip. Never raises."""
    empty = {
        "score": 0,
        "hot": False,
        "parts": {"discount": 0, "lowest": 0, "drop": 0, "size": 0},
        "tooltip": FORMULA,
    }
    if not isinstance(item, dict):
        return empty
    try:
        parts = {
            "discount": _discount_points(item),
            "lowest": _lowest_points(item, history),
            "drop": _drop_points(item, history, drop),
            "size": _size_points(item, width),
        }
        score = min(100, parts["discount"] + parts["lowest"] + parts["drop"] + parts["size"])
        hot = score >= HOT_AT
        return {
            "score": score,
            "hot": hot,
            "parts": parts,
            "tooltip": _tooltip(parts, score, hot),
        }
    except Exception:
        return empty
