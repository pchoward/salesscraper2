"""Mountain-bike gear stays off Skate (owner, 2026-11-26)."""

import unittest

from stores import protection_brands as brands


class SkateBikeGear(unittest.TestCase):
    def test_demon_bike_helmets_stay_off_skate(self):
        demon = brands.part_of_brand("Demon")
        for title in ("Demon Podium X MIPS® Helmet 710g. MTB NO ORIGINAL PACKAGING/TAGS",
                      "Demon Podium Helmet w/MIPS - NO ORIGINAL PACKAGING",
                      "Demon United Steel Crown Loadout — Helmet, Zero PLUS Shorts + Knee Pads"):
            self.assertIsNone(demon(title), title)
        self.assertEqual(demon("Demon Hyper X D3O Knee Pads"), "Protection")
        self.assertEqual(demon("Demon Skate Helmet"), "Protection")

    def test_mtb_words_stay_off_skate_for_every_brand(self):
        triple8 = brands.part_of_brand("Triple 8")
        self.assertIsNone(triple8("Triple Eight Sweatsaver Mountain Bike Helmet"))
        self.assertIsNone(brands.part_of("G-Form Pro-X3 MTB Knee Guards"))
        self.assertEqual(triple8("Triple 8 Gotham Dual Certified Helmet"), "Protection")


if __name__ == "__main__":
    unittest.main()
