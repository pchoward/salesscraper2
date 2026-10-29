"""Disappeared over-counting: a same-day re-scrape is not a second miss.

On 2026-10-28 Tactics' sale index shrank from about 131 decks to about 50.
The first scan that day carried the missing decks (one miss). A re-scrape
the same day saw them in its previous catalog, missed them again, and the
second miss turned all of them into Disappeared at once.
"""

import unittest

from history import _ordered_entry, apply_lifecycle, recently_gone, record_misses, update_price_history


def _deck(n, price="50.00"):
    return {
        "name": f"Baker Brand Logo Deck {n} 8.25",
        "url": f"https://www.tactics.com/baker/deck-{n}",
        "price_new": price,
        "price_old": "80.00",
        "part": "Decks",
        "store": "Tactics",
    }


def _seen(count, day):
    catalog = {"Tactics_Decks": [_deck(n) for n in range(count)]}
    history = {}
    update_price_history(catalog, history, today=day)
    return catalog, history


def _kept(count):
    """A smaller sale index: the first ``count`` decks."""
    return {"Tactics_Decks": [_deck(n) for n in range(count)]}


class SameDayMissTests(unittest.TestCase):
    def test_same_day_rescrape_carries_instead_of_disappearing(self):
        full, history = _seen(10, "2026-10-27")
        first = _kept(4)
        carried = record_misses(full, first, history, today="2026-10-28")
        self.assertEqual(len(carried), 6)
        self.assertEqual(len(first["Tactics_Decks"]), 10)

        # Re-scrape on the same day: the carried six are in its previous catalog.
        second = _kept(4)
        carried = record_misses(first, second, history, today="2026-10-28")
        self.assertEqual(len(carried), 6, "still one miss; carried again")
        self.assertEqual(len(second["Tactics_Decks"]), 10)
        for n in range(4, 10):
            self.assertEqual(history[_deck(n)["url"]]["miss_streak"], 1)
        apply_lifecycle(history, second, today="2026-10-28")
        self.assertEqual(recently_gone(history, second, today="2026-10-28"), [])

        # A third scan that day changes nothing either.
        third = _kept(4)
        record_misses(second, third, history, today="2026-10-28")
        self.assertEqual(recently_gone(history, third, today="2026-10-28"), [])

        # The next day's scan is the real second miss.
        next_day = _kept(4)
        carried = record_misses(third, next_day, history, today="2026-10-29")
        self.assertEqual(carried, set())
        self.assertEqual(len(next_day["Tactics_Decks"]), 4)
        apply_lifecycle(history, next_day, today="2026-10-29")
        gone = recently_gone(history, next_day, today="2026-10-29")
        self.assertEqual(sorted(row["url"] for row in gone), sorted(_deck(n)["url"] for n in range(4, 10)))

    def test_return_the_same_day_clears_the_miss(self):
        full, history = _seen(3, "2026-10-27")
        first = _kept(2)
        record_misses(full, first, history, today="2026-10-28")
        url = _deck(2)["url"]
        self.assertEqual(history[url]["miss_day"], "2026-10-28")
        back = _kept(3)
        record_misses(first, back, history, today="2026-10-28")
        self.assertNotIn("miss_streak", history[url])
        self.assertNotIn("miss_day", history[url])
        # Missing again later that day is a fresh first miss, not a second.
        again = _kept(2)
        self.assertEqual(record_misses(back, again, history, today="2026-10-28"), {url})

    def test_history_only_rows_count_once_per_day(self):
        # A row the saved catalog never had: the saved catalog was its first miss.
        _, history = _seen(2, "2026-10-27")
        url = _deck(1)["url"]
        history[url]["miss_streak"] = 1
        history[url]["miss_day"] = "2026-10-28"
        record_misses(_kept(1), _kept(1), history, today="2026-10-28")
        self.assertEqual(history[url]["miss_streak"], 1)
        record_misses(_kept(1), _kept(1), history, today="2026-10-29")
        self.assertEqual(history[url]["miss_streak"], 2)

    def test_failed_scrape_still_adds_no_miss(self):
        full, history = _seen(3, "2026-10-27")
        current = {"Tactics_Decks": []}
        record_misses(full, current, history, skip_keys={"Tactics_Decks"}, today="2026-10-28")
        for n in range(3):
            self.assertNotIn("miss_streak", history[_deck(n)["url"]])
            self.assertNotIn("miss_day", history[_deck(n)["url"]])

    def test_without_today_each_call_is_its_own_scan(self):
        full, history = _seen(2, "2026-10-27")
        first = _kept(1)
        record_misses(full, first, history)
        second = _kept(1)
        self.assertEqual(record_misses(first, second, history), set())
        self.assertEqual(history[_deck(1)["url"]]["miss_streak"], 2)

    def test_miss_day_survives_saving_and_bad_values_are_dropped(self):
        entry = {"name": "x", "store": "Tactics", "part": "Decks", "prices": {}, "miss_streak": 1, "miss_day": "2026-10-28"}
        self.assertEqual(_ordered_entry(entry)["miss_day"], "2026-10-28")
        self.assertNotIn("miss_day", _ordered_entry({**entry, "miss_day": "yesterday"}))


if __name__ == "__main__":
    unittest.main()
