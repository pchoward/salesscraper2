"""Sparkline color follows the latest change inside the selected window."""

import datetime
import json
import os
import unittest

from page import SPARK_COLOR, clip_daily_prices, sparkline_direction, sparkline_svg


# OJ Rojers Elite Hardline 101a wheels in price_history.json.
# The price fell to 24.77, then rose back to 34.98 on 2026-09-01 and stayed there.
# A 90-day window ending 2026-10-11 still sees that rise. A 30-day window does not.
OJ_WHEELS = "https://www.skatewarehouse.com/OJ_Rojers_Elite_Hardline_101a_Wheels/descpage-OJREHWH.html?color=WH"


def _last_change(points):
    if len(points) < 2:
        return "flat"
    last = points[-1][1]
    for _day, price in reversed(points[:-1]):
        if abs(price - last) > 0.001:
            return "down" if last < price else "up"
    return "flat"


class SparklineWindowTests(unittest.TestCase):
    def test_color_follows_the_latest_change_inside_the_window(self):
        prices = {
            "2026-07-13": 34.98,
            "2026-08-22": 24.77,
            "2026-09-01": 34.98,
            "2026-10-11": 34.98,
        }
        self.assertEqual(sparkline_direction(prices, days=90, end="2026-10-11"), "up")
        self.assertEqual(sparkline_direction(prices, days=30, end="2026-10-11"), "flat")
        risen = sparkline_svg(prices, days=90, end="2026-10-11")
        self.assertIn('data-direction="up"', risen)
        self.assertIn('stroke="%s"' % SPARK_COLOR["up"], risen)
        self.assertIn("<circle", risen)
        flat = sparkline_svg(prices, days=30, end="2026-10-11")
        self.assertIn('data-direction="flat"', flat)
        self.assertIn('fill="%s"' % SPARK_COLOR["flat"], flat)
        self.assertNotIn("stroke=", flat)

        dropped = {"2026-10-01": 50.0, "2026-10-05": 50.0, "2026-10-11": 40.0}
        self.assertEqual(sparkline_direction(dropped, days=30, end="2026-10-11"), "down")
        self.assertIn('stroke="%s"' % SPARK_COLOR["down"], sparkline_svg(dropped, days=30, end="2026-10-11"))

        # An older low outside the window must not turn a flat recent series green.
        outside = {"2026-01-01": 10.0, "2026-10-01": 40.0, "2026-10-11": 40.0}
        self.assertEqual(sparkline_direction(outside, days=30, end="2026-10-11"), "flat")
        self.assertEqual(sparkline_direction(outside, days=90, end="2026-10-11"), "flat")

    def test_price_history_file_uses_the_same_window(self):
        path = os.path.join(os.path.dirname(__file__), "price_history.json")
        with open(path) as handle:
            history = json.load(handle)
        entry = history.get(OJ_WHEELS) or {}
        prices = entry.get("prices") or {}
        if prices.get("2026-08-22") is not None and prices.get("2026-09-01") is not None:
            self.assertEqual(round(float(prices["2026-08-22"]), 2), 24.77)
            self.assertEqual(round(float(prices["2026-09-01"]), 2), 34.98)
            self.assertEqual(sparkline_direction(prices, days=90, end="2026-10-11"), "up")
            self.assertEqual(sparkline_direction(prices, days=30, end="2026-10-11"), "flat")

        differed = 0
        checked = 0
        for item in history.values():
            series = item.get("prices") or {}
            if len(series) < 2:
                continue
            end = max(str(day)[:10] for day in series)
            for days in (30, 90, 180):
                points = clip_daily_prices(series, days=days, end=end)
                self.assertEqual(sparkline_direction(series, days=days, end=end), _last_change(points))
                outside = [day for day, _price in points if day < (datetime.date.fromisoformat(end) - datetime.timedelta(days=days)).isoformat()]
                self.assertEqual(outside, [])
            if sparkline_direction(series, days=30, end=end) != sparkline_direction(series, days=90, end=end):
                differed += 1
            checked += 1
        self.assertGreater(checked, 100)
        self.assertGreater(differed, 0)


if __name__ == "__main__":
    unittest.main()
