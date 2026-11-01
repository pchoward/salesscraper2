"""Sport as an engine setting (sports/__init__.py): Skate renders exactly as
before, BMX gets its own categories, branding, search words and folders, and
a BMX run never touches Skate's files or sends email."""

import json
import os
import re
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import page
import rebuild_page
import scraper
import sports

ITEM = {"name": "Cult Gateway Frame 20.75\"", "url": "https://bmx.example/cult-gateway", "price_new": "199.99",
        "price_old": "299.99", "availability": "In stock", "part": "Frames & Forks", "store": "Albe's BMX"}
HUB = {"name": "Odyssey Clutch Freecoaster Hub", "url": "https://bmx.example/clutch", "price_new": "150.00",
       "price_old": "190.00", "availability": "In stock", "part": "Wheel Parts", "store": "Albe's BMX"}
DATA = {"Albes_Frames": [ITEM], "Albes_WheelParts": [HUB]}


def render(sport=None, data=None):
    from report import build_report_html
    return build_report_html(data or DATA, {}, {}, set(), generated_at="2026-11-01T12:00:00+00:00",
                             **({} if sport is None else {"sport": sport}))


class SportSettingsTests(unittest.TestCase):
    def test_skate_is_the_default_and_keeps_its_files_where_they_are(self):
        self.assertIs(sports.get(), sports.SKATE)
        self.assertEqual(sports.SKATE.data_path(), sports.ROOT)
        self.assertEqual(sports.SKATE.page_file(), sports.ROOT / "sale_items_chart.html")
        self.assertTrue(sports.SKATE.delivery)
        with self.assertRaises(KeyError):
            sports.get("curling")

    def test_bmx_settings(self):
        bmx = sports.get("bmx")
        self.assertFalse(bmx.delivery, "no email or alerts until BMX is opted in")
        self.assertFalse(bmx.product_details)
        self.assertIn("Wheel Parts", bmx.parts)
        aliases = json.loads(bmx.aliases_file().read_text(encoding="utf-8"))
        self.assertEqual(set(aliases["categories"]), set(bmx.parts), "every chip has search words, and only chips")
        for words in ("valve caps", "spokes", "nipples", "hubs"):
            self.assertIn(words, aliases["categories"]["Wheel Parts"], "wheel parts grouped like Circuit BMX")
        self.assertIn("fc", aliases["models"]["Freecoaster"])


class RenderTests(unittest.TestCase):
    def test_skate_page_is_unchanged_by_the_setting(self):
        data = {"Shop_Decks": [{**ITEM, "part": "Decks", "name": "Baker Deck 8.25", "store": "Shop"}]}
        default = render(data=data)
        self.assertEqual(default, render(sports.SKATE, data=data))
        self.assertNotIn("const SPORT_SETTINGS =", default)
        self.assertIn("<title>SkateDeals |", default)
        self.assertIn('bridge.src="navigation/skate-bridge.js"', default)

    def test_bmx_page_has_its_own_chips_branding_and_vocabulary(self):
        html = render(sports.BMX)
        self.assertIn("<title>ShredDeals BMX |", html)
        settings = json.loads(re.search(r"const SPORT_SETTINGS = (\{.*?\});", html).group(1))
        self.assertEqual(settings["defaultPart"], "all")
        self.assertEqual(settings["parts"], list(sports.BMX.parts))
        self.assertTrue('data-part="all" data-count="2" aria-pressed="true"' in html, "opens on every category")
        for part in ("Frames &amp; Forks", "Wheel Parts"):
            self.assertTrue(f'data-part="{part}" data-count="1" aria-pressed="false"' in html, part)
        self.assertNotIn('data-part="Decks"', html)
        self.assertIn("freecoaster", html.lower(), "BMX aliases are inlined")
        self.assertNotIn("Gravity Pro", html)
        self.assertIn("Deals from Albe&#x27;s BMX.", html)
        self.assertIn('bridge.src="../navigation/skate-bridge.js"', html, "bmx/ page reaches shared assets")


SKATE_DATA = {"Shop_Decks": [{"name": "Baker Brand Logo Deck 8.25", "url": "https://skate.example/baker", "price_new": "49.99",
                               "price_old": "69.99", "availability": "In stock", "part": "Decks", "store": "Shop"}]}


def no_delivery(*args, **kwargs):
    raise AssertionError("must not send email or alerts")


def snapshot(folder):
    """Every file under ``folder`` and its bytes."""
    return {str(path.relative_to(folder)): path.read_bytes() for path in sorted(Path(folder).rglob("*")) if path.is_file()}


class RunTests(unittest.TestCase):
    """Runs in a scratch copy of the repository layout, never the real data."""

    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root)
        for sport in sports.SPORTS.values():
            target = self.root / sport.aliases
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(sport.aliases_file(), target)
        self.cwd = os.getcwd()
        self.addCleanup(os.chdir, self.cwd)
        patcher = mock.patch.object(sports, "ROOT", self.root)
        patcher.start()
        self.addCleanup(patcher.stop)

    def run_sport(self, sport_id, data, delivery=no_delivery):
        os.chdir(self.root)
        with mock.patch.object(scraper, "run_stores", return_value=(json.loads(json.dumps(data)), set())), \
             mock.patch.object(scraper, "build_scrapers", return_value=[]), \
             mock.patch.object(scraper, "send_admin_warnings", delivery), \
             mock.patch.object(scraper, "send_digest", delivery), \
             mock.patch.object(scraper, "send_notifications", delivery), \
             mock.patch.object(scraper, "fill_wheelbases", lambda *args, **kwargs: None), \
             mock.patch.dict(os.environ, {"NOTIFICATION_ENGINE_ENABLED": ""}):
            scraper.main(["--sport", sport_id] if sport_id else [])

    def test_a_bmx_run_writes_its_own_catalog_and_page_and_sends_nothing(self):
        self.run_sport("bmx", DATA)
        data = self.root / "catalogs/bmx"
        for name in ("previous_data.json", "price_history.json", "scrape_health.json", "report_inputs.json"):
            self.assertTrue((data / name).exists(), name)
        page_file = self.root / "bmx/sale_items_chart.html"
        self.assertIn("ShredDeals BMX", page_file.read_text(encoding="utf-8"))
        self.assertTrue((self.root / "bmx/history.json").exists())
        self.assertFalse((self.root / "previous_data.json").exists(), "nothing written at Skate's root")
        self.assertEqual(Path.cwd(), self.root, "the run puts the working folder back")

        page_file.unlink()
        rebuild_page.main(["--sport", "bmx"])
        self.assertIn("ShredDeals BMX", page_file.read_text(encoding="utf-8"))

    def test_catalogs_never_leak_between_sports(self):
        import filters

        sent = []
        self.run_sport(None, SKATE_DATA, delivery=lambda *args, **kwargs: sent.append(args))
        skate_files = {name: body for name, body in snapshot(self.root).items() if "/" not in name}
        self.assertIn("previous_data.json", skate_files)
        self.assertIn("sale_items_chart.html", skate_files)

        self.run_sport("bmx", DATA)
        self.assertIsNone(filters._SPORT_RULES, "Skate's rules are back after a BMX run")
        after_bmx = snapshot(self.root)
        for name, body in skate_files.items():
            self.assertEqual(after_bmx[name], body, f"BMX run changed Skate's {name}")
        bmx_files = {name: body for name, body in after_bmx.items() if name.startswith(("catalogs/bmx/", "bmx/"))}

        sent.clear()
        self.run_sport("ski", {})
        self.run_sport(None, SKATE_DATA, delivery=lambda *args, **kwargs: sent.append(args))
        final = snapshot(self.root)
        for name, body in bmx_files.items():
            self.assertEqual(final[name], body, f"Skate or Ski run changed BMX's {name}")

        bmx_urls = {item["url"] for items in DATA.values() for item in items}
        skate_urls = {item["url"] for items in SKATE_DATA.values() for item in items}
        for folder, own, other in ((self.root, skate_urls, bmx_urls), (self.root / "catalogs/bmx", bmx_urls, skate_urls)):
            for name in ("previous_data.json", "price_history.json"):
                text = (folder / name).read_text(encoding="utf-8")
                self.assertFalse(any(url in text for url in other), f"{folder}/{name} holds another sport's listings")
                self.assertTrue(any(url in text for url in own), f"{folder}/{name}")
        for page_name, other in (("sale_items_chart.html", bmx_urls), ("bmx/sale_items_chart.html", skate_urls)):
            text = (self.root / page_name).read_text(encoding="utf-8")
            self.assertFalse(any(url in text for url in other), f"{page_name} shows another sport's listings")
        self.assertIn("Deals from Albe&#x27;s BMX.", (self.root / "bmx/sale_items_chart.html").read_text(encoding="utf-8"))
        self.assertTrue((self.root / "catalogs/ski/previous_data.json").exists())
        self.assertTrue(sent, "Skate still delivers (patched here)")

    def test_skate_rules_never_see_bmx_listings_and_vice_versa(self):
        import filters

        frame = ("Cult Gateway Frame", "Frames & Forks")
        self.assertIsNotNone(filters.filter_reason(*frame), "Skate has no Frames & Forks")
        with sports.BMX.active():
            self.assertIsNone(filters.filter_reason(*frame))
            self.assertIsNotNone(filters.filter_reason("Baker Deck 8.25", "Decks"))
        self.assertIsNone(filters._SPORT_RULES)

    def test_scraper_options(self):
        self.assertEqual(scraper.parse_args([]).sport, "skate")
        args = scraper.parse_args(["--sport", "bmx", "--email-dry-run"])
        self.assertEqual((args.sport, args.email_dry_run), ("bmx", True))
        self.assertEqual(set(sports.SPORTS), {"skate", "ski", "mtb", "bmx"})


class AlbesTests(unittest.TestCase):
    def test_sale_feed_maps_to_bmx_categories(self):
        from sports.bmx import stores

        feed = {"products": [
            {"title": "Gateway Frame", "vendor": "Cult", "handle": "gateway", "product_type": "FRAMES",
             "variants": [{"id": 1, "price": "199.99", "compare_at_price": "299.99"}]},
            {"title": "Clutch Freecoaster Hub", "vendor": "Odyssey", "handle": "clutch", "product_type": "Hubs",
             "variants": [{"id": 2, "price": "150.00", "compare_at_price": "190.00"}]},
            {"title": "Team Tee", "vendor": "Cult", "handle": "tee", "product_type": "Hubs",
             "variants": [{"id": 3, "price": "10", "compare_at_price": "20"}]},
            {"title": "Bars", "vendor": "S&M", "handle": "bars", "product_type": "Bars",
             "variants": [{"id": 4, "price": "80", "compare_at_price": None}]},
            {"title": "Gift Card", "vendor": "Albes", "handle": "gift", "product_type": "Gift Card",
             "variants": [{"id": 5, "price": "8", "compare_at_price": "10"}]},
        ]}
        kept = {}
        with sports.BMX.active():
            for store_scraper in stores.scrapers():
                for item in store_scraper.parse(json.dumps(feed)):
                    kept[item["name"]] = item["part"]
        self.assertEqual(kept, {"Cult Gateway Frame": "Frames & Forks", "Odyssey Clutch Freecoaster Hub": "Wheel Parts"})
        self.assertEqual(stores.ALBES.sale_json, "https://www.albes.com/collections/bmx-sale-bikes-parts/products.json")
        self.assertEqual(sports.BMX.build_scrapers()[0].shop, stores.ALBES)


if __name__ == "__main__":
    unittest.main()
