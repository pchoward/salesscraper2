"""Price-history chart series for the static report.

Daily points come from ``price_history.json``, which keeps them for 90 days.
The 30-day and 90-day windows clip that series. The 180-day window uses the
same points and, when the all-time low is older than the daily window but
still inside 180 days, marks that low even though the day-by-day prices are
gone.

Markers:

* ``drop`` — the sale price is below the previous observation
* ``gone`` — the last observation before a gap of two or more missing days
* ``back`` — the next observation after that gap (back in stock)
* ``low`` — the all-time low, added when its date falls in the window

A single missed day is not a stock change. The catalog treats a listing as
gone only after two consecutive misses, which is a three-day gap between
observations.
"""

import datetime

from history import summarize_entry

# Date delta of 3 means two calendar days with no observation.
MISSING_GAP_DAYS = 3
WINDOWS = (30, 90, 180)
CHART_NOTE = (
    "Daily sale prices are kept for 90 days. "
    "The 180-day view adds the all-time low when that low is older than those daily prices. "
    "A gap of two or more missing days is marked gone, then back in stock."
)


def _day(value):
    return datetime.date.fromisoformat(str(value)[:10])


def markers_from_prices(prices):
    """Drop, gone, and back markers for a date → price map. Dates are sorted."""
    if not isinstance(prices, dict):
        return []
    days = [day for day in prices if day]
    days.sort()
    markers = []
    for index in range(1, len(days)):
        previous = days[index - 1]
        current = days[index]
        try:
            gap = (_day(current) - _day(previous)).days
            prev_price = float(prices[previous])
            price = float(prices[current])
        except (TypeError, ValueError):
            continue
        if gap >= MISSING_GAP_DAYS:
            markers.append(
                {
                    "date": previous,
                    "kind": "gone",
                    "label": "Gone",
                    "price": round(prev_price, 2),
                }
            )
            markers.append(
                {
                    "date": current,
                    "kind": "back",
                    "label": "Back in stock",
                    "price": round(price, 2),
                }
            )
        if price < prev_price - 0.001:
            delta = prev_price - price
            markers.append(
                {
                    "date": current,
                    "kind": "drop",
                    "label": f"Price reduction −${delta:.2f}",
                    "price": round(price, 2),
                }
            )
    return markers


def listing_series(entry, url, store, availability, currency=None):
    """One store's points, markers, and all-time low for the chart."""
    summary = summarize_entry(entry if isinstance(entry, dict) else {})
    prices = summary.get("prices") or {}
    low = None
    if summary.get("all_time_low") is not None and summary.get("all_time_low_date"):
        low = {"date": summary["all_time_low_date"], "price": summary["all_time_low"]}
    payload = {
        "store": store or "",
        "url": url or "",
        "availability": availability or "",
        "points": [[day, round(float(prices[day]), 2)] for day in prices],
        "markers": markers_from_prices(prices),
        "low": low,
    }
    if currency and str(currency).upper() not in {"", "USD"}:
        payload["currency"] = str(currency).upper()
    return payload


def clip_series(series, today, days):
    """Points and markers whose dates fall in the last ``days`` through ``today``."""
    today_day = _day(today)
    start = (today_day - datetime.timedelta(days=int(days))).isoformat()
    points = [point for point in (series.get("points") or []) if str(point[0]) >= start]
    markers = [
        dict(marker)
        for marker in (series.get("markers") or [])
        if str(marker.get("date") or "") >= start
    ]
    low = series.get("low")
    if isinstance(low, dict) and str(low.get("date") or "") >= start:
        markers.append(
            {
                "date": low["date"],
                "kind": "low",
                "label": "All-time low",
                "price": low.get("price"),
            }
        )
    clipped = {
        "store": series.get("store") or "",
        "url": series.get("url") or "",
        "availability": series.get("availability") or "",
        "points": points,
        "markers": markers,
    }
    if series.get("currency"):
        clipped["currency"] = series["currency"]
    if low:
        clipped["low"] = low
    return clipped


def chart_windows(series_list, today, windows=WINDOWS):
    """``{"30": [series...], "90": ..., "180": ...}``."""
    series_list = list(series_list or [])
    return {
        str(days): [clip_series(series, today, days) for series in series_list]
        for days in windows
    }
