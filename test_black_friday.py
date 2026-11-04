"""Black Friday coverage (owner, 2026-11-04): new sale collections, every
markdown on the Shopify skate shops, Tactics' deal pages, and the report of
sale sections no scraper reads."""

import json
import os
import tempfile
import unittest

import sale_watch
from stores import exodus, kinetic, shopify, spot, tactics, tgm


class WholeSiteTests(unittest.TestCase):
    def test_skate_shops_read_new_collections_and_whole_catalog(self):
        self.assertIn("https://exodusrideshop.com/collections/black-friday-specials/products.json", exodus.SHOP.sale_jsons)
        self.assertIn("https://exodusrideshop.com/collections/clearance-decks/products.json", exodus.SHOP.sale_jsons)
        self.assertIn("https://skateparkoftampa.com/collections/blacker-friday-deals/products.json", spot.SHOP.sale_jsons)
        self.assertIn("https://tgmskateboards.com/collections/flash-sale/products.json", tgm.SHOP.sale_jsons)
        for shop in (exodus.SHOP, spot.SHOP, tgm.SHOP, kinetic.SHOP):
            self.assertEqual(shop.sale_jsons[-1], shop.base + "/products.json", shop.store)
            self.assertEqual(shop.sale_jsons[0].split("/collections/")[0], shop.base)

    def test_whole_catalog_keeps_only_markdowns_and_dedupes(self):
        shop = shopify.ShopifyStore("T", "T", "https://t.example", whole_site=True)
        deck = {"id": 1, "handle": "deck", "title": "Baker Logo Deck 8.25", "product_type": "Decks", "vendor": "Baker",
                "variants": [{"id": 11, "price": "40.00", "compare_at_price": "60.00", "available": True}]}
        full = {"id": 2, "handle": "full", "title": "Baker Full Price Deck 8.5", "product_type": "Decks", "vendor": "Baker",
                "variants": [{"id": 21, "price": "60.00", "compare_at_price": None, "available": True}]}
        pages = {shop.sale_json: [deck], shop.base + "/products.json": [deck, full]}
        fetch = lambda url: {"products": pages.get(url.split("?")[0], []) if "page=1" in url else []}
        products = shopify.load_sale_products(shop, fetch=fetch, sleep=lambda s: None)
        self.assertEqual([p["id"] for p in products], [1, 2])
        self.assertEqual([p["id"] for p in products if shopify.sale_variants(p)], [1])

    def test_a_big_catalog_is_skipped_not_fatal(self):
        shop = shopify.ShopifyStore("T", "T", "https://t.example", whole_site=True)
        sale = {"id": 1, "handle": "a", "title": "A Deck", "product_type": "Decks",
                "variants": [{"id": 1, "price": "1.00", "compare_at_price": "2.00", "available": True}]}
        def fetch(url):
            if url.startswith(shop.sale_json):
                return {"products": [sale] if "page=1" in url else []}
            return {"products": [dict(sale, id=n) for n in range(shopify.PAGE_LIMIT)]}  # never ends
        products = shopify.load_sale_products(shop, fetch=fetch, sleep=lambda s: None)
        self.assertEqual([p["id"] for p in products], [1])


class TacticsDealTests(unittest.TestCase):
    def test_deal_pages_add_items_whose_title_names_the_part(self):
        card = ('<div class="browse-grid-item"><a href="/{slug}"><img alt="{name}"></a>'
                '<span class="browse-grid-item-sale-price">${price}</span>'
                '<span class="browse-grid-item-discount">40% off</span></div>')
        sale = card.format(slug="baker-deck", name="Baker Brand Logo Skateboard Deck 8.25", price="45.00")
        deals = card.format(slug="spitfire", name="Spitfire Formula Four Classic 54mm 99a Wheels", price="30.00") \
            + card.format(slug="girl-deck", name="Girl OG Skateboard Deck 8.5", price="50.00")
        old = tactics._deal_pages.copy()
        self.addCleanup(lambda: (tactics._deal_pages.clear(), tactics._deal_pages.update(old)))
        tactics._deal_pages.clear()
        tactics._deal_pages.update({url: [deals] for url in tactics.DEAL_URLS})
        original = tactics.collect_sale_pages
        tactics.collect_sale_pages = lambda url, fetch=None: [sale]
        self.addCleanup(setattr, tactics, "collect_sale_pages", original)
        decks = tactics.TacticsScraper("Tactics", "https://www.tactics.com/skateboard-decks/sale", "Decks").scrape()
        self.assertEqual(sorted(i["url"].rsplit("/", 1)[1] for i in decks), ["baker-deck", "girl-deck"])
        wheels = tactics.TacticsScraper("Tactics", "https://www.tactics.com/skateboard-wheels/sale", "Wheels").scrape()
        self.assertIn("spitfire", [i["url"].rsplit("/", 1)[1] for i in wheels])


class SiteSaleCutOverTests(unittest.TestCase):
    def test_wider_coverage_is_not_a_site_wide_sale(self):
        import datetime
        from site_sales import empty_state, record_catalog
        state = empty_state()
        for offset in range(20):
            day = (datetime.date(2026, 10, 14) + datetime.timedelta(days=offset)).isoformat()
            state["daily"][day] = {"SPoT": 40, "Tactics": 150}
        state["daily"]["2026-11-04"] = {"SPoT": 300, "Tactics": 420}
        state = record_catalog(state, {}, today="2026-11-05")
        self.assertIsNone(state["stores"]["SPoT"]["last_sale"])
        self.assertIsNone(state["stores"]["Tactics"]["last_sale"])


class SaleWatchTests(unittest.TestCase):
    def fetch(self, pages):
        return lambda url: pages.get(url)

    def test_new_sale_collections(self):
        listing = {"collections": [{"handle": h, "title": h} for h in (
            "sale", "flash-sale", "blacker-friday-deals", "baker-holiday-2026-complete-collection", "sale-pants",
            "disc-golf-sale", "new-arrivals")]}
        fetch = self.fetch({"https://shop.example/robots.txt": "User-agent: *\nDisallow: /cart",
                            "https://shop.example/collections.json?limit=250": json.dumps(listing)})
        found = sale_watch.shopify_sections("https://shop.example", {"sale"}, fetch)
        self.assertEqual([f["url"].rsplit("/", 1)[1] for f in found], ["flash-sale", "blacker-friday-deals"])

    def test_homepage_deal_links(self):
        html = ('<a href="/limited-time-deals">Pre-BlackFriday Clearance</a><a href="/decks/sale">Sale</a>'
                '<a href="/black-friday">Black Friday</a><a href="/about">About</a>')
        fetch = self.fetch({"https://store.example/robots.txt": "", "https://store.example/": html})
        found = sale_watch.homepage_links("https://store.example/", {"https://store.example/limited-time-deals"}, fetch)
        self.assertEqual([f["url"] for f in found], ["https://store.example/black-friday"])

    def test_report_file_and_summary_never_fail(self):
        folder = tempfile.mkdtemp()
        path, summary = os.path.join(folder, "s.json"), os.path.join(folder, "summary.md")
        original = sale_watch.check
        sale_watch.check = lambda: {"TGM": [{"label": "Flash Sale", "url": "https://tgm/collections/flash-sale"}]}
        self.addCleanup(setattr, sale_watch, "check", original)
        sale_watch.run(path=path, summary=summary)
        self.assertEqual(json.load(open(path))["stores"]["TGM"][0]["label"], "Flash Sale")
        self.assertIn("**TGM**", open(summary).read())
        sale_watch.check = lambda: (_ for _ in ()).throw(RuntimeError("offline"))
        self.assertIsNone(sale_watch.run(path=path, summary=summary))

    def test_scrape_runs_it_for_skate_and_commits_the_file(self):
        from pathlib import Path
        self.assertIn("sale_watch.run()", Path("scraper.py").read_text(encoding="utf-8"))
        workflow = Path(".github/workflows/scrape.yml").read_text(encoding="utf-8")
        self.assertIn("git add sale_sections.json", workflow)
        self.assertIn('SALE_WATCH: "1"', workflow)


if __name__ == "__main__":
    unittest.main()
