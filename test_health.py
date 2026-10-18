"""Broken-store detection: two bad runs, then recovery. No network."""

import datetime
import json
import unittest

from health import (
    MAX_RUNS,
    COMPLETENESS_WINDOW,
    assess_run,
    rolling_baseline,
    state_json,
    STALE_AFTER_HOURS,
    baseline_conflicts,
    broken_store_warnings,
    conflict_text,
    empty_store_keys,
    failed_keys_on,
    record_run,
    results_from_run,
    scan_freshness,
    suspect_store_warnings,
    warning_text,
)

DECK = "Zumiez_Decks"
BEARINGS = "Zumiez_Bearings"


def _ok(count):
    return {"count": count, "failed": False}


def _empty():
    return {"count": 0, "failed": False}


def _failed():
    return {"count": 0, "failed": True}


def _run(state, day, **keys):
    return record_run(state, day, keys)


class BrokenStoreTests(unittest.TestCase):
    def test_one_empty_run_does_not_warn(self):
        state = {"runs": [], "baseline": {}}
        state = _run(state, "2026-09-28", **{DECK: _ok(12), BEARINGS: _empty()})
        state = _run(state, "2026-09-29", **{DECK: _empty(), BEARINGS: _empty()})
        self.assertEqual(broken_store_warnings(state), [])

    def test_two_empty_runs_warn_and_recovery_clears_it(self):
        state = {"runs": [], "baseline": {}}
        state = _run(state, "2026-09-28", **{DECK: _ok(12)})
        state = _run(state, "2026-09-29", **{DECK: _empty()})
        state = _run(state, "2026-09-30", **{DECK: _empty()})
        warnings = broken_store_warnings(state)
        self.assertEqual(len(warnings), 1)
        warning = warnings[0]
        self.assertEqual(warning["key"], DECK)
        self.assertEqual(warning["kind"], "empty")
        self.assertEqual(warning["dates"], ["2026-09-29", "2026-09-30"])
        self.assertEqual(warning["last_positive_count"], 12)
        self.assertEqual(warning["last_positive_date"], "2026-09-28")
        text = warning_text(warning)
        self.assertIn("Zumiez Decks", text)
        self.assertIn("came back with no items", text)
        self.assertIn("two runs in a row", text)

        state = _run(state, "2026-10-01", **{DECK: _ok(4)})
        self.assertEqual(broken_store_warnings(state), [])
        self.assertEqual(state["baseline"][DECK]["count"], 4)
        self.assertEqual(state["baseline"][DECK]["date"], "2026-10-01")

    def test_two_errors_and_a_mixed_streak(self):
        state = {"runs": [], "baseline": {}}
        state = _run(state, "2026-09-28", **{DECK: _ok(9)})
        state = _run(state, "2026-09-29", **{DECK: _failed()})
        state = _run(state, "2026-09-30", **{DECK: _failed()})
        warnings = broken_store_warnings(state)
        self.assertEqual(warnings[0]["kind"], "error")
        self.assertIn("failed to scrape", warning_text(warnings[0]))

        state = _run(state, "2026-10-01", **{DECK: _empty()})
        self.assertEqual(broken_store_warnings(state)[0]["kind"], "mixed")

    def test_always_empty_category_does_not_warn(self):
        state = {"runs": [], "baseline": {}}
        for offset in range(4):
            day = (datetime.date(2026, 9, 27) + datetime.timedelta(days=offset)).isoformat()
            state = _run(state, day, **{BEARINGS: _empty(), DECK: _ok(3)})
        keys = {warning["key"] for warning in broken_store_warnings(state)}
        self.assertNotIn(BEARINGS, keys)
        self.assertNotIn(BEARINGS, state["baseline"])

    def test_same_day_rerun_does_not_count_twice(self):
        state = {"runs": [], "baseline": {}}
        state = _run(state, "2026-09-28", **{DECK: _ok(12)})
        state = _run(state, "2026-09-29", **{DECK: _failed()})
        state = _run(state, "2026-09-29", **{DECK: _failed()})
        self.assertEqual(len(state["runs"]), 2)
        self.assertEqual(broken_store_warnings(state), [])
        state = _run(state, "2026-09-30", **{DECK: _empty()})
        self.assertEqual(len(broken_store_warnings(state)), 1)

    def test_baseline_survives_after_old_runs_roll_off(self):
        state = {"runs": [], "baseline": {}}
        state = _run(state, "2026-01-01", **{DECK: _ok(5)})
        for offset in range(1, MAX_RUNS + 5):
            day = (datetime.date(2026, 1, 1) + datetime.timedelta(days=offset)).isoformat()
            state = _run(state, day, **{DECK: _empty()})
        self.assertEqual(len(state["runs"]), MAX_RUNS)
        self.assertEqual(state["baseline"][DECK]["date"], "2026-01-01")
        warnings = broken_store_warnings(state)
        self.assertEqual(warnings, [])
        self.assertEqual(state["baseline"][DECK]["count"], 5)

    def test_low_median_and_mostly_empty_do_not_warn(self):
        state = {"runs": [], "baseline": {}}
        for offset in range(6):
            day = (datetime.date(2026, 10, 1) + datetime.timedelta(days=offset)).isoformat()
            state = _run(state, day, **{BEARINGS: _ok(1), DECK: _ok(40)})
        state = _run(state, "2026-10-07", **{BEARINGS: _empty(), DECK: _empty()})
        state = _run(state, "2026-10-08", **{BEARINGS: _empty(), DECK: _empty()})
        keys = {warning["key"] for warning in broken_store_warnings(state)}
        self.assertNotIn(BEARINGS, keys)
        self.assertIn(DECK, keys)

        quiet = {"runs": [], "baseline": {}}
        for offset in range(8):
            day = (datetime.date(2026, 10, 1) + datetime.timedelta(days=offset)).isoformat()
            quiet = _run(quiet, day, **{BEARINGS: _empty()})
        quiet = _run(quiet, "2026-10-09", **{BEARINGS: _ok(20)})
        quiet = _run(quiet, "2026-10-10", **{BEARINGS: _empty()})
        quiet = _run(quiet, "2026-10-11", **{BEARINGS: _empty()})
        self.assertEqual(broken_store_warnings(quiet), [])

    def test_failed_fetch_on_a_quiet_category_still_warns(self):
        state = {"runs": [], "baseline": {}}
        state = _run(state, "2026-10-01", **{BEARINGS: _empty()})
        state = _run(state, "2026-10-02", **{BEARINGS: _failed()})
        state = _run(state, "2026-10-03", **{BEARINGS: _failed()})
        warnings = broken_store_warnings(state)
        self.assertEqual(len(warnings), 1)
        self.assertEqual(warnings[0]["key"], BEARINGS)
        self.assertEqual(warnings[0]["kind"], "error")
        self.assertIn("failed to scrape", warning_text(warnings[0]))

    def test_same_day_rerun_drops_a_replaced_baseline(self):
        state = {"runs": [], "baseline": {}}
        state = _run(state, "2026-10-11", **{BEARINGS: _ok(1)})
        self.assertEqual(state["baseline"][BEARINGS]["count"], 1)
        state = _run(state, "2026-10-11", **{BEARINGS: _empty()})
        self.assertNotIn(BEARINGS, state["baseline"])
        self.assertEqual(state["runs"][-1]["results"][BEARINGS]["count"], 0)
        self.assertEqual(len(state["runs"]), 1)
        stale = {
            "runs": [{"date": "2026-10-11", "results": {BEARINGS: _empty()}}],
            "baseline": {BEARINGS: {"date": "2026-10-11", "count": 1}},
        }
        stale = _run(stale, "2026-10-14", **{BEARINGS: _empty(), DECK: _ok(10)})
        self.assertNotIn(BEARINGS, stale["baseline"])
        self.assertEqual(stale["baseline"][DECK]["count"], 10)

    def test_stale_baseline_is_not_a_last_good_run(self):
        state = {
            "runs": [
                {"date": "2026-10-11", "results": {BEARINGS: _empty()}},
                {"date": "2026-10-13", "results": {BEARINGS: _empty()}},
                {"date": "2026-10-14", "results": {BEARINGS: _empty()}},
            ],
            "baseline": {BEARINGS: {"date": "2026-10-11", "count": 1}},
        }
        self.assertEqual(broken_store_warnings(state), [])
        conflicts = baseline_conflicts(state)
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0]["baseline_count"], 1)
        self.assertEqual(conflicts[0]["recorded_count"], 0)
        text = conflict_text(conflicts[0])
        self.assertIn("Zumiez Bearings", text)
        self.assertIn("2026-10-11", text)
        self.assertIn("1 item", text)
        self.assertIn("recorded 0", text)
        self.assertNotIn("1 items", text)

    def test_whole_store_empty_is_suspect_on_the_first_run(self):
        health = {
            "runs": [],
            "baseline": {
                "Zumiez_Decks": {"date": "2026-10-01", "count": 11},
                "Zumiez_Wheels": {"date": "2026-10-01", "count": 5},
                "Zumiez_Trucks": {"date": "2026-10-01", "count": 11},
            },
        }
        current = {
            "Zumiez_Decks": [],
            "Zumiez_Wheels": [],
            "Zumiez_Trucks": [],
            "Zumiez_Bearings": [],
            "CCS_Decks": [{"name": "kept"}],
            "CCS_Wheels": [],
        }
        flagged = empty_store_keys(current, set(), health)
        self.assertEqual(
            set(flagged),
            {"Zumiez_Decks", "Zumiez_Wheels", "Zumiez_Trucks", "Zumiez_Bearings"},
        )
        self.assertNotIn("CCS_Decks", flagged)
        self.assertNotIn("CCS_Wheels", flagged)
        warnings = suspect_store_warnings(flagged, health, "2026-10-02")
        self.assertEqual(len(warnings), 1)
        self.assertEqual(warnings[0]["kind"], "suspect")
        self.assertEqual(warnings[0]["store"], "Zumiez")
        self.assertEqual(warnings[0]["last_positive_count"], 27)
        text = warning_text(warnings[0])
        self.assertIn("no items in any category", text)
        self.assertIn("2026-10-01", text)
        self.assertIn("27", text)
        self.assertIn("retry the affected categories", text)
        results = results_from_run(current, set(), flagged)
        state = record_run(health, "2026-10-02", results)
        self.assertTrue(state["runs"][-1]["results"]["Zumiez_Decks"]["suspect"])
        self.assertTrue(state["runs"][-1]["results"]["Zumiez_Decks"]["failed"])
        self.assertEqual(state["runs"][-1]["results"]["Zumiez_Decks"]["count"], 0)
        self.assertFalse(state["runs"][-1]["results"]["CCS_Decks"]["failed"])
        self.assertEqual(state["baseline"]["Zumiez_Decks"]["count"], 11)

    def test_one_empty_category_does_not_flag_the_store(self):
        health = {"runs": [], "baseline": {"Zumiez_Decks": {"date": "2026-10-01", "count": 11}}}
        current = {"Zumiez_Decks": [{"name": "kept"}], "Zumiez_Bearings": []}
        self.assertEqual(empty_store_keys(current, set(), health), [])

    def test_new_store_with_no_baseline_is_not_suspect(self):
        current = {"Skate Deluxe_Decks": [], "Skate Deluxe_Wheels": []}
        self.assertEqual(empty_store_keys(current, set(), {"runs": [], "baseline": {}}), [])

    def test_scan_is_stale_after_36_hours_and_names_failed_keys(self):
        now = datetime.datetime(2026, 10, 2, 12, 0, tzinfo=datetime.timezone.utc)
        fresh = scan_freshness("2026-10-02T10:00:00+00:00", now=now)
        self.assertFalse(fresh["stale"])
        stale = scan_freshness("2026-09-30T12:00:00+00:00", now=now, failed_keys=["Zumiez_Decks"])
        self.assertTrue(stale["stale"])
        self.assertGreater(stale["hours"], STALE_AFTER_HOURS)
        self.assertEqual(stale["failed"], ["Zumiez_Decks"])
        state = {
            "runs": [
                {
                    "date": "2026-10-02",
                    "results": {"Zumiez_Decks": {"count": 0, "failed": True}, "CCS_Decks": {"count": 2, "failed": False}},
                }
            ]
        }
        self.assertEqual(failed_keys_on(state, "2026-10-02"), ["Zumiez_Decks"])
        self.assertEqual(failed_keys_on(state, "2026-10-01"), [])

    def test_workflow_commits_health_file(self):
        with open(".github/workflows/scrape.yml", encoding="utf-8") as handle:
            text = handle.read()
        self.assertIn("scrape_health.json", text)
        self.assertIn("price_history.json", text)


class CompletenessTests(unittest.TestCase):
    def history(self, counts, key=DECK):
        state = {"runs": [], "baseline": {}}
        for offset, count in enumerate(counts):
            day = (datetime.date(2026, 9, 1) + datetime.timedelta(days=offset)).isoformat()
            state = record_run(state, day, {key: _ok(count)})
        return state

    def assess(self, state, count, key=DECK, day="2026-10-01", failed=()):
        items = [{} for _ in range(count)] if count is not None else None
        return assess_run({key: items}, failed, state, day)[key]

    def test_normal_fluctuations_trends_growth_and_variable_inventory(self):
        for counts, actual in [([100, 95, 105, 98], 85), ([100, 95, 90, 85, 80, 75], 70),
                               ([100, 100, 100, 500], 100), ([30, 100, 170, 25, 110], 40),
                               ([0, 0, 8, 0], 0), ([2, 3, 2, 3], 0)]:
            with self.subTest(counts=counts, actual=actual):
                result = self.assess(self.history(counts), actual)
                self.assertFalse(result["failed"])
                self.assertEqual(result["diagnostics"]["reason"], "normal_variation")

    def test_partial_and_empty_category_drops_have_diagnostics_and_immediate_warnings(self):
        state = self.history([100, 98, 102, 100])
        for actual, reason in [(20, "partial_catalog_drop"), (0, "empty_catalog_drop")]:
            with self.subTest(actual=actual):
                result = self.assess(state, actual)
                self.assertTrue(result["suspect"])
                self.assertTrue(result["failed"])
                self.assertEqual(result["count"], 0)  # legacy safety flag/count
                diagnostic = result["diagnostics"]
                self.assertEqual(diagnostic["expected_count"], 100)
                self.assertEqual(diagnostic["actual_count"], actual)
                self.assertEqual(diagnostic["percentage_change"], actual - 100)
                self.assertEqual(diagnostic["reason"], reason)
                saved = record_run(state, "2026-10-01", {DECK: result})
                warning, = broken_store_warnings(saved)
                self.assertEqual(warning["kind"], "incomplete")
                self.assertEqual(warning["part"], "Decks")
                text = warning_text(warning)
                for expected in ["Zumiez Decks", "expected about 100", str(actual), "pagination", "retry", "Previous listings were kept"]:
                    self.assertIn(expected, text)
                self.assertEqual(saved["baseline"][DECK]["count"], 100)

    def test_relative_and_absolute_thresholds_and_warmup(self):
        self.assertFalse(self.assess(self.history([100, 100]), 1)["failed"])
        self.assertTrue(self.assess(self.history([10, 10, 10]), 5)["failed"])
        self.assertFalse(self.assess(self.history([8, 8, 8]), 4)["failed"])
        self.assertFalse(self.assess(self.history([100, 100, 100]), 51)["failed"])
        self.assertTrue(self.assess(self.history([100, 100, 100]), 50)["failed"])

    def test_explicit_failure_records_received_count_without_learning_from_it(self):
        state = self.history([100, 100, 100])
        for actual in [None, 10]:
            result = self.assess(state, actual, failed={DECK})
            self.assertTrue(result["failed"])
            self.assertEqual(result["diagnostics"]["actual_count"], actual or 0)
            self.assertEqual(result["diagnostics"]["reason"], "scrape_failed")
            recorded = record_run(state, "2026-10-01", {DECK: result})
            warning, = broken_store_warnings(recorded)
            self.assertEqual(warning["kind"], "scan_failed")
            self.assertIn("retry the category", warning_text(warning))
            self.assertEqual(rolling_baseline(recorded, DECK, "2026-10-02")["expected_count"], 100)

    def test_baselines_are_independent_per_store_and_category(self):
        state = self.history([100, 100, 100])
        for offset in range(3):
            day = f"2026-09-{offset + 4:02}"
            state = record_run(state, day, {"CCS_Decks": _ok(20), "Zumiez_Wheels": _ok(10)})
        results = assess_run({DECK: [{}] * 20, "CCS_Decks": [{}] * 20, "Zumiez_Wheels": [{}] * 10}, set(), state, "2026-10-01")
        self.assertTrue(results[DECK]["failed"])
        self.assertFalse(results["CCS_Decks"]["failed"])
        self.assertFalse(results["Zumiez_Wheels"]["failed"])

    def test_historical_files_migrate_and_failed_or_suspect_rows_are_excluded(self):
        state = self.history([100, 100, 100])
        state.pop("completeness_baseline")
        state["runs"].extend([
            {"date": "2026-09-04", "results": {DECK: {"count": 2, "failed": True}}},
            {"date": "2026-09-05", "results": {DECK: {"count": 1, "suspect": True, "failed": False}}},
        ])
        original = json.loads(state_json(state))
        baseline = rolling_baseline(state, DECK, "2026-10-01")
        self.assertEqual(baseline["expected_count"], 100)
        self.assertEqual(baseline["baseline_samples"], 3)
        self.assertEqual(state, original)  # read-only assessment
        result = self.assess(state, 20)
        saved = record_run(state, "2026-10-01", {DECK: result})
        restored = json.loads(state_json(saved))
        self.assertEqual(restored["runs"][-1]["results"][DECK]["diagnostics"], result["diagnostics"])
        self.assertEqual(len(restored["completeness_baseline"][DECK]), 3)

    def test_same_day_and_future_runs_cannot_contaminate_the_baseline(self):
        state = self.history([100, 100, 100])
        state = record_run(state, "2026-10-01", {DECK: _ok(1000)})
        state = record_run(state, "2026-10-02", {DECK: _ok(2000)})
        result = self.assess(state, 20)
        self.assertEqual(result["diagnostics"]["expected_count"], 100)
        self.assertEqual(result["diagnostics"]["baseline_samples"], 3)
        self.assertTrue(result["failed"])

    def test_repeated_failures_do_not_erase_baseline_and_recovery_clears_warning(self):
        state = self.history([100] * 20)
        self.assertEqual(len(state["completeness_baseline"][DECK]), COMPLETENESS_WINDOW)
        for offset in range(MAX_RUNS + 3):
            day = (datetime.date(2026, 10, 1) + datetime.timedelta(days=offset)).isoformat()
            result = self.assess(state, 20, day=day)
            self.assertTrue(result["failed"])
            state = record_run(state, day, {DECK: result})
        self.assertEqual(rolling_baseline(state, DECK, "2026-12-01")["expected_count"], 100)
        recovered = self.assess(state, 98, day="2026-12-01")
        self.assertFalse(recovered["failed"])
        state = record_run(state, "2026-12-01", {DECK: recovered})
        self.assertEqual(broken_store_warnings(state), [])
        self.assertEqual(state["baseline"][DECK]["count"], 98)

    def test_same_day_recovery_replaces_the_failure_and_clears_warning(self):
        state = self.history([100, 100, 100])
        state = record_run(state, "2026-10-01", {DECK: self.assess(state, 20)})
        self.assertEqual(len(broken_store_warnings(state)), 1)
        state = record_run(state, "2026-10-01", {DECK: self.assess(state, 99)})
        self.assertEqual(len(state["runs"]), 4)
        self.assertEqual(broken_store_warnings(state), [])
        self.assertEqual(state["completeness_baseline"][DECK][-1], {"date": "2026-10-01", "count": 99})

    def test_same_day_failed_replacement_invalidates_a_saved_success(self):
        state = self.history([100, 100, 100])
        state = record_run(state, "2026-10-01", {DECK: _ok(200)})
        state = record_run(state, "2026-10-01", {DECK: _failed()})
        self.assertNotIn("2026-10-01", [s["date"] for s in state["completeness_baseline"][DECK]])
        self.assertEqual(rolling_baseline(state, DECK, "2026-10-02")["baseline_samples"], 3)


if __name__ == "__main__":
    unittest.main()
