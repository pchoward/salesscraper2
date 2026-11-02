"""The House (Salesforce Commerce): on-sale ski hardgoods from each search
tile's structured data. No network."""

import unittest

import sports
from sports.ski import the_house

PAGE = """
<div class="product" data-pid="11" data-gtmdata="{&quot;name&quot;:&quot;Chronic 101 Skis&quot;,&quot;price&quot;:359.99,&quot;brand&quot;:&quot;Line&quot;,&quot;category&quot;:&quot;ski&quot;,&quot;subcategory&quot;:&quot;ski-equipment&quot;,&quot;dimension20&quot;:&quot;IN_STOCK&quot;,&quot;dimension46&quot;:&quot;park-skis&quot;,&quot;percentOff&quot;:40}"><span data-bg="https://img.example/11_1.jpg?sw=400"></span></div>
<div class="product" data-pid="12" data-gtmdata="{&quot;name&quot;:&quot;T.Rice Pro Snowboard&quot;,&quot;price&quot;:419.99,&quot;brand&quot;:&quot;Lib-Tech&quot;,&quot;category&quot;:&quot;snowboard&quot;,&quot;subcategory&quot;:&quot;snowboards&quot;,&quot;dimension20&quot;:&quot;IN_STOCK&quot;,&quot;percentOff&quot;:40}"></div>
<div class="product" data-pid="13" data-gtmdata="{&quot;name&quot;:&quot;Hawx Prime 100 Womens Ski Boots&quot;,&quot;price&quot;:300,&quot;brand&quot;:&quot;Atomic&quot;,&quot;category&quot;:&quot;ski&quot;,&quot;subcategory&quot;:&quot;ski-equipment&quot;,&quot;dimension20&quot;:&quot;IN_STOCK&quot;,&quot;percentOff&quot;:50}"></div>
<div class="product" data-pid="14" data-gtmdata="{&quot;name&quot;:&quot;Sold Out Skis&quot;,&quot;price&quot;:300,&quot;brand&quot;:&quot;K2&quot;,&quot;category&quot;:&quot;ski&quot;,&quot;subcategory&quot;:&quot;ski-equipment&quot;,&quot;dimension20&quot;:&quot;OUT_OF_STOCK&quot;,&quot;percentOff&quot;:50}"></div>
<div class="product" data-pid="15" data-gtmdata="{&quot;name&quot;:&quot;Full Price Skis&quot;,&quot;price&quot;:300,&quot;brand&quot;:&quot;K2&quot;,&quot;category&quot;:&quot;ski&quot;,&quot;subcategory&quot;:&quot;ski-equipment&quot;,&quot;dimension20&quot;:&quot;IN_STOCK&quot;,&quot;percentOff&quot;:0}"></div>
"""


class TheHouseTests(unittest.TestCase):
    def parse(self, part):
        with sports.SKI.active():
            return the_house.TheHouseScraper(part).parse(PAGE)

    def test_on_sale_in_stock_ski_gear_only(self):
        skis = self.parse("Skis")
        self.assertEqual([item["name"] for item in skis], ["Line Chronic 101 Skis"],
                         "snowboards, sold-out and full-price items are left out")
        ski = skis[0]
        self.assertEqual((ski["url"], ski["price_new"], ski["price_old"], ski["brand"]),
                         ("https://www.the-house.com/11.html", "359.99", "599.98", "Line"))
        self.assertEqual(ski["image"], "https://img.example/11_1.jpg?sw=400")
        self.assertEqual(ski["technical_specs"], {"ski_type": ["Park & Freestyle"]})
        boots = self.parse("Boots")
        self.assertEqual([item["name"] for item in boots], ["Atomic Hawx Prime 100 Womens Ski Boots"])
        self.assertEqual(boots[0]["technical_specs"], {"flex": ["Medium (80–100)"], "gender": ["Women"]})

    def test_pages_are_read_until_empty_and_shared(self):
        asked, waits = [], []
        pages = {0: PAGE, 48: PAGE.replace('data-pid="1', 'data-pid="2'), 96: "<html>no tiles</html>"}

        def fetch(url):
            asked.append(url)
            start = int(url.split("start=")[1].split("&")[0])
            return pages.get(start)

        found = the_house.load(fetch=fetch, sleep=waits.append)
        self.assertEqual(len(found), 10)
        self.assertEqual(len(asked), 3, "stops at the first page without new tiles")
        self.assertTrue(all(wait >= the_house.PAGE_DELAY for wait in waits))
        self.assertIsNone(the_house.load(fetch=lambda url: None, sleep=waits.append), "unreadable first page = failed")

    def test_part_and_price_helpers(self):
        self.assertEqual(the_house.was_price(300, 50), 600.0)
        self.assertIsNone(the_house.was_price(300, 0))
        equipment = {"category": "ski", "subcategory": "ski-equipment"}
        self.assertIsNone(the_house.part_for({"category": "snowboard", "subcategory": "snowboard-boots", "name": "Boots"}))
        self.assertIsNone(the_house.part_for({"category": "ski", "subcategory": "ski-clothing",
                                              "name": "AK Cyclic Gore-Tex Men's Snow Jacket"}), "ski clothing is out")
        self.assertEqual(the_house.part_for(dict(equipment, name="Look Pivot 15 GW Bindings")), "Bindings")
        self.assertEqual(the_house.part_for(dict(equipment, name="Stance 84 Skis w/ M12 GW Bindings")), "Skis")
        self.assertEqual(the_house.part_for(dict(equipment, name="Hawx Prime 100 Ski Boots")), "Boots")
        self.assertEqual(the_house.part_for(dict(equipment, name="Leki Carbon Poles")), "Poles")
        self.assertEqual(the_house.part_for({"category": "snowboard", "subcategory": "helmets", "name": "Smith Helmet"}), "Helmets")
        self.assertIsNone(the_house.part_for(dict(equipment, name="Ski Wax Kit")))

    def test_the_house_is_a_ski_store(self):
        self.assertIn("The House", {scraper.name for scraper in sports.SKI.build_scrapers()})


if __name__ == "__main__":
    unittest.main()
