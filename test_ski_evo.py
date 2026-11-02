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
