"""Kinetic and SPoT on the shared Shopify code (stores/shopify.py)."""

import unittest

from stores import kinetic, shopify, spot
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


class SharedTests(unittest.TestCase):
    def test_every_store_runs_every_part_in_the_daily_scrape(self):
        for name in ("Kinetic", "SPoT", "TGM"):
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
