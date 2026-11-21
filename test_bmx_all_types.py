"""BMX All hides category spec sections until a heading is picked.

Same data-for / syncTypeSections path as Ski. Product kind stays unmarked
so All keeps it. Order stays in the facet definitions
(docs/filters-evo-model.md). Headings with spaces ("Frames & Forks") match
as a phrase.
"""

import subprocess
import tempfile
import unittest
from pathlib import Path

from bs4 import BeautifulSoup

import sports
from page import bmx_section_owners
from report import build_report_html
from sports.bmx.facets import FIELDS
from sports.headings import headings


ROOT = Path(__file__).resolve().parent


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
    with sports.BMX.active():
        return build_report_html(data, {}, {}, set(), generated_at="2026-11-21T12:00:00+00:00", sport=sports.BMX)


def _tech(html):
    return BeautifulSoup(html, "html.parser").select("#contextSpecs [data-technical-field] .filter-section")


class OwnerTests(unittest.TestCase):
    def test_owners_follow_the_field_categories(self):
        self.assertEqual(bmx_section_owners("wheel_size"),
                         "Bikes Frames & Forks Wheels Tires Wheels & Hubs Tires & Tubes")
        self.assertEqual(bmx_section_owners("top_tube"), "Bikes Frames & Forks")
        self.assertEqual(bmx_section_owners("hub_type"), "Bikes Wheels Wheel Parts Wheels & Hubs")
        self.assertEqual(bmx_section_owners("bar_rise"), "Steering Bars & Steering")
        self.assertEqual(bmx_section_owners("crank_length"), "Drivetrain")
        # Empty categories apply to every BMX heading. Product kind is the
        # exception: All keeps that filter, so it stays unmarked.
        every = " ".join(headings(sports.BMX))
        self.assertEqual(bmx_section_owners("material"), every)
        self.assertEqual(bmx_section_owners("color"), every)
        self.assertEqual(bmx_section_owners("condition"), every)
        self.assertEqual(bmx_section_owners("kind"), "")
        self.assertEqual(bmx_section_owners("no-such-field"), "")

    def test_protection_scope_is_still_the_facet_list(self):
        for key in ("protects", "helmet_style", "certification", "rotational", "prot_size", "age"):
            field = next(item for item in FIELDS if item["key"] == key)
            self.assertEqual(bmx_section_owners(key), " ".join(field["categories"]))
            self.assertIn("Helmets", field["categories"])


class MarkupTests(unittest.TestCase):
    def test_bmx_all_marks_spec_sections_and_leaves_kind_and_generics_open(self):
        html = _page({
            "Fixture_Bikes": [_item("Cult Audit Bike", "Bikes", "https://example.test/bike", {
                "kind": ["Complete Bikes"],
                "wheel_size": ["20"],
                "top_tube": ['20.75"'],
                "material": ["Chromoly"],
                "color": ["Black"],
                "condition": ["Demo"],
            })],
            "Fixture_Bars": [_item("Cult Audit Bars", "Steering", "https://example.test/bars", {
                "kind": ["Handlebars"],
                "bar_rise": ['9"'],
            })],
            "Fixture_Helmets": [_item("S-One Audit Helmet", "Protection", "https://example.test/lid", {
                "prot_size": ["M"],
                "protects": ["Helmets"],
            })],
        })
        soup = BeautifulSoup(html, "html.parser")
        sections = _tech(html)
        self.assertGreaterEqual(len(sections), 4)
        for section in sections:
            key = section["data-section"][len("tech-"):]
            expected = bmx_section_owners(key)
            if key == "kind":
                self.assertIsNone(section.get("data-for"))
                self.assertNotIn("is-type-hidden", section["class"])
                continue
            self.assertEqual(section.get("data-for"), expected, key)
            self.assertTrue(expected, key)
            self.assertIn("is-type-hidden", section["class"])
        kind = soup.select_one('[data-section="tech-kind"]')
        self.assertIsNotNone(kind)
        self.assertIsNone(kind.get("data-for"))
        brand = soup.select_one('[data-section="brand"]')
        self.assertNotIn("is-type-hidden", brand["class"])
        self.assertIsNone(brand.get("data-for"))
        for generic in ("store", "price", "deals", "score", "interval"):
            node = soup.select_one(f'[data-section="{generic}"]')
            self.assertIsNotNone(node, generic)
            self.assertIsNone(node.get("data-for"), generic)
            self.assertNotIn("is-type-hidden", node["class"])
        tube = soup.select_one('[data-section="tech-top_tube"]')
        self.assertEqual(tube["data-for"], "Bikes Frames & Forks")
        self.assertIn('class="filter-section is-open is-type-hidden"', str(tube))
        material = soup.select_one('[data-section="tech-material"]')
        self.assertEqual(material["data-for"], " ".join(headings(sports.BMX)))
        size = soup.select_one('[data-section="tech-prot_size"]')
        self.assertEqual(size["data-for"], "Protection Helmets Goggles Gloves")


class PhraseMatchTests(unittest.TestCase):
    def test_multi_word_headings_match_as_a_phrase(self):
        source = (ROOT / "page.js").read_text(encoding="utf8")
        script = r"""
const assert = require("node:assert/strict");
const TruckFit = { fits(values) { return values || []; }, natives(values) { return values || []; }, brands: {} };
const nodes = [];
function mockEl(id, attrs) {
  const node = {
    id: id,
    hidden: false,
    attrs: Object.assign({}, attrs),
    parentNode: null,
    children: [],
    classList: {
      _s: new Set(),
      toggle(name, on) { if (on) this._s.add(name); else this._s.delete(name); },
      contains(name) { return this._s.has(name); },
      add(name) { this._s.add(name); },
      remove(name) { this._s.delete(name); }
    },
    getAttribute(name) { return Object.prototype.hasOwnProperty.call(this.attrs, name) ? this.attrs[name] : ""; },
    setAttribute(name, value) { this.attrs[name] = String(value); },
    querySelector() { return null; },
    querySelectorAll() { return []; },
    insertBefore(child, ref) {
      if (child === ref) return;
      if (child.parentNode && child.parentNode.children) {
        const old = child.parentNode.children;
        const at = old.indexOf(child);
        if (at >= 0) old.splice(at, 1);
      }
      child.parentNode = this;
      const index = ref ? this.children.indexOf(ref) : this.children.length;
      this.children.splice(index < 0 ? this.children.length : index, 0, child);
    }
  };
  nodes.push(node);
  return node;
}
const document = {
  addEventListener() {},
  dispatchEvent() {},
  getElementById(id) { return nodes.find(node => node.id === id) || null; },
  querySelector(sel) {
    if (sel === '[data-section="brand"]') return nodes.find(node => node.getAttribute("data-section") === "brand") || null;
    return null;
  },
  querySelectorAll(sel) {
    if (sel === "#contextSpecs .filter-section[data-for]") {
      const context = nodes.find(node => node.id === "contextSpecs");
      return nodes.filter(node => node.parentNode === context && node.getAttribute("data-for"));
    }
    if (sel === ".filter-section") return nodes.filter(node => node.getAttribute("data-section"));
    return [];
  }
};
const localStorage = { getItem() { return null; }, setItem() {} };
const window = { addEventListener() {} };
__SOURCE__
const specGroup = mockEl("specGroup");
const brand = mockEl("brand", { "data-section": "brand" });
const context = mockEl("contextSpecs");
const tube = mockEl("top_tube", { "data-section": "tech-top_tube", "data-for": "Bikes Frames & Forks" });
const wheels = mockEl("wheel_size", { "data-section": "tech-wheel_size", "data-for": "Bikes Wheels Wheels & Hubs" });
const decks = mockEl("width", { "data-section": "width", "data-for": "Decks" });
const helmets = mockEl("size", { "data-section": "tech-prot_size", "data-for": "Protection Helmets" });
const kind = mockEl("kind", { "data-section": "tech-kind" });
function nest(parent, child) { parent.children.push(child); child.parentNode = parent; }
nest(specGroup, brand);
nest(specGroup, context);
[tube, wheels, decks, helmets, kind].forEach(node => nest(context, node));
function hidden(node) { return node.classList.contains("is-type-hidden"); }
state.part = "all";
state.brand = "all";
syncTypeSections(false);
assert.equal(hidden(tube), true);
assert.equal(hidden(wheels), true);
assert.equal(hidden(decks), true);
assert.equal(hidden(helmets), true);
assert.equal(hidden(kind), false);
state.part = "Frames & Forks";
syncTypeSections(false);
assert.equal(hidden(tube), false);
assert.equal(hidden(wheels), true);
assert.equal(hidden(decks), true);
state.part = "Wheels & Hubs";
syncTypeSections(false);
assert.equal(hidden(tube), true);
assert.equal(hidden(wheels), false);
state.part = "Wheels";
syncTypeSections(false);
assert.equal(hidden(wheels), false, "old single-word Wheels category still matches");
assert.equal(hidden(tube), true);
state.part = "Decks";
syncTypeSections(false);
assert.equal(hidden(decks), false);
assert.equal(hidden(helmets), true);
assert.equal(hidden(tube), true);
state.part = "Helmets";
syncTypeSections(false);
assert.equal(hidden(helmets), false);
assert.equal(hidden(decks), true);
""".replace("__SOURCE__", source)
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf8") as handle:
            handle.write(script)
            path = handle.name
        result = subprocess.run(["node", path], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)


if __name__ == "__main__":
    unittest.main()
