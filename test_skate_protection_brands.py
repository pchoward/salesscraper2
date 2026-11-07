"""Skate protection from the multisport brands, and hip/ankle/shin types
(owner, 2026-11-03). No network."""

import json
import unittest

import protection
from stores import protection_brands, registry, shopify


def product(id, title, vendor, kind=""):
    return {"id": id, "title": title, "vendor": vendor, "handle": f"p{id}", "product_type": kind, "tags": [],
            "options": [{"name": "Size"}],
            "variants": [{"id": id * 10, "price": "18.00", "compare_at_price": "59.99", "available": True, "option1": "M"}]}


class SkateBrandTests(unittest.TestCase):
    def test_skate_pieces_with_their_types(self):
        store = protection_brands.STORES[0]  # Triple 8
        feed = [product(1, "Bike Bumsaver Padded Shorts", "Triple 8"),
                product(2, "Halo Snow Standard Helmet", "Triple 8", "Helmets"),
                product(3, "KP 22 Knee Pads", "Triple 8"),
                product(4, "Triple 8 Logo Tee", "Triple 8")]
        items = shopify.ShopifyScraper(store, "Protection").parse(json.dumps({"products": feed}))
        found = {item["name"]: protection.classify(item["name"]) for item in items}
        self.assertEqual(found, {"Triple 8 Bike Bumsaver Padded Shorts": "Hip & Tailbone",
                                 "Triple 8 KP 22 Knee Pads": "Knee Pads"}, "snow helmets and tees stay out")

    def test_registered_for_protection_only(self):
        scrapers = [s for s in registry.build_scrapers() if getattr(s, "shop", None) in protection_brands.STORES]
        self.assertEqual({s.shop.store for s in scrapers}, {"Triple 8", "187 Killer Pads", "Demon", "G-Form", "Zeitbike"})
        self.assertEqual({s.part for s in scrapers}, {"Protection"})

    def test_new_types_in_order(self):
        self.assertEqual(list(protection.SUBTYPE_TOKENS.values()),
                         ["helmet", "knee", "elbow", "wrist", "hip", "ankle", "shin", "set", "other"])


if __name__ == "__main__":
    unittest.main()
