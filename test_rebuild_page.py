"""rebuild_page.py reproduces the scrape's page from saved data, byte for byte."""

import contextlib
import copy
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import rebuild_page
import scraper
from pipeline import decorate_digest
from report import build_digest, build_report_html, compare_catalogs

ROOT = Path(__file__).resolve().parent
SCANNED_AT = "2026-10-25T09:38:00+00:00"


@contextlib.contextmanager
def working_copy():
    """A temp directory with the files the page reads from the working directory."""
    previous = os.getcwd()
    directory = Path(tempfile.mkdtemp())
    try:
        for name in ("watchlist.yaml", "site_sales.json"):
            if (ROOT / name).exists():
                shutil.copy(ROOT / name, directory / name)
        os.chdir(directory)
        yield directory
    finally:
        os.chdir(previous)
        shutil.rmtree(directory, ignore_errors=True)


def _catalogs():
    """Today's committed catalog, and an older one so there are real changes."""
    current = json.loads((ROOT / "previous_data.json").read_text(encoding="utf-8"))
    older = copy.deepcopy(current)
    for key, items in older.items():
        # Drop some listings (they become New), raise some prices (Price drops),
        # and add a listing that is gone today (Disappeared).
        del items[::7]
        for item in items[::5]:
            try:
                item["price_new"] = f"{float(item['price_new']) * 1.3:.2f}"
            except (KeyError, TypeError, ValueError):
                pass
        if items:
            gone = dict(items[0], url=items[0]["url"] + "?gone=1", name=items[0].get("name", "") + " Gone")
            items.append(gone)
    return older, current


def scrape_build(previous, current, history, failed_keys):
    """The scrape's own sequence (scraper.main): save, decorate, build, save inputs."""
    changes = compare_catalogs(previous, current, failed_keys)
    digest = build_digest(changes, failed_keys)
    history_saved = scraper.save_price_history(history)
    data_saved = scraper.save_current(current)
    decorate_digest(digest, current, history, [], previous_data=previous, scanned_at=SCANNED_AT, failed_keys=failed_keys)
    html = build_report_html(current, changes, history, failed_keys, generated_at=SCANNED_AT, digest=digest)
    Path("sale_items_chart.html").write_text(html, encoding="utf-8")
    assert data_saved and history_saved
    rebuild_page.save_report_inputs(changes, digest, failed_keys, SCANNED_AT, history_saved)
    return html, digest


class RebuildPageTests(unittest.TestCase):
    def setUp(self):
        self.previous, self.current = _catalogs()
        self.history = json.loads((ROOT / "price_history.json").read_text(encoding="utf-8"))
        self.failed = sorted(self.current)[:1]

    def test_rebuild_matches_the_scrape_page_exactly(self):
        with working_copy():
            html, digest = scrape_build(self.previous, self.current, self.history, self.failed)
            self.assertTrue(digest.new_items and digest.drops and digest.removed, "the fixture has every kind of change")
            Path("sale_items_chart.html").unlink()
            self.assertTrue(rebuild_page.rebuild())
            self.assertEqual(Path("sale_items_chart.html").read_text(encoding="utf-8"), html)
            self.assertFalse(rebuild_page.rebuild(), "a second rebuild changes nothing")
            for name in ("previous_data.json", "price_history.json", "report_inputs.json"):
                self.assertTrue(Path(name).exists())

    def test_new_page_code_with_the_same_changes(self):
        """A rebuild after a UI change keeps the last scrape's changes and time."""
        with working_copy():
            html, digest = scrape_build(self.previous, self.current, self.history, self.failed)
            # A plain build from the saved catalog alone, as a naive rebuild would
            # do, compares the catalog with itself: every change tab empties.
            naive = build_report_html(self.current, {}, self.history, self.failed, generated_at=SCANNED_AT)
            self.assertNotEqual(naive, html)
            inputs = rebuild_page.load_report_inputs()
            self.assertEqual(inputs["generated_at"], SCANNED_AT)
            self.assertEqual(len(inputs["digest"].new_items), len(digest.new_items))
            self.assertEqual(len(inputs["digest"].drops), len(digest.drops))
            self.assertEqual(len(inputs["digest"].removed), len(digest.removed))

    def test_refuses_when_the_saved_data_no_longer_matches(self):
        with working_copy():
            scrape_build(self.previous, self.current, self.history, self.failed)
            before = Path("sale_items_chart.html").read_text(encoding="utf-8")
            Path("previous_data.json").write_text("{}", encoding="utf-8")
            with self.assertRaisesRegex(rebuild_page.RebuildError, "previous_data.json changed"):
                rebuild_page.rebuild()
            self.assertEqual(Path("sale_items_chart.html").read_text(encoding="utf-8"), before, "nothing written")

        with working_copy():
            scrape_build(self.previous, self.current, self.history, self.failed)
            Path("price_history.json").write_text("{}", encoding="utf-8")
            with self.assertRaisesRegex(rebuild_page.RebuildError, "price_history.json changed"):
                rebuild_page.rebuild()

    def test_missing_or_discarded_inputs(self):
        with working_copy():
            with self.assertRaisesRegex(rebuild_page.RebuildError, "run Scrape Sale Items once"):
                rebuild_page.rebuild()
            self.assertEqual(rebuild_page.main(["--skip-if-missing"]), 0)
            self.assertFalse(Path("sale_items_chart.html").exists())
            with contextlib.redirect_stderr(open(os.devnull, "w")):
                self.assertEqual(rebuild_page.main([]), 1)
            scrape_build(self.previous, self.current, self.history, self.failed)
            rebuild_page.discard_report_inputs()
            self.assertFalse(Path("report_inputs.json").exists())

    def test_history_left_unsaved_rebuilds_with_empty_history(self):
        with working_copy():
            scraper.save_current(self.current)
            Path("price_history.json").write_text('{"stale": {}}', encoding="utf-8")
            changes = compare_catalogs(self.previous, self.current, [])
            digest = build_digest(changes, [])
            html = build_report_html(self.current, changes, {}, [], generated_at=SCANNED_AT, digest=digest)
            rebuild_page.save_report_inputs(changes, digest, [], SCANNED_AT, history_saved=False)
            rebuild_page.rebuild()
            self.assertEqual(Path("sale_items_chart.html").read_text(encoding="utf-8"), html)

    def test_workflow_is_page_only_and_shares_the_scrape_lock(self):
        workflow = (ROOT / ".github" / "workflows" / "rebuild-page.yml").read_text(encoding="utf-8")
        scrape = (ROOT / ".github" / "workflows" / "scrape.yml").read_text(encoding="utf-8")
        self.assertIn("group: scrape-${{ github.ref }}", workflow)
        self.assertIn("group: scrape-${{ github.ref }}", scrape)
        self.assertIn("git add sale_items_chart.html\n", workflow)
        self.assertIn("git pull --rebase origin main", workflow)
        self.assertIn("python rebuild_page.py", workflow)
        for forbidden in ("scraper.py", "chrome", "Chrome", "SMTP", "ALERTS_", "NOTIFICATION_", "secrets."):
            self.assertNotIn(forbidden, workflow)
        # The scrape commits the inputs, without failing when they were never created.
        self.assertIn("git add -A -- report_inputs.json", scrape)
        self.assertIn("[ -e report_inputs.json ] || git ls-files --error-unmatch report_inputs.json", scrape)

    def test_rebuild_never_imports_the_scraper_or_mailers(self):
        script = "import sys, rebuild_page; rebuild_page.load_report_inputs; print(sorted(m for m in ('scraper', 'notify', 'alerts_delivery', 'selenium') if m in sys.modules))"
        out = subprocess.run(["python", "-c", script], cwd=ROOT, capture_output=True, text=True, check=True)
        self.assertEqual(out.stdout.strip(), "[]")


if __name__ == "__main__":
    unittest.main()
