"""Ski's first catalog (issue #134): Gear West's alpine ski and boot
closeouts, with ski lengths, boot sizes, style and gender read from the
store's data, and nothing guessed."""

import json
import unittest

import sports
from sports.ski import specs, stores

FEED = {"products": [
    {"title": "Bent 110 Skis 2026", "vendor": "ATOMIC", "handle": "bent", "product_type": "ALPINE - ALPINE SKIS - Park Skis",
     "tags": ["Alpine", "Skis", "Park", "Men"], "options": [{"name": "Size"}, {"name": "Color"}],
     "variants": [{"id": 1, "option1": "172", "option2": "Blue", "price": "499.99", "compare_at_price": "749.99", "available": True},
                  {"id": 2, "option1": "180", "option2": "Blue", "price": "499.99", "compare_at_price": "749.99", "available": True},
                  {"id": 3, "option1": "188", "option2": "Blue", "price": "499.99", "compare_at_price": "749.99", "available": False},
                  {"id": 4, "option1": "164", "option2": "Blue", "price": "749.99", "compare_at_price": "749.99", "available": True}]},
    {"title": "Speedmachine 3 110 Ski Boots", "vendor": "NORDICA", "handle": "sm3", "product_type": "ALPINE - ALPINE BOOTS - Men's Boots",
     "tags": ["Boots", "Men"], "options": [{"name": "Size"}],
     "variants": [{"id": 5, "option1": "26.5", "price": "399", "compare_at_price": "599"},
                  {"id": 6, "option1": "27.5", "price": "399", "compare_at_price": "599"}]},
    {"title": "Redster G9", "vendor": "HEAD TYROLIA WINTERSPORTS", "handle": "g9", "product_type": "Skis", "tags": ["Race", "Women"],
     "options": [{"name": "Ski Length"}], "variants": [{"id": 7, "option1": "165cm", "price": "600", "compare_at_price": "900"}]},
    {"title": "Team Jr Skis", "vendor": "KASTLE SKIS", "handle": "jr", "product_type": "ALPINE - ALPINE SKIS - Kids Skis",
     "tags": ["Kids"], "options": [{"name": "Size"}], "variants": [{"id": 8, "option1": "One Size", "price": "200", "compare_at_price": "300"}]},
    {"title": "Wax Kit", "vendor": "SWIX", "handle": "wax", "product_type": "Tools",
     "variants": [{"id": 9, "price": "20", "compare_at_price": "30"}]},
    {"title": "Merino Base Layer", "vendor": "SMARTWOOL", "handle": "base", "product_type": "Baselayers",
     "variants": [{"id": 10, "price": "60", "compare_at_price": "90"}]},
]}


def parse(feed=FEED):
    kept = {}
    with sports.SKI.active():
        for scraper in stores.scrapers():
            for item in scraper.parse(json.dumps(feed)):
                kept[item["name"]] = item
    return kept


class GearWestTests(unittest.TestCase):
    def test_settings(self):
        self.assertEqual(sports.SKI.parts, ("Skis", "Boots", "Bindings", "Poles", "Helmets"))
        self.assertFalse(sports.SKI.delivery, "no email or alerts for Ski")
        self.assertEqual(stores.GEAR_WEST.sale_jsons, [
            "https://www.gearwest.com/collections/closeout-alpine-skis/products.json",
            "https://www.gearwest.com/collections/closeout-alpine-boots/products.json"])
        self.assertEqual({scraper.shop.store for scraper in sports.SKI.build_scrapers()}, {"Gear West"})

    def test_skis_and_boots_with_their_real_details(self):
        kept = parse()
        self.assertEqual(sorted(kept), ["Atomic Bent 110 Skis 2026", "Head Redster G9", "Kästle Team Jr Skis",
                                        "Nordica Speedmachine 3 110 Ski Boots"], "tools and base layers are left out")
        bent = kept["Atomic Bent 110 Skis 2026"]
        self.assertEqual((bent["part"], bent["brand"], bent["kind"], bent["gender"]), ("Skis", "Atomic", "Park", "Men"))
        self.assertEqual(bent["lengths"], ["172", "180"], "only lengths on sale and buyable (188 sold out, 164 full price)")
        self.assertEqual(bent["price_new"], "499.99")
        boots = kept["Nordica Speedmachine 3 110 Ski Boots"]
        self.assertEqual((boots["part"], boots["sizes"], boots["gender"]), ("Boots", ["26.5", "27.5"], "Men"))
        self.assertNotIn("lengths", boots)
        head = kept["Head Redster G9"]
        self.assertEqual((head["brand"], head["kind"], head["gender"], head["lengths"]), ("Head", "Race", "Women", ["165"]))
        junior = kept["Kästle Team Jr Skis"]
        self.assertEqual(junior["gender"], "Kids")
        self.assertNotIn("lengths", junior, "'One Size' is not a length; nothing is guessed")

    def test_spec_readers(self):
        self.assertIsNone(specs.style("Skis", ["Alpine", "Men"]), "no style unless the store says")
        self.assertEqual(specs.style("ALPINE - ALPINE BOOTS - Park Boots", []), "Park")
        self.assertEqual(specs.gender("ALPINE - ALPINE SKIS - Wmn's Skis", []), "Women")
        self.assertEqual(stores.type_part("alpine alpine boots race boots"), "Boots")
        self.assertEqual(specs.title_length("Rossignol Hero Athlete SL 150cm R22 Race Ski 2026"), ["150"])
        self.assertEqual(specs.title_length("Justis Ski 2026"), [])
        self.assertIsNone(stores.type_part("baselayers"))

    def test_ski_page(self):
        from report import build_report_html

        kept = parse()
        html = build_report_html({"Gear West_Skis": [i for i in kept.values() if i["part"] == "Skis"],
                                  "Gear West_Boots": [i for i in kept.values() if i["part"] == "Boots"]},
                                 {}, {}, set(), generated_at="2026-11-02T12:00:00+00:00", sport=sports.SKI)
        self.assertIn("<title>ShredDeals Ski |", html)
        self.assertIn('data-part="Skis" data-count="3"', html)
        self.assertIn('data-part="Boots" data-count="1"', html)
        catalog = json.loads(html.split('id="catalogJson"', 1)[1].split(">", 1)[1].split("</script>", 1)[0])
        entries = {entry["name"]: entry for entry in catalog["items"].values()}
        bent = entries["Atomic Bent 110 Skis 2026"]
        self.assertEqual((bent["lengths"], bent["kind"], bent["gender"]), (["172", "180"], "Park", "Men"))
        self.assertEqual(entries["Nordica Speedmachine 3 110 Ski Boots"]["sizes"], ["26.5", "27.5"])


if __name__ == "__main__":
    unittest.main()
