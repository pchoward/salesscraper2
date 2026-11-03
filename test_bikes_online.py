"""Bikes Online (issue #165): coarse product types, so parts come from titles;
road/gravel/city/kids bikes and accessories stay out. No network."""

import json
import unittest

import sports
from sports.mtb import stores


def product(id, title, kind, vendor="Polygon", options=("Size",), variants=None):
    return {"id": id, "title": title, "vendor": vendor, "handle": f"p{id}", "product_type": kind, "tags": ["General"],
            "options": [{"name": n} for n in options],
            "variants": variants or [{"id": id * 10, "price": "999.99", "compare_at_price": "1299.99", "available": True, "option1": "M"}]}


FEED = [
    product(1, "Polygon Siskiu T8 - Mountain Bike", "Bikes"),
    product(2, "Polygon Trid ZZ - Slopestyle - Dirt Jump Bike", "Bikes"),
    product(3, "Polygon Strattos S7X - 105 Di2 Carbon Road Bike", "Bikes"),
    product(4, "Polygon Path 3 - Urban City Bike [New]", "Bikes"),
    product(5, "Polygon Relic 24 - Kids Mountain Bike", "Bikes"),
    product(6, "Spank Spoon 800 Bar", "Parts", "Spank"),
    product(7, "5x Entity Inner Tube 27.5x1.5-2.5 Presta Valve 650b Mountain Bike", "Parts", "Entity"),
    product(8, "IXS Trigger AM Helmet - Mips", "Clothing & Protective Gear", "iXS"),
    product(9, "iXS Carve Evo Shorts", "Clothing & Protective Gear", "iXS"),
    product(10, "Entity Chain Whip Tool", "Accessories", "Entity"),
    product(11, "Muc-Off C3 Wet Ceramic Bike Chain Lube - 120ml", "Accessories", "Muc-Off"),
    product(12, "Spank Flare 25 Vibrocore Drop Bar", "Parts", "Spank"),
    product(13, "Linc Beta 50 Carbon Raod Wheelset", "Parts", "Linc"),
    product(14, "Continental Gatorskin Tire - 700 x 28", "Parts", "Continental"),
    product(15, "2x Entity Inner Tube 700x32-48c Presta Valve", "Parts", "Entity"),
    product(16, "Polygon Tambora G8X - Frameset", "Parts"),
    product(17, "Sram Force XG-1271 XPLR 12 Speed Cassette", "Parts", "SRAM"),
    product(18, "Fox 34 Float Performance SC GRIP 29 - OEM", "Parts", "Fox"),
]


class BikesOnlineTests(unittest.TestCase):
    def test_parts_from_titles(self):
        kept = {}
        with sports.MTB.active():
            for scraper in [stores.MtbShopifyScraper(stores.BIKES_ONLINE, part) for part in stores.PARTS]:
                for item in scraper.parse(json.dumps({"products": FEED})):
                    kept[item["name"]] = item["part"]
        self.assertEqual(kept, {
            "Polygon Siskiu T8 - Mountain Bike": "Bikes",
            "Polygon Trid ZZ - Slopestyle - Dirt Jump Bike": "Bikes",
            "Spank Spoon 800 Bar": "Cockpit",
            "5x Entity Inner Tube 27.5x1.5-2.5 Presta Valve 650b Mountain Bike": "Tires",
            "IXS Trigger AM Helmet - Mips": "Protection",
            "Fox 34 Float Performance SC GRIP 29 - OEM": "Forks & Shocks",
        }, "road/gravel parts (700 x 28, 32-48c, XPLR, Tambora, 'Raod') stay out")

    def test_collections(self):
        handles = [url.split("/collections/")[1].split("/")[0] for url in stores.BIKES_ONLINE.sale_jsons]
        self.assertEqual(handles[:3], ["mountain-bikes-sale", "mountain-gear-sale", "sale"])
        self.assertIn("cycling-body-armor", handles, "protection collections follow (2026-11-03)")


if __name__ == "__main__":
    unittest.main()
