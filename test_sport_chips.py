"""Sport spec filters look and behave like Skate's: one collapsible section per
field with count chips, several values per field (any matches), "All" clears."""

import json
import subprocess
import unittest
from pathlib import Path

from bs4 import BeautifulSoup

import sports
from sports import facets

ROOT = Path(__file__).resolve().parent
DATA = {"GW_Skis": [
    {"name": "Park Ski", "url": "https://x/park", "price_new": "300", "price_old": "500", "part": "Skis", "store": "GW",
     "technical_offers": [{"variant_id": 1, "price": 300.0, "compare": 500.0, "available": True,
                           "specs": {"ski_type": ["Park & Freestyle"], "length": ["170–179 cm"]}}]},
    {"name": "Race Ski", "url": "https://x/race", "price_new": "400", "price_old": "800", "part": "Skis", "store": "GW",
     "technical_offers": [{"variant_id": 2, "price": 400.0, "compare": 800.0, "available": True,
                           "specs": {"ski_type": ["Race"], "length": ["160–169 cm"]}}]},
    {"name": "Big Ski", "url": "https://x/big", "price_new": "350", "price_old": "700", "part": "Skis", "store": "GW",
     "technical_offers": [{"variant_id": 3, "price": 350.0, "compare": 700.0, "available": True,
                           "specs": {"ski_type": ["Freeride"], "length": ["180–189 cm"]}}]},
]}


def section(section_id, label, body, open_default=False, for_part="", tip=""):
    return (f'<section class="filter-section{" is-open" if open_default else ""}" data-section="{section_id}">'
            f'<button class="section-toggle">{label}</button><div class="section-body">{body}</div></section>')


class MarkupTests(unittest.TestCase):
    def test_one_section_per_field_with_count_chips(self):
        with sports.SKI.active():
            soup = BeautifulSoup(facets.sidebar(DATA, section, sports.SKI), "html.parser")
        type_field = soup.select_one('[data-technical-field="ski_type"]')
        self.assertEqual(type_field.select_one(".section-toggle").text, "Type", "its own section, like Deck Width")
        chips = {chip["data-value"]: chip.select_one(".spec-count").text for chip in type_field.select(".tech-chip")}
        self.assertEqual(chips, {"": "3", "Freeride": "1", "Park & Freestyle": "1", "Race": "1"}, "All plus a chip per value, with counts")
        self.assertEqual(type_field.select_one('.tech-chip[data-value=""]')["aria-pressed"], "true")
        self.assertTrue(all("spec-chip" in chip["class"] for chip in soup.select(".tech-chip")), "Skate's chip style")
        self.assertIsNone(soup.select_one("select"), "no dropdowns")


class BehaviourTests(unittest.TestCase):
    def test_several_values_match_any_and_encode_in_the_url(self):
        with sports.SKI.active():
            config = facets.payload(DATA, sports.SKI)
        script = r"""
const assert = require('node:assert/strict');
const f = require('./previews/sport-filters.js')(JSON.parse(process.argv[1]));
f.restore({ski_type: ['Park & Freestyle', 'Race']});
assert.equal(f.allows('https://x/park', 'Skis'), true);
assert.equal(f.allows('https://x/race', 'Skis'), true);
assert.equal(f.allows('https://x/big', 'Skis'), false);
f.restore({ski_type: ['Park & Freestyle', 'Race'], length: '160–169 cm'});
assert.equal(f.allows('https://x/park', 'Skis'), false, 'fields still combine with AND');
assert.equal(f.allows('https://x/race', 'Skis'), true);
const params = new URLSearchParams();
f.restore({ski_type: ['Park & Freestyle', 'Race']});
f.encode(params, f.capture());
assert.equal(params.get('ski_type'), 'Park & Freestyle,Race');
f.restore(f.decode(params));
assert.deepEqual(f.capture().ski_type, ['Park & Freestyle', 'Race']);
f.restore({ski_type: 'Race'});
assert.equal(f.capture().ski_type, 'Race', 'one value reads back as a string');
f.restore({ski_type: ['Nonsense']});
assert.deepEqual(f.capture(), {}, 'unknown values are dropped');
"""
        result = subprocess.run(["node", "-e", script, json.dumps(config)], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
