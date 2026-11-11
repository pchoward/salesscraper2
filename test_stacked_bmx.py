"""Stacked BMX (2026-11-11): Shopify, whole catalog, its own product types."""

import unittest

from sports.bmx import stores
from stores import shopify


class StackedBmxTests(unittest.TestCase):
    def part(self, kind, title="Thing"):
        return shopify.part_for(stores.STACKED, kind, title)

    def test_types(self):
        cases = {"Freestyle BMX Bikes": "Bikes", "Big BMX & Wheelie Bikes": "Bikes", "BMX Race Bikes": "Bikes",
                 "Brakes & accessories": "Braking", "Hubs & hub guards": "Wheel Parts",
                 "B.B. & crank bearings": "Drivetrain", "Protective Pads & Braces": "Protection",
                 "Seats": "Seating", "Handlebars": "Steering", "Frames": "Frames & Forks"}
        for kind, part in cases.items():
            self.assertEqual(self.part(kind), part, kind)

    def test_left_out(self):
        for kind in ("Electric Bikes", "City & Single-Speed Bikes", "Balance Bikes", "Kids Pedal Bikes",
                     "Tools", "Stickers", "T-Shirts"):
            self.assertIn(self.part(kind), (None, ""), kind)

    def test_registered(self):
        self.assertIn(stores.STACKED, stores.STORES)
        self.assertTrue(stores.STACKED.whole_site)


if __name__ == "__main__":
    unittest.main()
