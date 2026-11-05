"""The shared report CSS/JS is published as content-hashed, cacheable assets.

A page links ``assets/page.<sha256[:12]>.css`` instead of inlining it, so an
unchanged file stays in the browser cache across pages and visits, and a
changed one gets a new URL that no cache can serve stale.
"""

import datetime
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import page
from report import build_report_html

ROOT = Path(__file__).resolve().parent


class AssetNameTests(unittest.TestCase):
    def test_each_name_carries_a_prefix_of_the_file_hash(self):
        for name in page.SHARED_ASSETS:
            content = (ROOT / name).read_bytes()
            digest = hashlib.sha256(content).hexdigest()[:page._VERSION_LENGTH]
            stem, extension = name.split(".", 1)
            self.assertEqual(page.asset_name(name), f"{stem}.{digest}.{extension}")
            self.assertRegex(page.asset_name(name), r"^[a-z]+\.[0-9a-f]{12}\.[a-z]+$")

    def test_the_url_has_the_page_s_folder_prefix(self):
        name = page.asset_name("page.js")
        self.assertEqual(page.asset_url("page.js"), f"assets/{name}")
        self.assertEqual(page.asset_url("page.js", "../"), f"../assets/{name}")
        self.assertEqual(page.asset_url("page.js", "../../"), f"../../assets/{name}")

    def test_a_changed_asset_gets_a_new_name(self):
        original = page.asset_name("page.js")
        with patch.object(page, "_read_asset_bytes", return_value=b"changed"):
            self.assertNotEqual(page.asset_name("page.js"), original)
        # The hash is what changes the name; nothing else in the path does.
        self.assertEqual(original.count("."), 2)


class PageReferenceTests(unittest.TestCase):
    def _html(self, sport=None):
        kwargs = {} if sport is None else {"sport": sport}
        return build_report_html({}, {}, generated_at="2026-11-03T12:00:00+00:00", **kwargs)

    def test_pages_link_the_hashed_assets_and_inline_no_shared_code(self):
        from sports import BMX

        for sport in (None, BMX):
            with self.subTest(sport=getattr(sport, "id", "skate")):
                html = self._html(sport)
                prefix = "../" if sport is not None else ""
                self.assertNotIn("<style>", html)
                self.assertIn(f'<link rel="stylesheet" href="{page.asset_url("page.css", prefix)}">', html)
                self.assertIn(f'<link rel="stylesheet" href="{page.asset_url("mobile.css", prefix)}">', html)
                self.assertIn(f'<script src="{page.asset_url("page.js", prefix)}"></script>', html)
                self.assertNotIn("/* ALERTS_UI_START", html, "page.js is not inlined")
                # The per-page config stays inline, ahead of the shared script.
                self.assertLess(html.index("const CARD_PAGE_SIZE ="), html.index(page.asset_url("page.js", prefix)))

class WriteAssetsTests(unittest.TestCase):
    def test_writes_once_then_reports_no_change(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertTrue(page.write_assets(directory))
            folder = Path(directory) / page.ASSET_DIR
            written = {path.name for path in folder.iterdir()}
            self.assertEqual(written, {page.asset_name(name) for name in page.SHARED_ASSETS} | {page.ASSET_MANIFEST})
            for name in page.SHARED_ASSETS:
                self.assertEqual((folder / page.asset_name(name)).read_bytes(), (ROOT / name).read_bytes())
            self.assertFalse(page.write_assets(directory), "an unchanged build rewrites nothing")
            self.assertFalse(list(folder.glob("*.tmp")))

    def test_recent_unreferenced_versions_are_kept_during_the_grace_period(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory) / page.ASSET_DIR
            folder.mkdir(parents=True)
            old = folder / "page.000000000000.css"
            old.write_text("old", encoding="utf-8")
            page.write_assets(directory)
            self.assertEqual(old.read_text(encoding="utf-8"), "old")
            manifest = json.loads((folder / page.ASSET_MANIFEST).read_text(encoding="utf-8"))
            self.assertIn(old.name, manifest)

    def test_expired_unreferenced_versions_are_deleted(self):
        first = datetime.datetime(2026, 11, 1, tzinfo=datetime.timezone.utc)
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory) / page.ASSET_DIR
            folder.mkdir(parents=True)
            old = folder / "page.000000000000.css"
            old.write_text("old", encoding="utf-8")
            with patch.object(page, "_asset_now", return_value=first):
                page.write_assets(directory)
            with patch.object(page, "_asset_now", return_value=first + datetime.timedelta(days=4)):
                page.write_assets(directory)
            self.assertFalse(old.exists())
            manifest = json.loads((folder / page.ASSET_MANIFEST).read_text(encoding="utf-8"))
            self.assertNotIn(old.name, manifest)
            for name in page.SHARED_ASSETS:
                self.assertTrue((folder / page.asset_name(name)).is_file())

    def test_an_expired_version_referenced_by_a_partial_rebuild_is_kept(self):
        first = datetime.datetime(2026, 11, 1, tzinfo=datetime.timezone.utc)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            folder = root / page.ASSET_DIR
            folder.mkdir(parents=True)
            old = folder / "page.000000000000.js"
            old.write_text("old", encoding="utf-8")
            (root / "sale_items_chart.html").write_text(f'<script src="assets/{old.name}"></script>', encoding="utf-8")
            with patch.object(page, "_asset_now", return_value=first):
                page.write_assets(directory)
            with patch.object(page, "_asset_now", return_value=first + datetime.timedelta(days=4)):
                page.write_assets(directory)
            self.assertEqual(old.read_text(encoding="utf-8"), "old")

    def test_write_page_publishes_assets_before_the_page(self):
        html = build_report_html({}, {}, generated_at="2026-11-03T12:00:00+00:00")
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "sale_items_chart.html"
            self.assertTrue(page.write_page(html, str(target), asset_root=directory))
            self.assertTrue((Path(directory) / page.asset_url("page.js")).is_file())
            self.assertFalse(page.write_page(html, str(target), asset_root=directory))


if __name__ == "__main__":
    unittest.main()
