"""Deal score is deterministic and matches the documented formula."""

import unittest

from score import FORMULA, HOT_AT, deal_score


def _deck(price="40.00", old="80.00", width=8.5, url="https://example.com/baker"):
    return {
        "name": f"Baker Team Deck {width}",
        "url": url,
        "price_new": price,
        "price_old": old,
        "part": "Decks",
        "store": "Zumiez",
    }


def _history(url, prices, low=None):
    days = sorted(prices)
    lowest = min(prices.values()) if low is None else low
    return {
        url: {
            "name": "Baker",
            "store": "Zumiez",
            "part": "Decks",
            "first_seen": days[0],
            "last_seen": days[-1],
            "observation_count": len(prices),
            "all_time_low": lowest,
            "all_time_low_date": min(day for day, price in prices.items() if price == min(prices.values())),
            "prices": prices,
        }
    }


class DealScoreTests(unittest.TestCase):
    def test_formula_is_documented_on_the_tooltip(self):
        result = deal_score(_deck(), {})
        self.assertIn("capped at 50", FORMULA)
        self.assertIn("Hot means 70", result["tooltip"])
        self.assertIn(FORMULA, result["tooltip"])

    def test_full_hot_deal(self):
        item = _deck(price="40.00", old="80.00", width=8.5)
        history = _history(
            item["url"],
            {"2026-09-01": 55.0, "2026-09-15": 50.0, "2026-09-30": 40.0},
        )
        drop = {"old": "50.00", "new": "40.00", "delta": 10.0, "percent_vs_prior": 20.0}
        result = deal_score(item, history, drop=drop, width=8.5)
        # 50% off -> 50, at the low -> 25, 20% drop -> 8+4=12, popular size -> 10
        self.assertEqual(result["parts"], {"discount": 50, "lowest": 25, "drop": 12, "size": 10})
        self.assertEqual(result["score"], 97)
        self.assertTrue(result["hot"])
        self.assertGreaterEqual(result["score"], HOT_AT)

    def test_same_inputs_always_match(self):
        item = _deck(price="63.95", old="84.99", width=8.25)
        history = _history(item["url"], {"2026-08-01": 74.95, "2026-09-01": 69.95, "2026-09-30": 63.95})
        drop = {"old": "69.95", "new": "63.95", "delta": 6.0, "percent_vs_prior": 8.6}
        first = deal_score(item, history, drop=drop, width=8.25)
        second = deal_score(item, history, drop=drop, width=8.25)
        self.assertEqual(first, second)

    def test_edges_for_size_and_unqualified_low(self):
        self.assertEqual(deal_score(_deck(width=8.25), {}, width=8.25)["parts"]["size"], 10)
        self.assertEqual(deal_score(_deck(width=8.75), {}, width=8.75)["parts"]["size"], 10)
        self.assertEqual(deal_score(_deck(width=8.24), {}, width=8.24)["parts"]["size"], 0)
        self.assertEqual(deal_score(_deck(width=8.76), {}, width=8.76)["parts"]["size"], 0)
        self.assertEqual(deal_score(_deck(), {}, width=None)["parts"]["size"], 0)
        truck = _deck()
        truck["part"] = "Trucks"
        self.assertEqual(deal_score(truck, {}, width=8.5)["parts"]["size"], 0)

        fresh = _deck(price="40.00", old="80.00")
        history = _history(fresh["url"], {"2026-09-30": 40.0})
        result = deal_score(fresh, history, width=8.0)
        self.assertEqual(result["parts"]["lowest"], 0)
        self.assertFalse(result["hot"])

    def test_near_low_bands_and_small_dip(self):
        item = _deck(price="41.00", old="80.00", width=8.0)
        history = _history(
            item["url"],
            {"2026-09-01": 50.0, "2026-09-15": 45.0, "2026-09-30": 41.0},
            low=40.0,
        )
        history[item["url"]]["all_time_low"] = 40.0
        near = deal_score(item, history, width=8.0)
        self.assertEqual(near["parts"]["lowest"], 18)

        item["price_new"] = "42.00"
        history[item["url"]]["prices"]["2026-09-30"] = 42.0
        close = deal_score(item, history, width=8.0)
        self.assertEqual(close["parts"]["lowest"], 10)

        item["price_new"] = "43.00"
        history[item["url"]]["prices"]["2026-09-30"] = 43.0
        far = deal_score(item, history, width=8.0)
        self.assertEqual(far["parts"]["lowest"], 0)

        dipped = _deck(price="49.50", old="80.00", width=9.0)
        history = _history(
            dipped["url"],
            {"2026-09-01": 55.0, "2026-09-20": 50.0, "2026-09-30": 49.50},
        )
        # $0.50 is not a meaningful drop, but the last two points fell.
        result = deal_score(dipped, history, width=9.0)
        self.assertEqual(result["parts"]["drop"], 4)
        self.assertLess(result["score"], HOT_AT)

    def test_score_caps_at_100(self):
        item = _deck(price="10.00", old="80.00", width=8.5)
        history = _history(
            item["url"],
            {"2026-09-01": 40.0, "2026-09-15": 30.0, "2026-09-30": 10.0},
        )
        drop = {"old": "30.00", "new": "10.00", "delta": 20.0, "percent_vs_prior": 66.7}
        result = deal_score(item, history, drop=drop, width=8.5)
        self.assertEqual(result["score"], 100)
        self.assertEqual(result["parts"]["discount"], 50)
        self.assertEqual(result["parts"]["drop"], 15)


if __name__ == "__main__":
    unittest.main()
