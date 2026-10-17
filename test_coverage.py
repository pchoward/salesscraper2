"""Sneaker, bearing, and accessory parsers plus the Products row. No network."""

import os
import unittest

from health import broken_store_warnings, record_run
from query_state import decode_query, encode_state
from report import build_report_html
from stores.ccs import CCSCatalogScraper, apply_stock, enrich_stock, load_clearance_products, product_js_url
from stores.skatewarehouse import SkateWarehouseScraper
from stores.tactics import TacticsScraper
from stores.zumiez import ZumiezScraper

FIXTURE = os.path.join(os.path.dirname(__file__), "tests", "fixtures")


def _read(name):
    with open(os.path.join(FIXTURE, name), encoding="utf-8") as handle:
        return handle.read()


def _names(scraper, html):
    return sorted(item["name"] for item in scraper.parse(html))


class StoreFixtureTests(unittest.TestCase):
    def test_zumiez_cards(self):
        html = _read("zumiez_sale_cards.html")
        bearings = _names(ZumiezScraper("Zumiez", "https://www.zumiez.com/bearings", "Bearings"), html)
        sneakers = _names(ZumiezScraper("Zumiez", "https://www.zumiez.com/shoes", "Sneakers"), html)
        accessories = _names(ZumiezScraper("Zumiez", "https://www.zumiez.com/hardware", "Accessories"), html)
        self.assertEqual(bearings, ["Bones Reds Bearings"])
        self.assertEqual(
            sneakers,
            ["Nike SB Dunk Low Pro US 10", "Vans Skate Half Cab Wafflecup Shoes"],
        )
        self.assertEqual(accessories, ["Mob Grip Tape"])

    def test_tactics_cards(self):
        html = _read("tactics_sale_cards.html")
        bearings = _names(TacticsScraper("Tactics", "https://www.tactics.com/bearings", "Bearings"), html)
        sneakers = _names(TacticsScraper("Tactics", "https://www.tactics.com/shoes", "Sneakers"), html)
        accessories = _names(TacticsScraper("Tactics", "https://www.tactics.com/accessories", "Accessories"), html)
        self.assertEqual(bearings, ["Bones Reds Bearings"])
        self.assertEqual(sneakers, ["Nike SB Dunk High Pro", "Vans Skate Half Cab Wafflecup Shoes"])
        self.assertEqual(accessories, ["CCS Phillips Hardware"])

    def test_skatewarehouse_markdown_and_clearance_shoes(self):
        html = _read("skatewarehouse_sale_links.html")
        bearings = SkateWarehouseScraper("SkateWarehouse", "https://www.skatewarehouse.com/bearings.html", "Bearings", require_markdown=True)
        sneakers = SkateWarehouseScraper("SkateWarehouse", "https://www.skatewarehouse.com/shoes", "Sneakers")
        accessories = SkateWarehouseScraper("SkateWarehouse", "https://www.skatewarehouse.com/hardware.html", "Accessories", require_markdown=True)
        self.assertEqual(_names(bearings, html), ["Bronson Speed Co. G3 Bearings"])
        self.assertEqual(
            _names(sneakers, html),
            ["Nike SB Dunk Low Pro", "Vans Skate Rizzo Half Cab Wafflecup Shoes"],
        )
        self.assertEqual(_names(accessories, html), ["Bones Hardcore Bushings", "Mob Grip Tape"])

    def test_ccs_clearance_cards_and_catalog_description(self):
        html = _read("ccs_clearance_cards.html")
        bearings = _names(CCSCatalogScraper("Bearings"), html)
        sneakers = CCSCatalogScraper("Sneakers").parse(html)
        accessories = _names(CCSCatalogScraper("Accessories"), html)
        self.assertEqual(bearings, ["Bones Swiss Bearings", "Bronson x Black Sabbath G3 Bearings"])
        by_name = {item["name"]: item for item in sneakers}
        self.assertEqual(
            sorted(by_name),
            ["Nike SB Dunk Low Pro", "Vans Skate Kyle Walker"],
        )
        self.assertEqual(by_name["Vans Skate Kyle Walker"]["shoe_sizes"], ["10", "10.5"])
        self.assertEqual(by_name["Vans Skate Kyle Walker"]["price_new"], "79.95")
        self.assertEqual(by_name["Nike SB Dunk Low Pro"]["shoe_sizes"], ["9"])
        self.assertEqual(by_name["Nike SB Dunk Low Pro"]["price_new"], "89.95")
        self.assertEqual(
            accessories,
            ["CCS Bearing Spacers", "CCS Phillips 1 inch", "Mob Grip Tape", "RipTide Longboard Bushings"],
        )
        described = CCSCatalogScraper("Sneakers").products_from([
            {
                "title": "Vans Skate Old Skool",
                "handle": "old-skool",
                "product_type": "Shoes",
                "body_html": "<p>The Wafflecup sole.</p>",
                "variants": [
                    {"title": "US 11", "price": "60.00", "compare_at_price": "85.00", "available": True},
                    {"title": "10.0", "option1": "10.0", "price": "60.00", "compare_at_price": "85.00", "available": True},
                    {"title": "9.5", "option1": "9.5", "price": "20.00", "compare_at_price": "85.00", "available": False},
                ],
            },
            {
                "title": "Nike SB Zoom Blazer",
                "handle": "blazer",
                "product_type": "Shoes",
                "variants": [{"title": "10", "price": "70.00", "compare_at_price": "90.00", "available": True}],
            },
        ])
        self.assertEqual([item["name"] for item in described], ["Vans Skate Old Skool"])
        self.assertEqual(described[0]["shoe_sizes"], ["10", "11"])

    def test_catalog_fetch_failure_is_not_an_empty_sale(self):
        self.assertIsNone(load_clearance_products(lambda url: None))
        calls = []

        def fetch(url):
            calls.append(url)
            if "page=1" in url:
                return {"products": [{"title": "Bones Reds Bearings", "handle": "bones", "product_type": "Bearings"}]}
            return None

        products = load_clearance_products(fetch)
        self.assertEqual(len(products), 1)
        self.assertEqual(len(calls), 1)


class InStockVariantTests(unittest.TestCase):
    def test_sold_out_sizes_are_omitted_and_do_not_set_the_price(self):
        items = CCSCatalogScraper("Sneakers").products_from([
            {
                "title": "Vans BMX Proof Wafflecup Shoes - Black/Black",
                "handle": "vans-bmx-proof-wafflecup-shoes-black-black",
                "product_type": "Shoes",
                "body_html": "<p>Available in men's size 9.5.</p>",
                "variants": [
                    {"id": 1, "title": "9.5", "option1": "9.5", "price": "40.00", "compare_at_price": "90.00", "available": False},
                    {"id": 2, "title": "8.0", "option1": "8.0", "price": "63.00", "compare_at_price": "90.00", "available": True},
                    {"id": 3, "title": "7.5", "option1": "7.5", "price": "70.00", "compare_at_price": "100.00", "available": True},
                ],
            }
        ])
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["shoe_sizes"], ["7.5", "8"])
        self.assertEqual(items[0]["price_new"], "63.00")
        self.assertEqual(items[0]["price_old"], "90.00")
        self.assertEqual(items[0]["shoe_prices"], {"7.5": "70.00", "8": "63.00"})
        self.assertEqual(items[0]["shoe_compares"], {"7.5": "100.00", "8": "90.00"})

    def test_products_json_without_available_does_not_invent_sizes(self):
        items = CCSCatalogScraper("Sneakers").products_from([
            {
                "title": "Vans BMX Proof Wafflecup Shoes - Black/Black",
                "handle": "proof",
                "product_type": "Shoes",
                "variants": [
                    {"id": 1, "title": "9.5", "option1": "9.5", "price": "63.00", "compare_at_price": "90.00"},
                    {"id": 2, "title": "8.0", "option1": "8.0", "price": "63.00", "compare_at_price": "90.00"},
                ],
            }
        ])
        self.assertEqual(len(items), 1)
        self.assertNotIn("shoe_sizes", items[0])
        self.assertEqual(items[0]["price_new"], "63.00")

    def test_js_available_flag_is_joined_by_variant_id(self):
        product = {
            "title": "Vans BMX Proof Wafflecup Shoes - Black/Black",
            "handle": "vans-bmx-proof-wafflecup-shoes-black-black",
            "product_type": "Shoes",
            "variants": [
                {"id": 11, "title": "9.5", "option1": "9.5", "price": "40.00", "compare_at_price": "90.00"},
                {"id": 12, "title": "8", "option1": "8", "price": "63.00", "compare_at_price": "90.00"},
            ],
        }
        seen = []

        def fetch(url):
            seen.append(url)
            return {"variants": [{"id": 11, "available": False}, {"id": 12, "available": True}]}

        enrich_stock([product], "Sneakers", fetch)
        self.assertEqual(seen, [product_js_url(product["handle"])])
        self.assertNotIn("graphql", seen[0])
        items = CCSCatalogScraper("Sneakers").products_from([product])
        self.assertEqual(items[0]["shoe_sizes"], ["8"])
        self.assertEqual(items[0]["price_new"], "63.00")
        self.assertNotIn("shoe_prices", items[0])

    def test_a_sold_out_variant_does_not_set_another_parts_price(self):
        items = CCSCatalogScraper("Bearings").products_from([
            {
                "title": "Bones Reds Bearings",
                "handle": "bones-reds",
                "product_type": "Bearings",
                "variants": [
                    {"id": 1, "title": "Default Title", "price": "10.00", "compare_at_price": "30.00", "available": False},
                    {"id": 2, "title": "Default Title", "price": "24.00", "compare_at_price": "30.00", "available": True},
                ],
            },
            {
                "title": "Bronson G3 Bearings",
                "handle": "bronson-gone",
                "product_type": "Bearings",
                "variants": [
                    {"id": 3, "title": "Default Title", "price": "20.00", "compare_at_price": "40.00", "available": False},
                ],
            },
        ])
        self.assertEqual([item["name"] for item in items], ["Bones Reds Bearings"])
        self.assertEqual(items[0]["price_new"], "24.00")

    def test_apply_stock_matches_string_and_int_ids(self):
        product = {"variants": [{"id": 5, "title": "9.5"}, {"id": "6", "title": "8"}]}
        apply_stock(product, {"variants": [{"id": "5", "available": False}, {"id": 6, "available": True}]})
        self.assertIs(product["variants"][0]["available"], False)
        self.assertIs(product["variants"][1]["available"], True)

    def test_report_size_filter_uses_in_stock_sizes_and_their_prices(self):
        proof = {
            "name": "Vans BMX Proof Wafflecup Shoes - Black/Black",
            "url": "https://shop.ccs.com/products/proof",
            "price_new": "63.00",
            "price_old": "90.00",
            "part": "Sneakers",
            "store": "CCS",
            "description": "men's size 9.5",
            "shoe_sizes": ["7.5", "8"],
        }
        priced = {
            "name": "Vans Skate Half Cab Wafflecup Shoes",
            "url": "https://shop.ccs.com/products/half-cab",
            "price_new": "50.00",
            "price_old": "80.00",
            "part": "Sneakers",
            "store": "CCS",
            "shoe_sizes": ["8", "9.5"],
            "shoe_prices": {"8": "50.00", "9.5": "70.00"},
            "shoe_compares": {"8": "80.00", "9.5": "100.00"},
        }
        html = build_report_html(
            {"CCS_Sneakers": [proof, priced]},
            {},
            generated_at="2026-10-17T12:00:00+00:00",
        )
        proof_row = html.split("data-url=\"https://shop.ccs.com/products/proof\"", 1)[1].split(">", 1)[0]
        priced_row = html.split("data-url=\"https://shop.ccs.com/products/half-cab\"", 1)[1].split(">", 1)[0]
        self.assertIn('data-shoesize="7.5,8"', proof_row)
        self.assertNotIn("9.5", proof_row)
        self.assertIn('data-shoesize="8,9.5"', priced_row)
        self.assertIn('data-shoeprices="8:50.00,9.5:70.00"', priced_row)
        self.assertIn('data-shoecompares="8:80.00,9.5:100.00"', priced_row)
        self.assertIn(">Now: $50.00<", html)
        self.assertIn(">$50.00<", html)


class ReportCoverageTests(unittest.TestCase):
    def test_query_round_trip_for_sneakers_and_size(self):
        state = decode_query("type=sneaker&shoesize=10.5,10&brand=Vans")
        self.assertEqual(state["part"], "Sneakers")
        self.assertEqual(state["shoe_sizes"], ["10", "10.5"])
        again = decode_query(encode_state(state))
        self.assertEqual(again["part"], "Sneakers")
        self.assertEqual(again["shoe_sizes"], ["10", "10.5"])
        self.assertEqual(decode_query("")["part"], "Decks")
        self.assertEqual(decode_query("type=accessory")["part"], "Accessories")

    def test_products_row_shows_a_part_only_when_it_has_items(self):
        sized = []
        for index, size in enumerate(["9", "9.5", "10", "10.5", "11"]):
            sized.append({
                "name": f"Vans Skate Half Cab Wafflecup Shoes US {size}",
                "url": f"https://example.com/shoe-{index}",
                "price_new": "59.95",
                "price_old": "85.00",
                "part": "Sneakers",
                "store": "CCS",
                "shoe_sizes": [size],
            })
        sized.append({
            "name": "Nike SB Dunk Low Pro",
            "url": "https://example.com/dunk",
            "price_new": "89.95",
            "price_old": "115.00",
            "part": "Sneakers",
            "store": "Zumiez",
        })
        full = build_report_html(
            {
                "CCS_Bearings": [{
                    "name": "Bones Reds Bearings",
                    "url": "https://example.com/bones",
                    "price_new": "24.95",
                    "price_old": "34.95",
                    "part": "Bearings",
                    "store": "CCS",
                }],
                "CCS_Sneakers": sized,
                "Zumiez_Accessories": [{
                    "name": "Mob Grip Tape",
                    "url": "https://example.com/grip",
                    "price_new": "4.95",
                    "price_old": "7.95",
                    "part": "Accessories",
                    "store": "Zumiez",
                }],
            },
            {},
            generated_at="2026-10-17T12:00:00+00:00",
        )
        row = full.split('id="partFilters"', 1)[1].split("</select>", 1)[0]
        self.assertIn('data-part="Bearings"', row)
        self.assertIn('data-part="Sneakers"', row)
        self.assertIn('data-part="Accessories"', row)
        self.assertIn('data-section="shoesize"', full)
        self.assertIn('data-shoesize="10"', full)
        self.assertIn('data-brand="Nike SB"', full)
        decks = build_report_html(
            {
                "Zumiez_Decks": [{
                    "name": "Baker Logo Deck 8.25",
                    "url": "https://example.com/deck",
                    "price_new": "40.00",
                    "price_old": "70.00",
                    "part": "Decks",
                    "store": "Zumiez",
                }],
            },
            {},
            generated_at="2026-10-17T12:00:00+00:00",
        )
        deck_row = decks.split('id="partFilters"', 1)[1].split("</select>", 1)[0]
        self.assertIn('data-part="Decks"', deck_row)
        self.assertNotIn('data-part="Bearings"', deck_row)
        self.assertNotIn('data-part="Sneakers"', deck_row)
        self.assertNotIn('data-section="shoesize"', decks)

    def test_four_parsed_sizes_do_not_open_the_size_section(self):
        items = []
        for index, size in enumerate(["8", "9", "10", "11"]):
            items.append({
                "name": f"Vans Wafflecup Shoes size {size}",
                "url": f"https://example.com/few-{index}",
                "price_new": "50.00",
                "price_old": "80.00",
                "part": "Sneakers",
                "store": "CCS",
            })
        html = build_report_html(
            {"CCS_Sneakers": items},
            {},
            generated_at="2026-10-17T12:00:00+00:00",
        )
        self.assertNotIn('data-section="shoesize"', html)
        self.assertIn('data-shoesize="10"', html)


class QuietCategoryTests(unittest.TestCase):
    def test_new_categories_that_stay_empty_do_not_warn(self):
        state = {"runs": [], "baseline": {}}
        for offset in range(4):
            day = f"2026-10-{offset + 1:02d}"
            state = record_run(
                state,
                day,
                {
                    "Zumiez_Sneakers": {"count": 0, "failed": False},
                    "CCS_Accessories": {"count": 0, "failed": False},
                    "SkateWarehouse_Bearings": {"count": 0, "failed": False},
                },
            )
        self.assertEqual(broken_store_warnings(state), [])
        state = record_run(
            state,
            "2026-10-05",
            {"Zumiez_Sneakers": {"count": 0, "failed": True}},
        )
        state = record_run(
            state,
            "2026-10-06",
            {"Zumiez_Sneakers": {"count": 0, "failed": True}},
        )
        keys = {warning["key"] for warning in broken_store_warnings(state)}
        self.assertEqual(keys, {"Zumiez_Sneakers"})
        self.assertNotIn("CCS_Accessories", keys)
