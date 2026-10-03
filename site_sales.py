"""Days since each store's last site-wide sale.

The scraper only sees sale listings, not the whole catalog. A site-wide sale
is inferred when one day's filtered sale count is much larger than that
store's recent baseline:

* at least 2.5× the median count of the previous 14 recorded days, and
* at least 30 items above that median, and
* at least 7 earlier days on record (so the first week cannot trip it).

Skate Warehouse is seeded at 2026-07-04. A detected day replaces the seed
only when it is later. The date never moves backward. Other stores, including
Skate Deluxe and Muir Skate, stay "not recorded" until a day clears the
threshold.

Daily counts are kept about 120 days. The last-sale date is stored on its
own, so it survives after those counts age out.
"""

import datetime
import json
import logging
import statistics

from filters import item_passes_filters

logger = logging.getLogger("site_sales")

SITE_SALES_PATH = "site_sales.json"
STORES = ("Zumiez", "SkateWarehouse", "CCS", "Tactics", "Skate Deluxe", "Muir Skate")
SEEDS = {"SkateWarehouse": "2026-07-04"}
# Earlier daily counts for these stores are first-page scrapes. They are not
# a baseline for days on or after the full sale-page scrape, or a one-day
# jump in the count would look like a site-wide sale.
FULL_CATALOG_FROM = {"Zumiez": "2026-10-02", "Tactics": "2026-10-02"}

SPIKE_MULTIPLIER = 2.5
SPIKE_MIN_EXTRA = 30
SPIKE_BASELINE_DAYS = 14
SPIKE_MIN_BASELINE = 7
KEEP_DAYS = 120


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


def _day(value):
    parsed = _as_date(value)
    if parsed is None:
        parsed = datetime.date.today()
    return parsed.isoformat()


def empty_state():
    stores = {}
    for store in STORES:
        if store in SEEDS:
            stores[store] = {"last_sale": SEEDS[store], "source": "seed"}
        else:
            stores[store] = {"last_sale": None, "source": None}
    return {"stores": stores, "daily": {}}


def _coerce(state):
    if not isinstance(state, dict):
        logger.error("Site-sale state was not an object; using the seed")
        return empty_state()
    stores_in = state.get("stores") if isinstance(state.get("stores"), dict) else {}
    stores = {}
    for store in STORES:
        entry = stores_in.get(store)
        last = None
        source = None
        if isinstance(entry, dict):
            last = entry.get("last_sale") or None
            source = entry.get("source")
        if not last and store in SEEDS:
            last = SEEDS[store]
            source = "seed"
        stores[store] = {"last_sale": last, "source": source}
    daily_in = state.get("daily") if isinstance(state.get("daily"), dict) else {}
    daily = {}
    for day, counts in daily_in.items():
        parsed = _as_date(day)
        if parsed is None or not isinstance(counts, dict):
            continue
        clean = {}
        for store, count in counts.items():
            if store not in STORES:
                continue
            try:
                clean[store] = int(count)
            except (TypeError, ValueError):
                continue
        if clean:
            daily[parsed.isoformat()] = clean
    return {"stores": stores, "daily": daily}


def load_state(path=SITE_SALES_PATH):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except FileNotFoundError:
        return empty_state()
    except (OSError, json.JSONDecodeError) as exc:
        logger.error("Could not load site sales (using the seed): %s", exc)
        return empty_state()
    return _coerce(data)


def state_json(state):
    return json.dumps(_coerce(state), indent=2) + "\n"


def catalog_counts(current_data, failed_keys=None):
    """Filtered listings per store. Failed scrapes are skipped."""
    failed = {str(key) for key in (failed_keys or [])}
    counts = {store: 0 for store in STORES}
    for key, items in (current_data or {}).items():
        if str(key) in failed:
            continue
        store = str(key).rsplit("_", 1)[0]
        if store not in counts:
            continue
        for item in items or []:
            if item_passes_filters(item):
                counts[store] += 1
    return {store: count for store, count in counts.items() if count}


def counts_from_history(history):
    """Past daily counts from price history. Today is filled from the catalog."""
    daily = {}
    if not isinstance(history, dict):
        return daily
    for entry in history.values():
        if not isinstance(entry, dict):
            continue
        store = entry.get("store") or ""
        if store not in STORES:
            continue
        prices = entry.get("prices")
        if not isinstance(prices, dict):
            continue
        for day in prices:
            parsed = _as_date(day)
            if parsed is None:
                continue
            bucket = daily.setdefault(parsed.isoformat(), {})
            bucket[store] = bucket.get(store, 0) + 1
    return daily


def _note_spike(state, store, day):
    seed = SEEDS.get(store)
    if seed and day <= seed:
        return
    current = (state["stores"].get(store) or {}).get("last_sale")
    if current is None or day > current:
        state["stores"][store] = {"last_sale": day, "source": "detected"}


def is_spike(count, prior_counts):
    """True when ``count`` clears the documented threshold against ``prior_counts``."""
    prior = list(prior_counts or [])[-SPIKE_BASELINE_DAYS:]
    if len(prior) < SPIKE_MIN_BASELINE:
        return False
    median = statistics.median(prior)
    if median <= 0:
        return False
    return count >= SPIKE_MULTIPLIER * median and count >= median + SPIKE_MIN_EXTRA


def _apply_spikes(state):
    days = sorted(state["daily"])
    for index, day in enumerate(days):
        window = days[max(0, index - SPIKE_BASELINE_DAYS) : index]
        for store, count in state["daily"][day].items():
            prior = []
            start = FULL_CATALOG_FROM.get(store)
            for prev in window:
                if start and day >= start and prev < start:
                    continue
                if store in state["daily"][prev]:
                    prior.append(state["daily"][prev][store])
            if is_spike(count, prior):
                _note_spike(state, store, day)


def _trim(state, today):
    today_day = _as_date(today) or datetime.date.today()
    cutoff = (today_day - datetime.timedelta(days=KEEP_DAYS)).isoformat()
    state["daily"] = {
        day: counts for day, counts in sorted(state["daily"].items()) if day >= cutoff
    }


def record_catalog(state, current_data, today=None, failed_keys=None, history=None):
    """Record today's counts, backfill missing days, and move last-sale forward.

    Never moves a last-sale date backward. A problem in the caller should be
    caught there; this function still tolerates a bad ``state``.
    """
    state = _coerce(state)
    today_text = _day(today)
    if history:
        for day, counts in counts_from_history(history).items():
            if day == today_text:
                continue
            state["daily"].setdefault(day, counts)
    state["daily"][today_text] = catalog_counts(current_data, failed_keys)
    _apply_spikes(state)
    _trim(state, today_text)
    return state


def format_sale_line(row):
    store = row.get("store") or "Unknown"
    if row.get("days") is None or not row.get("last_sale"):
        return f"{store}: no site-wide sale recorded yet."
    day_word = "day" if row["days"] == 1 else "days"
    return (
        f"{store}: {row['days']} {day_word} since the last site-wide sale "
        f"({row['last_sale']})."
    )


DISPLAY_NAMES = {
    "Zumiez": "Zumiez",
    "SkateWarehouse": "Skate Warehouse",
    "CCS": "CCS",
    "Tactics": "Tactics",
    "Skate Deluxe": "Skate Deluxe",
    "Muir Skate": "Muir Skate",
}


def display_name(store):
    return DISPLAY_NAMES.get(store or "", store or "Unknown")


def activity_line(row):
    """One retailer-activity line. Seeded stores still report their age."""
    name = display_name((row or {}).get("store"))
    if not row or row.get("days") is None or not row.get("last_sale"):
        return f"{name}: no recorded site-wide sale"
    days = row["days"]
    if days <= 0:
        return f"{name}: last site-wide sale today"
    if days == 1:
        return f"{name}: last site-wide sale 1 day ago"
    return f"{name}: last site-wide sale {days} days ago"


def _extra_percent(state, store, day):
    """Percent above the prior median. None when the baseline is too short."""
    days = sorted(state.get("daily") or {})
    if day not in days:
        return None
    index = days.index(day)
    window = days[max(0, index - SPIKE_BASELINE_DAYS) : index]
    prior = []
    for prev in window:
        counts = state["daily"].get(prev) or {}
        if store in counts:
            prior.append(counts[store])
    prior = prior[-SPIKE_BASELINE_DAYS:]
    if len(prior) < SPIKE_MIN_BASELINE:
        return None
    median = statistics.median(prior)
    if median <= 0:
        return None
    count = (state["daily"].get(day) or {}).get(store)
    if count is None:
        return None
    return int(round((count - median) / median * 100))


def describe_sales(state, today=None):
    """One row per store: last sale date, days since, source, and today's spike."""
    state = _coerce(state)
    today_day = _as_date(today) or datetime.date.today()
    today_text = today_day.isoformat()
    rows = []
    for store in STORES:
        entry = state["stores"][store]
        last = entry.get("last_sale")
        days = None
        if last:
            last_day = _as_date(last)
            if last_day is not None:
                days = (today_day - last_day).days
        source = entry.get("source")
        detected_today = bool(source == "detected" and last == today_text)
        extra = _extra_percent(state, store, last) if detected_today and last else None
        rows.append(
            {
                "store": store,
                "last_sale": last,
                "days": days,
                "source": source,
                "detected_today": detected_today,
                "extra_percent": extra,
            }
        )
    return rows


def _parse_dt(value):
    if isinstance(value, datetime.datetime):
        return value
    if isinstance(value, datetime.date):
        return datetime.datetime(value.year, value.month, value.day)
    if not value:
        return None
    text = str(value).strip().replace("Z", "+00:00")
    try:
        return datetime.datetime.fromisoformat(text)
    except ValueError:
        pass
    try:
        return datetime.datetime.strptime(text[:19], "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None


def hours_since(scanned_at, now=None):
    """Hours from the scan timestamp to ``now``. Missing times count as zero."""
    start = _parse_dt(scanned_at)
    if start is None:
        return 0.0
    end = _parse_dt(now) if now is not None else datetime.datetime.now(datetime.timezone.utc)
    if end is None:
        return 0.0
    if start.tzinfo is None:
        start = start.replace(tzinfo=datetime.timezone.utc)
    if end.tzinfo is None:
        end = end.replace(tzinfo=datetime.timezone.utc)
    seconds = (end - start).total_seconds()
    if seconds < 0:
        seconds = 0
    return seconds / 3600.0


def hours_phrase(hours):
    try:
        hours = float(hours)
    except (TypeError, ValueError):
        hours = 0.0
    if hours < 1:
        return "under an hour ago"
    whole = int(hours)
    if whole < 1:
        whole = 1
    unit = "hour" if whole == 1 else "hours"
    return f"{whole} {unit} ago"


def format_sale_banner(store, percent, hours):
    name = display_name(store)
    try:
        shown = int(round(float(percent)))
    except (TypeError, ValueError):
        shown = 0
    return (
        f"🔥 {name} - site-wide sale detected ({shown}% more items on sale) "
        f"{hours_phrase(hours)}"
    )


def sale_banners(state, today=None, scanned_at=None, now=None):
    """Banners for sales detected on this scan. A seed date does not qualify."""
    try:
        rows = describe_sales(state, today)
    except Exception as exc:
        logger.error("Sale banner failed (continuing): %s", exc)
        return []
    hours = hours_since(scanned_at, now) if scanned_at else 0
    banners = []
    for row in rows:
        if not row.get("detected_today") or row.get("extra_percent") is None:
            continue
        banners.append(format_sale_banner(row["store"], row["extra_percent"], hours))
    return banners
