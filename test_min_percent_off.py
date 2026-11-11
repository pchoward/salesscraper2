"""Every listing is at least 5% off (owner, 2026-11-11; 10% from 2026-11-09), in every sport."""

import unittest

import sports
from filters import filter_reason, item_passes_filters


class MinimumMarkdownTests(unittest.TestCase):
    def test_skate_parts(self):
        self.assertEqual(filter_reason("Independent Stage 11 Truck", "Trucks", "", 97, 100), "3% off (< 5%)")
        self.assertIsNone(filter_reason("Independent Stage 11 Truck", "Trucks", "", 95, 100))
        self.assertIsNone(filter_reason("Independent Stage 11 Truck", "Trucks", "", 94, 100))

    def test_other_sports(self):
        bike = {"name": "Verde A/V Bike", "part": "Bikes", "url": "https://example.com/a",
                "price_new": "389.95", "price_old": "399.95", "store": "Albe's BMX"}
        with sports.BMX.active():
            self.assertFalse(item_passes_filters(bike))
            self.assertTrue(item_passes_filters(dict(bike, price_new="379.95")))  # 5% off
        crank = {"name": "Shimano XT M8100 Crankset", "part": "Drivetrain", "url": "https://example.com/c",
                 "price_new": "970", "price_old": "1000", "store": "Worldwide Cyclery", "product_type": "Cranksets"}
        with sports.MTB.active():
            self.assertFalse(item_passes_filters(crank))
            self.assertTrue(item_passes_filters(dict(crank, price_new="940")))  # 6% off

    def test_unknown_regular_price_left_to_other_rules(self):
        self.assertIsNone(filter_reason("Independent Stage 11 Truck", "Trucks", "", 97, None))
        self.assertIsNone(filter_reason("Independent Stage 11 Truck", "Trucks"))


if __name__ == "__main__":
    unittest.main()
