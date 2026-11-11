"""Ski shops added 2026-11-11: Willis, The Pro Ski and Ride, Aspen, Skipro."""

import unittest

from sports.ski import stores
from stores import shopify


class SkiShopTests(unittest.TestCase):
    def part(self, product_type, title="Thing"):
        return shopify.part_for(stores.SKI_SHOPS[0], product_type, title)

    def test_types(self):
        cases = {"Womens Ski Boots": "Boots", "Mid Width Ski Boots": "Boots", "System Skis": "Skis",
                 "Flat Skis": "Skis", "Junior Skis": "Skis", "Ski Packages": "Skis", "Demo Skis": "Skis",
                 "Junior Ski Bindings": "Bindings", "Ski Poles": "Poles", "Womens Helmets": "Helmets",
                 "Visor Helmets": "Helmets", "Goggles": "Protection"}
        for kind, part in cases.items():
            self.assertEqual(self.part(kind), part, kind)

    def test_left_out(self):
        for kind in ("Snowboard Boots", "Snowboards", "Insulated Ski and Snowboard Pants", "Ski Bags",
                     "Cross Country Skis", "Water Skis", "Boot Accessories", "After Ski", "Shot Skis",
                     "Womens Jackets", "Wakeboards", "Tuning Supplies", "Helmet/Goggle Accessories"):
            self.assertIsNone(self.part(kind), kind)

    def test_untyped_products_use_a_guarded_title(self):
        self.assertEqual(self.part("", "Dalbello DS MX 80 Ski Boot 2022-2023"), "Boots")
        self.assertEqual(self.part("NA", "Moment Commander 92 Ti Skis 2024"), "Skis")
        self.assertIsNone(self.part("", "Therm-ic Ski Warm Junior Ski Sock"))
        self.assertIsNone(self.part("", "Northside Ladies Brookelle SE Boot 2024"))

    def test_registered(self):
        names = [store.store for store in stores.STORES]
        for name in ("Willis Ski and Board", "The Pro Ski and Ride", "Aspen Ski and Board", "Skipro"):
            self.assertIn(name, names)
        self.assertEqual(stores.SKI_SHOPS[3].max_pages, 40)


if __name__ == "__main__":
    unittest.main()
