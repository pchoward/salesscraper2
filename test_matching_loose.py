"""Looser deck matching (owner, 2026-11-06: only 2 cross-store matches).
Good pairs from the live catalog must match; look-alikes that are different
products must not."""

import unittest

import matching


def deck(store, name, price="50.00", **extra):
    return dict({"store": store, "name": name, "part": "Decks", "price_new": price, "price_old": "80.00",
                 "url": f"https://{store}.example/{abs(hash(name))}"}, **extra)


def paired(left, right, part="Decks"):
    groups = matching.cross_store_groups([dict(left, part=part), dict(right, part=part)], apply_filters=False)
    return len(groups) == 1


class LooseDeckTests(unittest.TestCase):
    def test_real_pairs_match(self):
        pairs = [
            ("Opera Trey Lightning 8.25\" Skateboard Deck", "Opera Trey Wood Lightning Deck 8.25 x 32"),
            ("Real Nicole Pig Run 8.38\" Skateboard Deck", "Real Skateboard Deck Nicole Huase Pig Run 8.38\" x 32.25\""),
            ("Primitive Nuevo Script 7.75\" Skateboard Deck", "Primitive Skateboard Deck Nuevo Script Blue 7.75\" x 31.05\""),
            ("Birdhouse Lizzie Armanto Toybox Deck 8.0 x 31.75", "Birdhouse Skateboard Deck Lizzie Armanto Toy Box 8.0\" x 31.75\""),
            ("Jacuzzi Caswell Roll Up 8.25\" Skateboard Deck", "Jacuzzi Rider Stock Skateboard Deck Caswell Berry Rollup 8.25\" x 32.25\""),
            ("Santa Cruz Winkowski Cosmic 10.35 Skateboard Deck - prismatic", "Santa Cruz Skateboard Deck Winkowski Cosmic 10.35\" x 30.54\""),
            ("Anti-Hero Daan I Farted In Yoga 8.38\" Skateboard Deck", "Anti Hero Skateboard Deck Daan I Farted in Yoga Class 8.38\" x 32.25\""),
        ]
        for left, right in pairs:
            self.assertTrue(paired(deck("Zumiez", left), deck("TGM", right)), (left, right))

    def test_different_products_stay_apart(self):
        pairs = [
            ("Heroin Dead Dave KO2 Mummy Deck 10.125 x 32.25", "Heroin Skateboard Deck Dead Dave Dead Head Green 10.125\" x 32.425\""),
            ("Baker Sammy Baca Divine Evil Deck 8.5 x 32", "Baker Baca Cerberus 8.5\" Skateboard Deck"),
            ("Opera Trey Lightning 8.25\" Skateboard Deck", "Opera Trey Lightning 8.5\" Skateboard Deck"),  # width differs
            ("Opera Trey Lightning 8.25\" Skateboard Deck", "Opera Trey Piece 8.25\" Skateboard Deck"),
        ]
        for left, right in pairs:
            self.assertFalse(paired(deck("SkateWarehouse", left), deck("Zumiez", right)), (left, right))

    def test_a_vague_name_never_chains_two_decks(self):
        items = [deck("Zumiez", "Anti-Hero Grant Repossessed 8.5\" Skateboard Deck"),
                 deck("TGM", "Anti Hero Skateboard Deck Grant Taylor Repossessed Red 8.5\""),
                 deck("Tactics", "Anti Hero Grant Taylor Repossessed Blue Foil 8.5 Skateboard Deck")]
        groups = matching.cross_store_groups(items, apply_filters=False)
        self.assertLessEqual(max((len(g["offers"]) for g in groups), default=0), 2)

    def test_store_width_when_the_name_has_none(self):
        left = deck("Deathgear", "Heroin Auntie Razoregg Skateboard Deck", widths=[9.75])
        right = deck("TGM", "Heroin Skateboard Deck Auntie Razoregg (Assorted) 9.75\" x 32\"")
        self.assertTrue(paired(left, right))
        several = deck("Deathgear", "Heroin Auntie Razoregg Skateboard Deck", widths=[9.75, 10.0])
        self.assertIsNone(matching.describe_item(several)["key"], "a listing in several widths has no one size")


class StrictPartsTests(unittest.TestCase):
    def test_bearings_editions_stay_apart(self):
        self.assertFalse(paired(deck("SkateWarehouse", "Bronson Speed Co. x Fucking Awesome G3 Bearings"),
                                deck("Tactics", "Bronson Speed Co. G3 Skateboard Bearings - orange"), part="Bearings"))

    def test_single_truck_is_not_matched_to_a_pair(self):
        self.assertFalse(paired(deck("Zumiez", "Ace 60 AF1 Satin Lime Skateboard Truck"),
                                deck("TGM", "Ace Skateboard Trucks AF1 Satin Lime 60 (8.75\" Axle) Pair"), part="Trucks"))


if __name__ == "__main__":
    unittest.main()
