"""Sourceboards (Skate, 2026-11-11): US storefront, parts from type paths."""

import unittest

from stores import registry, shopify, sourceboards


class SourceboardsTests(unittest.TestCase):
    def test_us_storefront(self):
        self.assertTrue(sourceboards.SHOP.sale_json.startswith("https://www.sourceboards.com/en-us/collections/"))

    def test_type_paths(self):
        cases = {"Skateboards - Skate Decks - Sale Skate Decks 25% Off": "Decks",
                 "Skateboards - Skate Decks - Sale Skate Decks $70": "Decks",
                 "Skateboards - Complete Skateboards": "Completes",
                 "Skateboards - Skate Trucks": "Trucks", "Skateboards - Skate Wheels": "Wheels",
                 "Skateboards - Bearings": "Bearings", "Skateboards - Grip Tape": "Accessories"}
        for path, part in cases.items():
            self.assertEqual(shopify.part_for(sourceboards.SHOP, path, "Thing"), part, path)
        for path in ("Skateboards - Cruisers", "Skateboards - Longboards", "Men's Tops - Men's T-Shirts",
                     "Snowboards - Snowboards"):
            self.assertIsNone(shopify.part_for(sourceboards.SHOP, path, "Thing"), path)

    def test_registered(self):
        self.assertTrue(any(getattr(s, "name", "") == "Sourceboards" for s in registry.build_scrapers()))


if __name__ == "__main__":
    unittest.main()
