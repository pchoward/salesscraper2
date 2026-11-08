"""The brand 100% must survive name cleanup (owner, 2026-11-08: 100% Surpass
and Ridecamp pads showed as unbranded "Surpass ..." / "Ridecamp ...")."""

import unittest

from filters import normalize_product_name
from stores import shopify


class BrandHundredPercentTest(unittest.TestCase):
    def test_brand_kept_in_names(self):
        self.assertEqual(normalize_product_name("100%"), "100%")
        self.assertEqual(normalize_product_name("100% Ridecamp Knee Guard"), "100% Ridecamp Knee Guard")

    def test_skate_warehouse_prefixes_still_stripped(self):
        self.assertEqual(normalize_product_name("Clearance\xa0-10%April Deck"), "April Deck")
        self.assertEqual(normalize_product_name("Sale\xa0-24%Madness Deck"), "Madness Deck")
        self.assertEqual(normalize_product_name("Sale 24%Madness Deck"), "Madness Deck")
        self.assertEqual(normalize_product_name("-15% Baker Deck"), "Baker Deck")

    def test_vendor_100_percent_goes_in_front(self):
        product = {"title": "Surpass Elbow Guard - Heather Gray-Black", "vendor": "100%"}
        self.assertEqual(shopify.title_with_brand(product), "100% Surpass Elbow Guard - Heather Gray-Black")


if __name__ == "__main__":
    unittest.main()
