"""Empire BMX (2026-11-08): Shopify, categories from tags, whole catalog read."""

import unittest

import sports
from sports import brands
from sports.bmx import stores
from stores import shopify


def product(title, tags, price="500.00", compare="625.00"):
    return {"id": hash(title), "handle": title.lower().replace(" ", "-"), "title": title, "vendor": "Empire BMX",
            "product_type": "", "tags": tags, "body_html": "",
            "variants": [{"id": 1, "title": "Default Title", "price": price, "compare_at_price": compare,
                          "available": True}]}


class EmpireBmxTests(unittest.TestCase):
    def test_registered(self):
        self.assertIn(stores.EMPIRE, stores.STORES)
        self.assertEqual(stores.EMPIRE.sale_jsons[-1], "https://www.empirebmx.com/products.json")

    def test_category_from_tags(self):
        cases = {("Fairdale Lookfar 2023", ("26\" and larger", "Bikes", "Fairdale")): "Bikes",
                 ("Odyssey Boyd sprocket", ("Odyssey", "Parts", "Sprockets + sprocket guards + adapters")): "Drivetrain",
                 ("Fit Bikes Aitken stem", ("Fit Bikes", "Parts", "Stems")): "Steering",
                 ("Fuse Omega knee pads", ("Fuse", "Kneepads", "Safety Gear", "Sale Items")): "Protection",
                 ("Sunday t-shirt - Stairs", ("Shirts", "Softgoods", "Sunday")): None,
                 ("Park Tool PW-4 pedal wrench", ("Park Tool", "Tools")): None}
        for (title, tags), part in cases.items():
            self.assertEqual(shopify.part_for(stores.EMPIRE, "", title, list(tags)), part, title)

    def test_bike_listing(self):
        with sports.BMX.active():
            scraper = [s for s in shopify.scrapers_for(stores.EMPIRE, stores.PARTS) if s.part == "Bikes"][0]
            items = scraper.products_from([product("Rixin Local bike", ["20\"", "Bikes", "Rixin"])])
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["wheel_size"], "20")
        self.assertEqual(items[0]["kind"], "Complete Bikes")
        self.assertEqual(brands.from_title("Fairdale Lookfar 2023", sports.BMX.aliases_file()), "Fairdale")

    def test_cut_price_without_compare_at_is_not_listed(self):
        # Empire's "Sale Items" tag with no was-price shows no markdown.
        with sports.BMX.active():
            scraper = [s for s in shopify.scrapers_for(stores.EMPIRE, stores.PARTS) if s.part == "Bikes"][0]
            items = scraper.products_from([product("Fit Bikes CR 29", ["Bikes", "Sale Items"], "899.95", None)])
        self.assertEqual(items, [])


if __name__ == "__main__":
    unittest.main()
