"""All-time-low flags in the report, and conservative cross-store matching."""

import unittest

from history import all_time_low_status
from matching import canonical_width, cross_store_groups, product_identity
from report import Digest, build_report_html

TODAY = "2026-09-30"


def _deck(name, store, url, price="40.00", width_name=None):
    return {
        "name": name,
        "url": url,
        "price_new": price,
        "price_old": "90.00",
        "part": "Decks",
        "store": store,
    }


def _history_for(url, prices):
    days = sorted(prices)
    return {
        url: {
            "name": "tracked",
            "store": "Zumiez",
            "part": "Decks",
            "first_seen": days[0],
            "last_seen": days[-1],
            "observation_count": len(prices),
            "all_time_low": min(prices.values()),
            "all_time_low_date": min(day for day, price in prices.items() if price == min(prices.values())),
            "prices": prices,
        }
    }


class WidthAndIdentityTests(unittest.TestCase):
    def test_width_buckets_merge_rounding_but_not_real_size_steps(self):
        self.assertEqual(canonical_width(8.125), canonical_width(8.12))
        self.assertEqual(canonical_width(8.38), canonical_width(8.375))
        self.assertEqual(canonical_width(8.3875), canonical_width(8.38))
        self.assertNotEqual(canonical_width(8.475), canonical_width(8.5))
        self.assertNotEqual(canonical_width(8.0), canonical_width(8.06))
        self.assertNotEqual(canonical_width(8.25), canonical_width(8.28))

    def test_same_deck_matches_across_width_spellings(self):
        left = _deck(
            "Baker Figgy Divine Evil Deck 8.125",
            "Zumiez",
            "https://example.com/z",
            "64.99",
        )
        right = _deck(
            "Baker Figgy Divine Evil Deck 8.12 x 31.875",
            "SkateWarehouse",
            "https://example.com/s",
            "59.98",
        )
        self.assertEqual(product_identity(left)["key"], product_identity(right)["key"])
        groups = cross_store_groups([left, right])
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]["cheapest_price"], 59.98)
        stores = {offer["store"] for offer in groups[0]["offers"]}
        self.assertEqual(stores, {"Zumiez", "SkateWarehouse"})

    def test_different_width_or_model_does_not_match(self):
        base = _deck("Girl Howard Fullcourt Twin 8.25 Deck", "Zumiez", "https://example.com/a", "60.00")
        other_width = _deck(
            "Girl Howard Fullcourt Twin 8.0 Deck",
            "Tactics",
            "https://example.com/b",
            "50.00",
        )
        other_model = _deck(
            "Girl Howard Rick's Full Court 8.25 Deck",
            "CCS",
            "https://example.com/c",
            "55.00",
        )
        vague = _deck("Baker Team Deck 8.25", "Tactics", "https://example.com/d", "40.00")
        vague_two = _deck("Baker Team Deck 8.25", "CCS", "https://example.com/e", "41.00")
        self.assertNotEqual(product_identity(base)["key"], product_identity(other_width)["key"])
        self.assertNotEqual(product_identity(base)["key"], product_identity(other_model)["key"])
        self.assertIsNone(product_identity(vague))
        self.assertEqual(cross_store_groups([base, other_width, other_model, vague, vague_two]), [])

    def test_single_store_is_hidden_and_real_emb_can_match(self):
        only = _deck("Real EMB Deck 8.25", "Zumiez", "https://example.com/only", "50.00")
        self.assertEqual(cross_store_groups([only]), [])
        other = _deck("Real EMB Deck 8.25 x 32", "CCS", "https://example.com/ccs", "48.00")
        groups = cross_store_groups([only, other])
        self.assertEqual(len(groups), 1)
        self.assertIn("Real", groups[0]["label"])
        self.assertIn("EMB", groups[0]["label"])

    def test_wheels_need_diameter_and_trucks_keep_hollow_apart(self):
        conical = {
            "name": "Spitfire Formula Four Conical Full 54mm 99a Wheels",
            "url": "https://example.com/spit-z",
            "price_new": "35.00",
            "part": "Wheels",
            "store": "Zumiez",
        }
        conical_ccs = dict(conical, store="CCS", url="https://example.com/spit-c", price_new="32.00")
        radial = dict(
            conical,
            name="Spitfire Formula Four Radial Full 54mm 99a Wheels",
            store="Tactics",
            url="https://example.com/radial",
        )
        other_mm = dict(
            conical,
            name="Spitfire Formula Four Conical Full 56mm 99a Wheels",
            store="Tactics",
            url="https://example.com/56",
        )
        no_mm = dict(
            conical,
            name="Spitfire Formula Four Conical Full Wheels 99a",
            store="SkateWarehouse",
            url="https://example.com/nomm",
        )
        groups = cross_store_groups([conical, conical_ccs, radial, other_mm, no_mm])
        self.assertEqual(len(groups), 1)
        self.assertEqual({offer["store"] for offer in groups[0]["offers"]}, {"Zumiez", "CCS"})

        standard = {
            "name": "Independent Stage 11 Standard 149 Truck",
            "url": "https://example.com/indy-z",
            "price_new": "22.00",
            "part": "Trucks",
            "store": "Zumiez",
        }
        standard_ccs = dict(standard, store="CCS", url="https://example.com/indy-c", price_new="24.00")
        hollow = dict(
            standard,
            name="Independent Stage 11 Hollow 149 Truck",
            store="Tactics",
            url="https://example.com/hollow",
            price_new="20.00",
        )
        other_hanger = dict(
            standard,
            name="Independent Stage 11 Standard 139 Truck",
            store="SkateWarehouse",
            url="https://example.com/139",
        )
        truck_groups = cross_store_groups([standard, standard_ccs, hollow, other_hanger])
        self.assertEqual(len(truck_groups), 1)
        self.assertEqual({offer["store"] for offer in truck_groups[0]["offers"]}, {"Zumiez", "CCS"})

    def test_bones_swiss_matches_and_bones_reds_does_not(self):
        swiss = {
            "name": "Bones Swiss Skateboard Bearings",
            "url": "https://example.com/swiss-z",
            "price_new": "30.00",
            "price_old": "60.00",
            "part": "Bearings",
            "store": "Zumiez",
        }
        swiss_ccs = dict(swiss, store="CCS", url="https://example.com/swiss-c", price_new="28.00")
        reds = dict(
            swiss,
            name="Bones Reds Skateboard Bearings",
            store="Tactics",
            url="https://example.com/reds",
            price_new="18.00",
        )
        groups = cross_store_groups([swiss, swiss_ccs, reds])
        self.assertEqual(len(groups), 1)
        self.assertEqual({offer["store"] for offer in groups[0]["offers"]}, {"Zumiez", "CCS"})


class ReportSectionTests(unittest.TestCase):
    def test_report_highlights_cheapest_and_flags_all_time_low(self):
        cheap = _deck(
            "Baker Figgy Divine Evil Deck 8.25",
            "SkateWarehouse",
            "https://example.com/cheap",
            "50.00",
        )
        pricey = _deck(
            "Baker Figgy Divine Evil Deck 8.25",
            "Zumiez",
            "https://example.com/pricey",
            "64.99",
        )
        fresh = _deck("Baker Brand New 8.0 Deck", "CCS", "https://example.com/fresh", "40.00")
        lone = _deck("Real EMB Deck 8.5", "Tactics", "https://example.com/lone", "48.00")
        data = {
            "SkateWarehouse_Decks": [cheap],
            "Zumiez_Decks": [pricey],
            "CCS_Decks": [fresh],
            "Tactics_Decks": [lone],
        }
        history = {}
        history.update(
            _history_for(
                cheap["url"],
                {"2026-09-01": 60.0, "2026-09-15": 55.0, "2026-09-30": 50.0},
            )
        )
        history.update(_history_for(fresh["url"], {"2026-09-30": 40.0}))
        warning = {
            "store": "Zumiez",
            "part": "Decks",
            "kind": "empty",
            "dates": ["2026-09-29", "2026-09-30"],
            "last_positive_date": "2026-09-28",
            "last_positive_count": 12,
        }
        digest = Digest(warnings=[warning])
        html = build_report_html(
            data,
            {},
            history,
            generated_at="2026-09-30 08:00:00",
            digest=digest,
        )
        self.assertLess(html.index('id="storeAlerts"'), html.index("Digest"))
        self.assertIn("came back with no items two runs in a row", html)
        self.assertIn("Last good run on 2026-09-28 had 12 items", html)
        self.assertIn('id="compareSection"', html)
        self.assertIn('class="offer cheapest"', html)
        self.assertIn('data-store="SkateWarehouse"', html)
        compare = html.split('id="compareSection"', 1)[1].split('id="searchInput"', 1)[0]
        self.assertIn("$50.00", compare)
        self.assertIn("$64.99", compare)
        self.assertNotIn("Real EMB", compare)
        self.assertNotIn("Brand New", compare)
        self.assertEqual(compare.count('class="offer cheapest"'), 1)
        self.assertIn("ALL-TIME LOW", html)
        self.assertIn('id="atlSection"', html)
        atl = html.split('id="atlSection"', 1)[1].split('id="compareSection"', 1)[0]
        self.assertIn("Baker Figgy Divine Evil", atl)
        self.assertNotIn("Brand New", atl)
        self.assertTrue(all_time_low_status(cheap, history)["flagged"])
        self.assertFalse(all_time_low_status(fresh, history)["flagged"])


if __name__ == "__main__":
    unittest.main()
