"""The ShredDeals site with more than one catalog: the preview build adds a
page per sport that has listings, the homepage tabs open each sport's own
page, and the preview workflow can never reach production or send mail."""

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml

import scraper
import sports
from ci import build_preview
from test_sports import DATA

ROOT = Path(__file__).resolve().parent


def scrape_into(root, sport_id, data):
    """A real run of one sport into a scratch root, stores replaced by ``data``."""
    root = Path(root)
    for sport in sports.SPORTS.values():
        target = root / sport.aliases
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(sport.aliases_file(), target)
    cwd = os.getcwd()
    try:
        os.chdir(root)
        with mock.patch.object(sports, "ROOT", root), \
             mock.patch.object(scraper, "run_stores", return_value=(json.loads(json.dumps(data)), set())):
            scraper.main(["--sport", sport_id])
    finally:
        os.chdir(cwd)


class PreviewSiteTests(unittest.TestCase):
    def test_sports_with_listings_get_a_page_and_a_homepage_tab(self):
        with tempfile.TemporaryDirectory() as data_root, tempfile.TemporaryDirectory() as out:
            scrape_into(data_root, "bmx", DATA)
            scrape_into(data_root, "ski", {})
            build_preview.build(out, "test", data_root=data_root)
            out = Path(out)
            bmx = (out / "bmx/sale_items_chart.html").read_text(encoding="utf-8")
            self.assertIn("ShredDeals BMX", bmx)
            self.assertIn('id="previewBanner"', bmx)
            self.assertNotIn("window.SKATEDEALS_ALERTS = ", bmx)
            self.assertIn('bridge.src="../navigation/skate-bridge.js"', bmx)
            self.assertTrue((out / "bmx/history.json").is_file())
            self.assertFalse((out / "ski").exists(), "a sport without listings keeps 'coming soon'")
            skate = (out / "sale_items_chart.html").read_text(encoding="utf-8")
            self.assertNotIn("albes.com", skate)
            self.assertNotIn("albes.com", (out / "history.json").read_text(encoding="utf-8"))
            home = (out / "index.html").read_text(encoding="utf-8")
            config = json.loads(home.split('id="sportConfig"', 1)[1].split(">", 1)[1].split("</script>", 1)[0])
            catalogs = {sport["id"]: sport["catalog"] for sport in config["sports"]}
            self.assertEqual(catalogs, {"skate": "sale_items_chart.html", "ski": None, "mtb": None,
                                        "bmx": "bmx/sale_items_chart.html"})

    def test_without_sport_data_the_preview_is_unchanged(self):
        with tempfile.TemporaryDirectory() as data_root, tempfile.TemporaryDirectory() as out:
            files = build_preview.build(out, "test", data_root=data_root)
            self.assertEqual(files, ["_headers", "history.json", "index.html", "navigation", "sale_items_chart.html"])

    def test_published_homepage_still_has_only_skate(self):
        from previews.publish import publish

        with tempfile.TemporaryDirectory() as out:
            home = publish(out).read_text(encoding="utf-8")
            self.assertIn('"catalog": "sale_items_chart.html"', home)
            self.assertNotIn("bmx/sale_items_chart.html", home)


class NavigationTests(unittest.TestCase):
    def test_each_sport_opens_its_own_catalog_and_starts_with_fresh_filters(self):
        script = r"""
const assert = require('node:assert/strict');
const N = require('./previews/navigation.js');
const config = {defaultSport: 'skate', skateQueryKeys: ['type', 'q', 'store', 'sort'], sports: [
  {id: 'skate', label: 'Skate', catalog: 'sale_items_chart.html'},
  {id: 'ski', label: 'Ski', catalog: null},
  {id: 'bmx', label: 'BMX', catalog: 'bmx/sale_items_chart.html'}]};
const home = 'https://site.example/index.html?sport=bmx&type=wheel-parts&utm=x';
assert.equal(N.catalogURL(home, config, 'bmx').href, 'https://site.example/bmx/sale_items_chart.html?type=wheel-parts&utm=x');
assert.equal(N.skateURL(home, config).pathname, '/sale_items_chart.html');
const merged = N.mergeSkateURL(home, 'https://site.example/bmx/sale_items_chart.html?type=tires', config, 'bmx');
assert.equal(merged.search, '?sport=bmx&utm=x&type=tires');
assert.throws(() => N.mergeSkateURL(home, 'https://site.example/sale_items_chart.html?type=decks', config, 'bmx'),
              'a late Skate load cannot rewrite the BMX tab');
assert.throws(() => N.mergeSkateURL(home, 'https://other.example/bmx/sale_items_chart.html', config, 'bmx'));
// Moving between two catalogs drops the previous one's filters, keeps unrelated keys.
assert.equal(N.navigate(home, config, 'skate').search, '?sport=skate&utm=x');
assert.equal(N.navigate(home, config, 'bmx').search, '?sport=bmx&type=wheel-parts&utm=x');
// A "coming soon" sport keeps them for the way back (Codex's design).
const ski = N.navigate('https://site.example/?sport=skate&type=decks', config, 'ski');
assert.equal(ski.search, '?sport=ski&type=decks');
assert.equal(N.navigate(ski, config, 'skate').search, '?sport=skate&type=decks');
// Skate is the default sport, so its filters survive choosing Skate.
assert.equal(N.navigate('https://site.example/?type=decks', config, 'skate').search, '?type=decks&sport=skate');
"""
        subprocess.run(["node", "-e", script], check=True, cwd=ROOT)

    def test_published_copy_matches(self):
        self.assertEqual((ROOT / "navigation/navigation.js").read_bytes(), (ROOT / "previews/navigation.js").read_bytes())


class PreviewWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.text = (ROOT / ".github/workflows/shreddeals-preview.yml").read_text(encoding="utf-8")
        self.workflow = yaml.safe_load(self.text)
        self.workflow["on"] = self.workflow.pop(True, self.workflow.get("on"))

    def test_runs_by_hand_or_daily_and_scrapes_at_most_one_new_sport(self):
        self.assertEqual(sorted(self.workflow["on"]), ["schedule", "workflow_dispatch"])
        self.assertEqual(len(self.workflow["on"]["schedule"]), 1, "once a day")
        # A scheduled run has no inputs; "all" means the new sports, never Skate.
        self.assertIn("CHOICE: ${{ inputs.scrape || 'all' }}", self.text)
        self.assertIn("set -- bmx ski mtb", self.text)
        self.assertNotIn("skate", self.text.split("set -- bmx ski mtb")[0].split("CHOICE:")[1])
        options = self.workflow["on"]["workflow_dispatch"]["inputs"]["scrape"]["options"]
        self.assertEqual(options, ["all", "none", "bmx", "ski", "mtb"], "Skate is never scraped here")
        for option in ("bmx", "ski", "mtb"):
            self.assertFalse(sports.get(option).delivery, f"{option} would send email")
        self.assertIn('python scraper.py --sport "$SPORT"', self.text)

    def test_never_touches_production(self):
        self.assertEqual(self.workflow["permissions"], {"contents": "write"})
        self.assertNotIn("${{ secrets.", self.text, "no SMTP or alert credentials")
        self.assertNotIn("vars.", self.text)
        pushes = [line.strip() for line in self.text.splitlines() if "git push" in line]
        self.assertEqual(pushes, ['git push -q --force "$(git -C .. remote get-url origin)" "HEAD:$PREVIEW_BRANCH"'])
        self.assertEqual(self.workflow["jobs"]["preview"]["env"]["PREVIEW_BRANCH"], "shreddeals-preview")
        self.assertNotIn("main", self.workflow["jobs"]["preview"]["env"]["PREVIEW_BRANCH"])


if __name__ == "__main__":
    unittest.main()
