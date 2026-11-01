"""The ShredDeals visual preview stays off GitHub Pages and themes by tokens only."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PREVIEW = ROOT / "design" / "shreddeals"
CSS = (PREVIEW / "shreddeals.css").read_text()
HTML = (PREVIEW / "preview.html").read_text()
LOGO = (PREVIEW / "logo.svg").read_text()


def _excluded():
    names = set()
    for line in (ROOT / "_config.yml").read_text().splitlines():
        if line.startswith("  - "):
            names.add(line[4:].strip().strip('"'))
    return names


def _blocks(css):
    stripped = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    return re.findall(r"([^{}]+)\{([^{}]*)\}", stripped)


class ShredDealsDesignTests(unittest.TestCase):
    def test_preview_root_and_test_are_excluded_from_pages(self):
        excluded = _excluded()
        self.assertIn("design", excluded)
        self.assertIn("test_shreddeals_design.py", excluded)

    def test_accent_switch_only_sets_color_tokens(self):
        sport_rules = 0
        for selector, body in _blocks(CSS):
            if "data-accents" not in selector:
                continue
            declarations = [item.strip() for item in body.split(";") if item.strip()]
            self.assertTrue(declarations, selector)
            for declaration in declarations:
                name = declaration.split(":", 1)[0].strip()
                self.assertTrue(name.startswith("--"), declaration)
                self.assertIn(name, {"--sd-accent", "--sd-accent-bright"})
            if 'data-accents="sport"' in selector:
                sport_rules += 1
        self.assertEqual(sport_rules, 4)
        self.assertIn('html[data-accents="utility"]', CSS)
        for sport in ("skate", "ski", "mtb", "bmx"):
            self.assertIn(f'[data-sport="{sport}"]', CSS)

    def test_preview_is_self_contained_and_does_not_claim_an_alert(self):
        self.assertIn("shreddeals.css", HTML)
        self.assertIn('aria-current="page"', HTML)
        for label in ("Skate", "Ski", "MTB", "BMX", "Deals", "Track", "Insights", "Subscribe"):
            self.assertIn(label, HTML)
        self.assertLess(HTML.index(">Skate<"), HTML.index(">Ski<"))
        self.assertLess(HTML.index(">Ski<"), HTML.index(">MTB<"))
        self.assertLess(HTML.index(">MTB<"), HTML.index(">BMX<"))
        self.assertIn("no alert is set", HTML)
        self.assertIn("No alert was set", HTML)
        self.assertNotIn("<form", HTML.lower())
        self.assertNotIn("type=\"email\"", HTML.lower())
        self.assertNotRegex(HTML, r"api[_-]?key|secret|turnstile|cloudflare", re.I)
        for section in ("/* header */", "/* sport-nav */", "/* coming-soon */"):
            self.assertIn(section, CSS)
        self.assertIn("ShredDeals", LOGO)
        self.assertIn("M3 12c3.2-5.6 14.8-5.6 18 0", LOGO)
        self.assertIn("M3 12c3.2-5.6 14.8-5.6 18 0", HTML)

    def test_live_sources_do_not_carry_the_preview_tokens(self):
        for relative in (
            "page.css", "page.js", "page.py", "mobile.css", "index.html",
            "navigation/navigation.css", "scraper.py", "rebuild_page.py",
        ):
            text = (ROOT / relative).read_text(errors="ignore")
            self.assertNotIn("data-accents", text, relative)
            self.assertNotIn("--sd-accent", text, relative)


if __name__ == "__main__":
    unittest.main()
