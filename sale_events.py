"""Store sale history: what each sale was, when it ran, and what to expect.

(Owner, 2026-11-06.) ``site_sales.py`` only kept the date of each store's
last site-wide sale. This keeps a log of sale *events* per store:

* when it ran: ``start`` and ``end`` (the first scrape it was gone), or
  still running; a sale that keeps being extended is one long event (Skate
  Warehouse's 2025 Black Friday ran to Christmas);
* what it was: the extra cut ("Extra 20% off 72 of 83 deals we track"),
  and while it runs, the deals we list ("most deals 20% off" when most share
  one discount, else "up to 60% off (most 30-40%)") and each change of that.
  It is what we see on the store's sale pages, never called "sitewide";
* which shopping moment it fell in (Black Friday / Cyber Week, Christmas,
  Labor Day...), so the page can say what a store did last time;
* the store's rhythm: with three or more sales, the typical gap and a
  likely next date - always with how many sales it rests on.

A sale is noticed from the price history: many listings we already track
cut by the same amount on the same day, until they go back up. Counting
listings would mistake our own coverage changes (a new store, a sale page
read whole) for sales; those add listings but cut no prices. Past sales are
rebuilt from the history, with their cut but no "up to" figures.

Nothing here predicts a store will repeat a sale; the wording says what
happened, "last time" and "usually", never "will".
"""

import datetime
import json
import logging
import statistics

logger = logging.getLogger("sale_events")

PATH = "sale_events.json"
MOVE = 0.03                             # a price moved: 3%+ since the previous scrape
WAVE_MIN, WAVE_SHARE = 10, 0.10         # a sale: 10+ tracked listings and 10% of them cut the same day
END_SHARE = 0.10                        # it ends when 10% of the listings it cut go back up
MARKDOWN_DAYS = 45                      # cuts never reversed after 45 days: a markdown, not a sale
JOIN_DAYS = 3                           # cuts within 3 days of the last are the same start
UNIFORM_SHARE = 0.6                     # one discount: 60%+ of cuts / deals within a point or two
KEEP_EVENTS = 40


# ---- dates and shopping moments -------------------------------------------

def _date(value):
    try:
        return datetime.date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def _nth_weekday(year, month, weekday, n):
    """The nth ``weekday`` (Mon=0) of a month; n=-1 is the last."""
    if n > 0:
        first = datetime.date(year, month, 1)
        return first + datetime.timedelta(days=(weekday - first.weekday()) % 7 + 7 * (n - 1))
    last = (datetime.date(year, month + 1, 1) if month < 12 else datetime.date(year + 1, 1, 1)) - datetime.timedelta(days=1)
    return last - datetime.timedelta(days=(last.weekday() - weekday) % 7)


def moments(year):
    """[(name, first day, last day)] of the shopping moments in ``year``."""
    thanksgiving = _nth_weekday(year, 11, 3, 4)
    d = datetime.date
    span = datetime.timedelta
    return [
        ("New Year", d(year, 1, 1), d(year, 1, 7)),
        ("Presidents' Day", _nth_weekday(year, 2, 0, 3) - span(days=4), _nth_weekday(year, 2, 0, 3) + span(days=2)),
        ("End of ski season", d(year, 3, 15), d(year, 4, 30)),
        ("Memorial Day", _nth_weekday(year, 5, 0, -1) - span(days=5), _nth_weekday(year, 5, 0, -1) + span(days=2)),
        ("July 4th", d(year, 6, 29), d(year, 7, 7)),
        ("Labor Day", _nth_weekday(year, 9, 0, 1) - span(days=5), _nth_weekday(year, 9, 0, 1) + span(days=2)),
        ("Black Friday / Cyber Week", thanksgiving - span(days=10), thanksgiving + span(days=7)),
        ("Christmas", d(year, 12, 8), d(year, 12, 31)),
    ]


def moment_for(start, end=None):
    """The shopping moment a sale starting on ``start`` belongs to, or ""."""
    start = _date(start)
    if start is None:
        return ""
    for name, first, last in moments(start.year):
        if first <= start <= last:
            return name
    return ""


# ---- detecting sales from price cuts --------------------------------------

def _changes(history):
    """{store: {day: {"known": n, "cuts": [pct], "rises": [pct]}}}: for each
    listing seen on two scrapes, how its price moved since the previous one."""
    out = {}
    for entry in (history or {}).values():
        if not isinstance(entry, dict) or not isinstance(entry.get("prices"), dict):
            continue
        store = entry.get("store") or ""
        days = sorted(day for day in entry["prices"] if _date(day))
        if not store or len(days) < 2:
            continue
        for before, day in zip(days, days[1:]):
            try:
                old, new = float(entry["prices"][before]), float(entry["prices"][day])
            except (TypeError, ValueError):
                continue
            if old <= 0 or new <= 0:
                continue
            row = out.setdefault(store, {}).setdefault(str(day)[:10], {"known": 0, "cuts": [], "rises": []})
            row["known"] += 1
            if new <= old * (1 - MOVE):
                row["cuts"].append(round((old - new) / old * 100))
            elif new >= old * (1 + MOVE):
                row["rises"].append(round((new - old) / old * 100))
    return out


def _wave(moves, known):
    return len(moves) >= max(WAVE_MIN, WAVE_SHARE * known)


def _cut_stats(cuts, known):
    cuts = sorted(cuts)
    typical = statistics.median(cuts)
    near = sum(1 for pct in cuts if abs(pct - typical) <= 2)
    return {"cut": round(typical), "cut_low": cuts[len(cuts) // 4], "cut_high": cuts[-1 - len(cuts) // 4],
            "uniform": near >= UNIFORM_SHARE * len(cuts), "listings": len(cuts), "tracked": known}


def detect(changes):
    """[{start, end, cut, uniform, listings, tracked, steps}] from one store's
    daily price moves (``_changes``).

    A sale starts on a day when many listings we already track are cut at
    once (WAVE_MIN+ and WAVE_SHARE of them): adding a store or a sale page
    brings in new listings but cuts none, so our own coverage changes don't
    look like sales. Cuts on the next JOIN_DAYS days are the same start. It
    ends on the first day as many prices go back up (``end``, None while it
    runs). A new wave of cuts during a sale is a step ("25% -> 30%"). Prices
    going back up with no sale on record: a sale that ended before the
    history began (``start`` None). Cuts still in place after MARKDOWN_DAYS
    are ``kind`` "markdown" (clearance pricing), not a sale."""
    events, current, last_cut = [], None, None
    for day in sorted(changes):
        row = changes[day]
        cut_wave = _wave(row["cuts"], row["known"])
        # A sale ends when a good part of what it cut goes back up.
        rise_wave = current is not None and row["rises"] and \
            len(row["rises"]) >= max(5, END_SHARE * current["listings"]) and \
            statistics.median(row["rises"]) >= current["cut"] / 2
        if current is not None and rise_wave and len(row["rises"]) > len(row["cuts"]):
            current["end"] = day
            events.append(current)
            current, last_cut = None, None
            continue
        if not cut_wave:
            continue
        stats = _cut_stats(row["cuts"], row["known"])
        if current is not None and (_date(day) - _date(current["start"])).days > MARKDOWN_DAYS:
            events.append(current)       # never went back up: a markdown, see below
            current, last_cut = None, None
        if current is None:
            current = dict(stats, start=day, end=None, steps=[], _cuts=list(row["cuts"]))
        elif last_cut and (_date(day) - _date(last_cut)).days <= JOIN_DAYS and not current["steps"]:
            current["_cuts"].extend(row["cuts"])
            current.update(_cut_stats(current["_cuts"], max(current["tracked"], row["known"])))
        else:
            current["steps"].append({"from": day, "cut": stats["cut"], "listings": stats["listings"]})
        last_cut = day
    if current is not None:
        events.append(current)
    # A rise wave before any cut we saw: a sale already running when the
    # history began.
    first_start = events[0]["start"] if events else None
    for day in sorted(changes):
        if first_start and day >= first_start:
            break
        row = changes[day]
        if _wave(row["rises"], row["known"]) and statistics.median(row["rises"]) >= 8 \
                and len(row["rises"]) > len(row["cuts"]):
            back = [round((1 - 1 / (1 + pct / 100)) * 100) for pct in row["rises"]]
            events.insert(0, dict(_cut_stats(back, row["known"]), start=None, end=day, steps=[]))
            break
    last_day = _date(max(changes)) if changes else None
    for event in events:
        event.pop("_cuts", None)
        event["kind"] = "sale"
        if event["end"] is None and event["start"] and last_day and \
                (last_day - _date(event["start"])).days > MARKDOWN_DAYS:
            event["kind"] = "markdown"   # store lowered prices for good
    return events


# ---- what a sale was, from the deals scraped while it ran ------------------

def _percent_off(item):
    try:
        new, old = float(item.get("price_new")), float(item.get("price_old"))
    except (TypeError, ValueError):
        return None
    if old <= 0 or new <= 0 or new >= old:
        return None
    return round((old - new) / old * 100)


def describe_deals(items):
    """{deals, max_off, low, high, uniform} of one store's current markdowns.

    ``uniform``: the one discount most deals share ("most deals 20% off"),
    when 60%+ of them are within a point of it; else None. ``low``/``high``:
    the middle half of the discounts ("most 30-40%")."""
    offs = sorted(p for p in (_percent_off(item) for item in items or ()) if p is not None)
    if not offs:
        return None
    mode = statistics.mode(offs)
    near = sum(1 for p in offs if abs(p - mode) <= 1)
    quarter = len(offs) // 4
    return {"deals": len(offs), "max_off": offs[-1], "low": offs[quarter], "high": offs[-1 - quarter],
            "uniform": mode if near >= UNIFORM_SHARE * len(offs) and mode >= 10 else None}


def headline(stats):
    """ "most deals 20% off" / "up to 60% off (most 30-40%)" / "" - of the
    deals we list, which is not the whole store, so never "sitewide"."""
    if not stats:
        return ""
    if stats.get("uniform"):
        return f"most deals {stats['uniform']}% off"
    spread = f"most {stats['low']}%" if stats["low"] == stats["high"] else f"most {stats['low']}-{stats['high']}%"
    return f"up to {stats['max_off']}% off ({spread})"


# ---- the log ----------------------------------------------------------------

def load(path=PATH):
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save(state, path=PATH):
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(state, handle, indent=2, sort_keys=True)
        handle.write("\n")


def _key(event):
    return event.get("start") or f"before-{event.get('end')}"


def deals_by_store(current_data):
    """{store: [items]} from a run's {"Store_Part": [items]}."""
    out = {}
    for key, items in (current_data or {}).items():
        for item in items or ():
            if isinstance(item, dict):
                out.setdefault(item.get("store") or str(key).split("_", 1)[0], []).append(item)
    return out


def update(state, history, current_data, today):
    """Rebuild each store's events from the price history, keeping what
    earlier runs measured: a running sale gets today's deal figures
    ("Up to 60% off (most 30-40%)") and each change of them. Events older
    than the history (pruned listings) are kept as they were."""
    stores = dict((state or {}).get("stores") or {})
    today = str(today)[:10]
    deals = deals_by_store(current_data)
    for store, changes in sorted(_changes(history).items()):
        old_events = list((stores.get(store) or {}).get("events") or [])
        old = {_key(event): event for event in old_events}
        first_day = min(changes)
        kept = [event for event in old_events
                if (event.get("end") or event.get("start") or "9999") < first_day]
        events = []
        for found in detect(changes):
            event = dict(old.get(_key(found)) or {})
            event.update(found)
            event["moment"] = moment_for(found["start"]) if found["start"] else ""
            if found["end"] is None and found["kind"] == "sale" and deals.get(store):
                stats = describe_deals(deals[store])
                text = headline(stats)
                seen = list(event.get("headlines") or [])
                if text and (not seen or seen[-1]["text"] != text):
                    seen.append({"from": today, "text": text})
                if seen:
                    event["headlines"] = seen[-6:]
                if stats:
                    event["deals"] = stats
            events.append(event)
        stores[store] = {"events": (kept + events)[-KEEP_EVENTS:]}
    return {"updated": today, "stores": stores}


def summary(store_state, today):
    """What the page says about one store: the running sale, the last one,
    the last one at each shopping moment, and - with three or more sales -
    the usual gap and when the next would fall on that rhythm."""
    events = [event for event in (store_state or {}).get("events") or [] if event.get("kind", "sale") == "sale"]
    today_day = _date(today) or datetime.date.today()
    out = {"running": None, "last": None, "rhythm": None, "next": None, "moments": {}}
    if not events:
        return out
    if events[-1].get("end") is None:
        out["running"] = events[-1]
    finished = [event for event in events if event.get("end")]
    if finished:
        out["last"] = finished[-1]
    starts = [_date(event["start"]) for event in events if event.get("start")]
    gaps = [(b - a).days for a, b in zip(starts, starts[1:])]
    if len(gaps) >= 2:
        typical = round(statistics.median(gaps))
        out["rhythm"] = {"days": typical, "based_on": len(starts)}
        likely = starts[-1] + datetime.timedelta(days=typical)
        if out["running"] is None and likely >= today_day:
            out["next"] = {"around": likely.isoformat(), "based_on": len(starts)}
    for event in events:
        if event.get("moment"):
            out["moments"][event["moment"]] = event      # the latest at each moment
    return out


def _short(day):
    parsed = _date(day)
    return f"{parsed:%b} {parsed.day}" if parsed else ""


def _long(day):
    parsed = _date(day)
    return f"{parsed:%b} {parsed.day}, {parsed.year}" if parsed else ""


def what(event):
    """ "Extra 20% off 72 of 83 deals we track · now up to 60% off (most 30-40%)" """
    cut = f"{event['cut']}%" if event.get("uniform") or event.get("cut_low") == event.get("cut_high") \
        else f"{event['cut_low']}-{event['cut_high']}%"
    text = f"Extra {cut} off {event['listings']} of {event['tracked']} deals we track"
    for step in event.get("steps") or []:
        text += f", {step['cut']}% more from {_short(step['from'])}"
    texts = [h["text"] for h in event.get("headlines") or []]
    if texts:
        text += (" · now " if event.get("end") is None else " · at the time ") + texts[-1]
        if len(texts) > 1 and texts[0] != texts[-1]:
            text += f" (was {texts[0]})"
    return text


def when(event):
    """ "Sep 3 - Sep 11" / "since Oct 22" / "ended Aug 11" """
    if not event.get("start"):
        return f"ended {_short(event.get('end'))}"
    if event.get("end") is None:
        return f"since {_short(event['start'])}"
    return f"{_short(event['start'])} - {_short(event['end'])}"


def describe_event(event):
    return f"{what(event)} · {when(event)}" if event else ""


def lines(state, today, names=None):
    """[(store, [text])] for the page, stores with a sale on record only."""
    out = []
    for store, store_state in sorted(((state or {}).get("stores") or {}).items()):
        info = summary(store_state, today)
        rows = []
        if info["running"]:
            rows.append("On sale now: " + describe_event(info["running"]))
        if info["last"]:
            rows.append("Last sale: " + describe_event(info["last"]))
        for moment, event in sorted(info["moments"].items(), key=lambda pair: pair[1].get("start") or ""):
            if event is not info["running"] and event is not info["last"]:
                rows.append(f"Last {moment}: {describe_event(event)} ({_date(event['start']).year})")
            elif event.get("start"):
                rows[-1 if event is info["last"] else 0] += f" ({moment})"
        if info["next"]:
            rows.append(f"Sales usually {info['rhythm']['days']} days apart; on that rhythm the next would be "
                        f"around {_long(info['next']['around'])} (from {info['next']['based_on']} sales, "
                        "not a promise)")
        if rows:
            out.append(((names or {}).get(store, store), rows))
    return out


def run(history, current_data, today, path=PATH):
    """Update and save the log after a scrape. Never raises."""
    try:
        state = update(load(path), history, current_data, today)
        save(state, path)
        return state
    except Exception as exc:  # a broken log must never fail the scrape
        logger.warning("sale history skipped: %s", exc)
        return None
