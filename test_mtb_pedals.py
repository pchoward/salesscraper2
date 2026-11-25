"""MTB pedal filters: type, material, thread (owner, 2026-11-25, like Jenson's menu)."""

import unittest

from sports.mtb import facets
from sports.mtb.specs import (PEDAL_CLEATS, PEDAL_CLIP, PEDAL_FLAT, PEDAL_HYBRID, PEDAL_PARTS, PEDAL_ROAD, extract,
                              pedal_material, pedal_thread, pedal_type)

VARIANT = {"title": "Default Title", "option1": "Default Title"}


class PedalTypeTests(unittest.TestCase):
    def test_store_category_says_it(self):
        self.assertEqual(pedal_type("NS Bikes Radiance Pedals", "COMPONENTS/PEDALS/MTB FLAT"), PEDAL_FLAT)
        self.assertEqual(pedal_type("BikeSmart Decoolio Pedals", "COMPONENTS/PEDALS/MTB CLIPLESS"), PEDAL_CLIP)
        self.assertEqual(pedal_type("Eastern Linx MTB Pedals - Blue", "Flat Pedals"), PEDAL_FLAT)
        self.assertEqual(pedal_type("BikeSmart 98A Cleats", "COMPONENTS/PEDALS/CLEATS MTB"), PEDAL_CLEATS)
        self.assertEqual(pedal_type("Race Face Pedal Pin Kit", "Pedal Parts & Accessories"), PEDAL_PARTS)

    def test_title_says_it(self):
        cases = {
            "OneUp Components Clip Pedals": PEDAL_CLIP,
            "Shimano PD-M540 SPD Pedals": PEDAL_CLIP,
            "Shimano SPD-SL Pedals PD-R550": PEDAL_ROAD,
            "Look Keo Classic 3 Pedals": PEDAL_ROAD,
            "Shimano PD-EH500 Pedals": PEDAL_HYBRID,
            "Crankbrothers Double Shot 2 Pedals": PEDAL_HYBRID,
            "Wellgo WPD-95B Pedals - Single Side Clipless Platform Aluminum 9/16\"": PEDAL_HYBRID,
            "Origin8 Retox Platform 9/16` 1 Sealed and 1 Sleeve Black Composite": PEDAL_FLAT,
            "Shimano SM-SH51 SPD Cleat Set": PEDAL_CLEATS,
            "Origin8 Split 6 SPD-SL Cleats Black/Yellow SPD-SL 6° Float": PEDAL_CLEATS,
            "Shimano XTR Enduro Trail Pedal w/(CL-MT001) Cleat PD-M9220": PEDAL_CLIP,
            "Race Face Pedal Rebuild Kit - 2024+ Chester": PEDAL_PARTS,
            "Sunlite ATB Toe Clips and Straps Large Black Plastic": PEDAL_PARTS,
            "BikeSmart MTB Pedals with Clips and Straps": PEDAL_FLAT,
            "Dimension Combo Compe Toe Clip Pedals": PEDAL_FLAT,
            "Redline Lo-Pro Alloy Platform Pedals - Sealed Bearings": PEDAL_FLAT,
        }
        for name, expected in cases.items():
            self.assertEqual(pedal_type(name, "Pedals"), expected, name)

    def test_model_families(self):
        cases = {
            "Crankbrothers Mallet E Pedals": PEDAL_CLIP,
            "Crankbrothers Egg Beater 3 Pedals": PEDAL_CLIP,
            "Shimano PD-M520L Pedals": PEDAL_CLIP,
            "Shimano XTR PD-9120 Pedals": PEDAL_CLIP,
            "HT Components T2 Enduro Race Pedals": PEDAL_CLIP,
            "Garmin Rally XC200 Power Meter Pedal": PEDAL_CLIP,
            "Garmin Rally RS200 Power Meter Pedal": PEDAL_ROAD,
            "Shimano Dura-Ace PD-R9100 Pedals": PEDAL_ROAD,
            "Race Face Chester Pedals": PEDAL_FLAT,
            "Crankbrothers Stamp 7 Pedals": PEDAL_FLAT,
            "Deity Black Kat Pedals": PEDAL_FLAT,
            "HT Components ANS10 Supreme Pedals": PEDAL_FLAT,
            # Shimano's flat XT and Saint pedals share the PD-M numbering.
            "Shimano XT PD-M8040 Pedals": PEDAL_FLAT,
            "Shimano PD-M8140, Deore XT Pedals": PEDAL_FLAT,
            "Shimano Saint PD-MX80 Pedals": PEDAL_FLAT,
            "Shimano Saint PD-M820 SPD Pedals": PEDAL_CLIP,
        }
        for name, expected in cases.items():
            self.assertEqual(pedal_type(name, "Pedals"), expected, name)

    def test_unknown_stays_unknown(self):
        self.assertIsNone(pedal_type("Origin8 Pro Lite Track 9/16` Loose Ball Ano-Silver Alloy", "Pedals"))
        self.assertIsNone(pedal_type("Race Face Pedal and Stem Bundle", "Bundles"))


class PedalDetailTests(unittest.TestCase):
    def test_material(self):
        self.assertEqual(pedal_material("OneUp Components Composite Pedals"), "Composite")
        self.assertEqual(pedal_material("Specialized Supacaz Krypto CNC Alloy Pedals"), "Aluminum")
        self.assertEqual(pedal_material("Race Face Chester Pedals", "Body: Composite nylon. Pins: 8 per side"),
                         "Composite")
        self.assertEqual(pedal_material("Spank Spike Pedals", "Forged aluminum body, chromoly axle"), "Aluminum")
        self.assertIsNone(pedal_material("Spank Spike Pedals", "Aluminum, magnesium or composite: ride what you like"))
        self.assertIsNone(pedal_material("Origin8 Pro Lite Track PC-Black Alloy"))  # two materials named

    def test_thread(self):
        self.assertEqual(pedal_thread("Sunlite MTN Sport II 1/2` Loose Ball"), '1/2"')
        self.assertEqual(pedal_thread("Wellgo A-52 Pedals - Platform Aluminum 9/16\" Black"), '9/16"')
        self.assertIsNone(pedal_thread("Race Face Chester Pedals"))

    def test_extract(self):
        product = {"title": "Chester Pedals", "vendor": "Race Face", "product_type": "Pedals", "tags": [],
                   "body_html": "<p>Body: composite nylon</p>"}
        specs, _ = extract(product, VARIANT, "Pedals")
        self.assertEqual(specs["pedal_type"], [PEDAL_FLAT])
        self.assertEqual(specs["pedal_material"], ["Composite"])
        cleats = {"title": "SM-SH51 SPD Cleat Set", "vendor": "Shimano", "product_type": "Pedals", "tags": [],
                  "body_html": "<p>Aluminum alloy cleat</p>"}
        specs, _ = extract(cleats, VARIANT, "Pedals")
        self.assertEqual(specs, {"pedal_type": [PEDAL_CLEATS]})  # no material or thread for cleats
        specs, _ = extract(dict(product, title="Chester Flat Pedals"), VARIANT, "Brakes")
        self.assertNotIn("pedal_type", specs)  # pedals only

    def test_filters_on_the_pedals_heading(self):
        fields = {field["key"]: field for field in facets.FIELDS}
        for key in ("pedal_type", "pedal_material", "pedal_thread"):
            self.assertEqual(fields[key]["categories"], ("Pedals",))
        self.assertEqual(fields["pedal_type"]["order"][:2], ["Flat", "Clipless (MTB)"])
        params = [field["param"] for field in facets.FIELDS]
        self.assertEqual(len(params), len(set(params)))


if __name__ == "__main__":
    unittest.main()
