"""TGM Skateboards: product-type routing, compare-at sale rule, deck sizes, paging."""

import unittest
from pathlib import Path

from filters import extract_deck_dimensions, extract_deck_size, filter_reason
from stores import tgm
from stores.registry import build_scrapers


def variant(price, compare, vid=1, title="Default Title", available=None, option1=None):
    out = {"id": vid, "title": title, "price": price, "compare_at_price": compare}
    if available is not None:
        out["available"] = available
    if option1 is not None:
        out["option1"] = option1
    return out


def product(title, product_type, variants, handle=None, vendor="", body=""):
    return {
        "title": title,
        "handle": handle or title.lower().replace('"', "").replace(" ", "-"),
        "vendor": vendor,
        "product_type": product_type,
        "body_html": body,
        "images": [{"src": f"https://cdn.shopify.com/{(handle or 'x')}.jpg"}],
        "variants": variants,
    }


CATALOG = [
    product('Heroin Egg Shaped Deck 9.75" x 32"', "Decks", [variant("59.99", "84.99")], handle="heroin-egg-975"),
    product('Santa Cruz Classic Dot 10.34" x 30.54"', "Decks", [variant("49.99", "74.99")], handle="santa-cruz-dot-1034"),
    product('Heroin Symbiote 10.4"x32.25"', "Decks", [variant("59.99", "79.99")], handle="heroin-symbiote"),
    product('Baker Brand Logo Deck 8.25"', "Decks", [variant("64.99", "64.99")], handle="baker-full-price"),
    product('Baker Brand Logo Deck 8.5"', "Decks", [variant("54.99", None)], handle="baker-no-compare"),
    product('Baker Brand Logo Deck 8.38"', "Decks", [variant("74.99", "64.99")], handle="baker-compare-below"),
    product('Hockey Cruiser Deck 9.0" x 31"', "Decks", [variant("39.99", "69.99")], handle="hockey-cruiser"),
    product('Arbor Pin Deck 9.5" x 38"', "Decks", [variant("39.99", "89.99")], handle="arbor-38"),
    product("Real Oval Deck", "Decks", [variant("49.99", "64.99", 11, '8.25"'), variant("51.99", "64.99", 12, '8.5"')],
            handle="real-oval"),
    product('Polar Big Boy 9.5" Deck', "Decks", [variant("49.99", "79.99", available=False)], handle="polar-sold-out"),
    product("Formula Four Classic 54mm 99a", "Wheels", [variant("39.99", "54.99")], vendor="Spitfire", handle="f4-54"),
    product("Cheap Brand 52mm Wheels", "Wheels", [variant("19.99", "29.99")], handle="cheap-wheels"),
    product("Independent Stage 11 Trucks 144", "Trucks", [variant("49.99", "64.99")], handle="indy-144"),
    product("Bones Reds Bearings", "Bearings", [variant("14.99", "21.99")], handle="bones-reds"),
    product("Mob Grip Tape 9x33", "Grip Tape", [variant("7.99", "11.99")], handle="mob-grip"),
    product("Diamond 1in Hardware Allen", "Hardware", [variant("2.99", "4.99")], handle="diamond-hardware"),
    product("Independent Replacement Hanger", "Hardware", [variant("19.99", "29.99")], handle="indy-hanger"),
    product('Element Section Complete Skateboard 8.0" x 31.75"', "Completes", [variant("69.99", "99.99")],
            handle="element-complete"),
    product('Globe Cruiser Complete 9.0"', "Completes", [variant("59.99", "99.99")], handle="globe-cruiser-complete"),
    product("Vans Skate Wafflecup Shoes", "Mens Shoes",
            [variant("54.99", "79.99", 21, "9", True, "9"), variant("54.99", "79.99", 22, "10", False, "10")],
            handle="vans-wafflecup"),
    product("Vans Old Skool Shoes", "Mens Shoes", [variant("44.99", "69.99")], handle="vans-old-skool"),
    product("Thrasher Flame Hoodie", "Mens Clothing", [variant("39.99", "64.99")], handle="thrasher-hoodie"),
    product('Deck Disc Golf Driver 9"', "Disc", [variant("9.99", "19.99")], handle="disc-driver"),
    product("Roller Hockey Wheels 72mm", "Roller Hockey", [variant("19.99", "39.99")], handle="hockey-wheels"),
]


def kept(part, catalog=CATALOG):
    return {item["url"].rsplit("/", 1)[1]: item for item in tgm.TGMScraper(part).products_from(catalog)}


class ProductTypeTests(unittest.TestCase):
    def test_types_route_to_parts_and_everything_else_is_skipped(self):
        cases = {
            "Decks": "Decks", "Wheels": "Wheels", "Trucks": "Trucks", "Bearings": "Bearings",
            "Grip Tape": "Accessories", "grip  tape": "Accessories", "Hardware": "Accessories",
            "Completes": "Completes", "Mens Shoes": "Sneakers", "Men's Shoes": "Sneakers",
            "Risers": "Accessories", "Tool": "Accessories", "Womens Shoes": None, "Starter Sets": None,
            "Mens Clothing": None, "Disc": None, "Roller Hockey": None, "": None, None: None,
        }
        for kind, part in cases.items():
            self.assertEqual(tgm.part_for_type(kind), part, kind)

    def test_other_types_never_become_candidates(self):
        everything = [url for part in tgm.PARTS for url in kept(part)]
        for handle in ("thrasher-hoodie", "disc-driver", "hockey-wheels"):
            self.assertNotIn(handle, everything)
        # A "Deck" in the name does not make a Disc product a deck.
        self.assertNotIn("disc-driver", kept("Decks"))


class SaleRuleTests(unittest.TestCase):
    def test_only_compare_at_above_price_is_a_sale(self):
        decks = kept("Decks")
        for handle in ("baker-full-price", "baker-no-compare", "baker-compare-below"):
            self.assertNotIn(handle, decks)
        deck = decks["heroin-egg-975"]
        self.assertEqual((deck["price_new"], deck["price_old"]), ("59.99", "84.99"))

    def test_a_variant_the_feed_says_is_sold_out_is_not_listed(self):
        self.assertNotIn("polar-sold-out", kept("Decks"))


class DeckSizeTests(unittest.TestCase):
    def test_titles_with_width_and_length_parse(self):
        self.assertEqual(extract_deck_dimensions('Heroin Egg Shaped Deck 9.75" x 32"'), (9.75, 32.0))
        self.assertEqual(extract_deck_dimensions('Santa Cruz Classic Dot 10.34" x 30.54"'), (10.34, 30.54))
        # Inch marks touching the x used to lose the length, or read ".25" as 25.
        self.assertEqual(extract_deck_dimensions('Heroin Symbiote 10.4"x32.25"'), (10.4, 32.25))
        self.assertEqual(extract_deck_dimensions("Polar Big Boy 9.5”x32”"), (9.5, 32.0))
        self.assertEqual(extract_deck_dimensions('Welcome 9.75"X32.5"'), (9.75, 32.5))
        self.assertEqual(extract_deck_dimensions("Real Oval 8.25 x 31.8"), (8.25, 31.8))
        self.assertEqual(extract_deck_size('Santa Cruz Classic Dot 10.34" x 30.54"'), "10.34")

    def test_wide_street_decks_stay_and_cruisers_and_longboards_go(self):
        decks = kept("Decks")
        for handle, size in (("heroin-egg-975", "9.75"), ("santa-cruz-dot-1034", "10.34"), ("heroin-symbiote", "10.4")):
            self.assertIn(handle, decks)
            self.assertEqual(decks[handle]["size"], size)
        self.assertEqual(decks["heroin-symbiote"]["length"], 32.25)
        self.assertNotIn("hockey-cruiser", decks)
        self.assertNotIn("arbor-38", decks, "38 inches long is a longboard")
        self.assertEqual(filter_reason('Hockey Cruiser Deck 9.0" x 31"', "Decks", "", "39.99", "69.99"), "cruiser")

    def test_width_variants_become_separate_listings(self):
        decks = kept("Decks")
        self.assertIn("real-oval?variant=11", decks)
        self.assertIn("real-oval?variant=12", decks)
        self.assertEqual(decks["real-oval?variant=12"]["name"], 'Real Oval Deck 8.5"')
        self.assertEqual(decks["real-oval?variant=12"]["price_new"], "51.99")


class OtherPartTests(unittest.TestCase):
    def test_wheels_trucks_bearings_use_the_brand_lists(self):
        wheels = kept("Wheels")
        self.assertEqual(wheels["f4-54"]["name"], "Spitfire Formula Four Classic 54mm 99a", "vendor added for the brand check")
        # A title that already names the brand does not get the vendor twice.
        for vendor, title in (("OJ Wheels", "OJ III Wheels 56mm Elite Mini Combo 101A"),
                              ("Ace Trucks MFG", "Ace Skateboard Trucks AF1 66 Pair")):
            self.assertEqual(tgm._title({"title": title, "vendor": vendor}), title)
        self.assertEqual(tgm._title({"title": "Mid Pro Hollow 159", "vendor": "Independent Trucks"}),
                         "Independent Trucks Mid Pro Hollow 159")
        self.assertNotIn("cheap-wheels", wheels)
        self.assertIn("indy-144", kept("Trucks"))
        self.assertIn("bones-reds", kept("Bearings"))

    def test_bundled_brands_do_not_pass_the_brand_check(self):
        name = "Satori Skateboard Wheels 54mm Spencer Hamilton Canada Conical 101A with Spitfire Bearings"
        self.assertEqual(filter_reason(name, "Wheels", "", "31.95", "59.95"), "wheel brand not allowed")
        self.assertIsNone(filter_reason("Spitfire Formula Four 54mm with Free Sticker", "Wheels", "", "31.95", "59.95"))

    def test_risers_and_tools_are_accessories(self):
        self.assertEqual(tgm.part_for_type("Risers"), "Accessories")
        self.assertEqual(tgm.part_for_type("Tool"), "Accessories")

    def test_grip_and_hardware_are_accessories_but_truck_parts_are_not(self):
        accessories = kept("Accessories")
        self.assertIn("mob-grip", accessories)
        self.assertIn("diamond-hardware", accessories)
        self.assertNotIn("indy-hanger", accessories)

    def test_completes_use_the_deck_rules(self):
        completes = kept("Completes")
        self.assertIn("element-complete", completes)
        self.assertEqual(completes["element-complete"]["part"], "Completes")
        self.assertNotIn("globe-cruiser-complete", completes)
        self.assertIsNone(filter_reason('Element Section Complete 8.0"', "Completes", "", "69.99", "99.99"))
        self.assertEqual(filter_reason('Mini Complete 7.0"', "Completes", "", "29.99", "59.99"), 'mini width 7" (< 7.5")')

    def test_shoes_only_from_the_sneaker_allowlist_with_in_stock_sizes(self):
        shoes = kept("Sneakers")
        self.assertEqual(list(shoes), ["vans-wafflecup"])
        self.assertEqual(shoes["vans-wafflecup"]["shoe_sizes"], ["9"])


class FeedTests(unittest.TestCase):
    def test_pages_until_a_short_page_with_a_pause_between_requests(self):
        pages = {1: [product(f"P{n}", "Decks", [variant("1", "2")]) for n in range(250)],
                 2: [product(f"Q{n}", "Decks", [variant("1", "2")]) for n in range(250)],
                 3: [product("Last", "Decks", [variant("1", "2")])]}
        urls, pauses = [], []

        def fetch(url):
            urls.append(url)
            return {"products": pages[int(url.rsplit("page=", 1)[1])]}

        products = tgm.load_sale_products(fetch, sleep=pauses.append)
        self.assertEqual(len(products), 501)
        self.assertEqual(urls, [f"{tgm.SALE_JSON}?limit=250&page={n}" for n in (1, 2, 3)])
        self.assertEqual(pauses, [tgm.PAGE_DELAY, tgm.PAGE_DELAY])
        for url in urls:
            self.assertNotIn("sort_by", url)
            self.assertNotIn("filter.", url)

    def test_an_empty_page_ends_the_feed_and_a_failed_page_fails_the_run(self):
        full = [product(f"P{n}", "Decks", [variant("1", "2")]) for n in range(250)]
        self.assertEqual(len(tgm.load_sale_products(lambda url: {"products": full if url.endswith("page=1") else []},
                                                    sleep=lambda _s: None)), 250)
        self.assertIsNone(tgm.load_sale_products(lambda url: None, sleep=lambda _s: None))
        self.assertIsNone(tgm.load_sale_products(lambda url: {"products": full}, sleep=lambda _s: None),
                          "a feed that never ends is a failure, not 5,000 listings")

    def test_parse_reads_a_saved_products_json(self):
        import json
        items = tgm.TGMScraper("Decks").parse(json.dumps({"products": CATALOG}))
        self.assertIn("https://tgmskateboards.com/products/heroin-egg-975", [item["url"] for item in items])
        self.assertEqual(tgm.TGMScraper("Decks").parse("<html></html>"), [])


class WiringTests(unittest.TestCase):
    def test_every_part_runs_in_the_daily_scrape(self):
        parts = {scraper.part for scraper in build_scrapers() if scraper.name == "TGM"}
        self.assertEqual(parts, set(tgm.PARTS))

    def test_tgm_is_a_store_chip_and_has_slugs_colors_and_alert_hosts(self):
        root = Path(__file__).resolve().parent
        page_js = (root / "page.js").read_text(encoding="utf-8")
        self.assertIn('tgm: "TGM"', page_js)
        self.assertIn('TGM: "tgm"', page_js)
        self.assertIn('"tgmskateboards.com"', page_js)
        self.assertIn(".store-tgm {", (root / "page.css").read_text(encoding="utf-8"))
        self.assertIn('"TGM")', (root / "page.py").read_text(encoding="utf-8"))
        from query_state import STORE_SLUGS, TYPE_SLUGS
        from site_sales import DISPLAY_NAMES, STORES
        self.assertEqual(STORE_SLUGS["tgm"], "TGM")
        self.assertEqual(TYPE_SLUGS["completes"], "Completes")
        self.assertIn("TGM", STORES)
        self.assertEqual(DISPLAY_NAMES["TGM"], "TGM Skateboards")


if __name__ == "__main__":
    unittest.main()
