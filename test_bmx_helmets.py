"""BMX helmets and knee/shin guards from bike shops (owner, 2026-11-03):
dirt jump / BMX and full-face helmets only; trail, road, kids and snow stay out."""

import unittest

from sports import protection
from sports.bmx import stores
from stores import shopify


class BmxHelmetTests(unittest.TestCase):
    def test_titles(self):
        keep = ("Bell Local BMX Helmet - Matt Yellow", "Fox Racing Flight Dirt Jump Helmet",
                "7 iDP Project 23 ABS Full Face Helmet", "Troy Lee Designs D4 Composite Helmet Omega",
                "Leatt 3DF 5.0 Zip Knee Guard", "7 iDP Transition Knee Pads", "Fuse Stealth Shin Pad")
        drop = ("Giro Manifest Spherical MTB Helmet", "Smith Session MIPS Helmet", "Giro Cielo MIPS Road Helmet",
                "Bell Lil Ripper Child Helmet", "Fox Ranger Gloves", "Smith Holt Snow Helmet",
                "Troy Lee Designs D4 Helmet Replacement Visor")
        for title in keep:
            self.assertEqual(stores.bike_shop_part(title), "Protection", title)
        for title in drop:
            self.assertIsNone(stores.bike_shop_part(title), title)

    def test_shop_types(self):
        for kind in ("Dirt Jump Helmets", "Full Face Helmets", "Knee & Shin Pads", "P23 Helmet", "Bike - Full Face - Zoka"):
            self.assertEqual(stores.bike_shop_type(kind), "Protection", kind)
        for kind in ("MTB Helmets", "HELMETS", "Road Helmets"):
            self.assertEqual(stores.bike_shop_type(kind), shopify.BY_TITLE, kind)

    def test_full_face_models(self):
        for title in ("Project 23 Carbon - 2025 Helmet", "Bell Full-9 Fusion MIPS Helmet", "Fox Rampage Pro Carbon Helmet",
                      "Kali Zoka Helmet", "Fox Proframe RS Helmet"):
            self.assertEqual(protection.helmet_style(title), "Full face", title)

    def test_registered(self):
        self.assertEqual([s.store for s in stores.BIKE_SHOPS],
                         ["Colorado Cyclist", "Cambria", "7iDP", "Troy Lee Designs", "Bikes Online"])
        self.assertTrue(set(stores.BIKE_SHOPS) <= set(stores.STORES))


if __name__ == "__main__":
    unittest.main()
