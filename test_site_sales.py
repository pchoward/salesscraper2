"""Site-wide sale detection and the Skate Warehouse seed."""

import datetime
import unittest

from site_sales import (
    SEEDS,
    SPIKE_MIN_EXTRA,
    SPIKE_MULTIPLIER,
    catalog_counts,
    describe_sales,
    empty_state,
    format_sale_line,
    is_spike,
    record_catalog,
)


def _days(start, count, amount):
    day = datetime.date.fromisoformat(start)
    rows = {}
    for offset in range(count):
        rows[(day + datetime.timedelta(days=offset)).isoformat()] = {"Zumiez": amount}
    return rows


class SiteSaleTests(unittest.TestCase):
    def test_seed_and_days_since(self):
        state = empty_state()
        self.assertEqual(state["stores"]["SkateWarehouse"]["last_sale"], SEEDS["SkateWarehouse"])
        self.assertIsNone(state["stores"]["Zumiez"]["last_sale"])
        rows = {row["store"]: row for row in describe_sales(state, "2026-09-30")}
        self.assertEqual(rows["SkateWarehouse"]["days"], 88)
        self.assertIn("88 days", format_sale_line(rows["SkateWarehouse"]))
        self.assertIn("2026-07-04", format_sale_line(rows["SkateWarehouse"]))
        self.assertIn("no site-wide sale", format_sale_line(rows["Zumiez"]))

    def test_threshold_needs_both_a_multiple_and_extra_items(self):
        baseline = [40] * 7
        self.assertTrue(is_spike(40 * SPIKE_MULTIPLIER, baseline))
        self.assertFalse(is_spike(40 * SPIKE_MULTIPLIER - 1, baseline))
        self.assertFalse(is_spike(baseline[0] + SPIKE_MIN_EXTRA, baseline))
        self.assertFalse(is_spike(200, [10] * 6))
        self.assertTrue(is_spike(40, [10] * 7))

    def test_later_spike_replaces_the_seed_and_does_not_move_backward(self):
        state = empty_state()
        state["daily"] = _days("2026-09-01", 8, 20)
        state["daily"]["2026-09-09"] = {"Zumiez": 80, "SkateWarehouse": 200}
        state = record_catalog(state, {}, today="2026-09-09", history=None)
        # record_catalog overwrites today from the empty catalog, so stage the spike as a past day.
        state = empty_state()
        state["daily"] = _days("2026-08-01", 10, 40)
        state["daily"]["2026-08-11"] = {"Zumiez": 140, "SkateWarehouse": 40}
        quiet = {"Zumiez_Decks": []}
        state = record_catalog(state, quiet, today="2026-08-12")
        self.assertEqual(state["stores"]["Zumiez"]["last_sale"], "2026-08-11")
        self.assertEqual(state["stores"]["Zumiez"]["source"], "detected")
        self.assertEqual(state["stores"]["SkateWarehouse"]["last_sale"], "2026-07-04")
        self.assertEqual(state["stores"]["SkateWarehouse"]["source"], "seed")

        state["daily"]["2026-06-01"] = {"SkateWarehouse": 500}
        state = record_catalog(state, quiet, today="2026-08-13")
        self.assertEqual(state["stores"]["SkateWarehouse"]["last_sale"], "2026-07-04")

    def test_flat_history_does_not_invent_a_sale(self):
        state = empty_state()
        for offset in range(20):
            day = (datetime.date(2026, 9, 1) + datetime.timedelta(days=offset)).isoformat()
            state["daily"][day] = {"SkateWarehouse": 80, "Tactics": 60, "Zumiez": 27, "CCS": 3}
        state = record_catalog(state, {}, today="2026-09-30")
        self.assertEqual(state["stores"]["SkateWarehouse"]["last_sale"], "2026-07-04")
        self.assertIsNone(state["stores"]["Tactics"]["last_sale"])

    def test_failed_store_is_not_counted(self):
        item = {
            "name": "Baker Team Deck 8.25",
            "url": "https://example.com/baker",
            "price_new": "40.00",
            "price_old": "70.00",
            "part": "Decks",
            "store": "Zumiez",
        }
        counts = catalog_counts(
            {"Zumiez_Decks": [item], "CCS_Decks": [item, item, item]},
            failed_keys={"CCS_Decks"},
        )
        self.assertEqual(counts, {"Zumiez": 1})

    def test_workflow_commits_the_site_sale_file(self):
        with open(".github/workflows/scrape.yml", "r", encoding="utf-8") as handle:
            text = handle.read()
        self.assertIn("site_sales.json", text)
        self.assertIn("price_history.json", text)
        self.assertIn("scrape_health.json", text)

    def test_bad_state_does_not_raise(self):
        state = record_catalog(["nope"], {}, today="2026-09-30")
        self.assertEqual(state["stores"]["SkateWarehouse"]["last_sale"], "2026-07-04")


if __name__ == "__main__":
    unittest.main()
