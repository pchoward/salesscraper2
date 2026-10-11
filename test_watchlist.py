"""Watchlist rules, including the seeded preferences."""

import os
import unittest

from watchlist import load_watchlist, match_watchlist, parse_watchlist, rule_matches


def _deck(name, price="50.00", url="https://example.com/deck", width=None):
    item = {
        "name": name,
        "url": url,
        "price_new": price,
        "price_old": "80.00",
        "part": "Decks",
        "store": "SkateWarehouse",
    }
    if width is not None:
        item["width"] = width
    return item


class WatchlistTests(unittest.TestCase):
    def setUp(self):
        self.rules = load_watchlist(os.path.join(os.path.dirname(__file__), "watchlist.yaml"))
        self.ids = [rule["id"] for rule in self.rules]

    def test_seed_file_has_the_real_prefs(self):
        self.assertEqual(
            self.ids,
            ["black-label-decks", "powell-peralta-decks", "heroin-decks", "antihero-caster"],
        )
        widths = {rule["id"]: rule.get("min_width") for rule in self.rules}
        self.assertEqual(widths["black-label-decks"], 8.6)
        self.assertEqual(widths["powell-peralta-decks"], 8.6)
        self.assertEqual(widths["heroin-decks"], 8.6)
        self.assertNotIn("min_width", self.rules[3])
        self.assertNotIn("max_price", self.rules[0])

    def test_brand_width_rules(self):
        wide = _deck("Black Label Thumbhead 8.75 Deck", width=8.75)
        narrow = _deck("Black Label Thumbhead 8.5 Deck", width=8.5)
        exact = _deck("Black Label Thumbhead 8.60 Deck", width=8.60)
        heroin = _deck("Heroin Questions 9.0 Deck", width=9.0)
        truck = dict(heroin, part="Trucks", name="Slappy x Heroin Wide Boys Truck")
        powell = _deck("Powell Peralta Skeleton 8.75 Flight Deck", width=8.75)
        bones = _deck("Powell Bones Brigade Mullen 8.75 Deck", width=8.75)
        self.assertTrue(any(rule_matches(rule, wide) for rule in self.rules))
        self.assertTrue(any(rule_matches(rule, exact) for rule in self.rules))
        self.assertFalse(any(rule_matches(rule, narrow) for rule in self.rules))
        self.assertTrue(any(rule_matches(rule, heroin) for rule in self.rules))
        self.assertFalse(any(rule_matches(rule, truck) for rule in self.rules))
        self.assertTrue(any(rule_matches(rule, powell) for rule in self.rules))
        self.assertFalse(any(rule_matches(rule, bones) for rule in self.rules))

    def test_antihero_caster_any_width_and_spelling(self):
        names = [
            "Antihero Caster Deck 8.0",
            "Anti-Hero Caster Deck 7.75",
            "Anti Hero Caster 8.62 Deck",
        ]
        for name in names:
            item = _deck(name)
            matched = [rule["id"] for rule in self.rules if rule_matches(rule, item)]
            self.assertEqual(matched, ["antihero-caster"])
        other = _deck("Anti-Hero Doobie Expressions Deck 8.75")
        self.assertFalse(any(rule_matches(rule, other) for rule in self.rules))

    def test_default_rules_alert_on_new_back_and_any_drop(self):
        item = _deck("Heroin Egg 9.0 Deck", price="42.00", url="https://example.com/heroin", width=9.0)
        hits, alerts = match_watchlist([item], rules=self.rules, previous={}, history={}, today="2026-09-30")
        self.assertEqual(len(hits), 1)
        self.assertEqual(alerts[0]["reasons"], ["New"])

        previous = {"Zumiez_Decks": [dict(item, price_new="45.00")]}
        _hits, alerts = match_watchlist(
            [item],
            rules=self.rules,
            previous=previous,
            history={},
            today="2026-09-30",
        )
        self.assertEqual(alerts[0]["reasons"], ["Price dropped $3.00"])

        same = match_watchlist(
            [item],
            rules=self.rules,
            previous={"Zumiez_Decks": [dict(item)]},
            history={},
            today="2026-09-30",
        )
        self.assertEqual(same[0][0]["reasons"], [])
        self.assertEqual(same[1], [])

    def test_trigger_fields(self):
        rules = parse_watchlist(
            """
            rules:
              - id: under
                name: Caster
                max_price: 40
              - id: any-drop
                brand: Heroin
                part: Decks
                alert_on_drop: true
              - id: size-back
                brand: Black Label
                part: Decks
                back_in_stock_width: 8.75
            """
        )
        caster = _deck("Anti-Hero Caster Deck 8.0", price="39.00", url="https://example.com/caster")
        prior = {"SkateWarehouse_Decks": [dict(caster, price_new="44.00")]}
        _hits, alerts = match_watchlist([caster], rules=rules, previous=prior, today="2026-09-30")
        self.assertEqual([hit["rule_id"] for hit in alerts], ["under"])

        heroin = _deck("Heroin Egg 8.5 Deck", price="49.50", url="https://example.com/h", width=8.5)
        previous = {"Tactics_Decks": [dict(heroin, price_new="50.00")]}
        _hits, alerts = match_watchlist([heroin], rules=rules, previous=previous, today="2026-09-30")
        self.assertEqual(alerts[0]["rule_id"], "any-drop")
        self.assertIn("Price dropped $0.50", alerts[0]["reasons"])

        label = _deck("Black Label Egg 8.75 Deck", price="60.00", url="https://example.com/bl", width=8.75)
        history = {
            label["url"]: {
                "first_seen": "2026-08-01",
                "last_seen": "2026-08-20",
                "prices": {"2026-08-01": 60.0},
            }
        }
        _hits, alerts = match_watchlist(
            [label],
            rules=rules,
            previous={},
            history=history,
            today="2026-09-30",
        )
        self.assertEqual(alerts[0]["reasons"], ['8.75" back in stock'])
        other = dict(label, width=8.5, name="Black Label Egg 8.5 Deck")
        _hits, alerts = match_watchlist(
            [other],
            rules=rules,
            previous={},
            history=history,
            today="2026-09-30",
        )
        self.assertEqual(alerts, [])

    def test_exact_width_range_and_new_all_time_low(self):
        rules = parse_watchlist(
            """
            rules:
              - id: antihero-85
                brand: Anti Hero
                part: Decks
                width: 8.5
                max_price: 50
                note: Any 8.5 inch Anti Hero deck under $50
              - id: wide-band
                brand: Heroin
                part: Decks
                min_width: 9.5
                max_width: 10.0
              - id: low-watch
                brand: Baker
                part: Decks
                alert_on_low: true
            """
        )
        exact = _deck("Anti-Hero Eagle 8.50 Deck", price="49.00", url="https://example.com/ah", width=8.50)
        off_size = _deck("Anti-Hero Eagle 8.25 Deck", price="40.00", url="https://example.com/ah2", width=8.25)
        self.assertEqual(
            [rule["id"] for rule in rules if rule_matches(rule, exact)],
            ["antihero-85"],
        )
        self.assertFalse(any(rule_matches(rule, off_size) for rule in rules))

        wide = _deck("Heroin Wide Boy 9.75 Deck", price="60.00", url="https://example.com/w", width=9.75)
        too_wide = _deck("Heroin Wide Boy 10.25 Deck", price="60.00", url="https://example.com/w2", width=10.25)
        self.assertEqual(
            [rule["id"] for rule in rules if rule_matches(rule, wide)],
            ["wide-band"],
        )
        self.assertFalse(any(rule_matches(rule, too_wide) for rule in rules))

        prior = {"SkateWarehouse_Decks": [dict(exact, price_new="55.00")]}
        hits, alerts = match_watchlist([exact], rules=rules, previous=prior, today="2026-09-30")
        self.assertEqual(hits[0]["rule_id"], "antihero-85")
        self.assertEqual(alerts[0]["reasons"], ["Under $50.00"])
        still_high = dict(exact, price_new="60.00")
        hits, alerts = match_watchlist([still_high], rules=rules, previous=prior, today="2026-09-30")
        self.assertEqual(len(hits), 1)
        self.assertEqual(alerts, [])

        baker = _deck("Baker Figgy 8.5 Deck", price="40.00", url="https://example.com/baker", width=8.5)
        history = {
            baker["url"]: {
                "first_seen": "2026-09-01",
                "last_seen": "2026-09-30",
                "observation_count": 4,
                "all_time_low": 40.0,
                "all_time_low_date": "2026-09-30",
                "prices": {
                    "2026-09-01": 55.0,
                    "2026-09-10": 50.0,
                    "2026-09-20": 48.0,
                    "2026-09-30": 40.0,
                },
            }
        }
        previous = {"Zumiez_Decks": [dict(baker, price_new="48.00")]}
        _hits, alerts = match_watchlist(
            [baker],
            rules=rules,
            previous=previous,
            history=history,
            today="2026-09-30",
        )
        self.assertIn("New all-time low", alerts[0]["reasons"])
        self.assertIn("Price dropped $8.00", alerts[0]["reasons"])

        already = match_watchlist(
            [baker],
            rules=rules,
            previous={"Zumiez_Decks": [dict(baker, price_new="40.00")]},
            history=history,
            today="2026-09-30",
        )
        self.assertEqual(already[1], [])
        self.assertEqual(already[0][0]["reasons"], [])

    def test_missing_file_logs_and_matches_nothing(self):
        with self.assertLogs("watchlist", level="ERROR") as logs:
            hits, alerts = match_watchlist([_deck("Heroin Egg 9 Deck", width=9)], path="missing-watchlist.yaml")
        self.assertEqual(hits, [])
        self.assertEqual(alerts, [])
        self.assertTrue(any("not found" in line for line in logs.output))


if __name__ == "__main__":
    unittest.main()
