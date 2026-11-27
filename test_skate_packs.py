"""Packs at the custom Skate scrapers (2026-11-12): Tactics, Skate Warehouse, Zumiez."""

import unittest
from unittest import mock

from stores import skatewarehouse as sw
from stores import tactics, zumiez


class SkateBackpacksLabelTests(unittest.TestCase):
    def test_menu_label_preserves_packs_identity_and_query_aliases(self):
        from bs4 import BeautifulSoup
        from previews.publish import CategoryParser
        from query_state import decode_query
        from report import build_report_html

        pack = {"name": "Burton Day Hiker 22L Backpack", "part": "Packs", "store": "Tactics",
                "url": "https://example.test/pack", "price_new": "62.95", "price_old": "90.00"}
        html = build_report_html({"Tactics_Packs": [pack]}, {}, {})
        soup = BeautifulSoup(html, "html.parser")
        self.assertEqual(soup.select_one('#partFilters [data-part="Packs"] .quick-name').text, "Backpacks")
        self.assertEqual(soup.select_one('#partSelect option[value="Packs"]')["data-label"], "Backpacks")
        self.assertIsNotNone(soup.select_one('.deal-row[data-part="Packs"]'))
        parser = CategoryParser()
        parser.feed(html)
        self.assertEqual(parser.categories["Packs"]["label"], "Backpacks")
        self.assertEqual(parser.categories["Packs"]["slug"], "packs")
        for slug in ("pack", "packs", "backpacks"):
            with self.subTest(slug=slug):
                self.assertEqual(decode_query("type=" + slug)["part"], "Packs")


def tactics_card(slug, name, price, off):
    return (f'<div class="browse-grid-item"><a href="/{slug}"><img alt="{name}"></a>'
            f'<span class="browse-grid-item-sale-price">${price}</span>'
            f'<span class="browse-grid-item-discount">({off}% off)</span></div>')


BACKPACKS = "<div class='browse-grid'>" + "".join([
    tactics_card("burton-day-hiker-22l", "Burton Day Hiker 22L Backpack", "62.95", 30),
    tactics_card("deathwish-deathspray-backpack", "Deathwish Deathspray Backpack", "52.95", 20),
    tactics_card("dakine-boot-locker", "DAKINE Boot Locker 69L Bag", "48.95", 30),
]) + "</div>"
DAYPACKS = "<div class='browse-grid'>" + "".join([
    tactics_card("burton-day-hiker-22l", "Burton Day Hiker 22L Backpack", "62.95", 30),  # on both pages
    tactics_card("herschel-little-america", "Herschel Little America Backpack", "76.95", 30),
]) + "</div>"


class SkatePackTests(unittest.TestCase):
    def test_tactics_reads_both_pages_once_and_keeps_only_packs(self):
        pages = {tactics.PACK_URLS[0]: [BACKPACKS], tactics.PACK_URLS[1]: [DAYPACKS]}
        scraper = [s for s in tactics.scrapers() if s.part == "Packs"][0]
        with mock.patch.object(tactics, "collect_sale_pages", side_effect=lambda url: pages[url]), \
                mock.patch.object(tactics, "save_debug_file"):
            items = scraper.scrape()
        self.assertEqual(sorted(i["name"] for i in items),
                         ["Burton Day Hiker 22L Backpack", "Deathwish Deathspray Backpack",
                          "Herschel Little America Backpack"])
        with mock.patch.object(tactics, "collect_sale_pages", return_value=None):
            self.assertIsNone(scraper.scrape())  # a failed page fails the part

    def test_skate_warehouse_backpack_cards(self):
        from test_skatewarehouse_promos import card
        page = "<html>" + card("DKMABP", "Dickies Mike Anderson Pro Backpack", "Backpacks", "44.99", "79.99") + \
            card("DKFULL", "Dickies Lisbon Backpack", "Backpacks", "54.99") + "</html>"
        scraper = [s for s in sw.scrapers() if s.part == "Packs"][0]
        self.assertIn("backpacks.html", scraper.url)
        items = sw.card_items(scraper, page)
        self.assertEqual([(i["name"], i["price_new"], i["price_old"]) for i in items],
                         [("Dickies Mike Anderson Pro Backpack", "44.99", "79.99")])

    def test_zumiez_packs_registered(self):
        scraper = [s for s in zumiez.scrapers() if s.part == "Packs"][0]
        self.assertEqual(scraper.url, zumiez.PACKS_URL)
        self.assertIn("promotion_flag:Sale", scraper.url)


if __name__ == "__main__":
    unittest.main()
