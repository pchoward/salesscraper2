"""NEW, back in stock, today's drop, and lowest-ever stay distinct."""

import unittest

from badges import classify_badges


def _item(url="https://example.com/deck", price="40.00"):
    return {
        "name": "Baker Team Deck 8.25",
        "url": url,
        "price_new": price,
        "price_old": "70.00",
        "part": "Decks",
        "store": "Zumiez",
    }


def _history(url, first, prices, low=40.0):
    return {
        url: {
            "name": "Baker Team Deck 8.25",
            "store": "Zumiez",
            "part": "Decks",
            "first_seen": first,
            "last_seen": max(prices),
            "observation_count": len(prices),
            "all_time_low": low,
            "all_time_low_date": min(prices),
            "prices": prices,
        }
    }


def _kinds(badges):
    return [badge["kind"] for badge in badges]


class BadgeTests(unittest.TestCase):
    def test_new_when_never_seen(self):
        badges = classify_badges(_item(), {}, in_previous=False, today="2026-09-30")
        self.assertEqual(_kinds(badges), ["new"])
        self.assertEqual(badges[0]["label"], "NEW")

    def test_back_in_stock_is_not_new(self):
        item = _item()
        history = _history(
            item["url"],
            "2026-08-01",
            {"2026-08-01": 50.0, "2026-08-20": 45.0, "2026-09-01": 40.0},
        )
        badges = classify_badges(item, history, in_previous=False, today="2026-09-30")
        self.assertIn("back", _kinds(badges))
        self.assertNotIn("new", _kinds(badges))
        self.assertEqual(badges[0]["label"], "BACK IN STOCK")

    def test_drop_and_lowest_are_separate(self):
        item = _item(price="40.00")
        history = _history(
            item["url"],
            "2026-09-01",
            {"2026-09-01": 55.0, "2026-09-15": 50.0, "2026-09-30": 40.0},
        )
        drop = {"old": "50.00", "new": "40.00", "delta": 10.0, "percent_vs_prior": 20.0}
        badges = classify_badges(item, history, in_previous=True, drop=drop, today="2026-09-30")
        self.assertEqual(_kinds(badges), ["drop", "lowest"])
        self.assertEqual(badges[0]["label"], "down $10.00 TODAY")
        self.assertEqual(badges[1]["label"], "LOWEST EVER")

    def test_a_drop_alone_is_not_lowest_ever(self):
        item = _item(price="48.00")
        history = _history(
            item["url"],
            "2026-09-01",
            {"2026-09-01": 60.0, "2026-09-15": 55.0, "2026-09-30": 48.0},
            low=40.0,
        )
        drop = {"old": "55.00", "new": "48.00", "delta": 7.0, "percent_vs_prior": 12.7}
        badges = classify_badges(item, history, in_previous=True, drop=drop, today="2026-09-30")
        self.assertEqual(_kinds(badges), ["drop"])
        self.assertNotIn("LOWEST EVER", [badge["label"] for badge in badges])

    def test_lowest_without_a_drop_still_badges(self):
        item = _item(price="40.00")
        history = _history(
            item["url"],
            "2026-09-01",
            {"2026-09-01": 50.0, "2026-09-15": 40.0, "2026-09-30": 40.0},
        )
        badges = classify_badges(item, history, in_previous=True, today="2026-09-30")
        self.assertEqual(_kinds(badges), ["lowest"])

    def test_already_in_the_catalog_is_not_new_or_back(self):
        badges = classify_badges(_item(), {}, in_previous=True, today="2026-09-30")
        self.assertEqual(badges, [])


if __name__ == "__main__":
    unittest.main()
