"""Dry-check sale filters without scraping.

Run: python test_filters.py
"""

import unittest

from filters import (
    extract_deck_dimensions,
    extract_deck_size,
    filter_reason,
    is_meaningful_drop,
    item_passes_filters,
    normalize_product_name,
    passes_filters,
)
from report import build_report_html, compare_catalogs


class NormalizeTests(unittest.TestCase):
    def test_strips_clearance_prefix_and_nbsp(self):
        raw = "Clearance\xa0-10%April OG Logo Yellow/Purple MINI Deck 7.25 x 28.75"
        self.assertEqual(
            normalize_product_name(raw),
            "April OG Logo Yellow/Purple MINI Deck 7.25 x 28.75",
        )

    def test_strips_sale_prefix(self):
        raw = "Sale\xa0-24%Madness Son Deck 9.0 x 32"
        self.assertEqual(normalize_product_name(raw), "Madness Son Deck 9.0 x 32")

    def test_leaves_real_names_alone(self):
        name = "OJ Dressen Spider 56mm 101a White Skateboard Wheels"
        self.assertEqual(normalize_product_name(name), name)


class DeckSizeTests(unittest.TestCase):
    def test_two_digit_width(self):
        name = "Heroin Nolan Knock Off 10.25 Skateboard Deck"
        self.assertEqual(extract_deck_size(name), "10.25")
        self.assertEqual(extract_deck_dimensions(name)[0], 10.25)

    def test_width_by_length_not_truncated(self):
        self.assertEqual(
            extract_deck_dimensions("Baker Figgy Divine Evil Deck 8.3875 x 32")[0],
            8.3875,
        )
        self.assertEqual(
            extract_deck_dimensions("Deathwish Chris Athans Cherub Deck 8.475x31.875")[0],
            8.475,
        )
        self.assertEqual(
            extract_deck_dimensions("Powell Peralta Caballero Mask Deck 9.75x31.12")[0],
            9.75,
        )

    def test_clearance_percent_is_not_a_width(self):
        raw = "Clearance\xa0-9%Powell Peralta Hill Bulldog Blue/Red Fade Deck 10x31.5"
        width, length = extract_deck_dimensions(raw)
        self.assertEqual(width, 10.0)
        self.assertEqual(length, 31.5)
        self.assertNotEqual(extract_deck_size(raw), "9")

    def test_ten_point_width_in_pair(self):
        width, _length = extract_deck_dimensions(
            "Santa Cruz Malba Crash Test Reissue Deck 10.03 x 29.35"
        )
        self.assertEqual(width, 10.03)


class FilterTests(unittest.TestCase):
    def test_bearings_reject_skf_and_modus(self):
        self.assertFalse(passes_filters("SKF Ishod Pro Skateboard Bearings", "Bearings"))
        self.assertFalse(passes_filters("Modus ABEC 5 Skateboard Bearings - blue", "Bearings"))
        self.assertFalse(passes_filters("ABEC 7 Skateboard Bearings", "Bearings"))
        self.assertIn("bearing", filter_reason("SKF Louie Pro Skateboard Bearings", "Bearings"))

    def test_bearings_allow_listed_brands(self):
        self.assertTrue(passes_filters("Bones Swiss Skateboard Bearings", "Bearings"))
        self.assertTrue(passes_filters("Bronson G3 Skateboard Bearings", "Bearings"))
        self.assertTrue(passes_filters("Andalé Skateboard Bearings", "Bearings"))
        self.assertTrue(passes_filters("Andale Ceramic Skateboard Bearings", "Bearings"))
        self.assertTrue(passes_filters("CeramicSpeed Skateboard Bearings", "Bearings"))
        self.assertTrue(passes_filters("Zealous Bearings", "Bearings"))
        self.assertTrue(passes_filters("Independent Bearings", "Bearings"))
        self.assertTrue(passes_filters("Pixel Bearings", "Bearings"))

    def test_wheels_word_boundaries(self):
        self.assertTrue(passes_filters("OJ Dressen Spider 56mm Wheels", "Wheels"))
        self.assertTrue(passes_filters("Bones STF 53mm Skateboard Wheels", "Wheels"))
        self.assertTrue(passes_filters("powell-peralta dragon wheels", "Wheels"))
        self.assertFalse(passes_filters("Mojo 54mm Skateboard Wheels", "Wheels"))
        self.assertFalse(passes_filters("Ricta Clouds 54mm Wheels", "Wheels"))

    def test_trucks_word_boundaries_and_new_brands(self):
        self.assertTrue(
            passes_filters("Independent Eric Dressen Stage 4 Hollow Truck", "Trucks")
        )
        self.assertTrue(passes_filters("Ace 55 Classic Silver Skateboard Truck", "Trucks"))
        self.assertTrue(passes_filters("Thunder Polished Trucks", "Trucks"))
        self.assertTrue(passes_filters("Venture 5.2 Hi Trucks", "Trucks"))
        self.assertFalse(passes_filters("Space Program Nightcat Trucks", "Trucks"))
        self.assertFalse(passes_filters("Tensor Mag Light Trucks", "Trucks"))
        self.assertFalse(passes_filters("Face Off Hollow Trucks", "Trucks"))

    def test_dress_does_not_match_dressen(self):
        self.assertTrue(passes_filters("OJ Dressen Spider 56mm 101a White Skateboard Wheels", "Wheels"))
        self.assertFalse(passes_filters("CCS Floral Dress", "Decks", price_new="20", price_old="40"))
        self.assertFalse(passes_filters("Summer Dresses", "Wheels"))

    def test_apparel_all_stores(self):
        self.assertFalse(passes_filters("Nike SB Check Shirt", "Decks", price_new="20", price_old="40"))
        self.assertFalse(passes_filters("Spitfire Beanie", "Wheels"))
        self.assertFalse(passes_filters("Independent Hoodie", "Trucks"))
        self.assertTrue(
            passes_filters("Shorty's Mustache 8.25 Skateboard Deck", "Decks", price_new="40", price_old="60")
        )
        self.assertFalse(passes_filters("Board Shorts", "Decks", price_new="20", price_old="40"))

    def test_cruiser_longboard_mini_complete(self):
        self.assertFalse(
            passes_filters(
                "Daddies Trip On This Cruiser Skateboard Deck",
                "Decks",
                price_new="22.95",
                price_old="29.95",
            )
        )
        self.assertFalse(
            passes_filters(
                "Clearance\xa0-10%April OG Logo Yellow/Purple MINI Deck 7.25 x 28.75",
                "Decks",
                price_new="64.98",
                price_old="72.95",
            )
        )
        self.assertFalse(
            passes_filters("Loaded Hola Lou Coyote 30.75", "Decks", price_new="68", price_old="95")
        )
        self.assertFalse(
            passes_filters("Sector 9 Longboard Deck", "Decks", price_new="40", price_old="80")
        )
        self.assertFalse(
            passes_filters("Penny Nickel 22 Cruiser", "Decks", price_new="20", price_old="40")
        )
        self.assertFalse(
            passes_filters("Element Complete Skateboard", "Decks", price_new="40", price_old="80")
        )
        self.assertTrue(
            passes_filters(
                "Flip Penny Tom's Friends 8.1 Skateboard Deck",
                "Decks",
                price_new="55.95",
                price_old="69.07",
            )
        )

    def test_deck_width_window_and_discount_floors(self):
        self.assertFalse(
            passes_filters(
                "Santa Cruz Malba Crash Test Reissue Deck 10.03 x 29.35",
                "Decks",
                price_new="79.98",
                price_old="108.95",
            )
        )
        self.assertFalse(
            passes_filters(
                "Mini Logo Peacock Feather 7.4 Skateboard Deck",
                "Decks",
                price_new="20",
                price_old="40",
            )
        )
        self.assertTrue(
            passes_filters(
                "Mini Logo Peacock Feather 7.5 255 Shape Skateboard Deck",
                "Decks",
                price_new="30.95",
                price_old="37.74",
            )
        )
        self.assertTrue(
            passes_filters(
                "Baker Bryan Herman Deck 8.125 x 31.5",
                "Decks",
                price_new="74.98",
                price_old="86.99",
            )
        )
        self.assertFalse(
            passes_filters("Baker Team Deck 8.25", "Decks", price_new="91", price_old="100")
        )
        self.assertFalse(
            passes_filters("Shop Deck 8.25", "Decks", price_new="88", price_old="100")
        )
        self.assertTrue(
            passes_filters("Shop Deck 8.25", "Decks", price_new="85", price_old="100")
        )
        self.assertTrue(
            passes_filters(
                "Anti-Hero Jalopi Shop Lurker 9.18 Skateboard Deck",
                "Decks",
                price_new="61.95",
                price_old="88.50",
            )
        )

    def test_item_dict(self):
        self.assertFalse(
            item_passes_filters(
                {
                    "name": "SKF Ishod Pro Skateboard Bearings",
                    "part": "Bearings",
                    "url": "https://www.zumiez.com/skf-ishod-pro-skateboard-bearings-1.html",
                    "price_new": "34.99",
                    "price_old": "45.95",
                }
            )
        )


class DropTests(unittest.TestCase):
    def test_meaningful_drop_thresholds(self):
        self.assertTrue(is_meaningful_drop("40", "35"))
        self.assertTrue(is_meaningful_drop("20", "19"))  # 5%
        self.assertTrue(is_meaningful_drop("100", "97"))  # $3
        self.assertFalse(is_meaningful_drop("40", "39"))  # $1 and 2.5%
        self.assertFalse(is_meaningful_drop("40", "42"))
        self.assertFalse(is_meaningful_drop("40", "40"))


class CompareAndReportTests(unittest.TestCase):
    def test_compare_hides_noise_and_failed_removals(self):
        prev = {
            "Zumiez_Bearings": [
                {
                    "name": "SKF Ishod Pro Skateboard Bearings",
                    "url": "https://example.com/skf",
                    "price_new": "34.99",
                    "price_old": "45.95",
                    "part": "Bearings",
                    "store": "Zumiez",
                },
                {
                    "name": "Bones Swiss Skateboard Bearings",
                    "url": "https://example.com/bones",
                    "price_new": "30.00",
                    "price_old": "40.00",
                    "part": "Bearings",
                    "store": "Zumiez",
                },
            ],
            "CCS_Decks": [
                {
                    "name": "Baker Team 8.25 Deck",
                    "url": "\nhttps://example.com/baker\n",
                    "price_new": "50.00",
                    "price_old": "70.00",
                    "part": "Decks",
                    "store": "CCS",
                }
            ],
        }
        curr = {
            "Zumiez_Bearings": [
                {
                    "name": "Bones Swiss Skateboard Bearings",
                    "url": "https://example.com/bones",
                    "price_new": "24.00",
                    "price_old": "40.00",
                    "part": "Bearings",
                    "store": "Zumiez",
                },
                {
                    "name": "SKF Kader Pro Skateboard Bearings",
                    "url": "https://example.com/skf-new",
                    "price_new": "20.00",
                    "price_old": "40.00",
                    "part": "Bearings",
                    "store": "Zumiez",
                },
            ],
            "CCS_Decks": [],
        }
        changes = compare_catalogs(prev, curr, failed_keys={"CCS_Decks"})
        flat = [change for site_changes in changes.values() for change in site_changes]
        types = {(change["type"], change.get("name") or change.get("item", {}).get("name")) for change in flat}
        self.assertIn(("price_drop", "Bones Swiss Skateboard Bearings"), types)
        self.assertFalse(any("SKF" in (change.get("name") or change.get("item", {}).get("name", "")) for change in flat))
        self.assertFalse(any(change["type"] == "removed" for change in flat))

        drop = next(change for change in flat if change["type"] == "price_drop")
        self.assertEqual(drop["delta"], 6.0)
        self.assertEqual(drop["old"], "30.00")
        self.assertEqual(drop["new"], "24.00")

    def test_small_drop_and_cruiser_are_not_news(self):
        prev = {
            "Zumiez_Wheels": [
                {
                    "name": "Spitfire Formula Four 53mm Wheels",
                    "url": "https://example.com/spit",
                    "price_new": "40.00",
                    "price_old": "50.00",
                    "part": "Wheels",
                    "store": "Zumiez",
                }
            ]
        }
        curr = {
            "Zumiez_Wheels": [
                {
                    "name": "Spitfire Formula Four 53mm Wheels",
                    "url": "https://example.com/spit",
                    "price_new": "39.00",
                    "price_old": "50.00",
                    "part": "Wheels",
                    "store": "Zumiez",
                },
                {
                    "name": "Daddies Trip On This Cruiser Skateboard Deck",
                    "url": "https://example.com/cruiser",
                    "price_new": "22.95",
                    "price_old": "29.95",
                    "part": "Decks",
                    "store": "Zumiez",
                },
            ]
        }
        changes = compare_catalogs(prev, curr)
        self.assertEqual(changes, {})

    def test_report_leads_with_digest_and_labels_prior_sale(self):
        data = {
            "Zumiez_Bearings": [
                {
                    "name": "SKF Ishod Pro Skateboard Bearings",
                    "url": "https://example.com/skf",
                    "price_new": "34.99",
                    "price_old": "45.95",
                    "part": "Bearings",
                    "store": "Zumiez",
                },
                {
                    "name": "Bones Swiss Skateboard Bearings",
                    "url": "https://example.com/bones",
                    "price_new": "24.00",
                    "price_old": "40.00",
                    "part": "Bearings",
                    "store": "Zumiez",
                },
            ],
            "CCS_Decks": [
                {
                    "name": "Daddies Trip On This Cruiser Skateboard Deck",
                    "url": "https://example.com/cruiser",
                    "price_new": "22.95",
                    "price_old": "29.95",
                    "part": "Decks",
                    "store": "CCS",
                },
                {
                    "name": "Baker Team 8.25 Deck",
                    "url": "https://example.com/baker",
                    "price_new": "40.00",
                    "price_old": "70.00",
                    "part": "Decks",
                    "store": "CCS",
                },
            ],
        }
        changes = {
            "Zumiez_Bearings": [
                {
                    "type": "price_drop",
                    "url": "https://example.com/bones",
                    "name": "Bones Swiss Skateboard Bearings",
                    "old": "30.00",
                    "new": "24.00",
                    "delta": 6.0,
                    "percent_vs_prior": 20.0,
                    "item": data["Zumiez_Bearings"][1],
                },
                {
                    "type": "new",
                    "item": {
                        "name": "SKF Kader Pro Skateboard Bearings",
                        "url": "https://example.com/skf-new",
                        "price_new": "20",
                        "price_old": "40",
                        "part": "Bearings",
                        "store": "Zumiez",
                    },
                },
            ],
            "CCS_Decks": [
                {
                    "type": "removed",
                    "item": {
                        "name": "Real Classic Oval 8.5 Skateboard Deck",
                        "url": "https://example.com/real",
                        "price_new": "40",
                        "price_old": "70",
                        "part": "Decks",
                        "store": "CCS",
                    },
                }
            ],
        }
        html = build_report_html(
            data,
            changes,
            failed_keys={"CCS_Decks"},
            generated_at="2026-09-25 12:00:00",
        )
        self.assertLess(html.index("Digest"), html.index("All Deals"))
        self.assertIn("vs prior sale", html)
        self.assertIn("−$6.00", html)
        self.assertIn("Bones Swiss Skateboard Bearings", html)
        self.assertNotIn("SKF", html)
        self.assertNotIn("Cruiser", html)
        self.assertNotIn("Real Classic Oval", html)
        self.assertIn('class="section-header collapsed"', html)
        self.assertIn("Baker Team 8.25 Deck", html)


if __name__ == "__main__":
    unittest.main()
