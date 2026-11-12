"""Nothing under $2 is listed (owner, 2026-11-12: clear clutter)."""

import unittest

import sports
from filters import filter_reason, item_passes_filters


class MinimumPriceTests(unittest.TestCase):
    def test_under_two_dollars_left_out(self):
        self.assertEqual(filter_reason("Independent Stage 11 Truck", "Trucks", "", "1.50", "3.00"), "under $2")
        self.assertEqual(filter_reason("Independent Stage 11 Truck", "Trucks", "", "1.99", None), "under $2")
        self.assertIsNone(filter_reason("Independent Stage 11 Truck", "Trucks", "", "2.00", "4.00"))

    def test_other_sports(self):
        spacer = {"name": "Wheels Manufacturing Aluminum Headset Spacer - 1\" x 2mm - Black", "part": "Cockpit",
                  "url": "https://cambriabike.com/products/spacer", "price_new": "0.50", "price_old": "1.25",
                  "store": "Cambria", "product_type": "Headsets"}
        with sports.MTB.active():
            self.assertFalse(item_passes_filters(spacer))
            self.assertTrue(item_passes_filters(dict(spacer, price_new="2.50", price_old="5.00")))


if __name__ == "__main__":
    unittest.main()
