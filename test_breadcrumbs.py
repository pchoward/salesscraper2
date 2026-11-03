"""Tactics-style breadcrumbs (2026-11-03): Sport / Type / Brand / ...; a crumb
backs out of everything after it."""

import unittest
from pathlib import Path

import sports
from report import build_report_html

ROOT = Path(__file__).resolve().parent


class BreadcrumbTests(unittest.TestCase):
    def test_every_sport_page_has_the_trail(self):
        for sport in (sports.SKATE, sports.SKI, sports.MTB, sports.BMX):
            html = build_report_html({}, {}, generated_at="2026-11-03T00:00:00+00:00", sport=sport)
            self.assertIn('<nav class="crumbs" id="breadcrumbs" aria-label="Breadcrumb" hidden><ol></ol></nav>', html, sport.id)

    def test_trail_order_and_back_out(self):
        page = (ROOT / "page.js").read_text(encoding="utf-8")
        trail = page.split("function breadcrumbTrail()", 1)[1].split("\nfunction ", 1)[0]
        self.assertIn('["part", "brand", "store"]', trail, "type, brand and store lead; other picks follow in pick order")
        back = page.split("function backOutTo(", 1)[1].split("\nfunction ", 1)[0]
        self.assertIn("crumbBatch = true", back, "one repaint, not one per removed filter")
        self.assertIn("SportSpecFilters.restore(kept)", back, "spec picks are dropped together")
        self.assertIn("if (crumbBatch) return;", page.split("function applyFilters()", 1)[1][:80])


if __name__ == "__main__":
    unittest.main()
