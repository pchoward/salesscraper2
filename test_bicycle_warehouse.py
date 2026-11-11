"""Bicycle Warehouse (MTB, 2026-11-11): only mountain bikes count as bikes."""

import unittest

from sports.mtb import stores
from stores import shopify


class BicycleWarehouseTests(unittest.TestCase):
    def part(self, kind, title="Thing"):
        return shopify.part_for(stores.BICYCLE_WAREHOUSE, kind, title)

    def test_bikes(self):
        for kind in ("Bikes - Full Suspension 29", "Bikes - E-Full Suspension 29", "Bikes - Hardtail 29"):
            self.assertEqual(self.part(kind), "Bikes", kind)
        for kind in ("Bikes - Hybrid", "Bikes - E-Hybrid", "Bikes - Road", "Bikes - E-Road"):
            self.assertIsNone(self.part(kind), kind)

    def test_parts_and_clothing(self):
        self.assertEqual(self.part("Tires", "Specialized Butcher Grid Trail 27.5 Tire"), "Tires")
        self.assertEqual(self.part("Framesets", "S-Works Turbo Levo 4 Frameset"), "Frames")
        self.assertEqual(self.part("Helmets", "Specialized Ambush II Bike Helmet"), "Protection")
        self.assertEqual(self.part("Protective", "Fox Launch Knee/Shin Pads"), "Protection")
        for kind in ("Jerseys", "Shorts", "Gloves", "Shoes", "Lights", "Water Bottle Cages", "Bar Tape"):
            self.assertIsNone(self.part(kind), kind)

    def test_registered(self):
        self.assertIn(stores.BICYCLE_WAREHOUSE, stores.STORES)


if __name__ == "__main__":
    unittest.main()
