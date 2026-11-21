"""Deck shape chips, wheel spec order, and the All-types sidebar."""

import subprocess
import tempfile
import unittest
from pathlib import Path

from page import DECK_SHAPE_ORDER, deck_shape
from part_specs import MIN_SPEC_COUNT
from query_state import decode_query, encode_state
from report import build_report_html


ROOT = Path(__file__).resolve().parent


def _item(name, part, url):
    return {
        "name": name,
        "url": url,
        "price_new": "40.00",
        "price_old": "80.00",
        "part": part,
        "store": "Zumiez",
    }


class DeckShapeParseTests(unittest.TestCase):
    def test_only_a_printed_shape_word_counts(self):
        self.assertEqual(deck_shape("Baker Logo 8.25 Skateboard Deck"), "")
        self.assertEqual(deck_shape("Powell Peralta Ripper 8.5 Skateboard Deck"), "")
        self.assertEqual(deck_shape("Sector 9 Cruiser Deck"), "")
        self.assertEqual(deck_shape("Enjoi Fish Logo 8.25 Skateboard Deck"), "")
        self.assertEqual(deck_shape(""), "")
        self.assertEqual(deck_shape("Girl Popsicle 8.0 Skateboard Deck"), "popsicle")
        self.assertEqual(deck_shape("The Heated Wheel Fan For Sale Shaped Deck"), "shaped")
        self.assertEqual(deck_shape("Opera Spectator Football Shape 9.0 Deck"), "shaped")
        self.assertEqual(deck_shape("Heroin Swampy Egg 11 Skateboard Deck"), "shaped")
        self.assertEqual(deck_shape("Heroin Auntie Razoregg Skateboard Deck"), "shaped")
        self.assertEqual(deck_shape("Heroin Merged Anatomy Razor-egg Deck"), "shaped")
        self.assertEqual(deck_shape("WKND Sunset 8.6 Fishtail Skateboard Deck"), "shaped")
        self.assertEqual(deck_shape("WKND Sunset Fish Tail Skateboard Deck"), "shaped")
        self.assertEqual(deck_shape("Scanners Twin Tail Skateboard Deck"), "twin")
        self.assertEqual(deck_shape("Baker Jacopo Rocket Science Twin 8.38 Deck"), "twin")
        self.assertEqual(deck_shape("Chocolate York Kid Reissue 7.5 Deck"), "reissue")
        self.assertEqual(deck_shape("Powell Mike Frazier Yellow Man Re-Issue Deck"), "reissue")
        self.assertEqual(deck_shape("Old School Pool Deck"), "reissue")
        self.assertEqual(deck_shape("Twin Popsicle Reissue Deck"), "twin")
        self.assertEqual(deck_shape("Shaped Reissue Deck"), "shaped")
        self.assertEqual(list(DECK_SHAPE_ORDER), ["popsicle", "shaped", "twin", "reissue"])

    def test_query_keeps_wheel_shape_and_adds_deckshape(self):
        state = decode_query("type=deck&deckshape=reissue,twin,nope&shape=radial")
        self.assertEqual(state["part"], "Decks")
        self.assertEqual(state["deck_shapes"], ["twin", "reissue"])
        self.assertEqual(state["shapes"], ["radial"])
        encoded = encode_state(state)
        self.assertIn("deckshape=twin%2Creissue", encoded)
        self.assertIn("shape=radial", encoded)
        self.assertEqual(decode_query(encoded), state)
        wheel = decode_query("type=wheel&shape=conical,sidecut")
        self.assertEqual(wheel["shapes"], ["conical", "sidecut"])
        self.assertEqual(wheel["deck_shapes"], [])
        self.assertNotIn("deckshape", encode_state(wheel))
        self.assertEqual(decode_query("deckshape=cruiser")["deck_shapes"], [])
        self.assertEqual(encode_state({}), "")


class DeckShapeSectionTests(unittest.TestCase):
    def test_section_follows_width_and_hides_until_enough_names_match(self):
        few = [
            _item(f"Heroin Egg {index} Skateboard Deck", "Decks", f"https://example.com/egg-{index}")
            for index in range(MIN_SPEC_COUNT - 1)
        ]
        few.append(_item("Baker Logo 8.25 Skateboard Deck", "Decks", "https://example.com/plain"))
        hidden = build_report_html({"Zumiez_Decks": few}, {}, generated_at="2026-10-11T21:46:35+00:00")
        self.assertNotIn('data-section="deckshape"', hidden)
        plain = next(row for row in hidden.split("<tr ") if "example.com/plain" in row)
        self.assertIn('data-deckshape=""', plain)
        egg = next(row for row in hidden.split("<tr ") if "example.com/egg-0" in row)
        self.assertIn('data-deckshape="shaped"', egg)

        decks = [
            _item(f"Heroin Swampy Egg Black 9.{index} x 32 Skateboard Deck", "Decks", f"https://example.com/deck-{index}")
            for index in range(MIN_SPEC_COUNT)
        ]
        decks.append(_item("Baker Logo 8.25 x 32 Skateboard Deck", "Decks", "https://example.com/street"))
        decks.append(_item("Girl Popsicle 8.0 x 31.5 Skateboard Deck", "Decks", "https://example.com/pop"))
        wheels = [
            _item(
                "Spitfire Formula Four Conical 54mm 99a White Skateboard Wheels",
                "Wheels",
                f"https://example.com/wheel-{index}",
            )
            for index in range(MIN_SPEC_COUNT)
        ]
        html = build_report_html(
            {"Zumiez_Decks": decks, "Zumiez_Wheels": wheels},
            {},
            generated_at="2026-10-11T21:46:35+00:00",
        )
        self.assertLess(html.index('data-section="width"'), html.index('data-section="deckshape"'))
        self.assertLess(html.index('data-section="deckshape"'), html.index('data-section="length"'))
        self.assertLess(html.index('data-section="length"'), html.index('data-section="deckcolor"'))
        self.assertIn('data-section="deckshape" data-for="Decks"', html)
        self.assertIn(">Deck Shape<", html)
        self.assertIn('id="deckshapeFilters"', html)
        self.assertIn('data-value="shaped"', html)
        self.assertIn('data-value="popsicle"', html)
        self.assertIn(">Shaped<", html)
        self.assertIn(">Popsicle<", html)
        self.assertIn("Popsicle is not assumed", html)
        street = next(row for row in html.split("<tr ") if "example.com/street" in row)
        self.assertIn('data-deckshape=""', street)
        shaped = next(row for row in html.split("<tr ") if "example.com/deck-0" in row)
        self.assertIn('data-deckshape="shaped"', shaped)
        # Wheels: Diameter, Durometer, Shape, then Color.
        self.assertLess(html.index('data-section="diameter"'), html.index('data-section="duro"'))
        self.assertLess(html.index('data-section="duro"'), html.index('data-section="shape"'))
        self.assertLess(html.index('data-section="shape"'), html.index('data-section="wheelcolor"'))
        self.assertIn('class="chip spec-chip', html.split('id="deckshapeFilters"', 1)[1].split("</div>", 1)[0])

    def test_all_types_hides_category_sections_until_a_type_is_picked(self):
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
  Object.defineProperty(node, "nextSibling", {
    get() {
      if (!this.parentNode) return null;
      const kids = this.parentNode.children;
      const index = kids.indexOf(this);
      return index >= 0 && index + 1 < kids.length ? kids[index + 1] : null;
    }
  });
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
const width = mockEl("width", { "data-section": "width", "data-for": "Decks" });
const deckshape = mockEl("deckshape", { "data-section": "deckshape", "data-for": "Decks" });
const diameter = mockEl("diameter", { "data-section": "diameter", "data-for": "Wheels" });
const duro = mockEl("duro", { "data-section": "duro", "data-for": "Wheels" });
const shape = mockEl("shape", { "data-section": "shape", "data-for": "Wheels" });
const wheelcolor = mockEl("wheelcolor", { "data-section": "wheelcolor", "data-for": "Wheels" });
const tech = mockEl("tech", { "data-section": "tech-wheel_size", "data-technical-field": "wheel_size" });
const specs = mockEl("productSpecs", { "data-section": "specs" });
const specsBody = mockEl("productSpecsBody");
function nest(parent, child) { parent.children.push(child); child.parentNode = parent; }
nest(specGroup, brand);
nest(specGroup, context);
nest(context, width);
nest(context, deckshape);
nest(context, diameter);
nest(context, duro);
nest(context, shape);
nest(context, wheelcolor);
nest(context, tech);
nest(specGroup, specs);
nest(specs, specsBody);
state.part = "all";
state.brand = "all";
syncTypeSections(false);
assert.equal(specs.hidden, true);
assert.equal(context.parentNode, specGroup);
assert.equal(specsBody.children.includes(context), false);
for (const section of [width, deckshape, diameter, duro, shape, wheelcolor]) {
  assert.equal(section.classList.contains("is-type-hidden"), true, section.id);
}
assert.equal(tech.classList.contains("is-type-hidden"), false);
state.part = "Wheels";
syncTypeSections(false);
assert.equal(width.classList.contains("is-type-hidden"), true);
assert.equal(deckshape.classList.contains("is-type-hidden"), true);
assert.equal(diameter.classList.contains("is-type-hidden"), false);
assert.equal(duro.classList.contains("is-type-hidden"), false);
assert.equal(shape.classList.contains("is-type-hidden"), false);
assert.equal(wheelcolor.classList.contains("is-type-hidden"), false);
const wheelIds = context.children.filter(node => node.getAttribute("data-for") === "Wheels" && !node.classList.contains("is-type-hidden")).map(node => node.id);
assert.deepEqual(wheelIds, ["diameter", "duro", "shape", "wheelcolor"]);
state.part = "Decks";
syncTypeSections(false);
assert.equal(width.classList.contains("is-type-hidden"), false);
assert.equal(deckshape.classList.contains("is-type-hidden"), false);
assert.equal(diameter.classList.contains("is-type-hidden"), true);
const deckIds = context.children.filter(node => node.getAttribute("data-for") === "Decks" && !node.classList.contains("is-type-hidden")).map(node => node.id);
assert.deepEqual(deckIds, ["width", "deckshape"]);
state.part = "Decks";
state.deckShapes = ["twin"];
state.shapes = ["radial"];
const decoded = decodeQuery("deckshape=twin,popsicle&shape=radial");
assert.deepEqual(decoded.deckShapes, ["popsicle", "twin"]);
assert.deepEqual(decoded.shapes, ["radial"]);
const again = decodeQuery(encodeState(Object.assign({}, decoded, { part: "Decks" })));
assert.deepEqual(again.deckShapes, ["popsicle", "twin"]);
assert.deepEqual(again.shapes, ["radial"]);
assert.equal(encodeState(decodeQuery("shape=conical")).includes("deckshape"), false);
const row = { dataset: {
  part: "Decks", deckshape: "twin", length: "", size: "8.25", search: "baker", store: "Zumiez",
  brand: "Baker", price: "40", discount: "50", score: "10",
  starred: "0", fresh: "0", drop: "0", lowest: "0", added: "0", highlight: "0",
  dropday: "", soldout: "0", wheelbase: "", diameter: "", duros: "", shape: "",
  trucksize: "", truckheight: "", construction: "", abec: "", shoesize: "",
  prottype: "", protsize: "", color: ""
}};
assert.equal(rowMatches(row), true);
row.dataset.deckshape = "shaped";
assert.equal(rowMatches(row), false);
row.dataset.deckshape = "";
assert.equal(rowMatches(row), false);
state.part = "all";
row.dataset.deckshape = "shaped";
assert.equal(rowMatches(row), true);
state.part = "Wheels";
state.deckShapes = ["twin"];
state.shapes = ["conical"];
row.dataset.part = "Wheels";
row.dataset.shape = "conical";
row.dataset.deckshape = "";
assert.equal(rowMatches(row), true);
row.dataset.shape = "radial";
assert.equal(rowMatches(row), false);
""".replace("__SOURCE__", source)
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf8") as handle:
            handle.write(script)
            path = handle.name
        result = subprocess.run(["node", path], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)


if __name__ == "__main__":
    unittest.main()
