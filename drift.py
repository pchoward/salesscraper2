"""Daily drift check: what changed at the stores that the scrape guard alone
won't show (owner, 2026-11-21).

The scrape guard (health.py) catches a sudden collapse and keeps the old
listings. Slow drift is quieter: a store renames a product type and its
listings drop out, a description format changes and a filter goes blank, or
the guard keeps holding old listings for days. This check reads what each
scrape already saves and lists those cases for a person or the monitoring
agent:

- ``held``: store/part pairs the guard is holding from an earlier day, with
  how many runs in a row.
- ``volume``: a store's listing count well below (or far above) its recent
  median, short of the guard's own threshold.
- ``new_unmapped``: product types a store sells marked down that have no
  category, seen for the first time (from ``feed_summary.json``).
- ``fill``: a filter field (or brand, or photo) whose share of a store's
  listings fell to under half its recent median.
- ``stale``: a sport whose last scrape is more than a day old.
- ``new_unclassified``: listings one of our rules couldn't place (owner,
  2026-11-26: "flag what rules don't recognise"): MTB pedals with no pedal
  type, BMX parts with no Type, protection that doesn't say what it
  protects. Each listing once, the first run it shows up, with examples.

For each sport it writes ``drift_report.json`` and keeps a short history in
``drift_history.json`` next to that sport's data (the repository root for
Skate, ``catalogs/<sport>/`` for the others).

    python drift.py skate            # after the Skate scrape
    python drift.py bmx ski mtb      # after the evening scrapes

A Markdown summary is printed, and appended to ``$GITHUB_STEP_SUMMARY`` when
that is set. Never raises and always exits 0: it reports, it never blocks a
publish.
"""

import argparse
import datetime
import json
import logging
import os
import statistics
from pathlib import Path

import sports

logger = logging.getLogger("drift")

REPORT = "drift_report.json"
HISTORY = "drift_history.json"
KEEP_DAYS = 21  # history kept per sport
RECENT_RUNS = 7  # runs compared for volume and fill

# Volume: only stores with a meaningful median, and a clear change.
VOLUME_MIN_MEDIAN = 10
VOLUME_DROP = 0.6  # today at or below 60% of the median
VOLUME_RISE = 2.0  # today at least double the median ...
VOLUME_RISE_MIN = 25  # ... and at least this many more listings

# Fill rates: only (store, part) groups with enough listings, and fields
# the store normally fills.
FILL_MIN_ITEMS = 10
FILL_MIN_MEDIAN = 0.3
FILL_DROP = 0.5  # today under half the median share
FILL_MIN_SAMPLES = 3

NEW_UNMAPPED_MIN = 3  # listings of a new uncategorized type worth a mention

# Row keys that every listing has or that hold prices and offers rather than
# a filter value.
_PLAIN_KEYS = {"name", "url", "price_new", "price_old", "availability", "part", "store", "images",
               "product_type", "description", "technical_offers", "technical_specs", "spec_offers",
               "spec_warnings", "first_seen", "last_seen", "length"}


def _read(path, default):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _write(path, payload):
    from stores.files import safe_write_file
    return safe_write_file(str(path), json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _store_of(key):
    return key.split("_", 1)[0]


def _filled(value):
    return value not in (None, "", [], {}, ())


def _fields(item):
    """The filter values this listing has: its technical specs, its other
    spec keys (Skate's widths and sizes), its brand and its photo."""
    found = {key for key, value in (item.get("technical_specs") or {}).items() if _filled(value)}
    found |= {key for key, value in item.items() if key not in _PLAIN_KEYS and _filled(value)}
    return found


def fill_rates(current_data):
    """{"store|part": {"items": n, "fields": {field: share}}} for groups with
    enough listings to judge."""
    rates = {}
    for key, items in (current_data or {}).items():
        if not isinstance(items, list) or len(items) < FILL_MIN_ITEMS:
            continue
        counts = {}
        for item in items:
            if isinstance(item, dict):
                for field in _fields(item):
                    counts[field] = counts.get(field, 0) + 1
        rates[key] = {"items": len(items), "fields": {f: round(c / len(items), 3) for f, c in counts.items()}}
    return rates


def held(health):
    """Keys the guard held in the latest run, with how many runs in a row."""
    runs = (health or {}).get("runs") or []
    if not runs:
        return []
    found = []
    for key, result in sorted((runs[-1].get("results") or {}).items()):
        if not result.get("failed"):
            continue
        streak = 0
        for run in reversed(runs):
            if ((run.get("results") or {}).get(key) or {}).get("failed"):
                streak += 1
            else:
                break
        reason = (result.get("diagnostics") or {}).get("reason") or "failed"
        found.append({"kind": "held", "key": key, "store": _store_of(key), "runs": streak, "reason": reason,
                      "level": "action" if streak >= 2 else "watch"})
    return found


def _store_counts(run):
    totals = {}
    for key, result in (run.get("results") or {}).items():
        if result.get("failed"):
            continue
        totals[_store_of(key)] = totals.get(_store_of(key), 0) + int(result.get("count") or 0)
    return totals


def volume(health):
    """Stores whose total listings today are well off their recent median.
    Stores with a held part are left to ``held``."""
    runs = (health or {}).get("runs") or []
    if len(runs) < 4:
        return []
    today = _store_counts(runs[-1])
    held_stores = {_store_of(k) for k, r in (runs[-1].get("results") or {}).items() if r.get("failed")}
    found = []
    earlier = [_store_counts(run) for run in runs[-1 - RECENT_RUNS:-1]]
    for store in sorted(set(today) | {s for counts in earlier for s in counts}):
        if store in held_stores:
            continue
        history = [counts[store] for counts in earlier if store in counts]
        if len(history) < 3:
            continue
        median = statistics.median(history)
        count = today.get(store, 0)
        if median >= VOLUME_MIN_MEDIAN and count <= median * VOLUME_DROP:
            found.append({"kind": "volume", "store": store, "count": count, "median": median,
                          "change": "drop", "level": "action" if count == 0 or count <= median * 0.3 else "watch"})
        elif median >= 1 and count >= median * VOLUME_RISE and count - median >= VOLUME_RISE_MIN:
            found.append({"kind": "volume", "store": store, "count": count, "median": median,
                          "change": "rise", "level": "watch"})
    return found


def new_unmapped(feed, seen):
    """Uncategorized product types not seen before for that store."""
    found = []
    for store, summary in sorted(((feed or {}).get("stores") or {}).items()):
        known = set((seen or {}).get(store) or [])
        for kind, count in (summary or {}).get("unmapped_types") or []:
            if kind not in known and count >= NEW_UNMAPPED_MIN:
                found.append({"kind": "new_unmapped", "store": store, "product_type": kind, "count": count,
                              "level": "action" if count >= 10 else "watch"})
    return found


UNCLASSIFIED_EXAMPLES = 5
UNCLASSIFIED_KEEP = 5000  # listing URLs remembered per field


def _pedal_type(item):
    return (item.get("technical_specs") or {}).get("pedal_type")


def _bmx_kind(item):
    return item.get("kind")


def _protects(item):
    from sports.protection import protects
    return protects(item.get("name") or "", item.get("product_type") or "")


# (field, label, sports, the store categories it applies to, skipped
# categories, the value). Categories None: every category but the skipped.
UNCLASSIFIED = (
    ("pedal_type", "pedal type", ("mtb",), ("Pedals",), (), _pedal_type),
    ("kind", "Type", ("bmx",), None, ("Protection", "Packs", "Bikes", "Tools & Care"), _bmx_kind),
    ("protects", "protection type", ("skate", "bmx", "ski", "mtb"), ("Protection",), (), _protects),
)


def unclassified(current_data, sport_id):
    """{field: [listing, ...]} for listings a rule couldn't place."""
    found = {}
    for field, _label, sport_ids, parts, skip, value in UNCLASSIFIED:
        if sport_id not in sport_ids:
            continue
        for items in (current_data or {}).values():
            for item in items if isinstance(items, list) else ():
                if not isinstance(item, dict) or not item.get("url"):
                    continue
                part = item.get("part") or ""
                if (parts is not None and part not in parts) or part in skip:
                    continue
                try:
                    placed = value(item)
                except Exception:
                    placed = None
                if not _filled(placed):
                    found.setdefault(field, []).append(item)
    return found


def new_unclassified(missing, seen):
    """One finding per field with listings not reported before."""
    labels = {field: label for field, label, *_ in UNCLASSIFIED}
    found = []
    for field, items in sorted(missing.items()):
        known = set(seen.get(field) or [])
        fresh = [item for item in items if item["url"] not in known]
        if not fresh:
            continue
        examples = [{"store": item.get("store") or "", "part": item.get("part") or "", "name": item.get("name") or ""}
                    for item in fresh[:UNCLASSIFIED_EXAMPLES]]
        found.append({"kind": "new_unclassified", "field": field, "label": labels[field], "count": len(fresh),
                      "examples": examples, "level": "action"})
    return found


def fill_drops(rates, past):
    """Fields whose share of a store/part's listings fell below half its
    recent median."""
    found = []
    for key, today in sorted(rates.items()):
        samples = [day.get(key) for day in past if day.get(key)]
        if len(samples) < FILL_MIN_SAMPLES:
            continue
        fields = {f for sample in samples for f in sample["fields"]}
        for field in sorted(fields):
            history = [sample["fields"].get(field, 0) for sample in samples]
            median = statistics.median(history)
            share = today["fields"].get(field, 0)
            if median >= FILL_MIN_MEDIAN and share < median * FILL_DROP:
                found.append({"kind": "fill", "key": key, "store": _store_of(key), "field": field,
                              "share": share, "median": round(median, 3), "items": today["items"],
                              "level": "action" if share == 0 else "watch"})
    return found


def stale(health, today):
    runs = (health or {}).get("runs") or []
    if not runs:
        return [{"kind": "stale", "last": None, "level": "action"}]
    try:
        last = datetime.date.fromisoformat(runs[-1].get("date"))
    except (TypeError, ValueError):
        return [{"kind": "stale", "last": runs[-1].get("date"), "level": "action"}]
    if (today - last).days > 1:
        return [{"kind": "stale", "last": last.isoformat(), "days": (today - last).days, "level": "action"}]
    return []


def check(folder, today, sport_id=""):
    """The drift report for the sport data in ``folder``; updates its history."""
    folder = Path(folder)
    health = _read(folder / "scrape_health.json", {})
    current = _read(folder / "previous_data.json", {})
    feed = _read(folder / "feed_summary.json", {})
    history = _read(folder / HISTORY, {})
    days = history.get("days") or {}
    past = [days[d]["fill"] for d in sorted(days) if d < today.isoformat() and days[d].get("fill")][-RECENT_RUNS:]
    seen = history.get("unmapped_seen") or {}

    rates = fill_rates(current)
    missing = unclassified(current, sport_id)
    unplaced_seen = history.get("unclassified_seen") or {}
    findings = (stale(health, today) + held(health) + volume(health)
                + new_unmapped(feed, seen) + new_unclassified(missing, unplaced_seen) + fill_drops(rates, past))

    # Remember today's fill rates and every uncategorized type seen so far
    # (a type is "new" once). The first run only records: with no history,
    # every type would look new.
    first = not history
    for store, summary in ((feed or {}).get("stores") or {}).items():
        names = set(seen.get(store) or []) | {kind for kind, _ in (summary or {}).get("unmapped_types") or []}
        seen[store] = sorted(names)
    # A listing is reported once. The first run reports today's backlog too:
    # it's small, and worth seeing once.
    for field, items in missing.items():
        urls = list(unplaced_seen.get(field) or [])
        known = set(urls)
        urls += [item["url"] for item in items if item["url"] not in known]
        unplaced_seen[field] = urls[-UNCLASSIFIED_KEEP:]
    if first:
        findings = [f for f in findings if f["kind"] != "new_unmapped"]
    days[today.isoformat()] = {"fill": rates}
    cutoff = (today - datetime.timedelta(days=KEEP_DAYS)).isoformat()
    days = {d: v for d, v in days.items() if d >= cutoff}
    _write(folder / HISTORY, {"days": days, "unmapped_seen": seen, "unclassified_seen": unplaced_seen})

    report = {
        "checked_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "date": today.isoformat(),
        "last_scrape": ((health.get("runs") or [{}])[-1] or {}).get("scanned_at"),
        "findings": findings,
        "counts": {level: sum(1 for f in findings if f["level"] == level) for level in ("action", "watch")},
    }
    _write(folder / REPORT, report)
    return report


def _line(finding):
    kind = finding["kind"]
    if kind == "stale":
        return f"last scrape {finding.get('last') or 'never'}" + (f" ({finding['days']} days ago)" if finding.get("days") else "")
    if kind == "held":
        return f"`{finding['key']}` held from an earlier day ({finding['reason']}, {finding['runs']} run(s) in a row)"
    if kind == "volume":
        word = "down" if finding["change"] == "drop" else "up"
        return f"{finding['store']}: {finding['count']} listings, {word} from a median of {finding['median']:g}"
    if kind == "new_unmapped":
        return f"{finding['store']}: new product type with no category, \"{finding['product_type']}\" ({finding['count']} marked down)"
    if kind == "new_unclassified":
        names = "; ".join(f"{e['store']}: {e['name']}" for e in finding["examples"])
        more = finding["count"] - len(finding["examples"])
        return f"{finding['count']} new listing(s) with no {finding['label']}: {names}" + (f" (+{more} more)" if more > 0 else "")
    if kind == "fill":
        return (f"`{finding['key']}`: `{finding['field']}` on {finding['share']:.0%} of {finding['items']} listings,"
                f" median {finding['median']:.0%}")
    return json.dumps(finding)


def markdown(reports):
    lines = ["## Drift check", ""]
    for label, report in reports:
        findings = report["findings"]
        lines.append(f"### {label}: {report['counts']['action']} to act on, {report['counts']['watch']} to watch")
        if not findings:
            lines.append("Nothing unusual.")
        for level in ("action", "watch"):
            for finding in findings:
                if finding["level"] == level:
                    lines.append(f"- {'**act**' if level == 'action' else 'watch'}: {_line(finding)}")
        lines.append("")
    return "\n".join(lines)


def run(sport_ids, today=None):
    today = today or datetime.datetime.now(datetime.timezone.utc).date()
    reports = []
    for sport_id in sport_ids:
        try:
            sport = sports.get(sport_id)
            folder = Path(".") if sport.is_default else sport.data_path()
            reports.append((sport.label, check(folder, today, sport.id)))
        except Exception as exc:  # reporting only; never fails a run
            logger.error("Drift check failed for %s (%s: %s)", sport_id, type(exc).__name__, exc)
    text = markdown(reports)
    print(text)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        try:
            with open(summary, "a", encoding="utf-8") as handle:
                handle.write(text + "\n")
        except OSError:
            pass
    return reports


def main(argv=None):
    parser = argparse.ArgumentParser(description="Report store drift after a scrape.")
    parser.add_argument("sports", nargs="+", choices=sorted(sports.SPORTS))
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    run(args.sports)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
