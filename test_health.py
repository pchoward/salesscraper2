"""Broken-store detection: two bad runs, then recovery. No network."""

import datetime
import unittest

from health import (
    MAX_RUNS,
    broken_store_warnings,
    record_run,
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
        self.assertEqual(len(warnings), 1)
        self.assertEqual(warnings[0]["last_positive_count"], 5)

    def test_workflow_commits_health_file(self):
        with open(".github/workflows/scrape.yml", encoding="utf-8") as handle:
            text = handle.read()
        self.assertIn("scrape_health.json", text)
        self.assertIn("price_history.json", text)


if __name__ == "__main__":
    unittest.main()
