"""Broken-store detection: two bad runs, then recovery. No network."""

import datetime
import unittest

from health import (
    MAX_RUNS,
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


if __name__ == "__main__":
    unittest.main()
