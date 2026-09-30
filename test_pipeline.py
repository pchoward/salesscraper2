"""Run bookkeeping must not raise, and must not wipe a corrupt history file."""

import unittest

from pipeline import apply_run_updates, decorate_digest
from report import Digest


def _deck():
    return {
        "name": "Baker Figgy Divine Evil 8.25 Deck",
        "url": "https://example.com/baker",
        "price_new": "40.00",
        "price_old": "70.00",
        "part": "Decks",
        "store": "Zumiez",
    }


class PipelineTests(unittest.TestCase):
    def test_corrupt_inputs_do_not_raise_or_replace_history(self):
        result = apply_run_updates(
            {"Zumiez_Decks": [_deck()]},
            set(),
            history=["not", "a", "dict"],
            health={"runs": "broken"},
            today="2026-09-30",
        )
        self.assertFalse(result["save_history"])
        self.assertIsInstance(result["health"], dict)
        self.assertIsInstance(result["health"]["runs"], list)
        self.assertIsInstance(result["warnings"], list)

    def test_normal_run_records_health_and_skips_failed_scrape_prices(self):
        result = apply_run_updates(
            {
                "Zumiez_Decks": [_deck()],
                "CCS_Decks": [_deck()],
            },
            failed_keys={"CCS_Decks"},
            history={},
            health={"runs": [], "baseline": {}},
            today="2026-09-30",
        )
        self.assertTrue(result["save_history"])
        self.assertIn("https://example.com/baker", result["history"])
        self.assertEqual(result["history"]["https://example.com/baker"]["observation_count"], 1)
        decks = result["health"]["runs"][0]["results"]
        self.assertEqual(decks["Zumiez_Decks"]["count"], 1)
        self.assertFalse(decks["Zumiez_Decks"]["failed"])
        self.assertTrue(decks["CCS_Decks"]["failed"])
        self.assertEqual(decks["CCS_Decks"]["count"], 0)

    def test_decorate_adds_warning_and_low_flag_without_raising(self):
        item = _deck()
        history = {
            item["url"]: {
                "name": item["name"],
                "store": "Zumiez",
                "part": "Decks",
                "first_seen": "2026-09-01",
                "last_seen": "2026-09-30",
                "observation_count": 4,
                "all_time_low": 40.0,
                "all_time_low_date": "2026-09-20",
                "prices": {
                    "2026-09-01": 55.0,
                    "2026-09-10": 50.0,
                    "2026-09-20": 40.0,
                    "2026-09-30": 40.0,
                },
            }
        }
        digest = Digest(new_items=[item])
        warning = {"store": "CCS", "part": "Wheels", "kind": "error", "dates": ["2026-09-29", "2026-09-30"]}
        decorate_digest(digest, {"Zumiez_Decks": [item]}, history, [warning])
        self.assertEqual(digest.warnings, [warning])
        self.assertTrue(item["at_all_time_low"])
        self.assertEqual(len(digest.all_time_lows), 1)
        decorate_digest(None, {}, {}, [])


if __name__ == "__main__":
    unittest.main()
