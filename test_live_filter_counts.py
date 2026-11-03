"""BMX/Ski/MTB spec chip counts narrow with the other filters, like Skate's
(2026-11-03: picking a brand left the Ski type/length counts unchanged)."""

import json
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

CONFIG = {
    "fields": [
        {"key": "ski_type", "label": "Type", "param": "ski_type", "categories": ["Skis"], "values": ["Freeride", "Race"]},
        {"key": "length", "label": "Length", "param": "ski_len", "categories": ["Skis"], "values": ["170", "180"]},
    ],
    "items": {
        "a": {"part": "Skis", "offers": [
            {"variant_id": 1, "price": 400, "compare": 600, "available": True, "specs": {"ski_type": ["Race"], "length": ["170"]}},
            {"variant_id": 2, "price": 400, "compare": 600, "available": True, "specs": {"ski_type": ["Race"], "length": ["180"]}}]},
        "b": {"part": "Skis", "offers": [
            {"variant_id": 3, "price": 300, "compare": 500, "available": True, "specs": {"ski_type": ["Freeride"], "length": ["180"]}},
            {"variant_id": 4, "price": 300, "compare": 500, "available": False, "specs": {"ski_type": ["Freeride"], "length": ["170"]}}]},
        "c": {"part": "Boots", "offers": [{"variant_id": 5, "price": 100, "compare": 200, "available": True, "specs": {}}]},
    },
}

SCRIPT = r"""
const assert = require('assert');
const create = require('./previews/sport-filters.js');
const f = create(JSON.parse(process.argv[1]));
const rows = [{url: 'a', part: 'Skis', brand: 'Blizzard'}, {url: 'b', part: 'Skis', brand: 'Atomic'}, {url: 'c', part: 'Boots', brand: 'Atomic'}];
// The page's filter test: a brand filter plus the spec picks.
const page = brand => (row, technical) => (brand === 'all' || row.brand === brand) && f.allows(row.url, row.part, technical);
let c = f.counts(rows, page('all'), {});
assert.deepStrictEqual(c.ski_type, {'': 2, Race: 1, Freeride: 1});
assert.deepStrictEqual(c.length, {'': 2, 170: 1, 180: 2}, 'the sold-out Freeride 170 is not counted');
// Picking a brand narrows every field.
c = f.counts(rows, page('Blizzard'), {});
assert.deepStrictEqual(c.ski_type, {'': 1, Race: 1});
assert.deepStrictEqual(c.length, {'': 1, 170: 1, 180: 1});
// Picking a spec narrows the other fields, by the same offer, but not its own.
f.restore({ski_type: 'Freeride'});
c = f.counts(rows, page('all'), {});
assert.deepStrictEqual(c.length, {'': 1, 180: 1});
assert.deepStrictEqual(c.ski_type, {'': 2, Race: 1, Freeride: 1}, 'its own options stay pickable');
// Price ranges apply per offer.
f.clear();
c = f.counts(rows, page('all'), {priceMax: 350});
assert.deepStrictEqual(c.ski_type, {'': 1, Freeride: 1});
"""


class LiveFilterCountTests(unittest.TestCase):
    def test_counts_follow_the_other_filters(self):
        result = subprocess.run(["node", "-e", SCRIPT, json.dumps(CONFIG)], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_page_repaints_them(self):
        page = (ROOT / "page.js").read_text(encoding="utf-8")
        self.assertIn("paintTechnicalCounts();", page.split("function paintFacetCounts()", 1)[1].split("\nfunction ", 1)[0])


if __name__ == "__main__":
    unittest.main()
