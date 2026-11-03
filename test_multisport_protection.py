"""Multisport protection brands (owner, 2026-11-03): Triple 8, 187, Kali,
Bern, Demon, G-Form... each piece goes to the sports it suits. No network."""

import unittest

from sports import protection


class SuitsTests(unittest.TestCase):
    def test_sport_routing(self):
        cases = {
            ("Halo Snow Standard Helmet", "Helmets"): {"ski"},
            ("The Certified Sweatsaver Helmet", ""): {"bmx", "mtb"},
            ("Major MIPS Bike Helmet (Barn Deal)", "Helmets,"): {"bmx", "mtb"},
            ("Hendrix MIPS Winter Helmet (Barn Deal)", "Helmets,"): {"ski"},
            ("Demon Flex-Force Pro Impact Shorts", "SKI/SNOW"): {"bmx", "mtb", "ski"},
            ("Demon Flexmeter Wrist Guard", "Sale"): {"bmx", "mtb", "ski"},
            ("Triple 8 Bumsaver Hip Pads", ""): {"bmx", "mtb", "ski"},
            ("Demon Hyper Knee D3O V3", "Sale"): {"bmx", "mtb"},
            ("Elite 2 Baseball Batter's Elbow Guard", ""): set(),
            ("Catalyst Liner & Cheek Pad Set", "Moto-Parts"): set(),
            ("Kali Logo Tee", ""): set(),
        }
        for (title, kind), expected in cases.items():
            self.assertEqual({s for s in ("bmx", "mtb", "ski") if protection.suits(s, title, kind)}, expected, title)

    def test_each_sport_reads_its_brands(self):
        from sports.bmx import stores as bmx
        from sports.mtb import stores as mtb
        from sports.ski import stores as ski
        self.assertEqual([s.store for s in bmx.BRAND_STORES], ["Triple 8", "187 Killer Pads", "Kali", "Bern", "Demon", "G-Form"])
        self.assertEqual([s.store for s in ski.BRAND_STORES], ["Triple 8", "Bern", "Demon"])
        self.assertTrue({"Kali", "Bern", "Smith"} <= {s.store for s in mtb.STORES})
        self.assertEqual(bmx.multisport_part("Triple 8 Saver Series Pad Set 3 Pack"), "Protection")
        self.assertEqual(ski.multisport_part("Halo Snow Standard Helmet"), "Helmets")
        self.assertEqual(ski.multisport_part("Demon Flex-Force Pro Impact Shorts"), "Protection")
        self.assertIsNone(ski.multisport_part("The Certified Sweatsaver Helmet"))


if __name__ == "__main__":
    unittest.main()
