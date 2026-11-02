"""evo-style ski filters (sports/ski/evo.py), read from how Gear West actually
words its descriptions (store probe snippets, 2026-11-02). Nothing guessed."""

import unittest

from sports.ski import evo


class SkiTests(unittest.TestCase):
    def test_gear_west_wording(self):
        fields = evo.fields("Skis", "Atomic Bent 90 Ski", "Skis", ["Park"],
                            "Intermediate floatation: 87mm at the waist Very short radius (13m): super reactivity "
                            "Double rocker. Designed for beginner and intermediate skiers, this all-mountain ski")
        self.assertEqual(fields, {"ski_type": ["Park & Freestyle"], "waist": ["85–94 mm"], "radius": ["Short (under 16 m)"],
                                  "rocker": ["Rocker / Camber / Rocker"], "ability": ["Beginner", "Intermediate"]})

    def test_dimensions_bindings_and_camber(self):
        self.assertEqual(evo.waist_widths("Dimensions: 120/68/104 Radius: 12.5 m"), [68])
        self.assertEqual(evo.turn_radii("Dimensions: 120/68/104 Radius: 12.5 m"), [12.5])
        self.assertEqual(evo.bindings("Dynastar M-Menace 90 Ski w/ Look XP11 Binding 2026", ""), "Included")
        self.assertEqual(evo.bindings("Nordica Dobermann SL Race Ski (Bindings Not Included)", ""), "Flat (no bindings)")
        self.assertEqual(evo.bindings("Black Crows Justis", "Bindings Included: Salomon WRT 12 GW Binding"), "Included")
        self.assertEqual(evo.rocker_profile("Full Camber Sintered UHD Base"), "Full Camber")
        self.assertEqual(evo.rocker_profile("AR Freestyle Rocker Poplar Ash Core"), "Rocker / Camber / Rocker")

    def test_nothing_is_guessed(self):
        self.assertEqual(evo.fields("Skis", "Atomic Bent 110", "Skis", [], "A fun ski."), {},
                         "the model number 110 is not a stated waist")
        self.assertEqual(evo.ski_types("Skis", [], "Race the lifts to first chair."), [], "'race' in prose is not a type")
        self.assertEqual(evo.ability("Last year at Gear West we tested it."), [])
        self.assertEqual(evo.waist_widths("Available in 172 and 180 cm."), [])
        self.assertEqual(evo.turn_radii("Built for wide-radius turns in deep powder."), [])


class BootTests(unittest.TestCase):
    def test_gear_west_wording(self):
        fields = evo.fields("Boots", "Lange Shadow 120 MV", "Boots", ["All Mountain"],
                            "MEMORY FIT 100MM LAST GripWalk ISO 5355 (Alpine DIN) SKI/WALK MODE : T2 Ability: Advanced to Expert")
        self.assertEqual(fields, {"ski_type": ["All-Mountain"], "last": ["Medium (99–101 mm)"], "flex": ["Stiff (105–120)"],
                                  "sole": ["GripWalk", "Alpine (ISO 5355)"], "walk": ["Walk mode"], "ability": ["Advanced", "Expert"]})

    def test_flex_stated_beats_model_and_is_not_guessed(self):
        self.assertEqual(evo.flex("Lange Shadow 120 MV", "Flex: 110"), (110, "stated"))
        self.assertEqual(evo.flex("Lange Shadow 120 MV", ""), (120, "model"))
        self.assertEqual(evo.flex("Nordica Speedmachine 3 110 Ski Boots 2026", ""), (110, "model"), "the year is ignored")
        self.assertEqual(evo.flex("K2 FL3X Method", "a forgiving flex"), (None, None))
        self.assertEqual(evo.flex("Tecnica Mach1 120 LV 130", ""), (None, None), "two numbers: ambiguous")
        self.assertEqual(evo.last_widths("For the last decade, the boot"), [], "'last' as a word is not a last width")
        self.assertEqual(evo.ability("Ability: Beginner to Advanced"), ["Beginner", "Intermediate", "Advanced"])


if __name__ == "__main__":
    unittest.main()


class UtahSkiTests(unittest.TestCase):
    """Utah Ski: categories and specs come from tags (store probe, 2026-11-02)."""

    FEED = [
        {"title": "Mantra 102 Skis 2026", "vendor": "VOLKL", "handle": "mantra", "product_type": "D S M",
         "tags": ["Category: Demo Skis", "Skis-Best Use: All Mountain", "Skis-With Bindings: Yes", "Skill Level: Advanced",
                  "Skill Level: Expert", "Skis-Waist Width: 85-95mm", "Skis-Rocker Profile: Rocker/Camber/Rocker", "Gender: Mens"],
         "options": [{"name": "Size"}], "variants": [{"id": 1, "option1": "177", "price": "499", "compare_at_price": "899"}]},
        {"title": "Shell Jacket", "vendor": "Picture", "handle": "jacket", "product_type": "C J M", "tags": ["Category: Jackets"],
         "variants": [{"id": 2, "price": "100", "compare_at_price": "200"}]},
        {"title": "Custom Snowboard", "vendor": "Burton", "handle": "sb", "product_type": "B S M", "tags": ["Category: Snowboards"],
         "variants": [{"id": 3, "price": "300", "compare_at_price": "500"}]},
        {"title": "Snowboard Boots", "vendor": "Burton", "handle": "sbb", "product_type": "B B M",
         "tags": ["Category: Snowboard Boots"], "variants": [{"id": 4, "price": "200", "compare_at_price": "300"}]},
        {"title": "Hawx Ultra 120 Ski Boots", "vendor": "Atomic", "handle": "hawx", "product_type": "A B M",
         "tags": ["Category: Ski Boots", "Gender: Mens"], "options": [{"name": "Size"}],
         "variants": [{"id": 5, "option1": "27.5", "price": "399", "compare_at_price": "649"}]},
    ]

    def test_tag_categories_and_specs(self):
        import json

        import sports
        from sports.ski import stores

        kept = {}
        with sports.SKI.active():
            for scraper in stores.shopify.scrapers_for(stores.UTAH_SKI, stores.PARTS):
                for item in scraper.parse(json.dumps({"products": self.FEED})):
                    kept[item["name"]] = item
        self.assertEqual(sorted(kept), ["Atomic Hawx Ultra 120 Ski Boots", "Völkl Mantra 102 Skis 2026"],
                         "clothing and snowboard gear are left out")
        mantra = kept["Völkl Mantra 102 Skis 2026"]["technical_specs"]
        self.assertEqual(mantra["waist"], ["85–94 mm"], "a tagged 85-95mm range is 85..94")
        self.assertEqual((mantra["ski_type"], mantra["bindings"], mantra["ability"], mantra["rocker"]),
                         (["All-Mountain"], ["Included"], ["Advanced", "Expert"], ["Rocker / Camber / Rocker"]))
        self.assertEqual(kept["Atomic Hawx Ultra 120 Ski Boots"]["technical_specs"]["mondo"], ["27.5"])
        self.assertIn(stores.UTAH_SKI, stores.STORES)
        self.assertEqual([url.split("/collections/")[1].split("/")[0] for url in stores.UTAH_SKI.sale_jsons],
                         ["sale", "demos-sale"])

    def test_tag_readers(self):
        self.assertEqual(evo.waist_widths("Skis-Waist Width: 96-110mm"), [96, 109])
        self.assertEqual(evo.bindings("Mantra 102", "Skis-With Bindings: No"), "Flat (no bindings)")
        from sports.ski.stores import utah_part
        self.assertEqual([utah_part([tag]) for tag in ("Category: Skis", "Category: Demo Skis", "Category: Ski Boots",
                                                      "Category: Ski Bindings", "Category: Snowboards", "Category: Jackets")],
                         ["Skis", "Skis", "Boots", "Bindings", None, None])
