"""MTB All hides category spec sections until a heading is picked.

Same data-for / syncTypeSections path as Ski and BMX. MTB has no Product
kind field, so nothing is left unmarked on purpose. Empty categories
(Condition, Riding type) stamp every menu heading: hidden on All, shown
under any heading. Order stays in the facet definitions
(docs/filters-evo-model.md).
"""

import unittest

from bs4 import BeautifulSoup

import sports
from page import mtb_section_owners
from report import build_report_html
from sports.headings import headings
from sports.mtb.facets import FIELDS


def _offer(specs, price=100, compare=200):
    return {"variant_id": 1, "price": price, "compare": compare, "available": True, "specs": specs}


def _item(name, part, url, specs):
    return {
        "name": name,
        "part": part,
        "store": "Fixture",
        "url": url,
        "price_new": "100",
        "price_old": "200",
        "technical_offers": [_offer(specs)],
    }


def _page(data):
    with sports.MTB.active():
        return build_report_html(data, {}, {}, set(), generated_at="2026-11-21T12:00:00+00:00", sport=sports.MTB)


def _tech(html):
    return BeautifulSoup(html, "html.parser").select("#contextSpecs [data-technical-field] .filter-section")


class OwnerTests(unittest.TestCase):
    def test_owners_follow_the_field_categories(self):
        self.assertEqual(mtb_section_owners("wheel_size"),
                         "Bikes Frames Forks & Shocks Suspension Wheels Tires")
        self.assertEqual(mtb_section_owners("frame_size"), "Bikes Frames")
        self.assertEqual(mtb_section_owners("power"), "Bikes Frames")
        self.assertEqual(mtb_section_owners("suspension"), "Bikes Frames")
        self.assertEqual(mtb_section_owners("frame_material"), "Bikes Frames")
        self.assertEqual(mtb_section_owners("travel_mm"), "Bikes Frames Forks & Shocks Suspension")
        self.assertEqual(mtb_section_owners("tire_width"), "Tires")
        self.assertEqual(mtb_section_owners("casing"), "Tires")
        self.assertEqual(mtb_section_owners("tubeless"), "Tires")
        self.assertEqual(mtb_section_owners("axle"), "Frames Forks & Shocks Suspension Wheels")
        self.assertEqual(mtb_section_owners("rotor_mm"), "Brakes")
        self.assertEqual(mtb_section_owners("speed"), "Drivetrain Bikes")
        # Empty categories apply to every MTB heading, so All hides them and
        # any heading shows them. Product kind is not a field; it stays
        # unmarked if one is added, the same way BMX leaves kind open.
        every = " ".join(headings(sports.MTB))
        self.assertEqual(mtb_section_owners("condition"), every)
        self.assertEqual(mtb_section_owners("riding_type"), every)
        self.assertNotIn("Forks & Shocks", headings(sports.MTB))
        self.assertIn("Suspension", headings(sports.MTB))
        self.assertEqual(mtb_section_owners("kind"), "")
        self.assertEqual(mtb_section_owners("no-such-field"), "")

    def test_protection_scope_is_still_the_facet_list(self):
        for key in ("protects", "helmet_style", "certification", "rotational", "prot_size", "age"):
            field = next(item for item in FIELDS if item["key"] == key)
            self.assertEqual(mtb_section_owners(key), " ".join(field["categories"]))
            self.assertIn("Helmets", field["categories"])
            self.assertIn("Protection", field["categories"])


class MarkupTests(unittest.TestCase):
    def test_mtb_all_marks_spec_sections_and_leaves_generics_open(self):
        html = _page({
            "Fixture_Bikes": [_item("Yeti SB140 Mountain Bike", "Bikes", "https://example.test/bike", {
                "frame_size": ["L"],
                "wheel_size": ["29"],
                "travel_mm": ["140"],
                "speed": ["12-speed"],
                "condition": ["Demo"],
                "riding_type": ["enduro"],
            })],
            "Fixture_Tires": [_item("Maxxis Minion Tire", "Tires", "https://example.test/tire", {
                "wheel_size": ["29"],
                "tire_width": ["2.5"],
                "casing": ["EXO"],
                "tubeless": ["Tubeless ready"],
            })],
            "Fixture_Forks": [_item("RockShox Pike Fork", "Forks & Shocks", "https://example.test/fork", {
                "wheel_size": ["29"],
                "travel_mm": ["140"],
            })],
            "Fixture_Wheels": [_item("DT Swiss XM481 Wheel", "Wheels", "https://example.test/wheel", {
                "axle": ["12x148mm"],
            })],
            "Fixture_Brakes": [_item("SRAM Centerline Rotor", "Brakes", "https://example.test/rotor", {
                "rotor_mm": ["180"],
            })],
            "Fixture_Helmets": [_item("Fox Speedframe Helmet", "Protection", "https://example.test/lid", {
                "prot_size": ["M"],
                "protects": ["Helmets"],
            })],
        })
        soup = BeautifulSoup(html, "html.parser")
        sections = _tech(html)
        self.assertGreaterEqual(len(sections), 6)
        for section in sections:
            key = section["data-section"][len("tech-"):]
            expected = mtb_section_owners(key)
            self.assertEqual(section.get("data-for"), expected, key)
            self.assertTrue(expected, key)
            self.assertIn("is-type-hidden", section["class"])
        self.assertIsNone(soup.select_one('[data-section="tech-kind"]'))
        brand = soup.select_one('[data-section="brand"]')
        self.assertNotIn("is-type-hidden", brand["class"])
        self.assertIsNone(brand.get("data-for"))
        for generic in ("store", "price", "deals", "score", "interval"):
            node = soup.select_one(f'[data-section="{generic}"]')
            self.assertIsNotNone(node, generic)
            self.assertIsNone(node.get("data-for"), generic)
            self.assertNotIn("is-type-hidden", node["class"])
        wheel = soup.select_one('[data-section="tech-wheel_size"]')
        self.assertEqual(wheel["data-for"], "Bikes Frames Forks & Shocks Suspension Wheels Tires")
        self.assertIn('class="filter-section is-open is-type-hidden"', str(wheel))
        every = " ".join(headings(sports.MTB))
        self.assertEqual(soup.select_one('[data-section="tech-condition"]')["data-for"], every)
        self.assertEqual(soup.select_one('[data-section="tech-riding_type"]')["data-for"], every)
        size = soup.select_one('[data-section="tech-prot_size"]')
        self.assertEqual(size["data-for"], "Protection Helmets Goggles Gloves")


if __name__ == "__main__":
    unittest.main()
