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
    product(12, "Maxxis Rekon Tire - 29 x 2.4, Tubeless, Folding, Black, Dual", "Maxxis", "Tires"),
    product(13, "Schwalbe Big Ben Tire - 27.5 x 2, Clincher, Wire, Black", "Schwalbe", "Tires"),
    product(14, "Schwalbe Marathon Racer Tire - 26 x 1.60, Clincher, Wire", "Schwalbe", "Tires"),
    product(15, "Maxxis Holy Roller Tire - 20 x 2.2, Clincher, Wire, Black", "Maxxis", "Tires"),
    product(16, "Maxxis Re-Fuse Tire - 700 x 32, Tubeless, Folding", "Maxxis", "Tires"),
    product(17, "Stan's Flow MK4 29 Boost Wheelset", "Stan's", "Wheels"),
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
            "Maxxis Rekon Tire - 29 x 2.4, Tubeless, Folding, Black, Dual": "Tires",
            "Stan's Flow MK4 29 Boost Wheelset": "Wheels",
        }, "road/kids helmets, visors, road/commuter/BMX tires and Cambria-duplicate bikes stay out")

    def test_collections(self):
        handles = [url.split("/collections/")[1].split("/")[0] for url in stores.COLORADO.sale_jsons]
        self.assertEqual(handles[:3], ["sale-helmets", "sale-tires", "sale-wheels"])
        self.assertIn("sale-body-armor", handles, "protection collections follow (2026-11-03)")

    def test_bmx_parts_still_out(self):
        from sports.mtb.rules import filter_reason
        self.assertIsNotNone(filter_reason("Odyssey BMX Stem", "Cockpit"))
        self.assertIsNone(filter_reason("Bell Local BMX Helmet", "Protection"))


if __name__ == "__main__":
    unittest.main()
