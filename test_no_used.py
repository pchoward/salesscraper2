"""Used gear stays out on every sport (owner, 2026-11-12)."""

import unittest

import sports
from filters import filter_reason, item_passes_filters


class NoUsedTests(unittest.TestCase):
    def test_used_listings_left_out_everywhere(self):
        item = {"name": "Atomic Hawx Ultra 110 S GW Ski Boots 2025 - Used", "part": "Boots",
                "url": "https://www.evo.com/products/hawx-used", "price_new": "72.00", "price_old": "399.99",
                "store": "evo"}
        with sports.SKI.active():
            self.assertFalse(item_passes_filters(item))
            self.assertTrue(item_passes_filters(dict(item, name="Atomic Hawx Ultra 110 S GW Ski Boots 2025")))
        for name in ("Shimano XT Crankset - Pre-Owned", "Fox 36 Fork (Refurbished)", "Second-Hand Sunday Primer"):
            self.assertEqual(filter_reason(name, "Decks", "", "10", "50"), "catalog scope: used", name)

    def test_demo_gear_is_not_used(self):
        with sports.SKI.active():
            self.assertIsNone(filter_reason("Nordica Enforcer 89 Mens Demo Skis 2026", "Skis", "", "300", "600"))


if __name__ == "__main__":
    unittest.main()
