"""Tactics shows a live store-wide code as a "20% off" tile badge on
full-price items (owner's cart test, 2026-11-27: BFCM26, "Full Price Items
Only"). Those tiles aren't markdowns; real ones at other percents stay."""

import datetime
import json
import os
import tempfile
import unittest
from unittest import mock

from stores import tactics

PAGE = ('<div class="browse-grid-item"><a href="/independent-stage-11-trucks"><img alt="Independent Stage 11 Trucks"/></a>'
        '<span class="browse-grid-item-sale-price">$59.95</span><span class="browse-grid-item-discount">(20% off)</span></div>'
        '<div class="browse-grid-item"><a href="/thunder-hollow-lights"><img alt="Thunder Hollow Lights Trucks"/></a>'
        '<span class="browse-grid-item-sale-price">$49.95</span><span class="browse-grid-item-discount">(30% off)</span></div>')
TODAY = datetime.date(2026, 11, 27)


def promos(*entries):
    handle = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
    json.dump({"promos": list(entries)}, handle)
    handle.close()
    return handle.name


class LiveCodeTests(unittest.TestCase):
    def setUp(self):
        tactics._live_code.clear()

    def tearDown(self):
        tactics._live_code.clear()

    def test_live_code_percent(self):
        path = promos({"store": "CCS", "code": "BFCM26", "percent": 25},
                      {"store": "Tactics", "code": "BFCM26", "percent": 20, "ends": ""})
        self.assertEqual(tactics.live_code_percent(path, TODAY), 20)
        os.unlink(path)

    def test_ended_or_no_code_means_none(self):
        for entry in ({"store": "Tactics", "code": "BFCM26", "percent": 20, "ends": "2026-11-26"},
                      {"store": "Tactics", "code": "", "auto": True, "percent": 20}):
            tactics._live_code.clear()
            path = promos(entry)
            self.assertIsNone(tactics.live_code_percent(path, TODAY))
            os.unlink(path)

    def parse(self, part, code):
        scraper = tactics.TacticsScraper("Tactics", "https://www.tactics.com/skateboard-trucks/sale", part)
        with mock.patch.object(tactics, "live_code_percent", return_value=code), \
                mock.patch.object(tactics, "save_debug_file"):
            return [item["name"] for item in scraper.parse(PAGE)]

    def test_a_badge_equal_to_the_code_is_skipped(self):
        self.assertEqual(self.parse("Trucks", 20), ["Thunder Hollow Lights Trucks"])

    def test_no_live_code_keeps_both(self):
        self.assertEqual(len(self.parse("Trucks", None)), 2)


if __name__ == "__main__":
    unittest.main()
