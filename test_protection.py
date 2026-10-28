"""Protection: helmets, pads, wrist guards, sets, and impact shorts at every store."""

import re
import unittest
from unittest import mock

import protection
from filters import filter_reason
from query_state import decode_query, encode_state
from report import build_report_html
from stores import ccs, skatewarehouse, tactics, tgm, zumiez
from stores.registry import build_scrapers


class ClassifyTests(unittest.TestCase):
    def test_subtypes(self):
        cases = {
            "Pro-Tec Classic Certified Helmet Matte Black": "Helmet",
            "187 Killer Pads Pro Knee Pads Black": "Knee Pads",
            "Smith Scabs Elite Elbow Pads": "Elbow Pads",
            "Triple Eight Wristsaver Wrist Guards": "Wrist Guards",
            "Triple Eight Saver Series 3-Pack Pad Set": "Pad Set",
            "TSG Junior Combo Pads": "Pad Set",
            "187 Killer Pads Six Pack Pad Set": "Pad Set",
            "Destroyer Pads Elbow and Knee": "Pad Set",
            "Pro-Tec Street Knee and Elbow Pads": "Pad Set",
            "187 Killer Pads Impact Shorts": "Other",
            "Triple Eight Bumsaver Hip Pads": "Other",
        }
        for name, subtype in cases.items():
            self.assertEqual(protection.classify(name), subtype, name)

    def test_the_product_type_counts(self):
        self.assertEqual(protection.classify("Pro-Tec Classic Certified Matte Black", "Helmets"), "Helmet")
        self.assertEqual(protection.classify("TSG Professional Black", "Combo Pads"), "Pad Set")
        self.assertEqual(protection.classify("Rector Pro Series Pads", "Protective Gear"), "Other")

    def test_things_that_are_not_protection(self):
        for name in ("Shorty's Riser Pads 1/8in", "Bones Swiss Shock Pads", "Thrasher Flame Shorts",
                     "Bones STF 54mm Wheels", "Helmet Sticker Pack", "Independent Stage 11 Trucks"):
            self.assertIsNone(protection.classify(name), name)


class SizeTests(unittest.TestCase):
    def test_option_labels(self):
        cases = {
            "S": ["S"], "Small": ["S"], "Medium": ["M"], "L": ["L"], "Large": ["L"], "X-Large": ["XL"],
            "Extra Large": ["XL"], "XXL": ["XXL"], "2XL": ["XXL"], "XS": ["XS"], "S/M": ["S", "M"],
            "L - XL": ["L", "XL"], "XS-S": ["XS", "S"], "Youth": [], "One Size": [], "10": [], "": [],
        }
        for label, sizes in cases.items():
            self.assertEqual(protection.size_tokens(label), sizes, label)

    def test_sizes_in_names_are_words_or_marked_letters(self):
        self.assertEqual(protection.sizes_in("187 Knee Pads Black Medium"), ["M"])
        self.assertEqual(protection.sizes_in("Impact Shorts Size L"), ["L"])
        self.assertEqual(protection.sizes_in("S-One Lifer Helmet (XL)"), ["XL"])
        self.assertEqual(protection.sizes_in("S-One Lifer Helmet Black"), [], "the S in S-One is not a size")

    def test_variant_sizes_in_order(self):
        variants = [{"option1": "Large"}, {"option1": "Small"}, {"option1": "X-Large"}, {"title": "M"}, {"option1": "Black"}]
        self.assertEqual(protection.variant_sizes(variants), ["S", "M", "L", "XL"])


class FilterTests(unittest.TestCase):
    def test_gear_on_markdown_is_kept(self):
        self.assertIsNone(filter_reason("187 Killer Pads Impact Shorts", "Protection", "", "29.99", "44.99"))
        # Apparel and longboard words do not reject protective gear.
        self.assertIsNone(filter_reason("Triple Eight Longboard Helmet", "Protection", "", "34.99", "49.99"))

    def test_not_gear_or_not_marked_down(self):
        self.assertEqual(filter_reason("Thrasher Shorts", "Protection", "", "19.99", "39.99"), "not protective gear")
        self.assertEqual(filter_reason("Pro-Tec Helmet", "Protection", "", "44.99", "44.99"), "no markdown")
        self.assertEqual(filter_reason("Pro-Tec Helmet", "Protection", "", "44.99", None), "no markdown")

    def test_other_parts_still_reject_shorts(self):
        self.assertEqual(filter_reason("187 Killer Pads Impact Shorts", "Accessories", "", "29.99", "44.99"), "apparel")


def _variant(price, compare, vid, size, available=None):
    out = {"id": vid, "title": size, "option1": size, "price": price, "compare_at_price": compare}
    if available is not None:
        out["available"] = available
    return out


def _product(title, product_type, variants, handle):
    return {"title": title, "handle": handle, "product_type": product_type, "body_html": "",
            "images": [{"src": f"https://cdn.shopify.com/{handle}.jpg"}], "variants": variants}


class CCSTests(unittest.TestCase):
    def test_clearance_feed_gives_subtype_and_in_stock_sizes(self):
        products = [
            _product("187 Killer Pads Pro Knee Pads", "Protective", [
                _variant("39.99", "59.99", 1, "Small", True),
                _variant("39.99", "59.99", 2, "Medium", False),
                _variant("39.99", "59.99", 3, "Large", True),
            ], "187-knee"),
            _product("Pro-Tec Classic Helmet", "Helmets", [_variant("34.99", "49.99", 4, "XL")], "protec-helmet"),
            _product("Pro-Tec Classic Helmet Full Price", "Helmets", [_variant("49.99", "49.99", 5, "M")], "protec-full"),
            _product("Shorty's Riser Pads", "Hardware", [_variant("2.99", "4.99", 6, "Default Title")], "risers"),
        ]
        items = {item["url"].rsplit("/", 1)[1]: item for item in ccs.CCSCatalogScraper("Protection").products_from(products)}
        self.assertEqual(sorted(items), ["187-knee", "protec-helmet"])
        self.assertEqual(items["187-knee"]["part"], "Protection")
        self.assertEqual(items["187-knee"]["protection_type"], "Knee Pads")
        self.assertEqual(items["187-knee"]["protection_sizes"], ["S", "L"], "the sold-out Medium is not listed")
        self.assertEqual(items["protec-helmet"]["protection_type"], "Helmet")
        self.assertEqual(items["protec-helmet"]["protection_sizes"], ["XL"])

    def test_protection_is_a_ccs_part(self):
        self.assertIn("Protection", [scraper.part for scraper in ccs.scrapers()])


class TGMTests(unittest.TestCase):
    def test_protective_types_route_to_protection(self):
        for kind in ("Helmets", "Combo Pads", "Elbow Pads", "Knee Pads", "Wrist Guards"):
            self.assertEqual(tgm.part_for_type(kind), "Protection", kind)
        self.assertIsNone(tgm.part_for_type("Starter Sets"))
        products = [
            _product("TSG Professional Pad Set", "Combo Pads", [_variant("49.95", "69.95", 1, "S/M"),
                                                                  _variant("49.95", "69.95", 2, "L/XL")], "tsg-set"),
            _product("Triple Eight Sweatsaver Helmet", "Helmets", [_variant("39.95", "54.95", 3, "Medium")], "t8-helmet"),
            _product("Smith Scabs Elbow Pads", "Elbow Pads", [_variant("24.95", "24.95", 4, "M")], "scabs-full"),
        ]
        items = {item["url"].rsplit("/", 1)[1]: item for item in tgm.TGMScraper("Protection").products_from(products)}
        self.assertEqual(sorted(items), ["t8-helmet", "tsg-set"])
        self.assertEqual(items["tsg-set"]["protection_type"], "Pad Set")
        self.assertEqual(items["tsg-set"]["protection_sizes"], ["S", "M", "L", "XL"])
        self.assertEqual(items["t8-helmet"]["protection_type"], "Helmet")
        self.assertIn("Protection", tgm.PARTS)


class HtmlStoreTests(unittest.TestCase):
    def test_no_guessed_urls_until_the_owner_confirms_them(self):
        parts = {(scraper.name, scraper.part) for scraper in build_scrapers()}
        self.assertIn(("CCS", "Protection"), parts)
        self.assertIn(("TGM", "Protection"), parts)
        if not zumiez.PROTECTION_URLS:
            self.assertNotIn(("Zumiez", "Protection"), parts)
        if not tactics.PROTECTION_URL:
            self.assertNotIn(("Tactics", "Protection"), parts)
        if not skatewarehouse.PROTECTION_URLS:
            self.assertNotIn(("SkateWarehouse", "Protection"), parts)

    def test_zumiez_and_tactics_use_the_confirmed_sale_pages(self):
        from pathlib import Path
        parts = {(scraper.name, scraper.part): scraper for scraper in build_scrapers()}
        self.assertEqual(parts["Zumiez", "Protection"].urls,
                         ["https://www.zumiez.com/skate/helmets-pads.html?customFilters=promotion_flag:Sale"])
        self.assertEqual(parts["Tactics", "Protection"].url, "https://www.tactics.com/protective-skate-gear/sale")
        robots = (Path(__file__).resolve().parent / "tests" / "fixtures" / "zumiez_robots.txt").read_text()
        self.assertTrue(zumiez.explicitly_allowed(zumiez.star_rules(robots), zumiez.PROTECTION_URLS[0]))

    def test_skate_warehouse_uses_its_category_pages_with_a_markdown_required(self):
        scraper = next(s for s in build_scrapers() if (s.name, s.part) == ("SkateWarehouse", "Protection"))
        self.assertEqual(scraper.urls, [
            "https://www.skatewarehouse.com/helmets.html",
            "https://www.skatewarehouse.com/kneepads.html",
            "https://www.skatewarehouse.com/elbowpad.html",
            "https://www.skatewarehouse.com/wristguards.html",
        ])
        self.assertTrue(scraper.require_markdown, "full-price gear on these pages is never listed")

    def test_a_confirmed_url_adds_the_part(self):
        with mock.patch.object(zumiez, "PROTECTION_URLS", ("https://www.zumiez.com/example-protection.html",)):
            self.assertIn("Protection", [scraper.part for scraper in zumiez.scrapers()])
        with mock.patch.object(tactics, "PROTECTION_URL", "https://www.tactics.com/example/sale"):
            self.assertIn("Protection", [scraper.part for scraper in tactics.scrapers()])
        with mock.patch.object(skatewarehouse, "PROTECTION_URLS", ("https://www.skatewarehouse.com/example.html",)):
            scraper = next(s for s in skatewarehouse.scrapers() if s.part == "Protection")
            self.assertTrue(scraper.require_markdown)

    def test_skate_warehouse_parser_passes_gear_to_the_filters(self):
        html = """
        <a href="/Triple_Eight_Helmet/descpage-T8H.html">Triple Eight Sweatsaver Helmet $39.95 $54.95</a>
        <a href="/Thrasher_Shorts/descpage-TS.html">Thrasher Shorts $19.95 $39.95</a>
        <a href="/Pro_Tec_Knee/descpage-PTK.html">Pro-Tec Street Knee Pads $24.95</a>
        """
        scraper = skatewarehouse.SkateWarehouseScraper("SkateWarehouse", "https://www.skatewarehouse.com/x.html",
                                                       "Protection", require_markdown=True)
        with mock.patch.object(skatewarehouse, "save_debug_file"):
            items = scraper.parse(html)
        self.assertEqual([item["name"].split(" $")[0] for item in items], ["Triple Eight Sweatsaver Helmet"])


def _gear(name, store, sizes=None, url=None, price="29.99", old="44.99"):
    item = {"name": name, "url": url or f"https://shop.ccs.com/products/{abs(hash(name))}", "price_new": price,
            "price_old": old, "part": "Protection", "store": store}
    if sizes is not None:
        item["protection_sizes"] = sizes
    return item


class PageTests(unittest.TestCase):
    def test_protection_chip_filters_and_attributes(self):
        gear = [
            _gear("Pro-Tec Classic Helmet", "CCS", ["M", "L"]),
            _gear("Triple Eight Sweatsaver Helmet", "CCS", ["S"]),
            _gear("187 Killer Pads Knee Pads", "CCS", ["M"]),
            _gear("Smith Scabs Elbow Pads", "CCS", ["L"]),
            _gear("Triple Eight Wristsaver Wrist Guards Small", "CCS"),
            _gear("TSG Pad Set", "CCS", []),
            _gear("187 Impact Shorts", "CCS", ["XL"]),
        ]
        html = build_report_html({"CCS_Protection": gear}, {}, generated_at="2026-10-27T12:00:00+00:00")
        self.assertIn('data-part="Protection"', html)
        self.assertIn('data-section="prottype"', html)
        self.assertIn('data-section="protsize"', html)
        row = re.search(r'<tr[^>]*data-name="Pro-Tec Classic Helmet"[^>]*>', html).group(0)
        self.assertIn('data-prottype="helmet"', row)
        self.assertIn('data-protsize="m,l"', row)
        # No size list from the store: sizes printed in the name are used.
        wrist = re.search(r'<tr[^>]*data-name="Triple Eight Wristsaver Wrist Guards Small"[^>]*>', html).group(0)
        self.assertIn('data-protsize="s"', wrist)
        self.assertIn('data-prottype="wrist"', wrist)

    def test_few_listings_hide_the_spec_sections(self):
        html = build_report_html({"CCS_Protection": [_gear("Pro-Tec Classic Helmet", "CCS", ["M"])]}, {},
                                 generated_at="2026-10-27T12:00:00+00:00")
        self.assertNotIn('data-section="prottype"', html)

    def test_query_round_trip(self):
        state = decode_query("type=protection&prottype=wrist,helmet,nope&protsize=xl,m,huge")
        self.assertEqual(state["prot_types"], ["helmet", "wrist"])
        self.assertEqual(state["prot_sizes"], ["m", "xl"])
        self.assertEqual(decode_query(encode_state(state))["prot_types"], ["helmet", "wrist"])


if __name__ == "__main__":
    unittest.main()
