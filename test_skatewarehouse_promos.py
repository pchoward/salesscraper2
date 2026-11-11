"""Skate Warehouse promo pages (owner, 2026-11-11: Black November sale)."""

import unittest
from unittest import mock

import sale_watch
from stores import skatewarehouse as sw


def card(code, name, category, now, was=None, href=None):
    msrp = (f'<span class="cattable-wrap-cell-info-price-msrp"><span class="is-crossout">${was}</span>*</span>'
            if was else "")
    href = href or f"https://www.skatewarehouse.com/{code}/descpage-{code}.html?color=BL"
    return (f'<div class="cattable-wrap-cell gtm_impression" data-code="{code}" data-gtm_impression_code="{code}" '
            f'data-gtm_impression_name="{name}" data-gtm_impression_price="{now}" data-gtm_impression_brand="X" '
            f'data-gtm_impression_category="{category}"><div class="cattable-wrap-cell-imgwrap">'
            f'<a href="\n{href}\n"><img src="https://img.skatewarehouse.com/{code}.jpg"></a></div>'
            f'<div class="cattable-wrap-cell-info-price is-sale"><span>${now}</span>{msrp}</div></div>')


PAGE = "<html><body>" + "".join([
    card("OJRH", "OJ Rojers Elite Hardline 101a Wheels", "Wheels", "23.97", "39.95"),
    card("ENWP", "Enjoi Whitey Panda Complete 8.0 x 31.6", "Complete Decks / Popsicle", "77.00", "110.00"),
    card("RLS", "Real Street Cleaner Shorts", "Apparel / Men's", "21.60", "36.00"),
    card("FULL", "Bones STF V5 Wheels", "Wheels", "39.95"),  # no crossed-out price: not a deal
    card("MINI", "Globe Kids Racer Micro Complete 6.5 x 27.25", "Complete Decks", "40.00", "80.00"),
]) + "</body></html>"


class SkateWarehousePromoTests(unittest.TestCase):
    def scraper(self, part):
        return [s for s in sw.scrapers() if s.part == part][0]

    def test_cards_sorted_by_their_own_category(self):
        wheels = sw.card_items(self.scraper("Wheels"), PAGE)
        self.assertEqual([i["name"] for i in wheels], ["OJ Rojers Elite Hardline 101a Wheels"])
        self.assertEqual(wheels[0]["url"], "https://www.skatewarehouse.com/OJRH/descpage-OJRH.html")
        self.assertEqual((wheels[0]["price_new"], wheels[0]["price_old"]), ("23.97", "39.95"))
        completes = sw.card_items(self.scraper("Completes"), PAGE)
        self.assertEqual([i["name"] for i in completes], ["Enjoi Whitey Panda Complete 8.0 x 31.6"])  # mini filtered
        self.assertEqual(sw.card_items(self.scraper("Trucks"), PAGE), [])

    def test_promo_pages_add_to_the_regular_page_and_a_missing_one_is_skipped(self):
        scraper = self.scraper("Wheels")
        regular = [{"url": "https://www.skatewarehouse.com/OJRH/descpage-OJRH.html", "name": "OJ Rojers"}]
        pages = {sw.BLACK_NOVEMBER: PAGE}
        merged = sw.add_promos(scraper, regular, fetch=pages.get)
        self.assertEqual(len(merged), 1)  # same product on both pages is kept once
        self.assertIsNone(sw.add_promos(scraper, None, fetch=pages.get))  # a failed regular page still fails
        self.assertEqual(sw.add_promos(scraper, [], fetch=lambda url: None), [])  # sale over: nothing, no failure

    def test_completes_scraper_registered(self):
        completes = self.scraper("Completes")
        self.assertIn("catpage-BRCOMPLETE", completes.url)
        self.assertIn(sw.BLACK_NOVEMBER, completes.promo_urls)

    def test_sale_watch_sees_black_november(self):
        self.assertTrue(sale_watch.SALE_LINK.search("/Black_November_Sale__Up_To_60_Off/catpage-BNSALE.html"))


if __name__ == "__main__":
    unittest.main()
