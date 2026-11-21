"""Ski All hides category spec sections until a heading is picked.

The gate is the same data-for / syncTypeSections path Skate uses. Order and
goggles scope stay in the facet definitions (docs/filters-evo-model.md).
"""

import unittest

from bs4 import BeautifulSoup

import sports
from page import ski_section_owners
from report import build_report_html
from sports.headings import headings
from sports.ski.facets import FIELDS


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


def _page(sport, data):
    with sport.active():
        return build_report_html(data, {}, {}, set(), generated_at="2026-11-21T12:00:00+00:00", sport=sport)


def _tech(html):
    return BeautifulSoup(html, "html.parser").select("#contextSpecs [data-technical-field] .filter-section")


class OwnerTests(unittest.TestCase):
    def test_owners_follow_the_field_categories(self):
        self.assertEqual(ski_section_owners("length"), "Skis Poles")
        self.assertEqual(ski_section_owners("ski_type"), "Skis Boots Bindings")
        self.assertEqual(ski_section_owners("mondo"), "Boots")
        # Empty categories apply to every Ski heading, including ones the
        # stored part list does not name (Goggles, Gloves).
        self.assertEqual(ski_section_owners("gender"), " ".join(headings(sports.SKI)))
        # Ability and Condition: skis, boots and bindings only (docs/filters-evo-model.md).
        self.assertEqual(ski_section_owners("ability"), "Skis Boots Bindings")
        self.assertEqual(ski_section_owners("condition"), "Skis Boots Bindings")
        self.assertEqual(ski_section_owners("no-such-field"), "")

    def test_protection_scope_is_still_the_facet_list(self):
        # Page stamps whatever categories the facet declares. Dropping
        # Goggles is a facet change; this locks the stamp to that list.
        for key in ("protects", "helmet_style", "certification", "rotational", "prot_size", "age"):
            field = next(item for item in FIELDS if item["key"] == key)
            self.assertEqual(ski_section_owners(key), " ".join(field["categories"]))
            # Goggles dropped (docs/filters-evo-model.md): helmet/armor fields only.
            self.assertNotIn("Goggles", field["categories"])


class MarkupTests(unittest.TestCase):
    def test_ski_all_marks_spec_sections_and_leaves_generics_open(self):
        html = _page(sports.SKI, {
            "Fixture_Skis": [_item("Armada Audit Skis", "Skis", "https://example.test/skis",
                                   {"length": ["170–179 cm"], "gender": ["Men"], "ski_type": ["All-Mountain"]})],
            "Fixture_Boots": [_item("Atomic Hawx Ski Boots", "Boots", "https://example.test/boots",
                                    {"mondo": ["26.5"], "gender": ["Women"]})],
        })
        soup = BeautifulSoup(html, "html.parser")
        sections = _tech(html)
        self.assertGreaterEqual(len(sections), 3)
        for section in sections:
            key = section["data-section"][len("tech-"):]
            self.assertEqual(section.get("data-for"), ski_section_owners(key), key)
            self.assertIn("is-type-hidden", section["class"])
        brand = soup.select_one('[data-section="brand"]')
        self.assertNotIn("is-type-hidden", brand["class"])
        self.assertIsNone(brand.get("data-for"))
        for generic in ("store", "price", "deals", "score"):
            node = soup.select_one(f'[data-section="{generic}"]')
            self.assertIsNotNone(node, generic)
            self.assertIsNone(node.get("data-for"), generic)
            self.assertNotIn("is-type-hidden", node["class"])
        length = soup.select_one('[data-section="tech-length"]')
        self.assertEqual(length["data-for"], "Skis Poles")
        self.assertIn('class="filter-section is-open is-type-hidden"', str(length))


if __name__ == "__main__":
    unittest.main()
