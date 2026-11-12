"""Demo gear stays listed, labelled "Demo" (owner, 2026-11-12)."""

import unittest

import sports
from report import build_report_html
from sports import condition
from sports.mtb import facets as mtb_facets
from sports.ski import facets as ski_facets


def item(name, url="https://www.utahskis.com/products/x"):
    return {"name": name, "url": url, "part": "Skis", "price_new": "399.00", "price_old": "699.00", "store": "Utah Ski",
            "technical_offers": [{"variant_id": 1, "price": 399.0, "compare": 699.0, "available": True,
                                  "specs": {"length": ["170–179 cm"]}}],
            "technical_specs": {"length": ["170–179 cm"]}}


class DemoLabelTests(unittest.TestCase):
    def test_demo_names(self):
        for name in ("Nordica Enforcer 89 Mens Demo Skis 2026", "Santa Cruz Bullit 4 C GX AXS Demo (Small)",
                     "Ex-Demo – Polygon Xtrada 5 - Mountain Bike [New]"):
            self.assertTrue(condition.is_demo(name), name)
        for name in ("Demolition Rotator V3 18\" Freecoaster Wheel", "Nordica Enforcer 94 Skis 2026"):
            self.assertFalse(condition.is_demo(name), name)

    def test_label_reaches_the_filters(self):
        demo = item("Nordica Enforcer 89 Mens Demo Skis 2026")
        data = {"Utah Ski_Skis": [demo, item("Nordica Enforcer 94 Skis 2026", "https://www.utahskis.com/products/y")]}
        self.assertEqual(condition.label_items(data), 1)
        self.assertEqual(demo["condition"], "Demo")
        self.assertEqual(demo["technical_specs"], {"length": ["170–179 cm"], "condition": ["Demo"]})
        self.assertEqual(demo["technical_offers"][0]["specs"]["condition"], ["Demo"])
        self.assertNotIn("condition", data["Utah Ski_Skis"][1])
        self.assertEqual(condition.label_items(data), 0)  # already labelled

    def test_ski_and_mtb_have_a_condition_filter(self):
        for fields in (ski_facets.FIELDS, mtb_facets.FIELDS):
            self.assertIn("condition", [field["key"] for field in fields])
        data = {"Utah Ski_Skis": [item("Nordica Enforcer 89 Mens Demo Skis 2026")]}
        condition.label_items(data)
        html = build_report_html(data, {}, {}, set(), generated_at="2026-11-12T10:00:00+00:00", sport=sports.SKI)
        self.assertIn("ski_condition", html)


if __name__ == "__main__":
    unittest.main()
