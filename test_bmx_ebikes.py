"""Electric bikes stay out of BMX (owner, 2026-11-05)."""

import json
import unittest
from pathlib import Path

from sports import rules


class BmxEbikeTests(unittest.TestCase):
    def test_electric_bikes_are_dropped(self):
        for name in ("Haro Skwad 1 Electric Bike", "Haro Skwad 2 Electric Bike", "Mongoose E-Bike Pro",
                     "Volt eBike 20\"", "Pedal-Assist BMX", "Kids Electric Balance Bike", "Some E-BMX"):
            self.assertEqual(rules.bmx(name, "Bikes"), "electric bike", name)

    def test_electric_as_a_colour_is_kept(self):
        for name in ("Odyssey Broc Grips Electric Blue", "Shadow Crow Grips - Electric Purple", "Haro Leucadia Bike"):
            self.assertNotEqual(rules.bmx(name, "Steering" if "Grips" in name else "Bikes"), "electric bike", name)

    def test_none_left_in_live_bmx_data(self):
        # The live catalog changes with every scrape: check what stays true
        # (no listing the rule would drop), not which bikes were on sale once.
        data = json.loads((Path(__file__).resolve().parent / "catalogs/bmx/previous_data.json").read_text())
        names = [i["name"] for v in data.values() if isinstance(v, list) for i in v]
        self.assertTrue(names)
        self.assertEqual([n for n in names if rules.bmx(n, "Bikes") == "electric bike"], [])

if __name__ == "__main__":
    unittest.main()
