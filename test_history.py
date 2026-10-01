"""Price-history pruning and all-time-low rules. No network."""

import datetime
import unittest

from history import (
    DETAIL_WINDOW_DAYS,
    STALE_AFTER_DAYS,
    all_time_low_status,
    prune_price_history,
    update_price_history,
)

TODAY = datetime.date(2026, 9, 30)


def _day(offset):
    return (TODAY + datetime.timedelta(days=offset)).isoformat()


def _entry(name, part, prices, store="Zumiez", **extra):
    entry = {
        "name": name,
        "store": store,
        "part": part,
        "prices": prices,
    }
    entry.update(extra)
    return entry


def _deck_prices(start_offset, days, price):
    return {_day(start_offset + offset): price for offset in range(days)}


class PruneTests(unittest.TestCase):
    def test_trims_daily_points_and_keeps_all_time_low(self):
        old_low_day = _day(-(DETAIL_WINDOW_DAYS + 40))
        recent = _day(-2)
        history = {
            "https://example.com/baker": _entry(
                "Baker Figgy Divine Evil 8.25 Deck",
                "Decks",
                {old_low_day: 40.0, recent: 55.0, _day(-1): 55.0, _day(0): 55.0},
            )
        }
        pruned, stats = prune_price_history(history, today=TODAY)
        entry = pruned["https://example.com/baker"]
        self.assertNotIn(old_low_day, entry["prices"])
        self.assertEqual(entry["all_time_low"], 40.0)
        self.assertEqual(entry["all_time_low_date"], old_low_day)
        self.assertEqual(entry["first_seen"], old_low_day)
        self.assertGreaterEqual(entry["observation_count"], 4)
        self.assertGreater(stats["points_before"], stats["points_after"])
        self.assertEqual(stats["points_trimmed"], 1)

    def test_all_time_low_still_flags_after_the_window_is_gone(self):
        old_low_day = _day(-(DETAIL_WINDOW_DAYS + 30))
        prices = {old_low_day: 40.0}
        prices.update(_deck_prices(-10, 11, 40.0))
        history = {
            "https://example.com/baker": _entry(
                "Baker Figgy Divine Evil 8.25 Deck",
                "Decks",
                prices,
            )
        }
        pruned, _stats = prune_price_history(history, today=TODAY)
        item = {
            "name": "Baker Figgy Divine Evil 8.25 Deck",
            "url": "https://example.com/baker",
            "price_new": "40.00",
            "price_old": "70.00",
            "part": "Decks",
            "store": "Zumiez",
        }
        status = all_time_low_status(item, pruned)
        self.assertTrue(status["flagged"])
        self.assertEqual(status["low"], 40.0)
        self.assertNotIn(old_low_day, pruned["https://example.com/baker"]["prices"])

    def test_brand_new_and_short_history_are_not_flagged(self):
        history = {
            "https://example.com/new": _entry(
                "Baker Brand New 8.25 Deck",
                "Decks",
                {_day(0): 40.0},
            ),
            "https://example.com/short": _entry(
                "Baker Short History 8.25 Deck",
                "Decks",
                {_day(-6): 50.0, _day(-3): 45.0, _day(0): 40.0},
            ),
        }
        fresh = {
            "name": "Baker Brand New 8.25 Deck",
            "url": "https://example.com/new",
            "price_new": "40.00",
            "price_old": "70.00",
            "part": "Decks",
            "store": "Zumiez",
        }
        short = dict(fresh, name="Baker Short History 8.25 Deck", url="https://example.com/short")
        self.assertFalse(all_time_low_status(fresh, history)["flagged"])
        self.assertFalse(all_time_low_status(short, history)["flagged"])
        self.assertEqual(all_time_low_status(short, history)["span_days"], 6)

    def test_qualified_low_flags_and_a_higher_price_does_not(self):
        prices = {_day(-10): 50.0, _day(-5): 45.0, _day(0): 40.0}
        history = {
            "https://example.com/low": _entry("Baker Low 8.25 Deck", "Decks", prices),
        }
        low = {
            "name": "Baker Low 8.25 Deck",
            "url": "https://example.com/low",
            "price_new": "40.00",
            "price_old": "70.00",
            "part": "Decks",
            "store": "Zumiez",
        }
        higher = dict(low, price_new="48.00")
        self.assertTrue(all_time_low_status(low, history)["flagged"])
        self.assertFalse(all_time_low_status(higher, history)["flagged"])

    def test_drops_filtered_listings_and_keeps_decks_without_msrp(self):
        history = {
            "https://example.com/skf": _entry("SKF Ishod Bearings", "Bearings", {_day(0): 20.0}),
            "https://example.com/cruiser": _entry(
                "Daddies Trip On This Cruiser Deck 8.5",
                "Decks",
                {_day(0): 30.0},
            ),
            "https://example.com/wide": _entry(
                "Heroin Wide 10.25 Deck",
                "Decks",
                {_day(0): 40.0},
            ),
            "https://example.com/mini": _entry(
                "Mini Logo Peacock 7.4 Deck",
                "Decks",
                {_day(0): 20.0},
            ),
            "https://example.com/keeper": _entry(
                "Baker Figgy Divine Evil 8.25 Deck",
                "Decks",
                {_day(-3): 50.0, _day(0): 45.0},
            ),
        }
        pruned, stats = prune_price_history(history, today=TODAY)
        self.assertNotIn("https://example.com/skf", pruned)
        self.assertNotIn("https://example.com/cruiser", pruned)
        self.assertNotIn("https://example.com/mini", pruned)
        self.assertIn("https://example.com/wide", pruned)
        self.assertIn("https://example.com/keeper", pruned)
        self.assertEqual(stats["dropped_filter"], 3)
        self.assertGreaterEqual(stats["listings_before"], stats["listings_after"])

    def test_drops_stale_listings_but_keeps_active_ones(self):
        stale_day = _day(-(STALE_AFTER_DAYS + 1))
        history = {
            "https://example.com/gone": _entry(
                "Baker Gone 8.25 Deck",
                "Decks",
                {stale_day: 40.0},
            ),
            "https://example.com/back": _entry(
                "Baker Back 8.0 Deck",
                "Decks",
                {stale_day: 42.0},
            ),
        }
        current = {
            "Zumiez_Decks": [
                {
                    "name": "Baker Back 8.0 Deck",
                    "url": "https://example.com/back",
                    "price_new": "42.00",
                    "price_old": "70.00",
                    "part": "Decks",
                    "store": "Zumiez",
                }
            ]
        }
        pruned, stats = prune_price_history(history, today=TODAY, current_data=current)
        self.assertNotIn("https://example.com/gone", pruned)
        self.assertIn("https://example.com/back", pruned)
        self.assertEqual(stats["dropped_stale"], 1)
        self.assertEqual(pruned["https://example.com/back"]["all_time_low"], 42.0)

    def test_prune_is_idempotent_and_observation_count_survives(self):
        prices = {_day(-120): 30.0, _day(-10): 36.0, _day(0): 36.0}
        history = {
            " https://example.com/baker ": _entry(
                "Clearance\u00a0-10%Baker Figgy Divine Evil 8.25 Deck",
                "Decks",
                prices,
            )
        }
        once, _stats = prune_price_history(history, today=TODAY)
        twice, stats = prune_price_history(once, today=TODAY)
        self.assertEqual(once, twice)
        self.assertEqual(stats["points_trimmed"], 0)
        entry = twice["https://example.com/baker"]
        self.assertEqual(entry["observation_count"], 3)
        self.assertNotIn("Clearance", entry["name"])
        self.assertEqual(entry["all_time_low"], 30.0)

    def test_failed_keys_are_not_new_observations(self):
        history = {}
        current = {
            "Zumiez_Decks": [
                {
                    "name": "Baker Figgy Divine Evil 8.25 Deck",
                    "url": "https://example.com/baker",
                    "price_new": "40.00",
                    "price_old": "70.00",
                    "part": "Decks",
                    "store": "Zumiez",
                }
            ]
        }
        update_price_history(current, history, today=TODAY, skip_keys={"Zumiez_Decks"})
        self.assertEqual(history, {})
        update_price_history(current, history, today=TODAY, skip_keys=set())
        entry = history["https://example.com/baker"]
        self.assertEqual(entry["prices"][TODAY.isoformat()], 40.0)
        self.assertEqual(entry["observation_count"], 1)
        update_price_history(current, history, today=TODAY, skip_keys=set())
        self.assertEqual(entry["observation_count"], 1)


if __name__ == "__main__":
    unittest.main()
