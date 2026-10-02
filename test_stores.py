"""Store parsers, isolated runs, and the backup-cron gate. No network."""

import datetime
import json
import os
import tempfile
import time
import unittest
from zoneinfo import ZoneInfo

from report import Digest, build_report_html
from schedule import BACKUP_CRON, already_succeeded_today, gate_should_scrape
from site_sales import activity_line, describe_sales, empty_state
from stores.muirskate import DISABLED_REASON, ENABLED, MuirSkateScraper
from stores.skatedeluxe import DISABLED_REASON as DELUXE_REASON
from stores.skatedeluxe import ENABLED as DELUXE_ENABLED
from stores.registry import build_scrapers
from stores.zumiez import ZumiezScraper, grid_loaded
from stores.runner import run_stores
from stores.skatedeluxe import (
    SkateDeluxeScraper,
    classify_part,
    page_progress,
    parse_euro,
)

FIXTURE = os.path.join(os.path.dirname(__file__), "tests", "fixtures")
EASTERN = ZoneInfo("America/New_York")


def _html():
    with open(os.path.join(FIXTURE, "skatedeluxe_sale.html"), encoding="utf-8") as handle:
        return handle.read()


def _muir():
    with open(os.path.join(FIXTURE, "muirskate_sale.json"), encoding="utf-8") as handle:
        return json.load(handle)


def _part(store_cls, part, payload):
    scraper = store_cls(part, catalog=None)
    if store_cls is SkateDeluxeScraper:
        return scraper.parse(payload)
    return scraper.parse_payload(payload)


class SkateDeluxeParserTests(unittest.TestCase):
    def setUp(self):
        self.html = _html()
        self.by_part = {
            part: _part(SkateDeluxeScraper, part, self.html)
            for part in ("Decks", "Wheels", "Trucks", "Bearings")
        }

    def test_euro_prices_and_sale_page_label(self):
        self.assertEqual(parse_euro("59,99 EUR"), "59.99")
        self.assertEqual(parse_euro("1.059,99 EUR"), "1059.99")
        self.assertEqual(page_progress(self.html), (1, 2))

    def test_known_brand_deck_is_kept_with_image_and_euros(self):
        decks = {item["name"]: item for item in self.by_part["Decks"]}
        kept = decks["Primitive Dirty P 8.25\" Skateboard Deck (black)"]
        self.assertEqual(kept["price_new"], "59.99")
        self.assertEqual(kept["price_old"], "69.99")
        self.assertEqual(kept["currency"], "EUR")
        self.assertEqual(kept["store"], "Skate Deluxe")
        self.assertEqual(kept["size"], "8.25")
        self.assertEqual(kept["image"], "https://cdn.skatedeluxe.com/product/184487-deck.jpg")
        self.assertEqual(kept["part"], "Decks")

    def test_discount_width_cruiser_and_longboard_rules(self):
        names = " ".join(item["name"] for item in self.by_part["Decks"])
        self.assertNotIn("Housebrand", names)
        self.assertNotIn("Baker", names)
        self.assertNotIn("Mini", names)
        self.assertNotIn("Cruiser", names)
        self.assertNotIn("Longboard", names)
        self.assertNotIn("Jacket", names)
        self.assertIsNone(classify_part("Volcom Hernan 10K Jacket"))
        self.assertEqual(classify_part("Globe Zuma 31\" Surf Skate Cruiser"), None)

    def test_wheels_trucks_and_bearings(self):
        wheels = [item["name"] for item in self.by_part["Wheels"]]
        trucks = [item["name"] for item in self.by_part["Trucks"]]
        bearings = [item["name"] for item in self.by_part["Bearings"]]
        self.assertEqual(wheels, ["Spitfire Formula Four Wheels 54mm"])
        self.assertEqual(trucks, ["Independent Stage 11 Truck 144"])
        self.assertEqual(bearings, ["Bones Bearings Reds Bearings"])
        self.assertTrue(bearings[0])
        self.assertEqual(self.by_part["Bearings"][0]["price_new"], "19.99")


class MuirParserTests(unittest.TestCase):
    def setUp(self):
        self.payload = _muir()
        self.by_part = {
            part: _part(MuirSkateScraper, part, self.payload)
            for part in ("Decks", "Wheels", "Trucks", "Bearings")
        }

    def test_street_parts_kept_and_longboards_cruisers_dropped(self):
        deck_names = [item["name"] for item in self.by_part["Decks"]]
        self.assertEqual(deck_names, ['Baker Brand Logo 8.25" Skateboard Deck'])
        deck = self.by_part["Decks"][0]
        self.assertEqual(deck["price_new"], "44.99")
        self.assertEqual(deck["price_old"], "64.95")
        self.assertEqual(deck["currency"], "USD")
        self.assertEqual(deck["image"], "https://cdn.shopify.com/s/files/baker-deck.jpg")
        self.assertEqual(deck["size"], "8.25")
        self.assertNotIn("longboard", " ".join(deck_names).lower())
        joined = " ".join(
            item["name"] for items in self.by_part.values() for item in items
        ).lower()
        self.assertNotIn("longboard", joined)
        self.assertNotIn("cruiser", joined)
        self.assertNotIn("mini logo", joined)
        self.assertNotIn("full price", joined)
        self.assertEqual([item["name"] for item in self.by_part["Wheels"]], ["Spitfire Formula Four 54mm Wheels"])
        self.assertEqual([item["name"] for item in self.by_part["Trucks"]], ["Independent Stage 11 144 Truck"])
        self.assertEqual([item["name"] for item in self.by_part["Bearings"]], ["Bones Reds Bearings"])

    def test_muir_and_skate_deluxe_stay_out_of_the_live_run(self):
        self.assertFalse(ENABLED)
        self.assertIn("unavailable", DISABLED_REASON.lower())
        self.assertFalse(DELUXE_ENABLED)
        self.assertIn("EUR-only European store", DELUXE_REASON)
        self.assertIn("2026-10-02", DELUXE_REASON)
        names = {scraper.name for scraper in build_scrapers()}
        self.assertIn("Zumiez", names)
        self.assertNotIn("Skate Deluxe", names)
        self.assertNotIn("Muir Skate", names)


class _Fake:
    def __init__(self, name, part, fn, candidates=2):
        self.name = name
        self.part = part
        self.fn = fn
        self.candidates = candidates

    def scrape(self):
        return self.fn()


class IsolationTests(unittest.TestCase):
    def test_one_part_failing_does_not_stop_the_run(self):
        def boom():
            raise RuntimeError("blocked")

        def ok():
            return [{"name": "kept"}]

        results, failed = run_stores(
            [
                _Fake("Zumiez", "Decks", boom),
                _Fake("Zumiez", "Wheels", ok),
                _Fake("CCS", "Decks", ok),
            ],
            timeout=30,
        )
        self.assertIsNone(results["Zumiez_Decks"])
        self.assertIn("Zumiez_Decks", failed)
        self.assertEqual(results["Zumiez_Wheels"], [{"name": "kept"}])
        self.assertEqual(results["CCS_Decks"], [{"name": "kept"}])
        self.assertNotIn("CCS_Decks", failed)
        self.assertNotIn("Zumiez_Wheels", failed)

    def test_store_timeout_does_not_stop_the_next_store(self):
        def ok():
            return [{"name": "kept"}]

        def slow():
            time.sleep(3)
            return [{"name": "late"}]

        results, failed = run_stores(
            [
                _Fake("Zumiez", "Decks", ok),
                _Fake("CCS", "Decks", slow),
                _Fake("Tactics", "Decks", ok),
            ],
            timeout=1,
        )
        self.assertEqual(results["Zumiez_Decks"], [{"name": "kept"}])
        self.assertIsNone(results["CCS_Decks"])
        self.assertIn("CCS_Decks", failed)
        self.assertEqual(results["Tactics_Decks"], [{"name": "kept"}])
        self.assertNotIn("Zumiez_Decks", failed)
        self.assertNotIn("Tactics_Decks", failed)


class BackupGateTests(unittest.TestCase):
    def _health(self, results, scanned_at):
        handle = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
        json.dump(
            {
                "runs": [
                    {
                        "date": "2026-10-02",
                        "scanned_at": scanned_at,
                        "results": results,
                    }
                ],
                "baseline": {},
            },
            handle,
        )
        handle.close()
        self.addCleanup(lambda: os.remove(handle.name))
        return handle.name

    def test_backup_skips_only_after_a_successful_eastern_day(self):
        now = datetime.datetime(2026, 10, 2, 9, 43, tzinfo=datetime.timezone.utc)
        path = self._health(
            {"Zumiez_Decks": {"count": 11, "failed": False}, "CCS_Decks": {"count": 0, "failed": True}},
            "2026-10-02T07:20:00+00:00",
        )
        self.assertTrue(already_succeeded_today(path, now=now))
        self.assertFalse(gate_should_scrape("schedule", BACKUP_CRON, path, now=now))
        self.assertTrue(gate_should_scrape("schedule", "17 7 * * *", path, now=now))
        self.assertTrue(gate_should_scrape("workflow_dispatch", "", path, now=now))

    def test_backup_runs_when_today_failed_or_is_missing(self):
        now = datetime.datetime(2026, 10, 2, 9, 43, tzinfo=EASTERN)
        failed = self._health({"Zumiez_Decks": {"count": 0, "failed": True}}, "2026-10-02T07:20:00+00:00")
        self.assertFalse(already_succeeded_today(failed, now=now))
        self.assertTrue(gate_should_scrape("schedule", "43 9 * * *", failed, now=now))
        missing = self._health({"Zumiez_Decks": {"count": 4, "failed": False}}, "2026-10-01T07:20:00+00:00")
        self.assertTrue(gate_should_scrape("schedule", BACKUP_CRON, missing, now=now))


class ZumiezEmptyPageTests(unittest.TestCase):
    def test_shell_page_is_not_a_real_empty_catalog(self):
        shell = "<html><a href='/skate/skateboard-decks.html'>Decks</a><p>You need to enable JavaScript</p></html>"
        self.assertFalse(grid_loaded(shell))
        self.assertFalse(grid_loaded(""))
        self.assertTrue(grid_loaded("<html><p class='CategoryPage-ItemsCount'>0 items found</p></html>"))
        card = (
            "<html><ul><li class='ProductCard ProductCard_layout_grid'>"
            "<a class='ProductCard-Link' href='/skate/deck.html'>"
            "<span class='ProductCard-Name'>Baker Figgy 8.25 Deck</span></a>"
            "<span class='ProductPrice-PriceValue'>$29.99</span>"
            "<span class='ProductCardPrice-HighPrice'>$64.99</span>"
            "</li></ul></html>"
        )
        self.assertTrue(grid_loaded(card))
        scraper = ZumiezScraper("Zumiez", "https://www.zumiez.com/example", "Decks")
        parsed = scraper.parse(card)
        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0]["store"], "Zumiez")
        self.assertEqual(parsed[0]["price_new"], "29.99")

    def test_zero_deal_store_card_stays_visible_with_a_warning(self):
        deck = {
            "name": "Baker Figgy Divine Evil Deck 8.25",
            "url": "https://example.com/ccs",
            "price_new": "40.00",
            "price_old": "60.00",
            "part": "Decks",
            "store": "CCS",
        }
        warning = {
            "store": "Zumiez",
            "part": "all categories",
            "kind": "suspect",
            "dates": ["2026-10-02"],
            "last_positive_date": "2026-10-01",
            "last_positive_count": 27,
        }
        html = build_report_html(
            {
                "Zumiez_Decks": [],
                "Zumiez_Wheels": [],
                "Zumiez_Trucks": [],
                "CCS_Decks": [deck],
            },
            {},
            generated_at="2026-10-02T11:38:00+00:00",
            digest=Digest(warnings=[warning]),
        )
        grid = html.split('class="stats-grid"', 1)[1].split('class="activity"', 1)[0]
        self.assertIn('data-store="Zumiez"', grid)
        zumiez = grid.split('data-store="Zumiez"', 1)[1].split("</button>", 1)[0]
        self.assertIn(">0<", zumiez)
        self.assertIn("warn-badge", zumiez)
        self.assertIn("Warning", zumiez)
        ccs = grid.split('data-store="CCS"', 1)[1].split("</button>", 1)[0]
        self.assertNotIn("warn-badge", ccs)
        self.assertIn("returned no items in any category", html)
        self.assertIn("marked suspect", html)


class RetailerActivityTests(unittest.TestCase):
    def test_new_stores_have_no_recorded_site_wide_sale(self):
        rows = {row["store"]: row for row in describe_sales(empty_state(), "2026-10-02")}
        self.assertIsNone(rows["Skate Deluxe"]["last_sale"])
        self.assertIsNone(rows["Muir Skate"]["last_sale"])
        self.assertIn("no recorded site-wide sale", activity_line(rows["Skate Deluxe"]))
        self.assertIn("no recorded site-wide sale", activity_line(rows["Muir Skate"]))
        self.assertEqual(rows["SkateWarehouse"]["last_sale"], "2026-07-04")


class SalePageTests(unittest.TestCase):
    """The three decks the owner found still on sale, past page 1."""

    LUCKY = "https://www.tactics.com/5boro/lucky-candle-brooklyn-825-skateboard-deck"
    SANTA = "https://www.tactics.com/santa-monica-airlines/skater-hall-of-fame-110-ltd-skateboard-deck"
    WELCOME = "https://www.zumiez.com/welcome-opps-8-5-skateboard-deck.html"

    def test_tactics_reads_past_the_first_sale_page(self):
        from stores.tactics import TacticsDecksScraper, collect_sale_pages

        page1 = '<a class="pagination-next" href="/skateboard-decks/sale/page-2"></a>'
        page2 = (
            '<div class="browse-grid-item">'
            f'<a href="/5boro/lucky-candle-brooklyn-825-skateboard-deck">'
            '<img alt="5boro Lucky Candle Brooklyn 8.25 Skateboard Deck"></a>'
            '<span class="browse-grid-item-sale-price">$47.95</span>'
            '<span class="browse-grid-item-discount">29% off</span></div>'
            '<div class="browse-grid-item">'
            '<a href="/santa-monica-airlines/skater-hall-of-fame-110-ltd-skateboard-deck">'
            '<img alt="Santa Monica Airlines Skater Hall Of Fame 11.0 LTD Skateboard Deck"></a>'
            '<span class="browse-grid-item-sale-price">$99.95</span>'
            '<span class="browse-grid-item-discount">20% off</span></div>'
        )

        def fetch(url):
            if url.rstrip("/").endswith("/sale"):
                return url, page1
            if url.rstrip("/").endswith("/page-2"):
                return url, page2
            return "https://www.tactics.com/skateboard-decks/sale", page1

        pages = collect_sale_pages("https://www.tactics.com/skateboard-decks/sale", fetch=fetch)
        self.assertEqual(len(pages), 2)
        scraper = TacticsDecksScraper()
        urls = [item["url"] for html in pages for item in scraper.parse(html)]
        self.assertIn(self.LUCKY, urls)
        self.assertIn(self.SANTA, urls)
        # A request that lands back on page 1 does not walk forever.
        self.assertEqual(
            len(collect_sale_pages("https://www.tactics.com/skateboard-decks/sale", fetch=lambda url: (
                "https://www.tactics.com/skateboard-decks/sale",
                page1,
            ))),
            1,
        )

    def test_zumiez_page_links_include_a_later_card(self):
        from stores.zumiez import ZumiezDecksScraper, has_page_link, listing_urls, page_url

        html = (
            '<li class="ProductCard"><a class="ProductCard-Link" href="/welcome-opps-8-5-skateboard-deck.html">'
            '<span class="ProductCard-Name">Welcome Opps 8.5&quot; Skateboard Deck</span></a>'
            '<span class="ProductPrice-PriceValue">$64.99</span>'
            '<span class="ProductCardPrice-HighPrice">$79.95</span></li>'
            '<a class="PaginationLink" href="/skate/skateboard-decks.html?customFilters=promotion_flag:Sale&amp;page=2">2</a>'
        )
        base = "https://www.zumiez.com/skate/skateboard-decks.html?customFilters=promotion_flag:Sale"
        self.assertEqual(page_url(base, 1), base)
        self.assertIn("page=2", page_url(base, 2))
        self.assertTrue(has_page_link(html, 2))
        self.assertIn(self.WELCOME, listing_urls(html))
        kept = ZumiezDecksScraper().parse(html)
        self.assertEqual([item["url"] for item in kept], [self.WELCOME])

    def test_sold_out_requires_the_product_status_node(self):
        from stores.stock import stock_from_html

        self.assertEqual(
            stock_from_html("Tactics", '<div class="product-head-orderable-status">Out of stock</div>'),
            "out_of_stock",
        )
        self.assertIsNone(stock_from_html("Tactics", "<button>Add to Cart</button>"))
        self.assertIsNone(
            stock_from_html(
                "Zumiez",
                '<div class="GetItNowBopis-Availability_isOutOfStock">out of stock</div>'
                '<div class="ProductActions-Stock">In stock</div>',
            )
        )
        self.assertEqual(
            stock_from_html("Zumiez", '<div class="ProductActions-Stock">Out of stock</div>'),
            "out_of_stock",
        )


if __name__ == "__main__":
    unittest.main()
