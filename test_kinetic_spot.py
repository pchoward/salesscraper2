"""Kinetic and SPoT on the shared Shopify code (stores/shopify.py)."""

import unittest

from stores import exodus, kinetic, shopify, spot
from stores.registry import build_scrapers


def variant(price, compare, vid=1, title="Default Title", available=None):
    out = {"id": vid, "title": title, "option1": title, "price": price, "compare_at_price": compare}
    if available is not None:
        out["available"] = available
    return out


def product(title, product_type, variants, handle, vendor=""):
    return {"title": title, "handle": handle, "vendor": vendor, "product_type": product_type, "body_html": "",
            "images": [{"src": f"https://cdn.shopify.com/{handle}.jpg"}], "variants": variants}


def kept(store, part, products):
    return {i["url"].rsplit("/", 1)[1]: i for i in shopify.ShopifyScraper(store, part).products_from(products)}


# Types from the owner's probe of each sale collection (2026-10-28).
KINETIC = [
    product("Vans Skate Wafflecup Shoes", "Footwear", [variant("59.99", "84.99", 1, "9", True)], "vans-wafflecup"),
    product("Vans Old Skool Shoes", "Footwear", [variant("49.99", "69.99")], "vans-old-skool"),
    product('Baker Brand Logo Deck 8.5"', "Skateboards", [variant("49.99", "69.99")], "baker-deck"),
    product('Element Section Complete Skateboard 8.0"', "Skateboards", [variant("69.99", "99.99")], "element-complete"),
    product("Spitfire Formula Four 54mm Wheels", "", [variant("39.99", "54.99")], "f4-untyped"),
    product("Kinetic Logo Hoodie", "Apparel", [variant("39.99", "59.99")], "hoodie"),
    product("Burton Custom Snowboard", "Snowboards", [variant("399.99", "599.99")], "snowboard"),
]
SPOT = [
    product('SPoT Life Deck 8.25"', "Deck", [variant("49.95", "64.95")], "spot-deck"),
    product("Nike SB Dunk Low Pro", "Shoes", [variant("89.99", "119.99", 2, "10", True)], "sb-dunk"),
    product("SPoT Logo T Shirt", "T Shirt", [variant("14.99", "24.99")], "tee"),
    product("SPoT Stickers", "Sticker", [variant("0.99", "1.99")], "sticker"),
]


class KineticTests(unittest.TestCase):
    def test_footwear_is_sneakers_and_only_tracked_models_stay(self):
        self.assertEqual(list(kept(kinetic.SHOP, "Sneakers", KINETIC)), ["vans-wafflecup"])

    def test_skateboards_and_untyped_products_take_their_part_from_the_title(self):
        self.assertEqual(list(kept(kinetic.SHOP, "Decks", KINETIC)), ["baker-deck"])
        self.assertEqual(list(kept(kinetic.SHOP, "Completes", KINETIC)), ["element-complete"])
        self.assertEqual(list(kept(kinetic.SHOP, "Wheels", KINETIC)), ["f4-untyped"])

    def test_apparel_and_snowboards_are_never_candidates(self):
        everything = [url for part in shopify.ALL_PARTS for url in kept(kinetic.SHOP, part, KINETIC)]
        self.assertNotIn("hoodie", everything)
        self.assertNotIn("snowboard", everything)
        self.assertEqual(kinetic.SHOP.sale_json, "https://kineticskateboarding.com/collections/sale/products.json")


class SpotTests(unittest.TestCase):
    def test_deck_and_shoe_types(self):
        decks = kept(spot.SHOP, "Decks", SPOT)
        self.assertEqual(list(decks), ["spot-deck"])
        self.assertEqual(decks["spot-deck"]["store"], "SPoT")
        self.assertEqual(decks["spot-deck"]["url"], "https://skateparkoftampa.com/products/spot-deck")
        shoes = kept(spot.SHOP, "Sneakers", SPOT)
        self.assertEqual(list(shoes), ["sb-dunk"])
        self.assertEqual(shoes["sb-dunk"]["shoe_sizes"], ["10"])

    def test_own_brand_vendor_is_not_added_twice(self):
        self.assertEqual(shopify.title_with_brand({"title": "Logo Deck", "vendor": "SPoT"}, spot.SHOP.own_vendor), "Logo Deck")


class ExodusTests(unittest.TestCase):
    def test_sale_1_collection_by_type_never_the_filter_url(self):
        self.assertEqual(exodus.SHOP.sale_json, "https://exodusrideshop.com/collections/sale-1/products.json")
        self.assertNotIn("filter", exodus.SHOP.sale_json)
        products = [
            product('Hockey Fire Deck 8.5"', "Decks", [variant("54.99", "74.99")], "hockey-deck"),
            product("Independent Stage 11 Trucks 144", "Trucks", [variant("49.99", "64.99")], "indy"),
            product("Spitfire Formula Four 54mm", "Wheels", [variant("39.99", "54.99")], "f4", vendor="Spitfire"),
            product("Burton Moto Boots", "Snowboard Boots", [variant("149.99", "199.99")], "boots"),
            product("Vans Skate Wafflecup", "Shoes", [variant("54.99", "79.99", 3, "9", True)], "wafflecup"),
        ]
        found = {part: list(kept(exodus.SHOP, part, products)) for part in shopify.ALL_PARTS}
        self.assertEqual(found["Decks"], ["hockey-deck"])
        self.assertEqual(found["Trucks"], ["indy"])
        self.assertEqual(found["Wheels"], ["f4"])
        self.assertEqual(found["Sneakers"], ["wafflecup"])
        self.assertNotIn("boots", sum(found.values(), []))


class StockReadTests(unittest.TestCase):
    """Exodus's and Kinetic's sale feeds leave out ``available``, so sizes came out empty."""

    def feed(self):
        return [
            product("Vans Skate Half Cab Wafflecup", "Skate Shoes", [
                variant("54.99", "79.99", 11, "9"), variant("54.99", "79.99", 12, "10"), variant("54.99", "79.99", 13, "11"),
            ], "half-cab"),
            product("Vans Old Skool", "Skate Shoes", [variant("49.99", "69.99", 21, "9")], "old-skool"),
            product("Burton Moto Boots", "Snowboard Boots", [variant("149.99", "199.99", 31, "9")], "boots"),
        ]

    def test_sizes_come_from_each_products_stock(self):
        products = self.feed()
        asked = []
        live = {"variants": [{"id": 11, "available": True}, {"id": 12, "available": False}, {"id": 13, "available": True}]}

        def fetch(url):
            asked.append(url)
            return live

        shopify.enrich_stock(exodus.SHOP, products, "Sneakers", fetch=fetch, sleep=lambda _s: None)
        self.assertEqual(asked, ["https://exodusrideshop.com/products/half-cab.js"],
                         "only shoes the filters keep are read; not Old Skool, not snow boots")
        shoes = kept(exodus.SHOP, "Sneakers", products)
        self.assertEqual(shoes["half-cab"]["shoe_sizes"], ["9", "11"], "the sold-out 10 is not listed")

    def test_unreadable_stock_and_the_read_limit(self):
        products = self.feed()
        shopify.enrich_stock(exodus.SHOP, products, "Sneakers", fetch=lambda url: None, sleep=lambda _s: None)
        self.assertNotIn("shoe_sizes", kept(exodus.SHOP, "Sneakers", products)["half-cab"])
        many = [product(f"Vans Wafflecup {n}", "Skate Shoes", [variant("54.99", "79.99", n, "9")], f"w{n}") for n in range(5)]
        asked = []
        shopify.enrich_stock(exodus.SHOP, many, "Sneakers", fetch=lambda url: asked.append(url), sleep=lambda _s: None, limit=2)
        self.assertEqual(len(asked), 2)

    def test_scrape_reads_stock_for_shoes_and_gear_only(self):
        from unittest import mock

        for part, expected in (("Sneakers", 1), ("Decks", 0), ("Protection", 1)):
            with mock.patch.object(shopify, "load_sale_products", return_value=[]), \
                    mock.patch.object(shopify, "enrich_stock") as enrich:
                shopify.ShopifyScraper(exodus.SHOP, part).scrape()
            self.assertEqual(enrich.call_count, expected, part)


class SharedTests(unittest.TestCase):
    def test_every_store_runs_every_part_in_the_daily_scrape(self):
        for name in ("Kinetic", "SPoT", "TGM", "Exodus"):
            self.assertEqual({s.part for s in build_scrapers() if s.name == name}, set(shopify.ALL_PARTS), name)

    def test_stores_keep_separate_downloads(self):
        a = shopify.ShopifyStore("A", "A", "https://a.example")
        b = shopify.ShopifyStore("B", "B", "https://b.example")
        a.cache["products"] = ["a"]
        self.assertNotIn("products", b.cache)

    def test_part_for_title(self):
        self.assertEqual(shopify.part_for_title("Pro-Tec Helmet"), "Protection")
        self.assertEqual(shopify.part_for_title("Mystery Item"), None)


if __name__ == "__main__":
    unittest.main()
