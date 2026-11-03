"""Protection filters for BMX, MTB and Ski (owner, 2026-11-03): helmets and
each body part, helmet style and rotational protection, per sport."""

import unittest

import sports
from sports import protection
from sports.ski import evo


class ProtectsTests(unittest.TestCase):
    def check(self, title, expected, product_type=""):
        self.assertEqual(protection.protects(title, product_type), expected, title)

    def test_each_body_part(self):
        self.check("Fuse Alpha Pro Wrist Guard", ["Wrists"])
        self.check("G-Form E-Line Elbow Guards", ["Elbows"])
        self.check("iXS Flow EVO+ Knee Pads", ["Knees"])
        self.check("Fuse Stealth Shin Pad", ["Shins"])
        self.check("Stay Strong Conflict Ankle Support", ["Ankles"])
        self.check("Fox Racing Baseframe Pro Chest Guard", ["Chest & Ribs"])
        self.check("POC Spine VPD Air Vest", ["Back & Spine"])
        self.check("Leatt 3DF AirFit Body Protector", ["Chest & Ribs", "Back & Spine"])
        self.check("Demon Flex-Force X D3O Impact Shorts", ["Hips & Tailbone"])
        self.check("Leatt 5.5 Neck Brace", ["Neck"])
        self.check("Fly Racing Lite Gloves", ["Gloves"])
        self.check("Stay Strong Race DVSN Goggles", ["Goggles"])

    def test_combos_sets_and_spares(self):
        self.check("FUSE DELTA 125 KNEE SHIN ANKLE COMBO PADS", ["Knees", "Shins", "Ankles"])
        self.check("Triple 8 Saver Series Pad Set (3-Pack)", ["Pad Sets"])
        self.check("Shadow Featherweight Helmet Replacement Pads", [], "Helmets")
        self.check("Fly Racing Zone/Focus goggle Replacement Lenses", ["Goggle lenses"])
        self.check("Troy Lee Designs D4 Helmet Replacement Visor", [])

    def test_helmet_style_and_rotational(self):
        self.assertEqual(protection.fields("Troy Lee Designs D4 Carbon Full Face Helmet"),
                         {"protects": ["Helmets"], "helmet_style": ["Full face"]})
        self.assertEqual(protection.fields("Giro Manifest Spherical MTB Helmet"),
                         {"protects": ["Helmets"], "helmet_style": ["Trail / half shell"], "rotational": ["Spherical"]})
        self.assertEqual(protection.fields("Bell Local BMX Helmet")["helmet_style"], ["Dirt jump / BMX"])
        self.assertEqual(protection.fields("Giro Caden MIPS II Helmet", "APPAREL/HELMETS/RECREATION HELMETS")["helmet_style"],
                         ["Road / commuter"])
        self.assertNotIn("helmet_style", protection.fields("Smith Session MIPS Helmet"), "no style is guessed from a model name")

    def test_ski_helmets_category_counts_as_helmets(self):
        found = evo.fields("Helmets", "Giro Ledge FS Mens Mips 2026", "H H M", [], "")
        self.assertEqual((found["protects"], found["helmet_style"], found["rotational"]), (["Helmets"], ["Snow"], ["MIPS"]))
        # A description that mentions gloves or all-mountain skiing changes neither.
        found = evo.fields("Helmets", "Giro Neo Mips Mens Helmet 2026", "H H M", [], "All-mountain comfort; pairs with our gloves")
        self.assertEqual((found["protects"], found["helmet_style"]), (["Helmets"], ["Snow"]))

    def test_every_sport_has_the_fields(self):
        for sport, categories in ((sports.BMX, ("Protection",)), (sports.MTB, ("Protection",)), (sports.SKI, ("Helmets",))):
            import importlib
            fields = {f["key"]: f for f in importlib.import_module(sport.facets).FIELDS}
            for key in protection.FIELD_KEYS:
                self.assertEqual(fields[key]["categories"], categories, (sport.id, key))


if __name__ == "__main__":
    unittest.main()


class MtbProtectionTests(unittest.TestCase):
    """Filling MTB protection (2026-11-03): pads, armor, gloves, goggles, neck braces."""

    def test_rules_keep_protection_and_drop_apparel(self):
        from sports.mtb.rules import filter_reason, title_part
        for title in ("Fox Racing Ranger Gloves", "100% Accuri 2 Goggles", "Leatt 5.5 Neck Brace",
                      "G-Form Pro-X3 Impact Shorts", "Fox Racing Baseframe Pro Chest Guard"):
            self.assertEqual(title_part(title), "Protection", title)
            self.assertIsNone(filter_reason(title, "Protection"), title)
        self.assertEqual(filter_reason("Fox Ranger Shorts", "Protection"), "apparel or unrelated merchandise")
        self.assertIsNotNone(filter_reason("Giro Cielo MIPS Road Helmet", "Protection"))

    def test_cambria_and_colorado_types(self):
        from sports.mtb import stores
        for kind in ("Knee Pads", "Arm Pads", "Knee & Shin Pads", "Ankle & Wrist Supports", "Body Armor Underwear",
                     "Goggles", "Roost Guards", "Neck Braces"):
            self.assertEqual(stores.cambria_part(kind), "Protection", kind)
            self.assertEqual(stores.colorado_part(kind), "Protection", kind)
        for kind in ("Helmet Parts", "Goggle Parts", "MTB Shorts"):
            self.assertIsNone(stores.cambria_part(kind), kind)
        self.assertEqual(stores.cambria_part("Derailleur Parts"), "Drivetrain")
        self.assertEqual(protection.protects("Demon Body Armor Underwear"), ["Hips & Tailbone"])
        self.assertEqual(protection.protects("Fox Racing Arm Pads"), ["Elbows"])
        # The title wins over the store's category.
        self.assertEqual(protection.protects("7 iDP Control Shoulder Support - Left", "Ankle & Wrist Supports"), ["Shoulders"])
        self.assertEqual(protection.protects("7 iDP Control Ankle Protector", "Ankle & Wrist Supports"), ["Ankles"])
        self.assertEqual(protection.protects("Race Face Ambush Leg", "Knee & Shin Pads"), ["Knees", "Shins"])
