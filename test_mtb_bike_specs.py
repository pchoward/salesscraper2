"""Evo-style MTB bike filters (owner, 2026-11-21): suspension, frame
material, wheel size and rear travel, from stated sources only."""

import unittest

from sports.mtb import facets
from sports.mtb.specs import FULL, HARDTAIL, extract

V = {"title": "L", "option1": "L"}


def bike(title, kind="Bikes", tags=(), body="", vendor=""):
    return {"title": title, "product_type": kind, "tags": list(tags), "body_html": body, "vendor": vendor}


def table(**rows):
    return "<table>" + "".join(f"<tr><td>{k.replace('_', ' ')}</td><td>{v}</td></tr>" for k, v in rows.items()) + "</table>"


class BikeSpecTests(unittest.TestCase):
    def test_fanatik_labeled_tags(self):
        product = bike("Ripmo V3 XT Demo - Large - Purple Complete Bike", "AM/Enduro Bikes",
                       ["axlesize:12x148mm Boost", "forktravel:160mm", "material:Carbon", "susptravel:150mm", 'wheelsize:29"'],
                       vendor="Ibis")
        specs = extract(product, V, "Bikes")[0]
        self.assertEqual(specs["wheel_size"], ["29"])
        self.assertEqual(specs["travel_mm"], ["150"])  # rear, not the fork's 160
        self.assertEqual(specs["frame_material"], ["Carbon"])
        self.assertEqual(specs["suspension"], [FULL])
        self.assertEqual(specs["axle"], ["12x148mm"])

    def test_mikes_spec_table(self):
        body = table(Frame="Carbon C frame, 150mm travel", Fork="FOX 36 Performance, 160mm",
                     Rear_Shock="RockShox Deluxe Select+, 150mm Travel", Tires="Maxxis Minion DHF 29 x 2.5")
        specs = extract(bike("Vala C 90", "BIKES AND FRAMES/BIKES - ELECTRIC/ELECTRIC MOUNTAIN FULL POWER/VALA",
                             body=body + "<p>160mm of travel up front</p>", vendor="Santa Cruz"), V, "Bikes")[0]
        self.assertEqual(specs["suspension"], [FULL])
        self.assertEqual(specs["travel_mm"], ["150"])
        self.assertEqual(specs["frame_material"], ["Carbon"])
        self.assertEqual(specs["wheel_size"], ["29"])

    def test_hardtails(self):
        cases = (bike("Scalpel HT Hi-MOD Ultimate", "BIKES AND FRAMES/BIKES - MOUNTAIN/CROSS COUNTRY/SCALPEL",
                      body=table(Fork="Lefty Ocho, 100mm travel"), vendor="Cannondale"),
                 bike("Highball 3 C 90", "BIKES AND FRAMES/BIKES - MOUNTAIN/CROSS COUNTRY/HIGHBALL",
                      body=table(Fork="RockShox SID, 110mm"), vendor="Santa Cruz"),
                 bike("Eastern Alpaka 29 MTB Hardtail Bike - Gray", "Hardtail"),
                 bike("Trail 1", "BIKES AND FRAMES/BIKES - MOUNTAIN/HARDTAIL/TRAIL", body="<p>100mm of rear travel</p>"))
        for product in cases:
            specs = extract(product, V, "Bikes")[0]
            self.assertEqual(specs.get("suspension"), [HARDTAIL], product["title"])
            self.assertNotIn("travel_mm", specs, product["title"])

    def test_store_category_and_names(self):
        specs = extract(bike("Specialized Turbo Levo SL 2 Comp Alloy (2026)", "Bikes - E-Full Suspension 29"), V, "Bikes")[0]
        self.assertEqual((specs["suspension"], specs["wheel_size"], specs["frame_material"]), ([FULL], ["29"], ["Alloy"]))
        specs = extract(bike("Santa Cruz Chameleon 8 AL D 29", "BIKES AND FRAMES/BIKES - MOUNTAIN/HARDTAIL/TRAIL"), V, "Bikes")[0]
        self.assertEqual(specs["frame_material"], ["Alloy"])
        specs = extract(bike("Polygon Siskiu D6 LTD - Dual Suspension Mountain Bike"), V, "Bikes")[0]
        self.assertEqual(specs["suspension"], [FULL])

    def test_no_guessing(self):
        specs = extract(bike("Polygon Siskiu T8 - Mountain Bike (UDH)"), V, "Bikes")[0]
        for key in ("suspension", "frame_material", "travel_mm", "wheel_size"):
            self.assertNotIn(key, specs, key)
        # Conflicting materials say nothing.
        specs = extract(bike("Steel and Carbon Frankenbike"), V, "Bikes")[0]
        self.assertNotIn("frame_material", specs)
        # Not for parts.
        self.assertNotIn("suspension", extract(bike("Maxxis Minion DHF 29x2.5", "Tires"), V, "Tires")[0])

    def test_facets(self):
        keys = {f["key"]: f for f in facets.FIELDS}
        self.assertEqual(keys["suspension"]["param"], "mtb_suspension")
        self.assertEqual(keys["frame_material"]["param"], "mtb_material")
        self.assertEqual(keys["suspension"]["categories"], ("Bikes", "Frames"))


if __name__ == "__main__":
    unittest.main()
