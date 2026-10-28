"""Deathgear (Squarespace): sale page JSON, parts from titles, on-sale variants, stock."""

import json
import unittest
from pathlib import Path

from stores import deathgear
from stores.registry import build_scrapers


def variant(price, sale, on_sale=True, qty=3, unlimited=False, attributes=None, vid="v1"):
    return {
        "id": vid, "onSale": on_sale, "qtyInStock": qty, "unlimited": unlimited,
        "attributes": attributes or {},
        "priceMoney": {"currency": "USD", "value": price},
        "salePriceMoney": {"currency": "USD", "value": sale},
        # Squarespace also sends cents; the money objects are what is read.
        "price": int(float(price) * 100), "salePrice": int(float(sale) * 100),
    }


def item(title, slug, variants, image="https://images.squarespace-cdn.com/x.jpg"):
    return {"title": title, "fullUrl": f"/shop/p/{slug}", "assetUrl": image,
            "structuredContent": {"productType": 1, "variants": variants}}


# The shape of https://www.deathgearproducts.com/shop/sale-clearance-blemished?format=json
# (owner's capture 2026-10-28: 44 items, no next page, productType 1).
PAGE = {
    "pagination": {"nextPageUrl": None},
    "items": [
        item("HEROIN~ QUESTIONS HEAVY HAULAGE SKATEBOARD DECK", "heroin-questions-heavy-haulage-skateboard-deck",
             [variant("83.00", "72.00")]),
        item("HEROIN~ CURB KILLER 8 EGG SKATEBOARD DECK", "heroin-curb-killer-8-egg-skateboard-deck",
             [variant("89.99", "76.99", qty=0)]),
        item("HEROIN~ DAWN OF THE EGG SKATEBOARD DECK", "heroin-dawn-of-the-egg-skateboard-deck",
             [variant("86.99", "86.99", on_sale=False)]),
        item("DEATH WIDE BOY SKATEBOARD DECK", "death-wide-boy-deck", [
            variant("79.99", "59.99", attributes={"Size": "9.0"}, vid="a"),
            variant("79.99", "61.99", attributes={"Size": "9.5"}, vid="b"),
        ]),
        item("DEATH LOGO CRUISER DECK 9.5", "death-cruiser", [variant("69.99", "39.99")]),
        item("SPITFIRE F4 99D CONICAL FULL 54MM WHEELS", "spitfire-f4-54", [variant("54.99", "44.99")]),
        item("PRO-TEC CLASSIC HELMET", "protec-classic", [
            variant("49.99", "34.99", attributes={"Size": "Medium"}, vid="m"),
            variant("49.99", "34.99", attributes={"Size": "Large"}, vid="l", qty=0),
        ]),
        item("DEATH LOGO T-SHIRT", "death-logo-tee", [variant("29.99", "19.99")]),
    ],
}


def kept(part):
    return {i["url"].rsplit("/", 1)[1]: i for i in deathgear.DeathgearScraper(part).products_from(PAGE["items"])}


class DeathgearTests(unittest.TestCase):
    def test_titles_are_readable_and_name_the_part(self):
        self.assertEqual(deathgear.clean_title("HEROIN~ QUESTIONS HEAVY HAULAGE SKATEBOARD DECK"),
                         "Heroin Questions Heavy Haulage Skateboard Deck")
        self.assertEqual(deathgear.clean_title("SPITFIRE F4 99D 54MM WHEELS"), "Spitfire F4 99D 54MM Wheels")
        self.assertEqual(deathgear.clean_title("Mixed Case Deck"), "Mixed Case Deck")
        cases = {"Heroin Questions Deck": "Decks", "Death Complete Skateboard 8.25": "Completes",
                 "Spitfire F4 54mm Wheels": "Wheels", "Independent Stage 4 Trucks": "Trucks",
                 "Bones Reds Bearings": "Bearings", "Mob Grip Tape": "Accessories",
                 "Pro-Tec Classic Helmet": "Protection", "Death Logo T-Shirt": None}
        for title, part in cases.items():
            self.assertEqual(deathgear.part_for_title(title), part, title)

    def test_only_variants_marked_on_sale_below_the_price(self):
        decks = kept("Decks")
        deck = decks["heroin-questions-heavy-haulage-skateboard-deck"]
        self.assertEqual((deck["price_new"], deck["price_old"]), ("72.00", "83.00"))
        self.assertEqual(deck["name"], "Heroin Questions Heavy Haulage Skateboard Deck")
        self.assertEqual(deck["url"], "https://www.deathgearproducts.com/shop/p/heroin-questions-heavy-haulage-skateboard-deck")
        self.assertEqual(deck["stock"], "in_stock")
        self.assertNotIn("heroin-dawn-of-the-egg-skateboard-deck", decks, "not on sale")
        self.assertNotIn("death-cruiser", decks, "cruisers stay out")

    def test_sold_out_is_kept_and_marked(self):
        deck = kept("Decks")["heroin-curb-killer-8-egg-skateboard-deck"]
        self.assertEqual(deck["stock"], "out_of_stock")
        self.assertEqual(deck["availability"], "Sold out")

    def test_width_variants_become_listings(self):
        decks = kept("Decks")
        self.assertEqual(decks["death-wide-boy-deck?variant=a"]["name"], 'Death Wide Boy Skateboard Deck 9.0"')
        self.assertEqual(decks["death-wide-boy-deck?variant=b"]["size"], "9.5")

    def test_other_parts(self):
        self.assertIn("spitfire-f4-54", kept("Wheels"))
        helmet = kept("Protection")["protec-classic"]
        self.assertEqual(helmet["protection_type"], "Helmet")
        self.assertEqual(helmet["protection_sizes"], ["M"], "the sold-out Large is not listed")
        everything = [url for part in deathgear.PARTS for url in kept(part)]
        self.assertNotIn("death-logo-tee", everything)

    def test_one_request_and_failures(self):
        asked = []
        items = deathgear.load_sale_items(lambda url: asked.append(url) or PAGE)
        self.assertEqual(asked, ["https://www.deathgearproducts.com/shop/sale-clearance-blemished?format=json"])
        self.assertEqual(len(items), len(PAGE["items"]))
        self.assertIsNone(deathgear.load_sale_items(lambda url: None))
        self.assertIsNone(deathgear.load_sale_items(lambda url: {"website": {}}), "a page without items fails the run")
        self.assertEqual(len(deathgear.DeathgearScraper("Decks").parse(json.dumps(PAGE))), 4)

    def test_wiring(self):
        self.assertEqual({s.part for s in build_scrapers() if s.name == "Deathgear"}, set(deathgear.PARTS))
        root = Path(__file__).resolve().parent
        self.assertIn('deathgear: "Deathgear"', (root / "page.js").read_text(encoding="utf-8"))
        self.assertIn(".store-deathgear {", (root / "page.css").read_text(encoding="utf-8"))
        from alerts_delivery import STORE_HOSTS
        self.assertIn("www.deathgearproducts.com", STORE_HOSTS)


if __name__ == "__main__":
    unittest.main()
