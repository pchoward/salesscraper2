"""Row badges for the report.

* NEW: in today's catalog, not in yesterday's, and not seen before.
* BACK IN STOCK: seen on an earlier day, missing yesterday, back today.
* down $X TODAY: the sale price fell by at least $2 or 5% versus yesterday.
* LOWEST EVER: the qualified all-time low. A drop that is not that low does
  not get this badge, and a low that did not drop today still does.
"""

from filters import is_meaningful_drop, normalize_url
from history import all_time_low_status


def _money(delta):
    return f"${float(delta):.2f}"


def classify_badges(item, history, in_previous, drop=None, today=None):
    """Return badge dicts ``{kind, label}`` in display order.

    ``in_previous`` is True when yesterday's catalog had this URL.
    ``drop`` is the catalog price-drop change, or None.
    """
    badges = []
    if not isinstance(item, dict):
        return badges
    url = normalize_url(item.get("url"))
    entry = history.get(url) if isinstance(history, dict) and url else None
    if entry is None and isinstance(history, dict):
        entry = history.get(item.get("url"))
    first_seen = ""
    if isinstance(entry, dict) and entry.get("first_seen"):
        first_seen = str(entry.get("first_seen"))[:10]
    today_text = str(today)[:10] if today else ""
    seen_before = bool(first_seen and today_text and first_seen < today_text)
    if not in_previous and seen_before:
        badges.append({"kind": "back", "label": "BACK IN STOCK"})
    elif not in_previous:
        badges.append({"kind": "new", "label": "NEW"})

    if isinstance(drop, dict) and is_meaningful_drop(drop.get("old"), drop.get("new")):
        delta = drop.get("delta")
        if delta is None:
            try:
                delta = float(drop.get("old")) - float(drop.get("new"))
            except (TypeError, ValueError):
                delta = None
        if delta is not None and delta > 0:
            badges.append({"kind": "drop", "label": f"down {_money(delta)} TODAY"})

    status = all_time_low_status(item, history if isinstance(history, dict) else {})
    if status.get("flagged"):
        badges.append({"kind": "lowest", "label": "LOWEST EVER"})
    return badges
