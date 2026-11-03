"""MTB brand-direct stores for protection (owner, 2026-11-03): Troy Lee,
Alpinestars, Demon, 7iDP, G-Form, Race Face. No network."""

import json
import unittest

import sports
from sports.mtb import stores


def product(id, title, vendor, kind=""):
    return {"id": id, "title": title, "vendor": vendor, "handle": f"p{id}", "product_type": kind, "tags": [],
            "options": [{"name": "Size"}],
            "variants": [{"id": id * 10, "price": "40.00", "compare_at_price": "80.00", "available": True, "option1": "M"}]}


class BrandStoreTests(unittest.TestCase):
    def kept(self, store, feed):
        found = {}
        with sports.MTB.active():
            for scraper in [stores.MtbShopifyScraper(store, part) for part in stores.PARTS]:
                for item in scraper.parse(json.dumps({"products": feed})):
                    found[item["name"]] = item["part"]
        return found

    def test_other_sports_stay_out(self):
        feed = [product(1, "Elite 2 Baseball Batter's Elbow Guard", "G-Form"),
                product(2, "Pro-S Blade Soccer Shin Guards", "G-Form"),
                product(3, "E-Line Knee Guards", "G-Form")]
        self.assertEqual(self.kept(stores.G_FORM, feed), {"G-Form E-Line Knee Guards": "Protection"})
        feed = [product(4, "Demon Faktor Snow Helmet with Audio", "Demon", "SKI/SNOW"),
                product(5, "Demon Hyper Knee D3O V3 - NO ORIGINAL PACKAGING/TAGS", "Demon", "Sale")]
        self.assertEqual(self.kept(stores.DEMON, feed), {"Demon Hyper Knee D3O V3 - NO ORIGINAL PACKAGING/TAGS": "Protection"})

    def test_types_and_apparel(self):
        feed = [product(6, "Stage Knee Guard Solid Black", "Troy Lee Designs", "PROTECTION"),
                product(7, "Gambit Glove Solid Charcoal", "Troy Lee Designs", "GLOVES"),
                product(8, "Skyline Jersey Solid Black", "Troy Lee Designs", "JERSEYS")]
        self.assertEqual(self.kept(stores.TROY_LEE, feed), {"Troy Lee Designs Stage Knee Guard Solid Black": "Protection",
                                                            "Troy Lee Designs Gambit Glove Solid Charcoal": "Protection"})
        self.assertEqual(self.kept(stores.SEVEN_IDP, [product(9, "Project 23 Carbon - 2025", "7iDP", "P23 Helmet")]),
                         {"7iDP Project 23 Carbon - 2025": "Protection"})

    def test_all_are_mtb_stores(self):
        for store in stores.BRAND_STORES:
            self.assertIn(store, stores.STORES)
            self.assertTrue(store.track_exclusions)


if __name__ == "__main__":
    unittest.main()
