"""Christy Sports (Salesforce Commerce): clearance ski gear from listing tiles
(real markup captured by the store probe, 2026-11-02). No network."""

import unittest

import sports
from sports.ski import christy


def tile(pid, name, listed, sale):
    old = (f'<del> <span class="strike-through list"> <span class="value" content="{listed}"> ${listed} </span></span></del>'
           if listed else "")
    return (f'<div class="product-tile on-hover" data-pid="{pid}"> <a href="/product/x-{pid}/{pid}.html?dwvar_{pid}_color=040&amp;cgid=c" '
            f'class="product-tile-image-link"> <img class="product-tile-image tile-image lazyload" src="https://img.example/{pid}.jpg?sw=600&amp;sh=600" '
            f'alt="{name}" title="{name}" /></a> <div class="price"> <span> {old} <span class="sales"> '
            f'<span class="value" content="{sale}"></span> ${sale} </span></span></div></div>')


PAGE = "".join([
    tile("1", "Tecnica Mach Sport HV 85 Ski Boots Womens", "529.99", "318.97"),
    tile("2", "Volkl Mantra 102 Skis", "899.99", "539.97"),
    tile("3", "Look Pivot 15 GW Ski Bindings", "499.99", "349.97"),
    tile("4", "Leki Carbon Ski Poles", "129.99", "77.97"),
    tile("5", "Smith Vantage MIPS Helmet", "300.00", "180.00"),
    tile("6", "Ski Wax Kit", "30.00", "20.00"),
    tile("7", "Full Price Skis", None, "500.00"),
])


class ChristyTests(unittest.TestCase):
    def parse(self, part):
        with sports.SKI.active():
            return christy.ChristyScraper(part).parse(PAGE)

    def test_tiles_become_deals_by_part(self):
        names = {part: [item["name"] for item in self.parse(part)] for part in christy.PARTS}
        self.assertEqual(names, {"Skis": ["Volkl Mantra 102 Skis"], "Boots": ["Tecnica Mach Sport HV 85 Ski Boots Womens"],
                                 "Bindings": ["Look Pivot 15 GW Ski Bindings"], "Poles": ["Leki Carbon Ski Poles"],
                                 "Helmets": ["Smith Vantage MIPS Helmet"], "Protection": []},
                         "wax kits and items without a list price are left out")
        boot = self.parse("Boots")[0]
        self.assertEqual((boot["price_new"], boot["price_old"], boot["url"]),
                         ("318.97", "529.99", "https://www.christysports.com/product/x-1/1.html"))
        self.assertEqual(boot["image"], "https://img.example/1.jpg?sw=600&sh=600")
        # "HV" in the name: Tecnica's high-volume (wide) last.
        self.assertEqual(boot["technical_specs"], {"flex": ["Medium (80–100)"], "last": ["Wide (102 mm and over)"],
                                                   "gender": ["Women"]})
        binding = self.parse("Bindings")[0]
        self.assertEqual(binding["technical_specs"]["din"], ["14 and up"])

    def test_pages_until_empty(self):
        asked, waits = [], []
        pages = {0: PAGE, 24: PAGE.replace('data-pid="', 'data-pid="9'), 48: "<html></html>"}

        def fetch(url):
            asked.append(url)
            return pages.get(int(url.split("start=")[1]))

        self.assertEqual(len(christy.load(fetch=fetch, sleep=waits.append)), 14)
        self.assertEqual(len(asked), 3)
        self.assertTrue(all(wait >= christy.PAGE_DELAY for wait in waits))
        self.assertIsNone(christy.load(fetch=lambda url: None, sleep=waits.append))

    def test_christy_is_a_ski_store(self):
        self.assertIn("Christy Sports", {scraper.name for scraper in sports.SKI.build_scrapers()})


if __name__ == "__main__":
    unittest.main()
