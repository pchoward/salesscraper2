"""Good-discount definition and the deals-intelligence summary."""

import unittest

from intel import GOOD_DEFINITION, intelligence_summary, is_good_deal


def _deck(price, old="80.00", url="https://example.com/deck", store="Tactics", name="Baker Figgy 8.5"):
    return {
        "name": name,
        "url": url,
        "price_new": price,
        "price_old": old,
        "part": "Decks",
        "store": store,
    }


def _history(url, prices, low=None, low_date=None):
    days = sorted(prices)
    lowest = min(prices.values()) if low is None else low
    return {
        "name": "Baker",
        "store": "Tactics",
        "part": "Decks",
        "first_seen": days[0],
        "last_seen": days[-1],
        "observation_count": max(3, len(prices)),
        "all_time_low": lowest,
        "all_time_low_date": low_date or days[0],
        "prices": prices,
        "span_via_dates": True,
    }


class IntelTests(unittest.TestCase):
    def test_good_means_deep_discount_near_a_qualified_low(self):
        item = _deck("40.00", old="80.00")
        history = {
            item["url"]: _history(
                item["url"],
                {"2026-09-01": 55.0, "2026-09-15": 48.0, "2026-09-30": 40.0},
            )
        }
        self.assertTrue(is_good_deal(item, history))

        shallow = _deck("60.00", old="80.00", url="https://example.com/shallow")
        history[shallow["url"]] = _history(
            shallow["url"],
            {"2026-09-01": 70.0, "2026-09-15": 65.0, "2026-09-30": 60.0},
        )
        self.assertFalse(is_good_deal(shallow, history))

        above = _deck("50.00", old="80.00", url="https://example.com/above")
        history[above["url"]] = _history(
            above["url"],
            {"2026-08-01": 40.0, "2026-09-01": 55.0, "2026-09-30": 50.0},
            low=40.0,
            low_date="2026-08-01",
        )
        self.assertFalse(is_good_deal(above, history))

        fresh = _deck("40.00", old="80.00", url="https://example.com/fresh")
        history[fresh["url"]] = {
            "first_seen": "2026-09-30",
            "last_seen": "2026-09-30",
            "observation_count": 1,
            "all_time_low": 40.0,
            "all_time_low_date": "2026-09-30",
            "prices": {"2026-09-30": 40.0},
        }
        self.assertFalse(is_good_deal(fresh, history))
        self.assertIn("30%", GOOD_DEFINITION)
        self.assertIn("7 days", GOOD_DEFINITION)

    def test_summary_ranks_drops_discounts_and_good_stores(self):
        tactics = _deck("40.00", store="Tactics", url="https://example.com/t", name="Baker A")
        zumiez = _deck("36.00", old="90.00", store="Zumiez", url="https://example.com/z", name="Baker B")
        weak = _deck("70.00", old="80.00", store="CCS", url="https://example.com/c", name="Baker C")
        history = {
            tactics["url"]: _history(tactics["url"], {"2026-09-01": 50.0, "2026-09-20": 45.0, "2026-09-30": 40.0}),
            zumiez["url"]: _history(zumiez["url"], {"2026-09-01": 50.0, "2026-09-20": 40.0, "2026-09-30": 36.0}),
            weak["url"]: _history(weak["url"], {"2026-09-01": 75.0, "2026-09-20": 72.0, "2026-09-30": 70.0}),
        }
        summary = intelligence_summary(
            [tactics, zumiez, weak],
            history,
            new_items=[tactics],
            drops=[
                {"item": zumiez, "delta": 12.0, "new": "36.00", "name": zumiez["name"]},
                {"item": tactics, "delta": 4.0, "new": "40.00", "name": tactics["name"]},
            ],
        )
        self.assertEqual(summary["new_count"], 1)
        self.assertEqual(summary["biggest_drops"][0]["name"], "Baker B")
        self.assertEqual(summary["discount_leader"]["store"], "Zumiez")
        self.assertEqual(summary["good_count"], 2)
        self.assertEqual(summary["good_by_store"][0]["count"], 1)
        stores = [row["store"] for row in summary["good_by_store"]]
        self.assertEqual(stores, ["Zumiez", "Tactics"])
        self.assertEqual(summary["good_leader"]["store"], "Zumiez")


if __name__ == "__main__":
    unittest.main()
