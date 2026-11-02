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

    def test_published_homepage_without_catalogs_has_only_skate(self):
        from previews.publish import publish

        with tempfile.TemporaryDirectory() as out:
            home = publish(out, catalogs={}).read_text(encoding="utf-8")
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

    def test_runs_by_hand_and_never_scrapes_skate(self):
        self.assertEqual(list(self.workflow["on"]), ["workflow_dispatch"], "the daily scrape is the live one now")
        self.assertIn("set -- bmx ski mtb", self.text)
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


class LiveSportsWorkflowTests(unittest.TestCase):
    """Going live (2026-11-02): the daily BMX/Ski/MTB scrape publishes to main."""

    def setUp(self):
        self.text = (ROOT / ".github/workflows/scrape-sports.yml").read_text(encoding="utf-8")
        self.workflow = yaml.safe_load(self.text)
        self.workflow["on"] = self.workflow.pop(True, self.workflow.get("on"))

    def test_daily_and_by_hand_for_the_new_sports_only(self):
        self.assertEqual(sorted(self.workflow["on"]), ["schedule", "workflow_dispatch"])
        self.assertEqual(self.workflow["on"]["workflow_dispatch"]["inputs"]["sport"]["options"], ["all", "bmx", "ski", "mtb"])
        for sport_id in ("bmx", "ski", "mtb"):
            self.assertFalse(sports.get(sport_id).delivery, f"{sport_id} would send email")
        self.assertIn('python scraper.py --sport "$SPORT"', self.text)
        self.assertNotIn("skate", self.text.lower().split("jobs:")[1].replace("skate's", ""))

    def test_shares_the_scrape_lock_uses_no_secrets_and_commits_only_its_sports(self):
        self.assertEqual(self.workflow["concurrency"]["group"], "scrape-${{ github.ref }}")
        skate = yaml.safe_load((ROOT / ".github/workflows/scrape.yml").read_text(encoding="utf-8"))
        self.assertEqual(skate["concurrency"]["group"], self.workflow["concurrency"]["group"])
        self.assertNotIn("${{ secrets.", self.text)
        self.assertNotIn("${{ vars.", self.text)
        adds = [line.strip() for line in self.text.splitlines() if "git add" in line]
        self.assertEqual(adds, ["git add index.html navigation",
                                'if [ -e "catalogs/$sport" ]; then git add -A -- "catalogs/$sport"; fi',
                                'if [ -e "$sport/sale_items_chart.html" ]; then git add -A -- "$sport"; fi'])
        for skate_file in ("previous_data.json", "price_history.json", "sale_items_chart.html\n", "scrape_health.json"):
            self.assertNotIn(f"git add {skate_file}", self.text)

    def test_non_skate_pages_carry_no_live_alerts(self):
        import page
        from report import build_report_html

        live = {"apiBase": "https://alerts.example", "turnstileSiteKey": "site-key"}
        with mock.patch.object(page, "ALERTS_UI_CONFIG", live):
            bmx = build_report_html({}, {}, {}, set(), generated_at="2026-11-02T12:00:00+00:00", sport=sports.BMX)
            skate = build_report_html({}, {}, {}, set(), generated_at="2026-11-02T12:00:00+00:00")
        self.assertNotIn("window.SKATEDEALS_ALERTS = ", bmx)
        self.assertIn("window.SKATEDEALS_ALERTS = ", skate)

    def test_homepage_tabs_follow_catalogs_with_listings(self):
        import json
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for sport_id, items in (("bmx", [{"url": "x"}]), ("ski", [])):
                sport = sports.get(sport_id)
                (root / sport.data_dir).mkdir(parents=True)
                (root / sport.data_dir / "previous_data.json").write_text(json.dumps({"A_Parts": items}))
                (root / sport.page_path).parent.mkdir(parents=True)
                (root / sport.page_path).write_text("<html></html>")
            self.assertEqual(sports.published_catalogs(root), {"bmx": "bmx/sale_items_chart.html"},
                             "Ski has a page but no listings yet: still 'coming soon'")
