"""Price-history chart windows and stock/price markers."""

import datetime
import unittest

from charts import CHART_NOTE, chart_windows, listing_series, markers_from_prices


def _entry(prices, low=None, low_date=None, store="Zumiez"):
    days = sorted(prices)
    lowest = min(prices.values()) if low is None else low
    return {
        "name": "Baker",
        "store": store,
        "part": "Decks",
        "first_seen": days[0],
        "last_seen": days[-1],
        "observation_count": len(prices),
        "all_time_low": lowest,
        "all_time_low_date": low_date or min(day for day, price in prices.items() if price == min(prices.values())),
        "prices": prices,
    }


class ChartTests(unittest.TestCase):
    def test_price_reduction_and_gap_markers(self):
        prices = {
            "2026-09-01": 70.0,
            "2026-09-02": 70.0,
            "2026-09-04": 60.0,
            "2026-09-10": 55.0,
        }
        kinds = [(marker["kind"], marker["date"]) for marker in markers_from_prices(prices)]
        self.assertIn(("drop", "2026-09-04"), kinds)
        self.assertNotIn(("gone", "2026-09-02"), kinds)
        self.assertIn(("gone", "2026-09-04"), kinds)
        self.assertIn(("back", "2026-09-10"), kinds)
        drop = next(marker for marker in markers_from_prices(prices) if marker["kind"] == "drop")
        self.assertIn("10.00", drop["label"])

    def test_one_missing_day_is_not_a_stock_change(self):
        prices = {"2026-09-01": 40.0, "2026-09-03": 40.0}
        kinds = [marker["kind"] for marker in markers_from_prices(prices)]
        self.assertNotIn("gone", kinds)
        self.assertNotIn("back", kinds)

    def test_windows_clip_points_and_keep_an_older_low(self):
        today = datetime.date(2026, 9, 30)
        recent = {
            "2026-09-20": 50.0,
            "2026-09-28": 44.0,
            "2026-09-30": 44.0,
        }
        entry = _entry(recent, low=39.0, low_date="2026-06-01")
        series = listing_series(entry, "https://example.com/b", "Zumiez", "On sale")
        windows = chart_windows([series], today)
        self.assertEqual(set(windows), {"30", "90", "180"})
        self.assertEqual([point[0] for point in windows["30"][0]["points"]], list(recent))
        older = _entry(
            {"2026-07-01": 60.0, "2026-09-30": 44.0},
            low=39.0,
            low_date="2026-06-01",
        )
        wide = chart_windows(
            [listing_series(older, "https://example.com/b", "Zumiez", "On sale")],
            today,
        )
        self.assertEqual(wide["30"][0]["points"], [["2026-09-30", 44.0]])
        self.assertTrue(any(marker["kind"] == "low" and marker["date"] == "2026-06-01" for marker in wide["180"][0]["markers"]))
        self.assertFalse(any(marker["kind"] == "low" for marker in wide["30"][0]["markers"]))
        self.assertIn("90 days", CHART_NOTE)

    def test_several_stores_stay_separate_series(self):
        today = "2026-09-30"
        left = listing_series(
            _entry({"2026-09-01": 64.99, "2026-09-30": 64.99}, store="Zumiez"),
            "https://example.com/z",
            "Zumiez",
            "On sale",
        )
        right = listing_series(
            _entry({"2026-09-01": 70.0, "2026-09-30": 44.99}, store="SkateWarehouse"),
            "https://example.com/s",
            "SkateWarehouse",
            "On sale",
        )
        window = chart_windows([left, right], today)["90"]
        self.assertEqual([row["store"] for row in window], ["Zumiez", "SkateWarehouse"])
        self.assertEqual(window[1]["points"][-1][1], 44.99)
        self.assertTrue(any(marker["kind"] == "drop" for marker in window[1]["markers"]))


if __name__ == "__main__":
    unittest.main()
