"""E-MTB or Regular on MTB bikes and frames (owner, 2026-11-21)."""

import unittest

from sports.mtb import facets
from sports.mtb.specs import EMTB, NOT_EMTB, extract, power


class EmtbTests(unittest.TestCase):
    def test_store_category_or_tags(self):
        for kind in ("Electric Mountain Bikes", "Bikes - E-Full Suspension 29", "Electric Full Suspension Mountain Bike",
                     "BIKES AND FRAMES/BIKES - ELECTRIC/ELECTRIC MOUNTAIN LIGHT WEIGHT/HECKLER SL"):
            self.assertEqual(power("Santa Cruz Heckler SL C R", kind), EMTB, kind)
        self.assertEqual(power("Orbea Something 10", "Bikes", ["e-bike", "trail"]), EMTB)

    def test_names(self):
        for name in ("Polygon Siskiu T7E - E-Mountain Bike", "Polygon Collosus N8XE - E-Mountain Bike",
                     "Polygon Siskiu TE-N Bosch E-Mountain Bike", "Specialized Turbo Levo 4 S-Works Carbon Frameset",
                     "Cannondale Moterra Neo Carbon 2", "Giant Trance X E+ 2", "Trek Fuel EXe 9.7", "Trek Rail+ 9",
                     "YT Decoy Core 3", "Santa Cruz Vala C 90", "Orbea Wild M10", "Specialized Kenevo SL 2"):
            self.assertEqual(power(name, "Bikes"), EMTB, name)

    def test_regular_bikes(self):
        for name in ("Specialized Stumpjumper 15 EVO S-Works Complete Bike - 2026", "Santa Cruz Megatower 2 C GX AXS",
                     "Polygon Siskiu T8 - Mountain Bike (UDH)", "Polygon Collosus DH9 - Downhill Bike",
                     "Ibis Ripmo V3 XT Demo - Large - Purple Complete Bike", "Transition Sentinel Carbon Frame - 2026",
                     "Cannondale Habit 3", "Specialized Epic 9 Expert Complete Bike", "Eastern Alpaka 29 MTB Hardtail Bike"):
            self.assertEqual(power(name, "Bikes"), NOT_EMTB, name)

    def test_battery_in_description(self):
        self.assertEqual(power("Mondraker Crafty R", "Bikes", (), "<p>Bosch Performance CX motor, 750Wh battery</p>"), EMTB)
        self.assertEqual(power("Mondraker Raze R", "Bikes", (), "<p>Weight 14.2 kg</p>"), NOT_EMTB)

    def test_regular_needs_a_bike_category(self):
        self.assertIsNone(power("Unknown frame", ""))
        self.assertEqual(power("Unknown frame", "Trail/AM Frames"), NOT_EMTB)
        self.assertEqual(power("Kona Process X 29", "Full Suspension"), NOT_EMTB)

    def test_accessories_filed_as_frames_get_no_value(self):
        for name in ("RideWrap 2020-2022 Turbo Levo SL Frame Protection", "ODI DH Race Number Plate - Black",
                     "Specialized S-Works Shiv TT Disc Module - FACT 11r Carbon"):
            self.assertIsNone(power(name, "Frame Protection"), name)

    def test_extract_and_facet(self):
        product = {"title": "Polygon Siskiu T7E - E-Mountain Bike", "product_type": "Bikes", "tags": [], "body_html": ""}
        variant = {"title": "M", "option1": "M"}
        self.assertEqual(extract(product, variant, "Bikes")[0].get("power"), [EMTB])
        self.assertNotIn("power", extract(dict(product, title="Maxxis Minion DHF 29x2.5"), variant, "Tires")[0])
        self.assertNotIn("power", extract(dict(product, title="RideWrap Levo Frame Protection"), variant, "Frames")[0])
        field = next(f for f in facets.FIELDS if f["key"] == "power")
        self.assertEqual((field["label"], field["param"], field["categories"]), ("Motor", "mtb_motor", ("Bikes", "Frames")))


if __name__ == "__main__":
    unittest.main()
