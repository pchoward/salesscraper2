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

    def test_kits_with_shorts_protect_hips(self):
        self.assertIn("Hips & Tailbone", protection.protects("Demon Steel Spine Kit — Zero PLUS Vest + Shorts"))
        self.assertIn("Hips & Tailbone", protection.protects("Demon Park Rat Kit — Padded Shorts + Wrist Guards"))
        self.assertEqual(protection.protects("Demon Crossover Kit — X V7 Shorts + Zero RF Knee Pads"), ["Knees", "Hips & Tailbone"])
        self.assertEqual(protection.protects("Pearl Izumi Padded Liner Shorts"), [])

    def test_each_sport_reads_its_brands(self):
        from sports.bmx import stores as bmx
        from sports.mtb import stores as mtb
        from sports.ski import stores as ski
        self.assertEqual([s.store for s in bmx.BRAND_STORES], ["Triple 8", "187 Killer Pads", "Kali", "Demon", "G-Form", "Zeitbike"])
        self.assertEqual([s.store for s in ski.BRAND_STORES], ["Triple 8", "Bern", "Demon", "Zeitbike"])
        self.assertTrue({"Kali", "Bern", "Smith"} <= {s.store for s in mtb.STORES})
        self.assertEqual(bmx.multisport_part("Triple 8 Saver Series Pad Set 3 Pack"), "Protection")
        self.assertEqual(ski.multisport_part("Halo Snow Standard Helmet"), "Helmets")
        self.assertEqual(ski.multisport_part("Demon Flex-Force Pro Impact Shorts"), "Protection")
        self.assertIsNone(ski.multisport_part("The Certified Sweatsaver Helmet"))



class DriftUnclassifiedTests(unittest.TestCase):
    """The drift check's first unclassified report (2026-11-26)."""

    def test_impact_shorts_and_protection_vests(self):
        from sports.protection import protects
        for name, wanted in (("Burton Impact Short", ["Hips & Tailbone"]),
                             ("Burton Total Impact Short - Women's", ["Hips & Tailbone"]),
                             ("Atomic Live Shield Amid M Protection Vest", ["Back & Spine"]),
                             ("Atomic Live Shield Amid Lite Jr. Vest - Kids'", ["Back & Spine"]),
                             ("Pearl Izumi Short Sleeve Jersey", [])):
            self.assertEqual(protects(name, "Protection"), wanted, name)

    def test_a_helmet_light_mount_is_not_mtb_protection(self):
        from sports.mtb.rules import filter_reason
        self.assertEqual(filter_reason("Gloworm Universal Helmet Mount", "Protection"), "spare or accessory")
        self.assertIsNone(filter_reason("Fox Speedframe Pro Helmet", "Protection"))


if __name__ == "__main__":
    unittest.main()
