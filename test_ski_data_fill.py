"""Ski data from Grok's evo list (docs/filters-evo-model.md, 2026-11-21):
binding brake width, Unisex, BOA, helmet shell and goggle lens shape."""

import unittest

from sports.ski import evo, facets, specs


def binding(option_name, values):
    return {"options": [{"name": "Color"}, {"name": option_name}],
            "variants": [{"option1": "Black", "option2": value} for value in values]}


class BrakeTests(unittest.TestCase):
    def test_brake_option_names(self):
        cases = {("Ski Brake Width", ("85mm", "95mm")): ["85 mm", "95 mm"],
                 ("Brake", ("100mm", "90mm")): ["100 mm", "90 mm"],
                 ("Size", ("90 mm", "100 mm", "110 mm")): ["90 mm", "100 mm", "110 mm"],
                 ("Size", ("L90", "L100")): ["90 mm", "100 mm"],
                 ("Size", ("136 mm (No Screws)",)): ["136 mm"],
                 ("Size", ("S", "M", "L")): []}
        for (name, values), expected in cases.items():
            product = binding(name, values)
            got = [b for variant in product["variants"] for b in specs.variant_brake(product, variant)]
            self.assertEqual(got, expected, (name, values))


class GenderTests(unittest.TestCase):
    def test_unisex_and_store_tags(self):
        self.assertEqual(specs.gender("Skis", ["gender_unisex"]), "Unisex")
        self.assertEqual(specs.gender("Skis", ["gender_ladies"]), "Women")
        self.assertEqual(specs.gender("Skis", ["gender_mens"]), "Men")
        self.assertEqual(specs.gender("Ski Bindings", ["Mens", "Womens"]), "Unisex")
        self.assertEqual(specs.gender("Salomon Stance 90 Unisex All-Mountain Skis", []), "Unisex")
        self.assertEqual(specs.gender("Skis", [], "K2 Women's Mindbender 85 Skis"), "Women")
        self.assertEqual(specs.gender("Skis", ["Mens", "Womens", "Kids"]), "Kids")
        self.assertIsNone(specs.gender("Skis", [], "Nordica Enforcer 89 Skis"))
        field = next(f for f in facets.FIELDS if f["key"] == "gender")
        self.assertEqual(field["order"], ["Men", "Women", "Unisex", "Kids"])


class NewFieldTests(unittest.TestCase):
    def test_boa(self):
        self.assertEqual(evo.fields("Boots", "K2 Women's BFC BOA 85 Ski Boots", "", [], "")["closure"], ["BOA"])
        self.assertNotIn("closure", evo.fields("Boots", "Lange Shadow 120 MV", "", [], "Four buckles."))

    def test_helmet_shell(self):
        self.assertEqual(evo.fields("Helmets", "Giro Taggert MIPS Helmet", "", [], "In-mold construction")["helmet_shell"],
                         ["In-mold"])
        self.assertEqual(evo.helmet_shell("Smith Mission", "Hybrid shell construction"), "Hybrid")
        self.assertEqual(evo.helmet_shell("POC Fornix", "In-mold liner bonded to a hard shell"), "Hybrid")
        self.assertEqual(evo.helmet_shell("Giro Ledge", "ABS shell"), "Hard shell")
        self.assertNotIn("helmet_shell", evo.fields("Helmets", "Pret Epic MIPS Helmet", "", [], "Warm and light."))

    def test_lens_shape(self):
        fields = evo.fields("Protection", "Smith Reason OTG Goggles", "", [], "ChromaPop spherical lens")
        self.assertEqual(fields["lens_shape"], ["Spherical"])
        self.assertEqual(evo.lens_shape("Sweet Protection Connor RIG", "Toric lens"), "Toric")
        self.assertIsNone(evo.lens_shape("Two lens", "Comes with a cylindrical and a spherical lens"))
        self.assertNotIn("lens_shape", evo.fields("Helmets", "Giro Jackson MIPS Helmet", "", [], "spherical comfort"))

    def test_facets(self):
        field = {f["key"]: f for f in facets.FIELDS}
        self.assertEqual(field["closure"]["categories"], ("Boots",))
        self.assertEqual(field["lens_shape"]["categories"], ("Goggles",))
        self.assertEqual(field["helmet_shell"]["categories"], ("Helmets",))
        self.assertIn("closure", facets.ORDER["Boots"])
        self.assertEqual(facets.ORDER["Boots"][-1], "condition")
        self.assertIn("lens_shape", facets.ORDER["Goggles"])


if __name__ == "__main__":
    unittest.main()
