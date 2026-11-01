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
        self.assertIs(settings["alerts"], False, "the page can hide alert buttons for BMX")
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
            for store_scraper in stores.shopify.scrapers_for(stores.ALBES, stores.PARTS):
                for item in store_scraper.parse(json.dumps(feed)):
                    kept[item["name"]] = item["part"]
        self.assertEqual(kept, {"Cult Gateway Frame": "Frames & Forks", "Odyssey Clutch Freecoaster Hub": "Wheel Parts"})
        self.assertEqual(stores.ALBES.sale_json, "https://www.albes.com/collections/bmx-sale-bikes-parts/products.json")
        self.assertEqual(sports.BMX.build_scrapers()[0].shop, stores.ALBES)


class BmxBrandTests(unittest.TestCase):
    FEED = {"products": [
        {"title": "Eastern Cobra Bike", "vendor": "Eastern Bikes", "handle": "cobra", "product_type": "BMX BIKES",
         "variants": [{"id": 1, "price": "329.95", "compare_at_price": "379.95"}]},
        {"title": "OEM 16\" Wheelset", "vendor": "FIT", "handle": "fit-wheels", "product_type": "Wheels",
         "variants": [{"id": 2, "price": "74.95", "compare_at_price": "129.99"}]},
        {"title": "DefendR Fork", "vendor": "Black Ops", "handle": "defendr", "product_type": "Forks",
         "variants": [{"id": 3, "price": "79.95", "compare_at_price": "159.99"}]},
        {"title": "Shop Tool", "vendor": "Albes", "handle": "tool", "product_type": "Tools",
         "variants": [{"id": 4, "price": "5", "compare_at_price": "10"}]},
        {"title": "Sold Out Bars", "vendor": "S&M", "handle": "bars", "product_type": "Bars",
         "variants": [{"id": 5, "price": "50", "compare_at_price": "90", "available": False}]},
    ]}

    def items(self):
        from sports.bmx import stores

        kept = []
        with sports.BMX.active():
            for store_scraper in stores.shopify.scrapers_for(stores.ALBES, stores.PARTS):
                kept += store_scraper.parse(json.dumps(self.FEED))
        return {item["name"]: item.get("brand") for item in kept}

    def test_brand_comes_from_the_vendor_with_one_spelling(self):
        self.assertEqual(self.items(), {"Eastern Cobra Bike": "Eastern", "Fit OEM 16\" Wheelset": "Fit",
                                        "Black Ops DefendR Fork": "Black Ops"})

    def test_page_brand_filter_uses_it(self):
        data = {"Albes_Forks": [{"name": "Black Ops DefendR Fork", "url": "https://bmx.example/defendr", "price_new": "79.95",
                                 "price_old": "159.99", "part": "Frames & Forks", "store": "Albe's BMX", "brand": "Black Ops"}]}
        html = render(sports.BMX, data=data)
        self.assertIn('data-brand="Black Ops"', html)
        self.assertNotIn('data-brand="Black"', html)

    def test_feed_summary_says_what_was_skipped(self):
        from sports.bmx import stores
        from stores import shopify

        summary = shopify.feed_summary(stores.ALBES, self.FEED["products"])
        self.assertEqual((summary["products"], summary["marked_down"], summary["sold_out"]), (5, 4, 1))
        self.assertEqual(summary["unmapped_types"], [("Tools", 1)])

    def test_skate_titles_are_unchanged(self):
        from stores import shopify

        product = {"title": "Formula Four Classic 54mm", "vendor": "Spitfire"}
        self.assertEqual(shopify.title_with_brand(product), "Spitfire Formula Four Classic 54mm")


class BmxSpecTests(unittest.TestCase):
    def test_wheel_size_is_read_not_guessed(self):
        from sports.bmx.specs import wheel_size

        cases = {'Fit 29" Rim': "29", 'FIT OEM 16" WHEELSET': "16", 'Black Ops DefendR 24" Fork': "24",
                 "Cult 20 inch Front Wheel": "20", 'Haro Klunkerson 27.5" Bike': "27.5", "Odyssey Path 20x2.4 Tire": "20",
                 'Kink Gap 20.5" TT Frame': None, 'Primo 12" and 14" Wheels': None, "Cult Race Stem": None}
        for title, size in cases.items():
            self.assertEqual(wheel_size(title), size, title)
        self.assertEqual(wheel_size("Cult Frame", ['Wsize_20"', "frames"]), "20", "a store tag wins")

    def test_kind_and_vague_types_from_the_title(self):
        from sports.bmx import stores

        feed = {"products": [
            {"title": "Clutch Freecoaster Hub", "vendor": "Odyssey", "handle": "clutch", "product_type": "Hubs",
             "tags": ['Wsize_20"'], "variants": [{"id": 1, "price": "150", "compare_at_price": "190"}]},
            {"title": "Pro Front Wheel", "vendor": "Merritt", "handle": "front", "product_type": "Wheels",
             "variants": [{"id": 2, "price": "120", "compare_at_price": "160"}]},
            {"title": "Graduate Pegs", "vendor": "Odyssey", "handle": "pegs", "product_type": "PARTS",
             "variants": [{"id": 3, "price": "20", "compare_at_price": "30"}]},
            {"title": "Mystery Thing", "vendor": "Odyssey", "handle": "thing", "product_type": "",
             "variants": [{"id": 4, "price": "5", "compare_at_price": "10"}]},
        ]}
        kept = {}
        with sports.BMX.active():
            for store_scraper in stores.shopify.scrapers_for(stores.ALBES, stores.PARTS):
                for item in store_scraper.parse(json.dumps(feed)):
                    kept[item["name"]] = (item["part"], item.get("kind"), item.get("wheel_size"))
        self.assertEqual(kept, {
            "Odyssey Clutch Freecoaster Hub": ("Wheel Parts", "Hubs", "20"),
            "Merritt Pro Front Wheel": ("Wheels", "Wheels", None),
            "Odyssey Graduate Pegs": ("Wheel Parts", "Pegs", None),
        })

    def test_catalog_entries_carry_the_fields_for_the_filters(self):
        data = {"Albes_Hubs": [{"name": "Odyssey Clutch Hub", "url": "https://bmx.example/clutch", "price_new": "150",
                                "price_old": "190", "part": "Wheel Parts", "store": "Albe's BMX", "kind": "Hubs",
                                "wheel_size": "20"}]}
        html = render(sports.BMX, data=data)
        catalog = json.loads(html.split('id="catalogJson"', 1)[1].split(">", 1)[1].split("</script>", 1)[0])
        entry = next(iter(catalog["items"].values()))
        self.assertEqual((entry["kind"], entry["wheel_size"]), ("Hubs", "20"))


class CircuitTests(unittest.TestCase):
    def test_second_store_reads_unknown_types_by_title(self):
        from sports.bmx import stores

        self.assertEqual(stores.CIRCUIT.sale_json, "https://www.circuitbmx.com/collections/sale-items/products.json")
        self.assertIn("Circuit BMX", {scraper.shop.store for scraper in sports.BMX.build_scrapers()})
        feed = {"products": [
            {"title": "Plastic Pegs 4.5in", "vendor": "Odyssey", "handle": "pegs", "product_type": "Small Parts",
             "variants": [{"id": 1, "price": "20", "compare_at_price": "30"}]},
            {"title": "Logo Hoodie", "vendor": "Circuit BMX", "handle": "hoodie", "product_type": "Softgoods",
             "variants": [{"id": 2, "price": "40", "compare_at_price": "60"}]},
            {"title": "Pivotal Seat", "vendor": "Cult", "handle": "seat", "product_type": "Seats",
             "variants": [{"id": 3, "price": "25", "compare_at_price": "35"}]},
        ]}
        kept = {}
        with sports.BMX.active():
            for store_scraper in stores.shopify.scrapers_for(stores.CIRCUIT, stores.PARTS):
                for item in store_scraper.parse(json.dumps(feed)):
                    kept[item["name"]] = (item["part"], item.get("kind"), item["store"])
        self.assertEqual(kept, {"Odyssey Plastic Pegs 4.5in": ("Wheel Parts", "Pegs", "Circuit BMX"),
                                "Cult Pivotal Seat": ("Seating", "Seats", "Circuit BMX")})

    def test_skate_stores_still_skip_unknown_types(self):
        from stores import shopify

        store = shopify.ShopifyStore("Shop", "Shop", "https://shop.example")
        self.assertIsNone(shopify.part_for(store, "Mystery", "Baker Deck 8.25"))


class MoreBmxStoresTests(unittest.TestCase):
    def test_four_stores_with_their_sale_collections(self):
        from sports.bmx import stores

        self.assertEqual({scraper.shop.store for scraper in sports.BMX.build_scrapers()},
                         {"Albe's BMX", "Circuit BMX", "Powers BMX", "Source BMX US"})
        self.assertEqual(stores.POWERS.sale_jsons, [
            "https://www.powersbmx.com/collections/clearance/products.json",
            "https://www.powersbmx.com/collections/black-friday-deals/products.json"])
        self.assertEqual([url.split("/collections/")[1].split("/")[0] for url in stores.SOURCE_US.sale_jsons],
                         ["bmx-parts-sale", "bmx-wheel-sale", "bmx-frame-sale", "bmx-bike-sale"])

    def test_several_collections_are_merged_and_one_missing_is_skipped(self):
        from stores import shopify

        store = shopify.ShopifyStore("S", "S", "https://s.example", collection="a", more_collections=("b", "gone"))
        pages = {"https://s.example/collections/a/products.json": [{"id": 1}, {"id": 2}],
                 "https://s.example/collections/b/products.json": [{"id": 2}, {"id": 3}]}

        def fetch(url):
            base = url.split("?")[0]
            if base not in pages:
                return None
            return {"products": pages[base] if "page=1" in url else []}

        products = shopify.load_sale_products(store, fetch=fetch, sleep=lambda seconds: None)
        self.assertEqual([product["id"] for product in products], [1, 2, 3])
        single = shopify.ShopifyStore("T", "T", "https://s.example", collection="gone")
        self.assertIsNone(shopify.load_sale_products(single, fetch=fetch, sleep=lambda seconds: None),
                          "a store with one collection still fails when it can't be read")

    def test_source_scratch_and_dent_is_a_condition_not_a_brand(self):
        from sports.bmx import stores

        feed = {"products": [
            {"title": "Radio Raceline Xenon Pro Frame", "vendor": "Scratch & Dent", "handle": "xenon",
             "product_type": "BMX Race Frames", "tags": ["Scratch & Dent", 'Wheel Size: 20"'],
             "variants": [{"id": 1, "price": "199", "compare_at_price": "349"}]},
            {"title": "Profile Mini Rear Hub", "vendor": "Profile", "handle": "mini", "product_type": "BMX Rear Hubs",
             "variants": [{"id": 2, "price": "150", "compare_at_price": "190"}]},
            {"title": "Stay Strong Race Gloves", "vendor": "Stay Strong", "handle": "gloves", "product_type": "BMX Gloves",
             "variants": [{"id": 3, "price": "15", "compare_at_price": "25"}]},
        ]}
        kept = {}
        with sports.BMX.active():
            for store_scraper in stores.shopify.scrapers_for(stores.SOURCE_US, stores.PARTS):
                for item in store_scraper.parse(json.dumps(feed)):
                    kept[item["name"]] = (item["part"], item.get("kind"), item.get("brand"), item.get("condition"))
        self.assertEqual(kept, {
            "Radio Raceline Xenon Pro Frame": ("Frames & Forks", "Frames", None, "Scratch & Dent"),
            "Profile Mini Rear Hub": ("Wheel Parts", "Hubs", "Profile", None),
        })


class TitleFallbackTests(unittest.TestCase):
    def test_brand_words_never_make_a_bike(self):
        from sports.bmx import stores

        feed = {"products": [
            {"title": "Wing Padset", "vendor": "SE BIKES", "handle": "padset", "product_type": "Pad Sets",
             "variants": [{"id": 1, "price": "15.99", "compare_at_price": "25.99"}]},
            {"title": "SE Racing Keychain", "vendor": "SE Bikes", "handle": "key", "product_type": "Apparel",
             "variants": [{"id": 2, "price": "5.99", "compare_at_price": "9.99"}]},
            {"title": "Bike Life Number plate", "vendor": "SE Bikes", "handle": "plate", "product_type": "number plate",
             "variants": [{"id": 3, "price": "19.99", "compare_at_price": "28.99"}]},
            {"title": "Arrow Rear Hub Female Bolt Set", "vendor": "We The People", "handle": "bolts", "product_type": "",
             "variants": [{"id": 4, "price": "9", "compare_at_price": "12"}]},
            {"title": "Mini Race Bike", "vendor": "SE Bikes", "handle": "mini", "product_type": "Race BMX - Mini",
             "variants": [{"id": 5, "price": "299", "compare_at_price": "399"}]},
        ]}
        kept = {}
        with sports.BMX.active():
            for store_scraper in stores.shopify.scrapers_for(stores.POWERS, stores.PARTS):
                for item in store_scraper.parse(json.dumps(feed)):
                    kept[item["name"]] = (item["part"], item.get("kind"))
        self.assertEqual(kept, {"We The People Arrow Rear Hub Female Bolt Set": ("Wheel Parts", "Hubs"),
                                "SE Bikes Mini Race Bike": ("Bikes", "Complete Bikes")})

    def test_whole_bikes_without_a_type_are_still_bikes(self):
        from sports.bmx import stores

        for title in ("Haro Skwad 2 Electric Bike", "Kuwahara KW-29 Bike", "Fit Series 22\u201d Wheel Complete Bike 2026",
                      "Radio Cobalt mini Race Bike black/red"):
            self.assertEqual(stores.title_part(title), "Bikes", title)
        for title in ("SE BIKES Wing Padset", "SE BIkes Bike Life Number plate black/white/blue", "SE Bikes SE Racing Keychain"):
            self.assertIsNone(stores.title_part(title), title)
        self.assertEqual(stores.TYPES["complete bike"], "Bikes")


if __name__ == "__main__":
    unittest.main()
