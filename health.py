"""Per-store, per-part scrape counts, and broken-store warnings.

Each run records how many items came back for every store/part key, and
whether the fetch failed. The file stays small: the last 30 runs, plus a
baseline of the last time each key actually had items.

For historical rows without completeness diagnostics, a warning fires when
both of the last two recorded runs for a key are bad.
An empty streak warns only when that category usually has items: not empty
on most recent runs, and not a low median. A failed fetch still warns.
One empty category does not warn. A later run that returns items clears the
warning. Keys that have never had items stay quiet.

A same-day re-run replaces that day's count. A baseline is dropped when the
saved run on its own date is empty or failed, including when a later day is
recorded. Otherwise a one-item scrape that was corrected to zero still looks
like the last good run.

Completeness checks additionally compare raw counts with the last 14 successful
observations per category. At least three prior dates are required; a drop must
be at least half the median, at least five items, and outside normal variability.
New incomplete and failed scans warn immediately, and normal recovery clears
those warnings. Optional diagnostics and completeness_baseline fields extend historical files
without changing the existing count/failed or last-positive baseline fields.

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
# Successful observations are retained separately so repeated failures cannot
# roll the last healthy counts out of the baseline. Historical runs seed it.
COMPLETENESS_WINDOW = 14
COMPLETENESS_MIN_RUNS = 3
COMPLETENESS_MIN_DROP = 5
COMPLETENESS_DROP_FRACTION = 0.5
COMPLETENESS_MAD_MULTIPLIER = 3
ALERT_STREAK = 2
# Median item count below this is a normally small category. An empty streak
# there is not a drop. Failed fetches still warn.
MIN_TYPICAL_COUNT = 5
# The morning scrape is daily. A page older than a day and a half is stale.
STALE_AFTER_HOURS = 36


def empty_state():
    return {"runs": [], "baseline": {}}


def _good(result):
    return bool(result) and not result.get("failed") and not result.get("suspect") and int(result.get("count") or 0) > 0


def _bad(result):
    if not isinstance(result, dict):
        return True
    if result.get("failed") or result.get("suspect"):
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
        if isinstance(result.get("diagnostics"), dict):
            entry["diagnostics"] = dict(result["diagnostics"])
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
    recorded = {}
    for run in runs:
        for key, result in (run.get("results") or {}).items():
            if isinstance(result, dict):
                recorded.setdefault(key, {})[str(run.get("date") or "")] = result
    for key, info in list(baseline.items()):
        # A same-day re-run can replace a count of 1 with 0 and leave the old
        # baseline behind. If that day's saved run is not good, drop it.
        result = (recorded.get(key) or {}).get(str((info or {}).get("date") or ""))
        if isinstance(result, dict) and not _good(result):
            baseline.pop(key, None)
    sample_state = {"runs": runs, "completeness_baseline": state.get("completeness_baseline") or {}}
    sample_keys = set(clean) | set(baseline)
    if isinstance(sample_state["completeness_baseline"], dict):
        sample_keys.update(sample_state["completeness_baseline"])
    for run in runs:
        sample_keys.update(run.get("results") or {})
    completeness = {}
    for key in sorted(sample_keys):
        samples = _successful_samples(sample_state, key)
        if samples:
            completeness[key] = samples
    return {"runs": runs, "baseline": baseline, "completeness_baseline": completeness}


def _observed_counts(series):
    counts = []
    for _day, result in series:
        if result.get("failed") or result.get("suspect"):
            continue
        counts.append(int(result.get("count") or 0))
    return counts


def _median(values):
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2


def _successful_samples(state, key, before=None):
    """Merge additive saved samples with historical runs, one count per date.

    Runs take precedence, including a failed same-day replacement invalidating
    a saved success. Unknown/malformed observations are never baseline samples.
    """
    if not isinstance(state, dict):
        return []
    saved = state.get("completeness_baseline") or {}
    samples = saved.get(key, []) if isinstance(saved, dict) else []
    by_day = {}
    if isinstance(samples, list):
        for sample in samples:
            if not isinstance(sample, dict):
                continue
            try:
                day = datetime.date.fromisoformat(str(sample.get("date") or "")).isoformat()
                count = int(sample["count"])
            except (ValueError, TypeError, KeyError):
                continue
            if count >= 0:
                by_day[day] = count
    runs = state.get("runs") or []
    for run in runs if isinstance(runs, list) else []:
        if not isinstance(run, dict) or not isinstance(run.get("results"), dict):
            continue
        result = run["results"].get(key)
        if not isinstance(result, dict):
            continue
        try:
            day = datetime.date.fromisoformat(str(run.get("date") or "")).isoformat()
        except (ValueError, TypeError):
            continue
        by_day.pop(day, None)
        try:
            count = int(result["count"])
        except (ValueError, TypeError, KeyError):
            continue
        if count >= 0 and not result.get("failed") and not result.get("suspect"):
            by_day[day] = count
    return [
        {"date": day, "count": by_day[day]}
        for day in sorted(by_day) if before is None or day < str(before)
    ][-COMPLETENESS_WINDOW:]


def rolling_baseline(state, key, day):
    """Median and variability of successful scans strictly before this date."""
    samples = _successful_samples(state, key, before=day)
    counts = [sample["count"] for sample in samples]
    expected = _median(counts) if counts else None
    mad = _median([abs(count - expected) for count in counts]) if counts else None
    return {"expected_count": expected, "baseline_samples": len(counts),
            "median_absolute_deviation": mad}


def assess_run(current_data, failed_keys, health, day, suspect_keys=None):
    """Assess raw results before retention or first-miss rows inflate counts.

    A drop must be at least 50%, at least five items, and exceed three median
    absolute deviations. Small/variable categories and insufficient histories
    are left alone. Suspect scans use the existing failed-key safety path.
    """
    failed = set(failed_keys or [])
    whole_store = set(suspect_keys or [])
    results = {}
    for key in sorted(set(current_data or {}) | failed | whole_store):
        items = (current_data or {}).get(key)
        actual = len(items) if isinstance(items, list) else 0
        baseline = rolling_baseline(health, key, day)
        expected = baseline["expected_count"]
        change = round(100 * (actual - expected) / expected, 1) if expected else None
        suspect = key in whole_store
        is_failed = key in failed or not isinstance(items, list)
        reason = "normal_variation"
        if is_failed:
            reason = "scrape_failed"
        elif suspect:
            reason = "whole_store_empty"
        elif baseline["baseline_samples"] < COMPLETENESS_MIN_RUNS:
            reason = "insufficient_history"
        elif expected is not None and expected >= MIN_TYPICAL_COUNT:
            drop = expected - actual
            suspect = (drop >= COMPLETENESS_MIN_DROP
                       and drop >= expected * COMPLETENESS_DROP_FRACTION
                       and drop > COMPLETENESS_MAD_MULTIPLIER * baseline["median_absolute_deviation"])
            if suspect:
                reason = "partial_catalog_drop" if actual else "empty_catalog_drop"
        diagnostics = dict(baseline, actual_count=actual, percentage_change=change, reason=reason)
        entry = {"count": 0 if is_failed or suspect else actual,
                 "failed": bool(is_failed or suspect), "diagnostics": diagnostics}
        if suspect:
            entry["suspect"] = True
        results[key] = entry
    return results


def _completeness_warning(key, day, result):
    diagnostics = result.get("diagnostics")
    if not isinstance(diagnostics, dict):
        return None
    reason = diagnostics.get("reason")
    if reason not in {"partial_catalog_drop", "empty_catalog_drop", "scrape_failed"}:
        return None
    try:
        store, part = split_key(key)
    except ValueError:
        return None
    return dict(diagnostics, key=key, store=store, part=part, dates=[day],
                kind="scan_failed" if reason == "scrape_failed" else "incomplete")


def normally_populated(series):
    """Whether the runs before a two-run streak usually had items.

    Empty on most of those runs, or a low median, is a normally quiet
    category. A later empty scrape is not a drop.
    """
    prior = list(series or [])[:-ALERT_STREAK]
    counts = _observed_counts(prior)
    if not counts:
        return False
    empties = sum(1 for count in counts if count <= 0)
    if empties * 2 > len(counts):
        return False
    return _median(counts) >= MIN_TYPICAL_COUNT


def _agreed_positive(series, baseline, key):
    """Last recorded good run, ignoring a baseline that disagrees with that day."""
    for day, result in reversed(series or []):
        if _good(result):
            return {"date": day, "count": int(result.get("count") or 0)}
    base = baseline.get(key) if isinstance(baseline, dict) else None
    if not isinstance(base, dict) or int(base.get("count") or 0) <= 0:
        return None
    day = str(base.get("date") or "")
    recorded = {run_day: result for run_day, result in series or []}
    if day in recorded and not _good(recorded[day]):
        return None
    return {"date": day, "count": int(base.get("count") or 0)}


def broken_store_warnings(state):
    """Immediate diagnosed failures/drops, plus legacy two-run warnings."""
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
        if series:
            immediate = _completeness_warning(key, series[-1][0], series[-1][1])
            if immediate:
                warnings.append(immediate)
                continue
        if len(series) < ALERT_STREAK:
            continue
        (older_day, older), (newer_day, newer) = series[-2], series[-1]
        if not (_bad(older) and _bad(newer)):
            continue
        failed_streak = bool(older.get("failed") or newer.get("failed"))
        if not failed_streak and not normally_populated(series):
            continue
        base = _agreed_positive(series, baseline, key)
        if base and str(base.get("date") or "") >= older_day:
            base = None
        if not failed_streak and not base:
            continue
        if not base:
            base = {"date": "", "count": 0}
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
    if kind in {"incomplete", "scan_failed"}:
        actual = warning.get("actual_count", 0)
        expected = warning.get("expected_count")
        sentence = f"{store} {part}: "
        sentence += "scrape failed" if kind == "scan_failed" else "likely incomplete scrape"
        if dates:
            sentence += f" on {dates}"
        sentence += f"; received {actual} items"
        if expected is not None:
            sentence += f", expected about {expected:g}"
        change = warning.get("percentage_change")
        if change is not None:
            sentence += f" ({change:+g}%)"
        sentence += f". Reason: {warning.get('reason')}."
        sentence += " Previous listings were kept; missing-product tracking was skipped."
        sentence += " Check retailer availability, pagination, and fetch logs, then retry the category."
        return sentence
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
        sentence += " Check retailer availability, pagination, and fetch logs, then retry the affected categories."
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
        noun = "item" if int(count) == 1 else "items"
        sentence += f" Last good run on {last} had {count} {noun}."
    return sentence


def baseline_conflicts(state):
    """Baselines whose own day was saved as empty or failed.

    A same-day re-run can replace a count of 1 with 0 and leave the old
    baseline behind. That leftover is not a last good run.
    """
    if not isinstance(state, dict):
        return []
    by_key = {}
    for run in state.get("runs") or []:
        if not isinstance(run, dict):
            continue
        day = str(run.get("date") or "")
        results = run.get("results") or {}
        if not isinstance(results, dict):
            continue
        for key, result in results.items():
            if isinstance(result, dict):
                by_key.setdefault(str(key), {})[day] = result
    conflicts = []
    for key, info in sorted((state.get("baseline") or {}).items()):
        if not isinstance(info, dict):
            continue
        day = str(info.get("date") or "")
        count = int(info.get("count") or 0)
        recorded = (by_key.get(str(key)) or {}).get(day)
        if count <= 0 or not isinstance(recorded, dict) or _good(recorded):
            continue
        try:
            store, part = split_key(key)
        except ValueError:
            continue
        conflicts.append(
            {
                "key": str(key),
                "store": store,
                "part": part,
                "date": day,
                "baseline_count": count,
                "recorded_count": int(recorded.get("count") or 0),
            }
        )
    return conflicts


def conflict_text(conflict):
    """One sentence for a baseline that disagrees with the saved run."""
    store = conflict.get("store") or "Unknown"
    part = conflict.get("part") or "items"
    saved = int(conflict.get("baseline_count") or 0)
    recorded = int(conflict.get("recorded_count") or 0)
    saved_noun = "item" if saved == 1 else "items"
    return (
        f"{store} {part} is saved as {saved} {saved_noun} on {conflict.get('date')}, "
        f"but that day's run recorded {recorded}. That saved count is not a last good run."
    )


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
    if kinds & {"incomplete", "scan_failed"}:
        return (
            "Some retailer categories failed or returned unusually low counts compared with successful scans. "
            "Those scans are not evidence of discontinued products; review the affected categories and retry."
        )
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


def _parse_moment(value):
    if isinstance(value, datetime.datetime):
        moment = value
    else:
        text = str(value or "").strip()
        if not text:
            return None
        try:
            moment = datetime.datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            try:
                moment = datetime.datetime.strptime(text[:19], "%Y-%m-%d %H:%M:%S")
            except ValueError:
                return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=datetime.timezone.utc)
    return moment


def failed_keys_on(state, day):
    """Store/part keys marked failed on ``day`` in ``scrape_health.json``."""
    day = str(day or "")[:10]
    if not day or not isinstance(state, dict):
        return []
    found = []
    for run in state.get("runs") or []:
        if not isinstance(run, dict) or str(run.get("date") or "")[:10] != day:
            continue
        results = run.get("results") or {}
        if not isinstance(results, dict):
            continue
        for key, result in results.items():
            if isinstance(result, dict) and result.get("failed") and str(key) not in found:
                found.append(str(key))
    return found


def scan_freshness(generated_at, now=None, failed_keys=None):
    """Whether the published scan is stale or recorded a failed store/part.

    Stale means the scan timestamp is more than ``STALE_AFTER_HOURS`` before
    ``now``. An unparseable timestamp is not called stale.
    """
    moment = _parse_moment(generated_at)
    if now is None:
        now = datetime.datetime.now(datetime.timezone.utc)
    elif not isinstance(now, datetime.datetime):
        now = _parse_moment(now) or datetime.datetime.now(datetime.timezone.utc)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=datetime.timezone.utc)
    hours = None
    stale = False
    if moment is not None:
        hours = (now - moment).total_seconds() / 3600.0
        stale = hours > STALE_AFTER_HOURS
    failed = []
    for key in failed_keys or []:
        text = str(key)
        if text and text not in failed:
            failed.append(text)
    return {
        "stale": stale,
        "hours": None if hours is None else round(hours, 1),
        "failed": failed,
    }


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
