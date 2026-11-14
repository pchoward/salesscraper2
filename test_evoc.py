"""EVOC's US shop (owner, 2026-11-14): bike packs and armor on MTB, snow packs on Ski."""

import unittest

import sports
from sports import evoc, packs
from stores import shopify


def _product(title, kind, price="99.99", compare="230.00", handle=None):
    return {"id": hash(title), "title": title, "handle": handle or title.lower().replace(" ", "-"), "vendor": "EVOC",
            "product_type": kind, "tags": ["outlet"], "body_html": "",
            "variants": [{"id": 1, "title": "Default", "price": price, "compare_at_price": compare, "available": True}],
            "images": []}


class EvocTests(unittest.TestCase):
    def test_us_shop_whole_catalog(self):
        store = evoc.store(sports.MTB, evoc.MTB_TYPES)
        self.assertEqual(store.base, "https://evocsports.us")
        self.assertTrue(store.whole_site)
        self.assertIn("https://evocsports.us/collections/outlet/products.json", store.sale_jsons)
        self.assertIn("https://evocsports.us/products.json", store.sale_jsons)

    def test_mtb_reads_bike_packs_and_armor_only(self):
        store = evoc.store(sports.MTB, evoc.MTB_TYPES)
        cases = {("FR ENDURO BLACKLINE", "Protector Backpacks"): "Packs",
                 ("RIDE 12", "Hydration Bags"): "Packs",
                 ("Hip Pack 3", "Hip Packs"): "Packs",
                 ("Protector Shirt Zip", "Body Armor"): "Protection",
                 ("Knee Protector LS Flex Lite", "Knee Guards"): "Protection",
                 ("Line 20", "Snow Backpacks"): None,
                 ("Duffle Backpack 26", "Luggage / Duffle Bags"): None,
                 ("SEAT BAG TOUR L", "Seat Bags"): None,
                 ("Bike Travel Bag Pro", "Bike Travel Bags and Cases"): None,
                 ("Enduro Touch Glove", "Full Finger Gloves"): None}
        for (title, kind), part in cases.items():
            self.assertEqual(shopify.part_for(store, kind, title), part, title)

    def test_ski_reads_snow_packs_only(self):
        store = evoc.store(sports.SKI, evoc.SKI_TYPES)
        self.assertEqual(shopify.part_for(store, "Snow Backpacks", "Line Pro 30"), "Packs")
        self.assertIsNone(shopify.part_for(store, "Protector Backpacks", "FR ENDURO"))

    def test_snow_packs_stay_on_ski(self):
        self.assertEqual(packs.sport_of("Line 20", "EVOC", "Snow Backpacks"), "ski")
        self.assertIsNone(packs.sport_of("MISSION", "EVOC", "Backpacks"))
        def item(name, kind, url):
            return {"name": name, "url": url, "part": "Packs", "product_type": kind, "brand": "EVOC",
                    "price_new": "90", "price_old": "180"}
        catalogs = {"ski": {"EVOC_Packs": [item("EVOC Line 20", "Snow Backpacks", "https://evocsports.us/line-20")]},
                    "mtb": {"EVOC_Packs": [item("EVOC MISSION", "Backpacks", "https://evocsports.us/mission")]},
                    "skate": {}, "bmx": {}}
        pooled = packs.pool({}, "bmx", load=lambda sport: catalogs[sport.id])
        self.assertEqual([i["url"] for items in pooled.values() for i in items], ["https://evocsports.us/mission"])

    def test_only_marked_down_items_kept(self):
        store = evoc.store(sports.SKI, evoc.SKI_TYPES)
        with sports.SKI.session():
            scraper = shopify.ShopifyScraper(store, "Packs")
            items = scraper.products_from([_product("Line 20", "Snow Backpacks", "89.99", "180.00"),
                                           _product("Patrol 32L", "Snow Backpacks", "220.00", "230.00")])
        self.assertEqual([i["name"] for i in items], ["EVOC Line 20"])
        self.assertEqual(items[0]["brand"], "EVOC")

    def test_registered(self):
        from sports.mtb import stores as mtb
        from sports.ski import stores as ski
        self.assertIn(mtb.EVOC, mtb.STORES)
        self.assertIn(ski.EVOC, ski.STORES)


if __name__ == "__main__":
    unittest.main()
