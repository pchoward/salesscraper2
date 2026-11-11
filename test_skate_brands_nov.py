"""Wheel and truck brands the owner added on 2026-11-11."""

import unittest

from filters import filter_reason


class AddedSkateBrandsTests(unittest.TestCase):
    def test_added_wheels(self):
        for name in ("Opera SOS Echo Classic 101a Wheels 52mm", "Orbs Specters Swirls 99a Wheels",
                     "Satori Illuminating Slim 101a Wheels"):
            self.assertIsNone(filter_reason(name, "Wheels", "", "21.50", "36.00"), name)

    def test_added_trucks(self):
        for name in ("Bullet Standard Truck Silver", "Krux K5 DLK Truck Polished"):
            self.assertIsNone(filter_reason(name, "Trucks", "", "10.75", "18.00"), name)

    def test_others_still_out(self):
        self.assertEqual(filter_reason("Ruckus Mid Trucks", "Trucks", "", "11.25", "18.99"), "truck brand not allowed")
        self.assertEqual(filter_reason("Slime Balls Kendall 99a Wheels", "Wheels", "", "20", "40"), "wheel brand not allowed")


if __name__ == "__main__":
    unittest.main()
