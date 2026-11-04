"""A category word narrower than its category ranks that kind first
(owner, 2026-11-04: "triple 8 helmet" on BMX listed elbow pads first)."""

import json
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

SCRIPT = r"""
const assert = require("node:assert/strict");
const S = require(%s);
S.configure(require(%s));
const rows = [
  ["elbow", "Triple 8 Street Elbow Pads", "Triple 8", "Protection"],
  ["shorts", "Triple 8 Bike Bumsaver Padded Shorts", "Triple 8", "Protection"],
  ["helmet", "Triple 8 Gotham Dual Certified Helmet", "Triple 8", "Protection"],
  ["knee", "Triple 8 KP 22 Knee Pads", "Triple 8", "Protection"],
  ["other-helmet", "Pro-Tec Classic Helmet", "Pro-Tec", "Protection"],
  ["bars", "Triple 8 Handlebar", "Triple 8", "Steering"]
].map(([id, name, brand, part]) => ({ dataset: { id, name, brand, part, store: "CCS" } }));
const index = S.createIndex(rows.map(S.docFromRow));
function order(query) {
  const parsed = S.parseQuery(query);
  const hits = parsed.remainingText ? S.search(index, parsed.remainingText) : null;
  const prefer = parsed.preferText ? S.preferred(index, parsed.preferText) : new Set();
  const score = id => (prefer.has(id) ? 1e6 : 0) + ((hits && hits.get(id)) || 0);
  return rows.filter(row => (!hits || hits.has(row.dataset.id)) && (!parsed.filters.parts || parsed.filters.parts.includes(row.dataset.part)))
    .map(row => row.dataset.id).sort((a, b) => score(b) - score(a));
}
let parsed = S.parseQuery("triple 8 helmet");
assert.deepEqual(parsed.filters.parts, ["Protection"]);
assert.equal(parsed.preferText, "helmet");
assert.equal(order("triple 8 helmet")[0], "helmet");
assert.equal(order("triple 8 helmet").length, 4, "helmet still only ranks; the other Triple 8 pads stay listed");
assert.deepEqual(order("helmets").slice(0, 2).sort(), ["helmet", "other-helmet"]);
assert.equal(order("triple 8 knee pads")[0], "knee");
assert.equal(S.parseQuery("triple 8 protection").preferText, "", "the category's own name ranks nothing");
assert.ok(S.highlightRanges("Triple 8 Gotham Helmet", "triple 8 helmet").length >= 3);
"""


class PreferTests(unittest.TestCase):
    def test_narrow_category_word_ranks_first(self):
        script = SCRIPT % (json.dumps(str(ROOT / "search" / "search.js")),
                           json.dumps(str(ROOT / "sports" / "bmx" / "aliases.json")))
        result = subprocess.run(["node", "-e", script], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)


if __name__ == "__main__":
    unittest.main()


SPECS = r"""
const assert = require("node:assert/strict");
const S = require(%s);
S.configure(require(%s));
const docs = [
  {id: "leatt", name: "Leatt AirFlex Pro", brand: "Leatt", category: "Protection", store: "Cambria", specs: "Knees Pads & Guards Adult"},
  {id: "p23", name: "7iDP Project 23 Helmet", brand: "7iDP", category: "Protection", store: "Colorado Cyclist", specs: "Full face CPSC Adult"},
  {id: "shin", name: "SixSixOne Comp Shin Guard", brand: "SixSixOne", category: "Protection", store: "Cambria", specs: "Shins"},
  {id: "tire", name: "Maxxis Minion Tyre", brand: "Maxxis", category: "Tires", store: "Mike's Bikes", specs: "29"}
];
const index = S.createIndex(docs);
const ids = query => Array.from((S.search(index, query) || new Map()).keys()).sort();
assert.deepEqual(ids("knees"), ["leatt"], "body part from the filters, not the title");
assert.deepEqual(ids("cpsc"), ["p23"]);
assert.deepEqual(ids("full face"), ["p23"]);
assert.deepEqual(ids("shin pad"), ["shin"], "guard and pad are one word");
assert.deepEqual(ids("tire 29"), ["tire"], "tyre and tire are one word");
const parsed = S.parseQuery("mikes bikes tire");
assert.deepEqual(parsed.filters.stores, ["Mike's Bikes"]);
assert.equal(S.parseQuery("triple 8 pads").filters.stores, undefined, "a brand's own store is not a store filter");
"""


class SearchV2Tests(unittest.TestCase):
    def test_specs_synonyms_and_stores(self):
        script = SPECS % (json.dumps(str(ROOT / "search" / "search.js")),
                          json.dumps(str(ROOT / "sports" / "mtb" / "aliases.json")))
        result = subprocess.run(["node", "-e", script], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_page_indexes_the_technical_catalog(self):
        text = (ROOT / "page.js").read_text(encoding="utf-8")
        self.assertIn('document.getElementById("technicalCatalog")', text)
        self.assertIn("doc.specs = words", text)
