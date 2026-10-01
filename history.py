"""Bounded sale-price history.

``price_history.json`` is committed every day. Keeping every daily price for
every listing ever seen made the file grow without a ceiling (about 2 MB, and
another point per listing per day).

Retention policy:

* Daily prices are kept for a rolling 90-day window (``date >= today - 90
  days``). That is enough for the recent trend arrow. The digest's $2 / 5%
  drop check uses ``previous_data.json``, not this file.
* Each listing also stores a small summary that is not trimmed with the
  window: first seen, last seen, how many days were observed, and the
  all-time low price with the date it was first hit. All-time-low detection
  still works after the daily points age out.
* Listings the current filters reject are dropped. A deck with no original
  price stored here is kept, because this file never recorded MSRP and the
  discount rule cannot be applied. Size, keyword, and brand rejections still
  apply. A URL in the current passing catalog is always kept.
* Listings not seen for more than 180 days, and not in the current catalog,
  are dropped. Half a year is long enough to hold a seasonal return; after
  that the summary is not worth committing forever.

Pruning is safe to run every day. It does not rewrite git history.
"""

import datetime
import logging

from filters import filter_reason, item_passes_filters, normalize_product_name, normalize_url

logger = logging.getLogger("history")

DETAIL_WINDOW_DAYS = 90
STALE_AFTER_DAYS = 180
MIN_ATL_OBSERVATIONS = 3
MIN_ATL_SPAN_DAYS = 7
RECENTLY_GONE_DAYS = 7
STAGES = ("new", "price_drop", "all_time_low", "sold_out", "gone")
STAGE_LABEL = {
    "new": "NEW",
    "price_drop": "PRICE DROP",
    "all_time_low": "ALL-TIME LOW",
    "sold_out": "SOLD OUT",
    "gone": "GONE",
}

# Missing MSRP is not evidence a deck is off-policy. History never stored it.
_KEEP_WITHOUT_MSRP = "deck discount unknown"

_ENTRY_FIELDS = (
    "name",
    "store",
    "part",
    "first_seen",
    "last_seen",
    "observation_count",
    "all_time_low",
    "all_time_low_date",
    "stage",
)


def _as_date(value):
    if isinstance(value, datetime.datetime):
        return value.date()
    if isinstance(value, datetime.date):
        return value
    if value is None:
        return None
    try:
        return datetime.date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _date_str(value):
    day = _as_date(value) if not isinstance(value, str) else _as_date(value)
    if day is None:
        day = datetime.date.today()
    return day.isoformat()


def _cents(value):
    try:
        return int(round(float(value) * 100))
    except (TypeError, ValueError):
        return None


def _round_price(value):
    cents = _cents(value)
    if cents is None:
        return None
    return cents / 100.0


def _clean_prices(prices):
    """Date → price, invalid points dropped, dates sorted on insertion."""
    cleaned = {}
    if not isinstance(prices, dict):
        return cleaned
    for raw_day, raw_price in prices.items():
        day = _as_date(raw_day)
        price = _round_price(raw_price)
        if day is None or price is None:
            continue
        cleaned[day.isoformat()] = price
    return {day: cleaned[day] for day in sorted(cleaned)}


def _latest_price(prices):
    if not prices:
        return None
    return prices[max(prices)]


def summarize_entry(entry):
    """Read-only summary. Does not raise the stored all-time low."""
    entry = entry or {}
    prices = _clean_prices(entry.get("prices"))
    first = entry.get("first_seen") or None
    last = entry.get("last_seen") or None
    first_day = _as_date(first)
    last_day = _as_date(last)
    if prices:
        earliest = _as_date(min(prices))
        latest = _as_date(max(prices))
        if first_day is None or (earliest and earliest < first_day):
            first_day = earliest
        if last_day is None or (latest and latest > last_day):
            last_day = latest
    count = entry.get("observation_count")
    try:
        count = int(count) if count is not None else len(prices)
    except (TypeError, ValueError):
        count = len(prices)
    count = max(count, len(prices))

    low = _round_price(entry.get("all_time_low"))
    low_date = entry.get("all_time_low_date")
    low_day = _as_date(low_date)
    if prices:
        plow = min(prices.values())
        pdate = min(day for day, price in prices.items() if price == plow)
        pday = _as_date(pdate)
        if low is None or _cents(plow) < _cents(low):
            low = plow
            low_day = pday
        elif _cents(plow) == _cents(low) and (low_day is None or (pday and pday < low_day)):
            low_day = pday

    span_days = 0
    if first_day and last_day:
        span_days = (last_day - first_day).days
    return {
        "prices": prices,
        "first_seen": first_day.isoformat() if first_day else None,
        "last_seen": last_day.isoformat() if last_day else None,
        "observation_count": count,
        "all_time_low": low,
        "all_time_low_date": low_day.isoformat() if low_day else None,
        "span_days": span_days,
    }


def _write_summary(entry, summary):
    for field in ("first_seen", "last_seen", "all_time_low_date"):
        if summary.get(field):
            entry[field] = summary[field]
    entry["observation_count"] = summary["observation_count"]
    if summary.get("all_time_low") is not None:
        entry["all_time_low"] = summary["all_time_low"]
    entry["prices"] = summary["prices"]
    return entry


def _media_fields(entry):
    """Image and specs, kept only when the listing actually has them."""
    media = {}
    image = str((entry or {}).get("image") or "").strip()
    if image.startswith("http"):
        media["image"] = image
    for field in ("width", "length", "wheelbase"):
        value = (entry or {}).get(field)
        try:
            if value is None or value == "":
                continue
            media[field] = float(value)
        except (TypeError, ValueError):
            continue
    return media


def _copy_media(target, source):
    """Copy a new image, and fill specs that are still empty."""
    media = _media_fields(source)
    if media.get("image"):
        target["image"] = media["image"]
    for field in ("width", "length", "wheelbase"):
        if field in media and target.get(field) in (None, ""):
            target[field] = media[field]


def _ordered_entry(entry):
    ordered = {}
    name = normalize_product_name(entry.get("name") or "")
    ordered["name"] = name
    ordered["store"] = str(entry.get("store") or "")
    ordered["part"] = str(entry.get("part") or "")
    for field in _ENTRY_FIELDS:
        if field in ("name", "store", "part"):
            continue
        value = entry.get(field)
        if value is None or value == "":
            continue
        if field == "stage" and value not in STAGES:
            continue
        ordered[field] = value
    ordered.update(_media_fields(entry))
    ordered["prices"] = _clean_prices(entry.get("prices"))
    return ordered


def _note_price(entry, day, price):
    """Record one observed sale price and maintain the summary."""
    prices = _clean_prices(entry.get("prices"))
    if "observation_count" not in entry:
        entry["observation_count"] = len(prices)
    previous = prices.get(day)
    if day not in prices:
        entry["observation_count"] = int(entry["observation_count"]) + 1
    prices[day] = price
    entry["prices"] = prices
    summary = summarize_entry(entry)
    _write_summary(entry, summary)
    if (
        previous is not None
        and entry.get("all_time_low_date") == day
        and _cents(price) > _cents(previous)
        and _cents(previous) == _cents(entry.get("all_time_low"))
    ):
        # The only copy of today's low was overwritten by a higher same-day price.
        entry["all_time_low"] = None
        entry["all_time_low_date"] = None
        summary = summarize_entry(entry)
        _write_summary(entry, summary)
    return entry


def update_price_history(current_data, history, today=None, skip_keys=None):
    """Add today's sale price for listings that were actually scraped.

    ``skip_keys`` are store/part scrapes that failed. Retained previous rows
    are not treated as a new observation.
    """
    if not isinstance(history, dict):
        raise TypeError("price history must be a dict")
    day = _date_str(today or datetime.date.today())
    skip = set(skip_keys or [])
    for site_key, items in (current_data or {}).items():
        if site_key in skip:
            continue
        for item in items or []:
            if not isinstance(item, dict) or not item_passes_filters(item):
                continue
            url = normalize_url(item.get("url"))
            price = _round_price(item.get("price_new"))
            if not url or price is None:
                continue
            entry = history.get(url)
            if not isinstance(entry, dict):
                entry = {"prices": {}}
                history[url] = entry
            entry["name"] = item.get("name") or entry.get("name") or ""
            entry["store"] = item.get("store") or entry.get("store") or ""
            entry["part"] = item.get("part") or entry.get("part") or ""
            _copy_media(entry, item)
            _note_price(entry, day, price)
    return history


def _merge_entries(left, right):
    """Combine two history rows that normalize to the same URL."""
    left_summary = summarize_entry(left)
    right_summary = summarize_entry(right)
    prices = dict(left_summary["prices"])
    prices.update(right_summary["prices"])
    prices = _clean_prices(prices)
    merged = {
        "name": left.get("name") or right.get("name") or "",
        "store": left.get("store") or right.get("store") or "",
        "part": left.get("part") or right.get("part") or "",
        "prices": prices,
        "observation_count": max(
            left_summary["observation_count"],
            right_summary["observation_count"],
            len(prices),
        ),
    }
    firsts = [value for value in (left_summary["first_seen"], right_summary["first_seen"]) if value]
    lasts = [value for value in (left_summary["last_seen"], right_summary["last_seen"]) if value]
    if firsts:
        merged["first_seen"] = min(firsts)
    if lasts:
        merged["last_seen"] = max(lasts)
    _copy_media(merged, left)
    _copy_media(merged, right)
    lows = []
    for summary in (left_summary, right_summary):
        if summary.get("all_time_low") is not None:
            lows.append((summary["all_time_low"], summary.get("all_time_low_date") or "9999-99-99"))
    if lows:
        low, low_date = min(lows, key=lambda pair: (_cents(pair[0]), pair[1]))
        merged["all_time_low"] = low
        if low_date != "9999-99-99":
            merged["all_time_low_date"] = low_date
    return _write_summary(merged, summarize_entry(merged))


def _active_items(current_data):
    active = {}
    for items in (current_data or {}).values():
        for item in items or []:
            if not isinstance(item, dict) or not item_passes_filters(item):
                continue
            url = normalize_url(item.get("url"))
            if url:
                active[url] = item
    return active


def _filters_allow(entry, url):
    price = _latest_price(_clean_prices(entry.get("prices")))
    if price is None:
        price = entry.get("all_time_low")
    reason = filter_reason(entry.get("name"), entry.get("part"), url, price, None)
    return reason is None or reason == _KEEP_WITHOUT_MSRP


def _empty_stats():
    return {
        "listings_before": 0,
        "listings_after": 0,
        "points_before": 0,
        "points_after": 0,
        "dropped_filter": 0,
        "dropped_stale": 0,
        "points_trimmed": 0,
    }


def prune_price_history(history, today=None, current_data=None):
    """Return ``(pruned_history, stats)``. See the module docstring for policy."""
    if not isinstance(history, dict):
        raise TypeError("price history must be a dict")
    today_day = _as_date(today) or datetime.date.today()
    window_start = (today_day - datetime.timedelta(days=DETAIL_WINDOW_DAYS)).isoformat()
    stale_before = today_day - datetime.timedelta(days=STALE_AFTER_DAYS)
    active = _active_items(current_data)

    merged = {}
    points_before = 0
    for raw_url, entry in history.items():
        if not isinstance(entry, dict):
            continue
        points_before += len(entry.get("prices") or {}) if isinstance(entry.get("prices"), dict) else 0
        url = normalize_url(raw_url)
        if not url:
            continue
        try:
            if url in merged:
                merged[url] = _merge_entries(merged[url], entry)
            else:
                merged[url] = dict(entry)
        except Exception as exc:
            logger.error("Skipping unreadable price history row %s: %s", raw_url, exc)

    stats = _empty_stats()
    stats["listings_before"] = len(history)
    stats["points_before"] = points_before
    kept = {}

    for url, entry in merged.items():
        try:
            summary = summarize_entry(entry)
            _write_summary(entry, summary)
            item = active.get(url)
            if item:
                entry["name"] = item.get("name") or entry.get("name") or ""
                entry["store"] = item.get("store") or entry.get("store") or ""
                entry["part"] = item.get("part") or entry.get("part") or ""
                _copy_media(entry, item)
            elif not _filters_allow(entry, url):
                stats["dropped_filter"] += 1
                continue

            last_day = _as_date(entry.get("last_seen"))
            if item is None and last_day is not None and last_day < stale_before:
                stats["dropped_stale"] += 1
                continue
            if item is None and last_day is None and not entry.get("prices"):
                stats["dropped_stale"] += 1
                continue

            before = len(entry.get("prices") or {})
            prices = {
                day: price
                for day, price in _clean_prices(entry.get("prices")).items()
                if day >= window_start
            }
            stats["points_trimmed"] += before - len(prices)
            entry["prices"] = prices
            kept[url] = _ordered_entry(entry)
        except Exception as exc:
            logger.error("Skipping price history row %s: %s", url, exc)
            stats["dropped_filter"] += 1

    pruned = {url: kept[url] for url in sorted(kept)}
    stats["listings_after"] = len(pruned)
    stats["points_after"] = sum(len(entry["prices"]) for entry in pruned.values())
    logger.info(
        "Price history pruned: %s listings to %s, %s points to %s "
        "(filtered %s, stale %s, trimmed %s points)",
        stats["listings_before"],
        stats["listings_after"],
        stats["points_before"],
        stats["points_after"],
        stats["dropped_filter"],
        stats["dropped_stale"],
        stats["points_trimmed"],
    )
    return pruned, stats


def all_time_low_status(item, history):
    """Whether ``item`` is at its tracked all-time low.

    Brand-new listings are not flagged. The first observed price is always
    the low so far, so a listing needs at least 3 observations spanning 7
    days. The low may live in the summary after daily points have been trimmed.
    """
    empty = {
        "flagged": False,
        "low": None,
        "low_date": None,
        "observations": 0,
        "first_seen": None,
        "span_days": 0,
        "title": "",
    }
    if not isinstance(item, dict) or not isinstance(history, dict):
        return empty
    url = normalize_url(item.get("url"))
    entry = history.get(url) if url else None
    if entry is None:
        entry = history.get(item.get("url"))
    if not isinstance(entry, dict):
        return empty
    current = _cents(item.get("price_new"))
    if current is None:
        return empty
    summary = summarize_entry(entry)
    low = summary.get("all_time_low")
    qualified = (
        summary["observation_count"] >= MIN_ATL_OBSERVATIONS
        and summary["span_days"] >= MIN_ATL_SPAN_DAYS
    )
    flagged = qualified and low is not None and current <= _cents(low)
    title = ""
    if low is not None:
        title = f"Lowest tracked price ${low:.2f}"
        if summary.get("all_time_low_date"):
            title += f" on {summary['all_time_low_date']}"
        title += f", {summary['observation_count']} observations"
    return {
        "flagged": flagged,
        "low": low,
        "low_date": summary.get("all_time_low_date"),
        "observations": summary["observation_count"],
        "first_seen": summary.get("first_seen"),
        "span_days": summary["span_days"],
        "title": title,
    }


def days_at_price(entry, today=None):
    """How long the latest sale price has held.

    ``days`` is the number of days from the first day of the current price
    run through ``today`` (0 when the price changed today). ``price`` is that
    sale price. ``since`` is the date the run started.
    """
    empty = {"days": 0, "price": None, "since": None}
    if not isinstance(entry, dict):
        return empty
    prices = _clean_prices(entry.get("prices"))
    if not prices:
        return {
            "days": 0,
            "price": _round_price(entry.get("all_time_low")),
            "since": entry.get("last_seen") or None,
        }
    ordered = list(prices)
    latest = ordered[-1]
    price = prices[latest]
    since = latest
    cents = _cents(price)
    for day in reversed(ordered):
        if _cents(prices[day]) == cents:
            since = day
        else:
            break
    today_day = _as_date(today) or _as_date(latest)
    since_day = _as_date(since)
    days = 0
    if today_day and since_day:
        days = (today_day - since_day).days
        if days < 0:
            days = 0
    return {"days": days, "price": price, "since": since}


def price_is_reduced(entry):
    """True when the latest price is below some earlier daily price."""
    if not isinstance(entry, dict):
        return False
    prices = _clean_prices(entry.get("prices"))
    if len(prices) < 2:
        return False
    latest = prices[max(prices)]
    cents = _cents(latest)
    return any(_cents(price) > cents for price in prices.values())


def freshly_reduced(entry, today=None):
    """True when the current price started today or yesterday and is a drop."""
    info = days_at_price(entry, today)
    if info.get("price") is None or info.get("days", 99) > 1 or not info.get("since"):
        return False
    if not isinstance(entry, dict):
        return False
    prices = _clean_prices(entry.get("prices"))
    prior = None
    since = info["since"]
    for day in prices:
        if day < since:
            prior = prices[day]
    if prior is None:
        return False
    return _cents(prior) > _cents(info["price"])


def listing_stage(entry, present, today=None, at_low=False):
    """Current lifecycle stage for one listing.

    Present listings are NEW, PRICE DROP, or ALL-TIME LOW. A listing missing
    from a successful scrape is SOLD OUT for 7 days, then GONE.
    """
    if not isinstance(entry, dict):
        entry = {}
    if not present:
        last = _as_date(entry.get("last_seen"))
        today_day = _as_date(today) or datetime.date.today()
        if last is None or today_day is None:
            return "gone"
        age = (today_day - last).days
        if age < 0:
            age = 0
        if age <= RECENTLY_GONE_DAYS:
            return "sold_out"
        return "gone"
    if at_low:
        return "all_time_low"
    if price_is_reduced(entry):
        return "price_drop"
    return "new"


def _store_key(entry):
    store = str((entry or {}).get("store") or "")
    part = str((entry or {}).get("part") or "")
    if not store or not part:
        return ""
    return f"{store}_{part}"


def apply_lifecycle(history, current_data, today=None, skip_keys=None):
    """Persist ``stage`` on each history row. Never marks a failed scrape gone.

    Raises TypeError when ``history`` is not a dict. A bad row is logged and
    skipped so one listing cannot stop the run.
    """
    if not isinstance(history, dict):
        raise TypeError("price history must be a dict")
    day = _date_str(today or datetime.date.today())
    skip = {str(key) for key in (skip_keys or [])}
    active = _active_items(current_data)
    for url, entry in list(history.items()):
        if not isinstance(entry, dict):
            continue
        try:
            present = url in active
            key = _store_key(entry)
            if not present and key and key in skip:
                continue
            at_low = False
            if present:
                at_low = bool(all_time_low_status(active[url], history).get("flagged"))
            stage = listing_stage(entry, present, today=day, at_low=at_low)
            if stage in STAGES:
                entry["stage"] = stage
        except Exception as exc:
            logger.error("Lifecycle update failed for %s: %s", url, exc)
    return history


def recently_gone(history, current_data=None, today=None, skip_keys=None):
    """Disappeared listings kept for ``RECENTLY_GONE_DAYS`` days.

    Each row has the last sale price and last seen date. Failed store/part
    scrapes are left out. Listings the filters reject are left out.
    """
    if not isinstance(history, dict):
        return []
    today_day = _as_date(today) or datetime.date.today()
    skip = {str(key) for key in (skip_keys or [])}
    active = set(_active_items(current_data))
    rows = []
    seen = set()
    for raw_url, entry in history.items():
        if not isinstance(entry, dict):
            continue
        url = normalize_url(raw_url)
        if not url or url in seen or url in active:
            continue
        seen.add(url)
        try:
            key = _store_key(entry)
            if key and key in skip:
                continue
            if not _filters_allow(entry, url):
                continue
            last = _as_date(entry.get("last_seen"))
            if last is None or today_day is None:
                continue
            age = (today_day - last).days
            if age < 0 or age > RECENTLY_GONE_DAYS:
                continue
            prices = _clean_prices(entry.get("prices"))
            price = _latest_price(prices)
            if price is None:
                price = _round_price(entry.get("all_time_low"))
            rows.append(
                {
                    "url": url,
                    "name": normalize_product_name(entry.get("name") or ""),
                    "store": entry.get("store") or "",
                    "part": entry.get("part") or "",
                    "price": price,
                    "last_seen": last.isoformat(),
                    "days_gone": age,
                    "stage": "sold_out",
                }
            )
        except Exception as exc:
            logger.error("Recently gone row failed for %s: %s", raw_url, exc)
    rows.sort(key=lambda row: (row["days_gone"], (row["name"] or "").casefold(), row["store"]))
    return rows


def price_trend(entry):
    """``down``, ``up``, or ``stable`` from the last two daily points."""
    prices = _clean_prices((entry or {}).get("prices") if isinstance(entry, dict) else None)
    dates = list(prices)
    if len(dates) < 2:
        return "stable"
    latest = prices[dates[-1]]
    prior = prices[dates[-2]]
    if latest < prior:
        return "down"
    if latest > prior:
        return "up"
    return "stable"
