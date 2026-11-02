"""Colorado Cyclist (issue #165): helmets, tires and wheels only; its sale
bikes duplicate Cambria's. No network."""

import json
import unittest

import sports
from sports.mtb import stores


def product(id, title, vendor, kind, tags=()):
    return {"id": id, "title": title, "vendor": vendor, "handle": f"p{id}", "product_type": kind, "tags": list(tags),
            "options": [{"name": "Size"}],
            "variants": [{"id": id * 10, "price": "39.99", "compare_at_price": "59.95", "available": True, "option1": "M"}]}


FEED = [
    product(1, "Troy Lee Designs A2 MIPS MTB Helmet - Decoy - Black", "Troy Lee Designs", "MTB Helmets"),
    product(2, "Troy Lee Designs D4 Carbon Full Face Helmet - Frames - Black-Gold", "Troy Lee Designs", "Full Face Helmets"),
    product(3, "Bell Local BMX Helmet - Matt Yellow", "Bell", "Dirt Jump Helmets"),
    product(4, "Nutcase Street MIPS Helmet - Dust for Prints Reflective", "Nutcase", "Dirt Jump Helmets"),
    product(5, "Giro Cielo MIPS Road Helmet - Matt Black", "Giro", "Road Helmets"),
    product(6, "Bell Lil Ripper Child Helmet - Sunshine", "Bell", "Kids Helmets"),
    product(7, "Troy Lee Designs D4 Helmet Replacement Visor - Lowrider - Gray", "Troy Lee Designs", "Helmet Parts"),
    product(8, 'Maxxis Minion DHF 29" Folding MTB Tire', "Maxxis", "MTB Tires Folding", tags=['Fwheelsize_29"']),
    product(9, "Continental Grand Prix 5000 700c Tire", "Continental", "Road Tires Folding"),
    product(10, 'DT Swiss XM 1700 29" MTB Wheel - Rear', "DT Swiss", "MTB Wheels"),
    product(11, "Eastern Alpaka 29 MTB Hardtail Bike - Black", "Eastern", "Hardtail"),
]


class ColoradoCyclistTests(unittest.TestCase):
    def test_helmets_tires_wheels_only(self):
        kept = {}
        with sports.MTB.active():
            for scraper in [stores.MtbShopifyScraper(stores.COLORADO, part) for part in stores.PARTS]:
                for item in scraper.parse(json.dumps({"products": FEED})):
                    kept[item["name"]] = item["part"]
        self.assertEqual(kept, {
            "Troy Lee Designs A2 MIPS MTB Helmet - Decoy - Black": "Protection",
            "Troy Lee Designs D4 Carbon Full Face Helmet - Frames - Black-Gold": "Protection",
            "Bell Local BMX Helmet - Matt Yellow": "Protection",
            "Nutcase Street MIPS Helmet - Dust for Prints Reflective": "Protection",
            'Maxxis Minion DHF 29" Folding MTB Tire': "Tires",
            'DT Swiss XM 1700 29" MTB Wheel - Rear': "Wheels",
        }, "road/kids helmets, visors, road tires and Cambria-duplicate bikes stay out")

    def test_collections(self):
        self.assertEqual([url.split("/collections/")[1].split("/")[0] for url in stores.COLORADO.sale_jsons],
                         ["sale-helmets", "sale-tires", "sale-wheels"])

    def test_bmx_parts_still_out(self):
        from sports.mtb.rules import filter_reason
        self.assertIsNotNone(filter_reason("Odyssey BMX Stem", "Cockpit"))
        self.assertIsNone(filter_reason("Bell Local BMX Helmet", "Protection"))


if __name__ == "__main__":
    unittest.main()
