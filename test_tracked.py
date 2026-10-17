"""Tracked sneaker and accessory rules. No network."""

import os
import tempfile
import unittest

from filters import filter_reason
from page import listing_brand
from tracked import accessory_rule, load_tracked, parse_tracked, sneaker_rule


CATALOG = {
    "sneakers": [
        {"id": "vans-wafflecup", "all": [], "any": ["Wafflecup", "Waffle Cup"]},
        {"id": "nike-sb-dunk", "all": ["SB"], "any": ["Dunk Low", "Dunk High", "SB Dunk"]},
    ],
    "phrases": ["grip tape", "hardware", "bolts", "bolt", "wax", "tool", "riser", "risers", "bushing", "bushings"],
    "types": ["Hardware", "Grip tape"],
}


class TrackedCatalogTests(unittest.TestCase):
    def test_yaml_file_loads_the_two_sneaker_rules(self):
        catalog = load_tracked()
        ids = [rule["id"] for rule in catalog["sneakers"]]
        self.assertEqual(ids, ["vans-wafflecup", "nike-sb-dunk"])
        self.assertIn("grip tape", catalog["phrases"])
        self.assertIn("Hardware", catalog["types"])

    def test_broken_file_matches_nothing(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "tracked.yaml")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("sneakers:\n  - not a rule\n")
            catalog = load_tracked(path)
        self.assertEqual(catalog["sneakers"], [])
        self.assertEqual(sneaker_rule("Vans Wafflecup", catalog=catalog), "")

    def test_owner_can_add_a_model_without_code(self):
        text = """
sneakers:
  - id: half-cab
    any:
      - Half Cab
"""
        catalog = parse_tracked(text)
        self.assertEqual(sneaker_rule("Vans Skate Half Cab", catalog=catalog), "half-cab")
        self.assertEqual(sneaker_rule("Vans Wafflecup", catalog=catalog), "")

    def test_wafflecup_and_sb_dunk_matching(self):
        self.assertEqual(sneaker_rule("Vans Skate Kyle Walker", "Wafflecup sole", CATALOG), "vans-wafflecup")
        self.assertEqual(sneaker_rule("Vans BMX Proof Waffle Cup", catalog=CATALOG), "vans-wafflecup")
        self.assertEqual(sneaker_rule("CCS Waffle Knit Beanie", catalog=CATALOG), "")
        self.assertEqual(sneaker_rule("Nike SB Dunk Low Pro", catalog=CATALOG), "nike-sb-dunk")
        self.assertEqual(sneaker_rule("Nike SB x Beyond Dunk High Pro", catalog=CATALOG), "nike-sb-dunk")
        self.assertEqual(sneaker_rule("Nike Dunk Low", catalog=CATALOG), "")
        self.assertEqual(sneaker_rule("Nike SB Zoom Blazer", catalog=CATALOG), "")
        self.assertEqual(sneaker_rule("DGK Slam Dunk", catalog=CATALOG), "")

    def test_accessory_phrases_and_types(self):
        self.assertEqual(accessory_rule("Mob Grip Tape", catalog=CATALOG), "grip tape")
        self.assertEqual(accessory_rule("CCS Phillips 1 inch", "Hardware", CATALOG), "Hardware")
        self.assertEqual(accessory_rule("Girl Wax Deck", catalog=CATALOG), "wax")
        self.assertEqual(accessory_rule("Plain Deck", "Decks", CATALOG), "")
        self.assertIn("hanger", load_tracked()["exclude"])
        self.assertEqual(accessory_rule("Slappy ST1 Hanger", "Hardware"), "")
        self.assertEqual(accessory_rule("Krux DLK K5 Kingpin Set", "Hardware"), "")
        self.assertEqual(accessory_rule("Independent Phillips Hardware", "Hardware"), "hardware")

    def test_shared_filters_keep_the_allow_list(self):
        self.assertEqual(
            filter_reason("SKF Ishod Bearings", "Bearings", price_new="20", price_old="30"),
            "bearing brand not allowed",
        )
        self.assertEqual(
            filter_reason("Modus ABEC 7 Bearings", "Bearings", price_new="18.95", price_old="22.00"),
            "bearing brand not allowed",
        )
        self.assertIsNone(filter_reason("Bones Reds Bearings", "Bearings", price_new="24", price_old="32"))
        self.assertIsNone(
            filter_reason("Vans Skate Half Cab Wafflecup Shoes", "Sneakers", price_new="59", price_old="85")
        )
        self.assertEqual(filter_reason("Nike Dunk Low", "Sneakers", price_new="70", price_old="90"), "not a tracked sneaker")
        self.assertEqual(filter_reason("Vans Hat", "Sneakers", price_new="14", price_old="22"), "apparel")
        self.assertIsNone(filter_reason("Mob Grip Tape", "Accessories", price_new="5", price_old="8"))
        self.assertEqual(filter_reason("Girl Wax Deck", "Accessories", price_new="40", price_old="60"), "not an accessory")
        self.assertEqual(
            filter_reason("Toy Machine Bolts 58mm 97a Black Skateboard Wheels", "Accessories", price_new="21.99", price_old="32"),
            "not an accessory",
        )
        self.assertEqual(filter_reason("Rusted Bolt Shoes", "Accessories", price_new="40", price_old="60"), "apparel")
        self.assertEqual(
            filter_reason("Riser Pads", "Accessories", product_type="T-Shirts", price_new="20", price_old="28"),
            "apparel",
        )
        self.assertIsNone(
            filter_reason("RipTide Longboard Bushings", "Accessories", price_new="12", price_old="16")
        )
        self.assertEqual(listing_brand("Nike SB Dunk Low Pro", "Sneakers"), "Nike SB")
        self.assertEqual(listing_brand("Vans Skate Old Skool Wafflecup", "Sneakers"), "Vans")
