"""Mike's Bikes (issue #165): MTB from a path-typed Shopify catalog, with
size-specific availability on complete bikes. No network."""

import json
import unittest

import sports
from sports.mtb import stores
from stores import shopify

HECKLER = {
    "id": 1, "title": "Heckler SL CC X0 Transmission Reserve", "vendor": "Santa Cruz", "handle": "heckler-sl",
    "product_type": "BIKES AND FRAMES/BIKES - ELECTRIC/ELECTRIC MOUNTAIN LIGHT WEIGHT/HECKLER SL",
    "tags": ["Sale", "my24"], "options": [{"name": "Color"}, {"name": "Size"}],
    "variants": [
        {"id": 11, "option1": "Gloss Black", "option2": "XX-Large", "price": "4499.77", "compare_at_price": "12999.99", "available": True},
        {"id": 12, "option1": "Gloss Black", "option2": "Large", "price": "4499.77", "compare_at_price": "12999.99", "available": False},
        {"id": 13, "option1": "Gloss Black", "option2": "Medium", "price": "4499.77", "compare_at_price": "12999.99", "available": False},
    ],
}
ROAD = {"id": 2, "title": "Soloist", "vendor": "Cervelo", "handle": "soloist",
        "product_type": "BIKES AND FRAMES/BIKES - ROAD/PERFORMANCE ROAD/SOLOIST",
        "variants": [{"id": 21, "price": "3000", "compare_at_price": "4000", "available": True}]}
PEDALS = {"id": 3, "title": "Chester Pedals", "vendor": "Race Face", "handle": "chester",
          "product_type": "COMPONENTS/PEDALS/MTB FLAT",
          "variants": [{"id": 31, "price": "40", "compare_at_price": "55", "available": True}]}
JERSEY = {"id": 4, "title": "Trail Jersey", "vendor": "Fox", "handle": "jersey", "product_type": "APPAREL/TOPS/JERSEYS",
          "variants": [{"id": 41, "price": "40", "compare_at_price": "70", "available": True}]}


def parse(products):
    kept = {}
    with sports.MTB.active():
        for scraper in [stores.MtbShopifyScraper(stores.MIKES, part) for part in stores.PARTS]:
            for item in scraper.parse(json.dumps({"products": products})):
                kept[item["name"]] = item
    return kept


class MikesBikesTests(unittest.TestCase):
    def test_mountain_only(self):
        kept = parse([HECKLER, ROAD, PEDALS, JERSEY])
        self.assertEqual({name: item["part"] for name, item in kept.items()},
                         {"Santa Cruz Heckler SL CC X0 Transmission Reserve": "Bikes", "Race Face Chester Pedals": "Pedals"},
                         "road bikes and jerseys are left out; the e-MTB is a bike")

    def test_size_specific_availability(self):
        bike = parse([HECKLER])["Santa Cruz Heckler SL CC X0 Transmission Reserve"]
        self.assertEqual([offer["variant_id"] for offer in bike["technical_offers"]], [11],
                         "only the XXL is buyable; L and M are not offered")
        self.assertEqual(bike["technical_specs"].get("frame_size"), ["XXL"], "Mike's spells it XX-Large")
        self.assertEqual((bike["price_new"], bike["price_old"]), ("4499.77", "12999.99"))

    def test_collections_and_dedup(self):
        self.assertEqual([url.split("/collections/")[1].split("/")[0] for url in stores.MIKES.sale_jsons],
                         ["clearance-and-sale", "clearance-and-sale-bikes", "mountain-bikes", "santa-cruz-bikes-on-sale"])
        pages = {"clearance-and-sale": [HECKLER, PEDALS], "clearance-and-sale-bikes": [HECKLER],
                 "mountain-bikes": [HECKLER], "santa-cruz-bikes-on-sale": [HECKLER]}

        def fetch(url):
            handle = url.split("/collections/")[1].split("/")[0]
            return {"products": pages[handle] if "page=1" in url else []}

        products = shopify.load_sale_products(stores.MIKES, fetch=fetch, sleep=lambda seconds: None)
        self.assertEqual([product["id"] for product in products], [1, 3], "a bike in four collections is kept once")

    def test_path_reader(self):
        cases = {"BIKES AND FRAMES/BIKES - MOUNTAIN/CROSS COUNTRY/BLUR": "Bikes",
                 "BIKES AND FRAMES/BIKES - ELECTRIC/ELECTRIC ACTIVE/ULTIMATE": None,
                 "BIKES AND FRAMES/BIKES - GRAVEL/GRAVEL/ASPERO": None,
                 "COMPONENTS/SADDLES/ROAD SADDLES": None, "COMPONENTS/GRIPS AND TAPE/BAR TAPE": None,
                 "COMPONENTS/GRIPS AND TAPE/GRIPS": "Cockpit", "COMPONENTS/BRAKES/DISC PADS": "Brakes",
                 "APPAREL/HELMETS/MOUNTAIN": "Protection", "ACCESSORIES/PUMPS/FRAME PUMPS": None}
        for product_type, part in cases.items():
            self.assertEqual(stores.mikes_part(product_type), part, product_type)

    def test_other_stores_are_unchanged(self):
        self.assertFalse(stores.WORLDWIDE.raw_type_part)
        self.assertFalse(stores.FANATIK.raw_type_part)
        self.assertLessEqual({"Worldwide Cyclery", "Fanatik", "Mike's Bikes", "Cambria"}, {store.store for store in stores.STORES})


if __name__ == "__main__":
    unittest.main()
