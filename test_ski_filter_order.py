"""Ski filter order and scope per heading (docs/filters-evo-model.md, 2026-11-21)."""

import unittest

import sports
from sports import facets as shared
from sports.ski import facets


class SkiOrderTests(unittest.TestCase):
    def test_orders_from_the_doc(self):
        self.assertEqual(facets.ORDER["Boots"][:4], ("mondo", "gender", "flex", "last"))
        self.assertEqual(facets.ORDER["Bindings"][:3], ("din", "brake", "gender"))
        self.assertEqual(facets.ORDER["Goggles"][:2], ("gender", "goggle_size"))
        for heading in ("Skis", "Boots", "Bindings"):
            self.assertEqual(facets.ORDER[heading][-1], "condition", heading)
        keys = {field["key"] for field in facets.FIELDS}
        for heading, order in facets.ORDER.items():
            self.assertLessEqual(set(order), keys, heading)

    def test_rank(self):
        self.assertEqual(facets.rank("waist"), "Skis:3")
        self.assertIn("Boots:2", facets.rank("gender"))
        self.assertEqual(facets.rank("not_a_field"), "")

    def test_scopes(self):
        field = {f["key"]: f for f in facets.FIELDS}
        for key in ("ability", "condition"):
            self.assertEqual(field[key]["categories"], ("Skis", "Boots", "Bindings"), key)
        for key in ("protects", "helmet_style", "certification", "rotational", "prot_size", "age"):
            self.assertNotIn("Goggles", field[key]["categories"], key)
        for key in ("goggle_size", "goggle_fit", "goggle_lens"):
            self.assertEqual(field[key]["categories"], ("Goggles",), key)

    def test_sidebar_stamps_rank_only_where_ordered(self):
        item = {"url": "https://x/ski", "name": "Line Pandora 94", "part": "Skis", "price_new": "300", "price_old": "500",
                "technical_offers": [{"available": True, "specs": {"waist": ["85–94 mm"], "gender": ["Women"]}}]}
        section = lambda sid, label, body, open_default=False, **_: f'<section data-section="{sid}">{body}</section>'
        with sports.SKI.active():
            html = shared.sidebar({"evo_Skis": [item]}, section, sports.SKI)
        self.assertIn('data-technical-field="waist" data-rank="Skis:3"', html)
        mtb = dict(item, name="Santa Cruz Tallboy 29 Bike", part="Bikes",
                   technical_offers=[{"available": True, "specs": {"wheel_size": ["29"]}}])
        with sports.MTB.active():
            html = shared.sidebar({"x_Bikes": [mtb]}, section, sports.MTB)
        self.assertIn('data-technical-field="wheel_size"', html)
        self.assertNotIn("data-rank", html)


if __name__ == "__main__":
    unittest.main()
