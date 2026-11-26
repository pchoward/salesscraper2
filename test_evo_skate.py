"""evo on the Skate tab (owner, 2026-11-26): its skate sale was read only for
MTB and Ski until the owner found Bronson pro bearings at $19.47 there."""

import unittest

import query_state
from stores import evo_skate, shopify
from stores.registry import build_scrapers


def product(title, kind, price, compare, vendor="", handle=None, available=True):
    return {"title": title, "vendor": vendor, "product_type": kind, "tags": [], "body_html": "",
            "handle": handle or title.lower().replace(" ", "-").replace(".", ""),
            "variants": [{"id": 1, "title": "Default Title", "price": price, "compare_at_price": compare,
                          "available": available}]}


BRONSON = product("Bronson Speed Co. G3 Mason Silva Pro Skateboard Bearings", "Bearings", "19.47", "37.95",
                  vendor="Bronson Speed Co.")


class EvoSkateTests(unittest.TestCase):
    def parts(self, item):
        return shopify.part_for(evo_skate.SHOP, item["product_type"], item["title"], item["tags"])

    def test_types_map_to_skate_parts(self):
        cases = {
            "Skateboard Decks": "Decks", "Skateboard Completes": "Completes", "Skateboard Wheels": "Wheels",
            "Skateboard Trucks": "Trucks", "Bearings": "Bearings", "Grip Tape": "Accessories",
            "Hardware": "Accessories", "Risers": "Accessories", "Skate Tools": "Accessories",
            "Skate Helmets": "Protection", "Backpacks": "Packs", "Day Packs": "Packs", "Shoes": "Sneakers",
        }
        for kind, part in cases.items():
            self.assertEqual(self.parts(product("Thing", kind, "10", "20")), part, kind)
        for kind in ("Longboard Wheels", "Longboard Trucks", "Longboard Grip Tape", "Ski Boots"):
            self.assertIsNone(self.parts(product("Thing", kind, "10", "20")), kind)

    def test_the_bronson_bearings_are_listed(self):
        scraper = next(s for s in evo_skate.scrapers() if s.part == "Bearings")
        items = scraper.products_from([BRONSON])
        self.assertEqual(len(items), 1)
        self.assertEqual((items[0]["store"], items[0]["price_new"], items[0]["price_old"]), ("evo", "19.47", "37.95"))
        self.assertTrue(items[0]["url"].startswith("https://www.evo.com/products/"))

    def test_skate_rules_still_apply(self):
        completes = next(s for s in evo_skate.scrapers() if s.part == "Completes")
        cruiser = product("Landyachtz Dinghy Classic Wave Cruiser Skateboard Complete", "Cruiser Complete",
                          "90", "120", vendor="Landyachtz")
        self.assertEqual(completes.products_from([cruiser]), [])
        full_price = product("Bronson Speed Co. G3 Skateboard Bearings", "Bearings", "27.95", "27.95")
        bearings = next(s for s in evo_skate.scrapers() if s.part == "Bearings")
        self.assertEqual(bearings.products_from([full_price]), [])

    def test_reads_evo_skate_collections_only(self):
        self.assertEqual(evo_skate.SHOP.base, "https://www.evo.com")
        self.assertEqual([url.split("/collections/")[1].split("/")[0] for url in evo_skate.SHOP.sale_jsons],
                         ["skateboards", "skateboard-parts", "skateboard-helmets", "skateboard-backpacks",
                          "skateboard-shoes"])
        self.assertFalse(evo_skate.SHOP.whole_site)

    def test_registered_on_skate_with_a_store_link(self):
        evo = [s for s in build_scrapers() if getattr(getattr(s, "shop", None), "store", None) == "evo"]
        self.assertEqual(len(evo), len(shopify.ALL_PARTS))
        self.assertEqual(query_state.STORE_SLUGS["evo"], "evo")


if __name__ == "__main__":
    unittest.main()
