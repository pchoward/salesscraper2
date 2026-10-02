"""Per-store, per-part scrape counts, and broken-store warnings.

Each run records how many items came back for every store/part key, and
whether the fetch failed. The file stays small: the last 30 runs, plus a
baseline of the last time each key actually had items.

A warning fires only when the last two recorded runs for a key are both bad
(empty or failed) and that key has a baseline with items. One empty category
does not warn. A later run that returns items clears the warning. Keys that
have never had items (for example bearings that are always empty) stay quiet.

A whole store is different. When every category comes back empty and that
store's baseline still has items, the run is suspect: each of those keys is
failed, previous listings are kept, and the report warns on that same run.
"""

import datetime
import json
import logging

logger = logging.getLogger("health")

HEALTH_PATH = "scrape_health.json"
MAX_RUNS = 30
ALERT_STREAK = 2


def empty_state():
    return {"runs": [], "baseline": {}}


def _good(result):
    return bool(result) and not result.get("failed") and int(result.get("count") or 0) > 0


def _bad(result):
    if not isinstance(result, dict):
        return True
    if result.get("failed"):
        return True
    return int(result.get("count") or 0) <= 0


def _kind(older, newer):
    flags = [bool(older.get("failed")), bool(newer.get("failed"))]
    if all(flags):
        return "error"
    if not any(flags):
        return "empty"
    return "mixed"


def split_key(key):
    store, part = str(key).rsplit("_", 1)
    return store, part


def record_run(state, day, results, scanned_at=None):
    """Append or replace the run for ``day``. Update baselines on good keys.

    Replacing the same day means a manual re-run does not count as a second
    failure. ``scanned_at`` is the real scan timestamp when the caller has
    one. Raises TypeError when ``state`` is not usable; callers that must
    not stop the scrape catch that.
    """
    if not isinstance(state, dict):
        raise TypeError("health state must be a dict")
    raw_runs = state.get("runs") or []
    if not isinstance(raw_runs, list):
        raise TypeError("health runs must be a list")
    day = str(day)
    clean = {}
    for key, result in (results or {}).items():
        if not isinstance(result, dict):
            raise TypeError("each health result must be a dict")
        entry = {
            "count": int(result.get("count") or 0),
            "failed": bool(result.get("failed")),
        }
        if result.get("suspect"):
            entry["suspect"] = True
            entry["failed"] = True
        clean[str(key)] = entry

    runs = []
    for run in raw_runs:
        if isinstance(run, dict) and run.get("date") != day:
            kept = {"date": run.get("date"), "results": run.get("results") or {}}
            if run.get("scanned_at"):
                kept["scanned_at"] = run.get("scanned_at")
            runs.append(kept)
    current = {"date": day, "results": clean}
    if scanned_at:
        current["scanned_at"] = str(scanned_at)
    runs.append(current)
    runs.sort(key=lambda run: run.get("date") or "")
    runs = runs[-MAX_RUNS:]

    baseline = {}
    for key, info in (state.get("baseline") or {}).items():
        if isinstance(info, dict) and info.get("date") and int(info.get("count") or 0) > 0:
            baseline[str(key)] = {"date": str(info["date"]), "count": int(info["count"])}
    for key, result in clean.items():
        if _good(result):
            baseline[key] = {"date": day, "count": result["count"]}
    return {"runs": runs, "baseline": baseline}


def broken_store_warnings(state):
    """Warnings for keys that are bad two runs in a row after a real baseline."""
    if not isinstance(state, dict):
        return []
    runs = [run for run in (state.get("runs") or []) if isinstance(run, dict) and run.get("date")]
    runs.sort(key=lambda run: run["date"])
    baseline = state.get("baseline") if isinstance(state.get("baseline"), dict) else {}
    keys = set(baseline)
    for run in runs:
        results = run.get("results") or {}
        if isinstance(results, dict):
            keys.update(results)
    warnings = []
    for key in sorted(keys):
        series = []
        for run in runs:
            results = run.get("results") or {}
            if isinstance(results, dict) and key in results and isinstance(results[key], dict):
                series.append((run["date"], results[key]))
        if len(series) < ALERT_STREAK:
            continue
        (older_day, older), (newer_day, newer) = series[-2], series[-1]
        if not (_bad(older) and _bad(newer)):
            continue
        base = baseline.get(key)
        if not (isinstance(base, dict) and int(base.get("count") or 0) > 0):
            positives = [(day, result) for day, result in series[:-2] if _good(result)]
            if not positives:
                continue
            day, result = positives[-1]
            base = {"date": day, "count": int(result.get("count") or 0)}
        if str(base.get("date") or "") >= older_day:
            continue
        try:
            store, part = split_key(key)
        except ValueError:
            continue
        warnings.append(
            {
                "key": key,
                "store": store,
                "part": part,
                "kind": _kind(older, newer),
                "dates": [older_day, newer_day],
                "last_positive_date": str(base.get("date")),
                "last_positive_count": int(base.get("count") or 0),
            }
        )
    return warnings


def warning_text(warning):
    """One sentence for the HTML report and the email."""
    store = warning.get("store") or "Unknown"
    part = warning.get("part") or "items"
    dates = " and ".join(warning.get("dates") or [])
    kind = warning.get("kind")
    if kind == "suspect":
        sentence = f"{store} returned no items in any category"
        if dates:
            sentence += f" on {dates[0]}"
        sentence += "."
        last = warning.get("last_positive_date")
        count = warning.get("last_positive_count")
        if last and count:
            sentence += f" Last good run on {last} had {count} items."
        sentence += " Previous listings were kept."
        return sentence
    if kind == "error":
        problem = "failed to scrape"
    elif kind == "empty":
        problem = "came back with no items"
    else:
        problem = "failed to scrape or came back with no items"
    sentence = f"{store} {part} {problem} two runs in a row ({dates})."
    last = warning.get("last_positive_date")
    count = warning.get("last_positive_count")
    if last and count:
        sentence += f" Last good run on {last} had {count} items."
    return sentence


TWO_RUN_BLURB = (
    "These categories usually have sale items. The last two runs came back empty or failed. "
    "A single empty run does not raise this warning."
)
SUSPECT_BLURB = (
    "A store that normally has sale items came back empty in every category. "
    "This run is marked suspect. Previous listings were kept, and the store card stays on the report."
)


def warnings_blurb(warnings, email=False):
    """Intro line above the warning list. Suspect stores do not wait for a second run."""
    kinds = set()
    for warning in warnings or []:
        if isinstance(warning, dict) and warning.get("kind"):
            kinds.add(warning["kind"])
    if kinds and kinds <= {"suspect"}:
        return SUSPECT_BLURB
    text = TWO_RUN_BLURB
    if email:
        text = text.replace("raise this warning", "send this warning")
    if "suspect" in kinds:
        return f"{SUSPECT_BLURB} {text}"
    return text


def empty_store_keys(current_data, failed_keys, health):
    """Keys to fail when a store that normally has items returned nothing.

    One empty category is left alone (bearings are often empty). Every
    category empty or failed, after a baseline with items, is a suspect store.
    """
    baseline = {}
    if isinstance(health, dict) and isinstance(health.get("baseline"), dict):
        baseline = health["baseline"]
    by_store = {}
    for key, items in (current_data or {}).items():
        store = str(key).rsplit("_", 1)[0]
        by_store.setdefault(store, []).append((str(key), items))
    failed = {str(key) for key in (failed_keys or [])}
    flagged = []
    for store, parts in by_store.items():
        got_items = False
        for key, items in parts:
            if key in failed or items is None:
                continue
            if isinstance(items, list) and items:
                got_items = True
                break
        if got_items:
            continue
        normal = 0
        for bkey, info in baseline.items():
            if str(bkey).rsplit("_", 1)[0] != store or not isinstance(info, dict):
                continue
            normal += int(info.get("count") or 0)
        if normal <= 0:
            continue
        flagged.extend(key for key, _ in parts)
    return flagged


def suspect_store_warnings(suspect_keys, health, day=None):
    """One warning per store that came back empty across every category."""
    stores = []
    for key in suspect_keys or []:
        store = str(key).rsplit("_", 1)[0]
        if store not in stores:
            stores.append(store)
    baseline = {}
    if isinstance(health, dict) and isinstance(health.get("baseline"), dict):
        baseline = health["baseline"]
    warnings = []
    for store in stores:
        total = 0
        last = ""
        for bkey, info in baseline.items():
            if str(bkey).rsplit("_", 1)[0] != store or not isinstance(info, dict):
                continue
            total += int(info.get("count") or 0)
            date = str(info.get("date") or "")
            if date > last:
                last = date
        warnings.append(
            {
                "key": store,
                "store": store,
                "part": "all categories",
                "kind": "suspect",
                "dates": [str(day)] if day else [],
                "last_positive_date": last,
                "last_positive_count": total,
            }
        )
    return warnings


def results_from_run(current_data, failed_keys, suspect_keys=None):
    """Counts for health. A failed key is bad even if previous rows were kept."""
    failed = {str(key) for key in (failed_keys or [])}
    suspect = {str(key) for key in (suspect_keys or [])}
    failed |= suspect
    results = {}
    for key, items in (current_data or {}).items():
        key = str(key)
        is_failed = key in failed
        count = 0 if is_failed or not isinstance(items, list) else len(items)
        entry = {"count": count, "failed": is_failed}
        if key in suspect:
            entry["suspect"] = True
        results[key] = entry
    for key in failed:
        entry = {"count": 0, "failed": True}
        if key in suspect:
            entry["suspect"] = True
        results.setdefault(key, entry)
    return results


def load_state(path=HEALTH_PATH):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except FileNotFoundError:
        return empty_state()
    except (OSError, json.JSONDecodeError) as exc:
        logger.error("Could not load scrape health (starting fresh): %s", exc)
        return empty_state()
    if not isinstance(data, dict):
        logger.error("Scrape health was not an object; starting fresh")
        return empty_state()
    return data


def state_json(state):
    return json.dumps(state or empty_state(), indent=2) + "\n"
