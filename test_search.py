"""Search upgrade (tasks/search-upgrade.md): normalization, query parsing,
ranking, and speed. search/search.js is DOM-free, so these run it in Node."""

import json
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

PRELUDE = r"""
const assert = require("node:assert/strict");
const S = require(%s);
S.configure(require(%s));
""" % (json.dumps(str(ROOT / "search" / "search.js")), json.dumps(str(ROOT / "search" / "aliases.json")))

# A small catalog for ranking: the cases the task names, plus look-alikes.
FIXTURE = r"""
const rows = [
  ["bones-stf", "Bones STF V5 Sidecut 52mm 99a Wheels", "Bones", "Wheels", "", "99a"],
  ["bones-reds", "Bones Reds Bearings", "Bones", "Bearings", "", ""],
  ["oj-combo", "OJ Elite Mini Combo 101a Wheels", "OJ", "Wheels", "", "101a"],
  ["oj-chub-54", "OJ Double Duro Chubbies 54mm 101a/95a White Skateboard Wheels", "OJ", "Wheels", "", "101a,95a"],
  ["oj-chub-56", "OJ Double Duro Chubbies 56mm 99a & 95a Skateboard Wheels", "OJ", "Wheels", "", "99a,95a"],
  ["sf-bighead", "Spitfire Formula Four Radioactive Big Head 54mm 99a Black Skateboard Wheels", "Spitfire", "Wheels", "", "99a"],
  ["sf-classic", "Spitfire Formula Four Classic 53mm 99a Wheels", "Spitfire", "Wheels", "", "99a"],
  ["sf-80hd", "Spitfire 80HD Ransom Radial 56mm Wheels", "Spitfire", "Wheels", "", ""],
  ["bones-spf", "Bones SPF Scorpeedo P5 Sidecut 60mm 81B (101A) White", "Bones", "Wheels", "", "81b,101a"],
  ["baker", "Baker Brand Logo 8.25\" Skateboard Deck", "Baker", "Decks", "8.25", ""],
  ["combo-deck", "Toy Machine Combo Deck 8.5", "Toy Machine", "Decks", "8.5", ""],
  ["indy", "Independent Stage 11 Hollow Trucks 149", "Independent", "Trucks", "", ""],
  ["andy", "Andy Anderson Signature Deck 8.25", "Powell Peralta", "Decks", "8.25", ""]
].map(([id, name, brand, part, size, duros]) => ({ dataset: { id, name, brand, part, size, duros, store: "CCS" } }));
const index = S.createIndex(rows.map(S.docFromRow));
const byId = Object.fromEntries(rows.map(row => [row.dataset.id, row]));
function ranked(query) {
  const hits = S.search(index, query);
  return hits ? Array.from(hits.entries()).sort((a, b) => b[1] - a[1]).map(entry => entry[0]) : [];
}
function found(query) {
  const parsed = S.parseQuery(query);
  const hits = parsed.remainingText ? S.search(index, parsed.remainingText) : null;
  return rows.filter(row => (!hits || hits.has(row.dataset.id)) && S.rowAllows(parsed.filters, row)
    && (!parsed.filters.parts || parsed.filters.parts.includes(row.dataset.part))).map(row => row.dataset.id);
}
"""


def run(script):
    result = subprocess.run(["node", "-e", PRELUDE + script], capture_output=True, text=True)
    return result.returncode, (result.stderr or result.stdout)


class NormalizationTests(unittest.TestCase):
    def test_punctuation_units_and_durometer_scales(self):
        code, out = run(r"""
assert.equal(S.normalize("O.J. Chubbies"), "oj chubbies");
assert.equal(S.normalize("o j"), "oj");
assert.equal(S.normalize("101a/95a"), "101a 95a");
assert.equal(S.normalize("54 mm"), "54mm");
assert.equal(S.normalize("54MM"), "54mm");
assert.equal(S.normalize("8.25in"), "8.25");
assert.equal(S.normalize('8.25" deck'), "8.25 deck");
assert.equal(S.normalize("8.25”"), "8.25");
assert.equal(S.normalize("84b"), "104a");
assert.equal(S.normalize("99d"), "99a");
assert.equal(S.duroToA("84B"), "104a");
assert.equal(S.duroToA("99D"), "99a");
assert.equal(S.duroToA("99"), "", "a durometer needs its scale letter");
assert.equal(S.normalize("Spitfire Formula Four 55.5mm"), "spitfire formula four 55.5mm");
assert.equal(S.normalize("Bronson Speed Co."), "bronson speed co");
""")
        self.assertEqual(code, 0, out)

    def test_aliases_rewrite_text_and_queries_to_one_term(self):
        code, out = run(r"""
assert.equal(S.normalize("spitty"), "spitfire");
assert.equal(S.normalize("indy"), "independent");
assert.equal(S.normalize("indys"), "independent");
assert.equal(S.normalize("O.J.s"), "oj");
assert.equal(S.normalize("bonez"), "bones");
assert.equal(S.normalize("f4"), "formula four");
assert.equal(S.normalize("Formula 4"), "formula four");
assert.equal(S.normalize("big head"), "bighead");
assert.equal(S.normalize("Powell-Peralta"), "powell peralta");
assert.equal(S.normalize("Powell Peralta"), "powell peralta", "never powell peralta peralta");
assert.equal(S.normalize("powell"), "powell peralta");
assert.equal(S.normalize("antihero"), S.normalize("Anti-Hero"));
""")
        self.assertEqual(code, 0, out)

    def test_aliases_file_is_data_with_every_seeded_term(self):
        aliases = json.loads((ROOT / "search" / "aliases.json").read_text(encoding="utf-8"))
        for group in ("brands", "models", "categories", "stores"):
            self.assertIsInstance(aliases[group], dict)
            for name, spellings in aliases[group].items():
                self.assertIsInstance(spellings, list, name)
        for brand in ("Spitfire", "Independent", "OJ", "Bones", "Thunder", "Venture", "Ace", "Powell Peralta"):
            self.assertIn(brand, aliases["brands"])
        for model in ("Formula Four", "Chubbies", "Bighead", "Classic", "Conical", "Radial", "Double Duro", "Hardline", "Elite"):
            self.assertIn(model, aliases["models"])
        for part in ("Wheels", "Decks", "Trucks", "Bearings"):
            self.assertIn(part, aliases["categories"])
        self.assertIn("board", aliases["categories"]["Decks"])


class ParseQueryTests(unittest.TestCase):
    def parse(self, queries):
        script = "const out = {};\n" + "".join(
            f"out[{json.dumps(query)}] = S.parseQuery({json.dumps(query)});\n" for query in queries
        ) + "console.log(JSON.stringify(out));"
        result = subprocess.run(["node", "-e", PRELUDE + script], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_every_pattern_in_the_table(self):
        cases = {
            "54mm": {"diameter": 54},
            "54 mm": {"diameter": 54},
            "99a": {"duros": ["99a"]},
            "101a": {"duros": ["101a"]},
            "84b": {"duros": ["104a"]},
            "99d": {"duros": ["99a"]},
            "8.25": {"width": 8.25},
            "8.5 deck": {"width": 8.5, "parts": ["Decks"]},
            "8.25in": {"width": 8.25},
            '8.25"': {"width": 8.25},
            "under 30": {"priceMax": 30},
            "<30": {"priceMax": 30},
            "<$30": {"priceMax": 30},
            "below 30": {"priceMax": 30},
            "over 20": {"priceMin": 20},
            ">20": {"priceMin": 20},
            "40% off": {"discountMin": 40},
            "40%+": {"discountMin": 40},
            "tactics": {"stores": ["Tactics"]},
            "ccs": {"stores": ["CCS"]},
            "zumiez": {"stores": ["Zumiez"]},
            "skate warehouse": {"stores": ["SkateWarehouse"]},
            "wheels": {"parts": ["Wheels"]},
            "decks": {"parts": ["Decks"]},
            "trucks": {"parts": ["Trucks"]},
            "bearings": {"parts": ["Bearings"]},
        }
        parsed = self.parse(list(cases))
        for query, filters in cases.items():
            self.assertEqual(parsed[query]["filters"], filters, query)
            self.assertEqual(parsed[query]["remainingText"], "", query)

    def test_combinations_and_what_is_left_for_text(self):
        parsed = self.parse(["spitfire 54mm 99a under 30", "indy trucks under 50", "oj 101a/95a 40% off tactics", "baker 8.25 over 20"])
        full = parsed["spitfire 54mm 99a under 30"]
        self.assertEqual(full["filters"], {"diameter": 54, "duros": ["99a"], "priceMax": 30})
        self.assertEqual(full["remainingText"], "spitfire")
        self.assertEqual([token["label"] for token in full["tokens"]], ["54mm", "99a", "< $30"])
        self.assertEqual(parsed["indy trucks under 50"]["filters"], {"parts": ["Trucks"], "priceMax": 50})
        self.assertEqual(parsed["indy trucks under 50"]["remainingText"], "indy")
        self.assertEqual(parsed["oj 101a/95a 40% off tactics"]["filters"],
                         {"duros": ["101a", "95a"], "discountMin": 40, "stores": ["Tactics"]})
        self.assertEqual(parsed["baker 8.25 over 20"]["filters"], {"width": 8.25, "priceMin": 20})

    def test_non_matches(self):
        parsed = self.parse(["8.25", "99", "under 8.5", "54", "spitfire", "8.5mm", "12.5", "8", "150% off"])
        self.assertNotIn("priceMax", parsed["8.25"]["filters"], "8.25 is a deck width, not a price")
        self.assertEqual(parsed["99"]["filters"], {}, "99 alone is not a durometer")
        self.assertEqual(parsed["99"]["remainingText"], "99")
        self.assertEqual(parsed["under 8.5"]["filters"], {"priceMax": 8.5}, "a price cap is never also a width")
        self.assertEqual(parsed["54"]["filters"], {}, "a bare 54 stays text (it still prefix-matches 54mm)")
        self.assertEqual(parsed["spitfire"]["filters"], {})
        self.assertEqual(parsed["8.5mm"]["filters"], {}, "not a wheel size, not a width")
        self.assertEqual(parsed["12.5"]["filters"], {}, "outside the deck width range")
        self.assertEqual(parsed["8"]["filters"], {}, "a whole number needs its unit to be a width")
        self.assertEqual(parsed["150% off"]["filters"], {})

    def test_labels_and_removing_a_chip(self):
        code, out = run(r"""
const parsed = S.parseQuery("Spitfire 54 mm 84b under $30");
assert.deepEqual(parsed.tokens.map(token => token.label), ["54mm", "84b (104a)", "< $30"]);
const duro = parsed.tokens[1];
assert.equal(S.queryWithout("Spitfire 54 mm 84b under $30", duro), "Spitfire 54 mm under $30");
assert.equal(S.queryWithout("Spitfire 54 mm 84b under $30", parsed.tokens[2]), "Spitfire 54 mm 84b");
assert.deepEqual(S.parseQuery("ccs zumiez").filters, { stores: ["CCS", "Zumiez"] }, "several stores: any of them");
assert.equal(S.parseQuery("skate warehouse").tokens[0].label, "Skate Warehouse");
""")
        self.assertEqual(code, 0, out)


class RankingTests(unittest.TestCase):
    def test_the_named_cases(self):
        code, out = run(FIXTURE + r"""
const bo = ranked("bo");
assert.ok(bo[0].startsWith("bones"), "bo: Bones first, got " + bo.join(","));
assert.ok(bo.indexOf("oj-combo") > bo.indexOf("bones-stf"), "Combo (mid-word) after Bones");
assert.ok(bo.includes("oj-combo"), "short queries still match mid-word");
assert.deepEqual(ranked("spitfre").sort(), ["sf-80hd", "sf-bighead", "sf-classic"]);
assert.deepEqual(ranked("spitty bighead"), ["sf-bighead"]);
assert.deepEqual(found("oj chubbies 54"), ["oj-chub-54"]);
assert.deepEqual(found("O.J. chubbies"), ["oj-chub-54", "oj-chub-56"]);
assert.deepEqual(found("indy"), ["indy"], "a nickname, not a fuzzy Andy");
assert.deepEqual(found("f4 classic"), ["sf-classic"]);
""")
        self.assertEqual(code, 0, out)

    def test_the_acceptance_query_filters_exactly(self):
        code, out = run(FIXTURE + r"""
rows.find(row => row.dataset.id === "sf-bighead").dataset.price = "24.99";
assert.deepEqual(found("spitfire 54mm 99a"), ["sf-bighead"]);
assert.deepEqual(found("spitfire 53mm 99a"), ["sf-classic"]);
assert.deepEqual(found("spitfire 54mm 97a"), [], "99a is not 97a");
assert.deepEqual(found("101a"), ["oj-combo", "oj-chub-54", "bones-spf"], "81B is 101A");
assert.deepEqual(found("81b"), ["oj-combo", "oj-chub-54", "bones-spf"]);
assert.deepEqual(found("101a/95a"), ["oj-chub-54"], "a double duro needs both");
assert.deepEqual(found("8.25"), ["baker", "andy"]);
assert.deepEqual(found("bones bearings"), ["bones-reds"]);
assert.ok(!ranked("104a").length, "sizes and durometers are never fuzzy");
""")
        self.assertEqual(code, 0, out)

    def test_text_match_for_lists_outside_the_index(self):
        code, out = run(r"""
assert.ok(S.matchesText("indy", "Independent Stage 11 Truck Tactics Trucks Independent"));
assert.ok(S.matchesText("spitty f4", "Spitfire Formula Four Classic 53mm"));
assert.ok(!S.matchesText("bones", "Spitfire Formula Four Classic 53mm"));
assert.ok(S.matchesText("", "anything"));
""")
        self.assertEqual(code, 0, out)


class PerformanceTests(unittest.TestCase):
    def test_ten_thousand_items_stay_fast(self):
        code, out = run(r"""
const brands = ["Spitfire", "OJ", "Bones", "Independent", "Thunder", "Venture", "Baker", "Santa Cruz", "Powell Peralta", "Krooked"];
const models = ["Formula Four Classic", "Chubbies", "Bighead", "Elite Mini Combo", "Stage 11 Hollow", "Team Logo", "Conical Full", "Hardline"];
const parts = ["Wheels", "Decks", "Trucks", "Bearings"];
const rows = [];
for (let i = 0; i < 10000; i++) {
  const brand = brands[i % brands.length];
  rows.push({ dataset: { id: String(i), brand, part: parts[i % 4], store: "CCS", size: String(7.5 + (i % 12) / 4),
    duros: (95 + i % 7) + "a", name: brand + " " + models[i % models.length] + " " + (50 + i % 10) + "mm " + (95 + i % 7) + "a #" + i } });
}
let started = Date.now();
const index = S.createIndex(rows.map(S.docFromRow));
const built = Date.now() - started;
const queries = ["spitfire", "spitfre", "oj chubbies 54", "bo", "spitty bighead 54mm 99a under 30", "indy hollow", "santa cruz team"];
let worst = 0;
queries.forEach(query => {
  started = Date.now();
  const parsed = S.parseQuery(query);
  const hits = parsed.remainingText ? S.search(index, parsed.remainingText) : null;
  rows.forEach(row => (!hits || hits.has(row.dataset.id)) && S.rowAllows(parsed.filters, row));
  worst = Math.max(worst, Date.now() - started);
});
console.log(JSON.stringify({ built, worst }));
assert.ok(worst < 100, "slowest query " + worst + " ms");
assert.ok(built < 3000, "indexing " + built + " ms");
""")
        self.assertEqual(code, 0, out)


if __name__ == "__main__":
    unittest.main()
