"""Store parsers, isolated runs, and the backup-cron gate. No network."""

import datetime
import json
import os
import tempfile
import time
import unittest
from zoneinfo import ZoneInfo

from schedule import BACKUP_CRON, already_succeeded_today, gate_should_scrape
from site_sales import activity_line, describe_sales, empty_state
from stores.muirskate import DISABLED_REASON, ENABLED, MuirSkateScraper
from stores.registry import build_scrapers
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

    def test_muir_is_disabled_until_the_storefront_answers(self):
        self.assertFalse(ENABLED)
        self.assertIn("unavailable", DISABLED_REASON.lower())
        names = {scraper.name for scraper in build_scrapers()}
        self.assertIn("Skate Deluxe", names)
        self.assertIn("Zumiez", names)
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


class RetailerActivityTests(unittest.TestCase):
    def test_new_stores_have_no_recorded_site_wide_sale(self):
        rows = {row["store"]: row for row in describe_sales(empty_state(), "2026-10-02")}
        self.assertIsNone(rows["Skate Deluxe"]["last_sale"])
        self.assertIsNone(rows["Muir Skate"]["last_sale"])
        self.assertIn("no recorded site-wide sale", activity_line(rows["Skate Deluxe"]))
        self.assertIn("no recorded site-wide sale", activity_line(rows["Muir Skate"]))
        self.assertEqual(rows["SkateWarehouse"]["last_sale"], "2026-07-04")


if __name__ == "__main__":
    unittest.main()
