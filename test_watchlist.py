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

    def test_missing_file_logs_and_matches_nothing(self):
        with self.assertLogs("watchlist", level="ERROR") as logs:
            hits, alerts = match_watchlist([_deck("Heroin Egg 9 Deck", width=9)], path="missing-watchlist.yaml")
        self.assertEqual(hits, [])
        self.assertEqual(alerts, [])
        self.assertTrue(any("not found" in line for line in logs.output))


if __name__ == "__main__":
    unittest.main()
