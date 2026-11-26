"""MTB Type inside each heading, and Tools & Care (owner, 2026-11-26)."""

import unittest

from sports import headings
from sports.mtb import kinds


def kind(part, name, product_type=""):
    return kinds.kind(part, name, product_type)


class Suspension(unittest.TestCase):
    def test_whole_forks_and_shocks(self):
        self.assertEqual(kind("Forks & Shocks", 'RockShox Lyrik Ultimate Fork - 27.5" - Charger 3.1 RC2 - 37mm Offset - 2025', "Fork"), "Forks")
        self.assertEqual(kind("Forks & Shocks", "DVO Onyx SC 29 D2 - Fork (OEM)", "Parts"), "Forks")
        self.assertEqual(kind("Forks & Shocks", "2026 Fox Factory Float X2 Shock - 225 x 75 mm", "Rear Shocks"), "Rear Shocks")
        self.assertEqual(kind("Forks & Shocks", "RockShox Metric Coil Spring 57.5-65mm", "Rear Shock Coil Springs"), "Coil Springs")

    def test_parts_stay_parts(self):
        self.assertEqual(kind("Forks & Shocks", "RockShox 200 Hour Service Kit - Pike Dual Position Air A1", "Fork Parts"), "Fork Parts")
        self.assertEqual(kind("Forks & Shocks", "PUSH Industries ACS3 Coil Conversion Kit Fox 36 2021+", "Fork Parts"), "Fork Parts")
        self.assertEqual(kind("Forks & Shocks", "RockShox Monarch+ B1 Med/Low Tune Kit", "Rear Shock Parts"), "Shock Parts")
        self.assertEqual(kind("Forks & Shocks", "Polygon Shock Bolts Kit for Trid ZZ", "Parts"), "Shock Parts")


class OtherHeadings(unittest.TestCase):
    def test_wheels(self):
        self.assertEqual(kind("Wheels", 'Stan\'s Arch MK4 Rear Wheel - 29" - 12x148mm - 6-Bolt - HG Driver', "Rear Wheel"), "Wheels")
        self.assertEqual(kind("Wheels", "OneUp Components XD Freehub/Driver", "Rear Hub Drivers"), "Hub Parts")
        self.assertEqual(kind("Wheels", "Onyx Vesper ISO 12x157mm Super Boost 32h Rear Hub", "Rear Hubs"), "Hubs")
        self.assertEqual(kind("Wheels", "WTB TCS Rim Tape - 26mm x 55m Roll", "Tubeless Tape"), "Rim Tape & Valves")

    def test_drivetrain(self):
        self.assertEqual(kind("Drivetrain", "SRAM GX Eagle T-Type Direct Mount Chainring - 30t - 8-bolt - 3mm Offset", "Chainrings"), "Chainrings")
        self.assertEqual(kind("Drivetrain", "Shimano Deore M616 2x10 High Clamp Front Derailleur - OE", "MTB Front Derailleurs"), "Derailleurs")
        self.assertEqual(kind("Drivetrain", "SRAM X1 1400 Crankset (175mm)", "COMPONENTS/CRANKS/CRANK PARTS"), "Cranks")
        self.assertEqual(kind("Drivetrain", "Sram Force DUB Crankset", "Parts"), "Cranks")
        self.assertEqual(kind("Drivetrain", "Shimano CN-HG40 8-Speed Chain w/ Quick Link", "Chains"), "Chains")
        self.assertEqual(kind("Drivetrain", "SRAM PowerLock Link for 11 Speed Chain", "Chains"), "Drivetrain Parts")
        self.assertEqual(kind("Drivetrain", "SRAM Self-Extracting Crank Arm Bolt Kit - M18/M30", "Cranksets"), "Drivetrain Parts")
        self.assertEqual(kind("Drivetrain", "SRAM Universal Derailleur Hanger", "Derailleur Hangers"), "Drivetrain Parts")

    def test_brakes(self):
        self.assertEqual(kind("Brakes", "Shimano Deore M4100/MT410 Disc Brake & Lever - Front - Black", "MTB Disc Brakes"), "Brakes")
        self.assertEqual(kind("Brakes", "Shimano XT BR-M8100 Hydraulic Disc Brake with Metal Pad", "Brakes Front and Rear"), "Brakes")
        self.assertEqual(kind("Brakes", "Formula CURA 4 Disc Brake Kit - Silver", "MTB Disc Brakes"), "Brakes")
        self.assertEqual(kind("Brakes", "SRAM Level B1 / Elixir Sintered Disc Brake Pads", "Disc Brake Pads"), "Pads")
        self.assertEqual(kind("Brakes", "SRAM HS2 6-bolt Rounded Rotor", "Disc Brake Rotors"), "Rotors")
        self.assertEqual(kind("Brakes", "SRAM 20mm IS to Post Mount Disc Brake Adaptor - 180mm Front", "Brake Adapters"), "Brake Parts")
        self.assertEqual(kind("Brakes", "SRAM Code Silver Stealth Lever Blade Kit", "Disc Brake Parts"), "Brake Parts")

    def test_cockpit(self):
        self.assertEqual(kind("Cockpit", "Race Face Atlas Handlebar - 800mm Width - 50mm Rise - 35mm Clamp", "Handlebars"), "Handlebars")
        self.assertEqual(kind("Cockpit", "5Dev Titanium 2-Bolt Stem", "Stems"), "Stems")
        self.assertEqual(kind("Cockpit", "Entity Expert Seatpost", "Parts"), "Seatposts")
        self.assertEqual(kind("Cockpit", "KS Suspension eTen Remote External Dropper Post - No Remote", "Dropper Adjustable Seatposts"), "Dropper Posts")
        self.assertEqual(kind("Cockpit", "OneUp Components EDC Top Cap", "Stems"), "Cockpit Parts")
        self.assertEqual(kind("Cockpit", "Wheels Manufacturing Silver Seat Binder Bolt", "COMPONENTS/SEATPOSTS/SEAT BINDERS"), "Cockpit Parts")
        self.assertEqual(kind("Cockpit", "OneUp Components Dropper Post Remote V3", "Dropper Remotes"), "Cockpit Parts")

    def test_no_type_for_bikes_frames_pedals(self):
        self.assertIsNone(kind("Bikes", "Santa Cruz Hightower 4"))
        self.assertIsNone(kind("Pedals", "OneUp Components Aluminum Pedals", "Pedals"))


class Placement(unittest.TestCase):
    def item(self, part, name, product_type="", offers=True):
        row = {"part": part, "name": name, "product_type": product_type, "url": "https://shop.example/" + name}
        if offers:
            row["technical_offers"] = [{"price": 10, "specs": {"wheel_size": ["29"]}}]
        return row

    def test_tools_and_care_from_any_heading(self):
        for part, name, kind_ in (("Forks & Shocks", "RockShox High Pressure Fork/Shock Pump - 300 psi", "Shock Pumps"),
                                  ("Brakes", "SRAM DOT 5.1 Brake Fluid - 4oz", "Brake Bleed Kits/Fluids"),
                                  ("Drivetrain", "Boeshield T9 Chain Lube - 4oz", "Greases/Lubes"),
                                  ("Tires", "Park Tool BMT-1 Tire Bead Breaker", "Tire Lever")):
            self.assertEqual(headings.heading("mtb", self.item(part, name, kind_)), "Tools & Care", name)
        # A rebuild kit that mentions oil is still a part.
        self.assertEqual(headings.heading("mtb", self.item("Forks & Shocks", "Cane Creek DBInline - Damper/ Oil Rebuild Kit", "Rear Shock Parts")), "Suspension")

    def test_brake_items_filed_under_wheels_show_under_brakes(self):
        self.assertEqual(headings.heading("mtb", self.item("Wheels", "Avid 20R V-Brake Pads", "Rim Brake Parts")), "Brakes")
        self.assertEqual(headings.heading("mtb", self.item("Wheels", "Race Face Next R 31 Wheels", "Wheels")), "Wheels")

    def test_regroup_puts_the_type_on_every_offer(self):
        data = {"Fanatik_Forks & Shocks": [self.item("Forks & Shocks", "RockShox 32mm Seal and Foam Ring Kit", "Fork Parts")]}
        row = headings.regroup(data, "mtb")["Fanatik_Forks & Shocks"][0]
        self.assertEqual(row["part"], "Suspension")
        self.assertEqual(row["store_part"], "Forks & Shocks")
        self.assertEqual(row["technical_offers"][0]["specs"], {"wheel_size": ["29"], "kind": ["Fork Parts"]})
        self.assertEqual(row["technical_specs"]["kind"], ["Fork Parts"])
        # The stored row is not changed.
        self.assertNotIn("kind", data["Fanatik_Forks & Shocks"][0]["technical_offers"][0]["specs"])

    def test_heading_order(self):
        self.assertEqual(headings.HEADINGS["mtb"][9], "Tools & Care")
        self.assertEqual(headings.HEADINGS["mtb"][10:], headings._gear("mtb"))

    def test_other_sports_unchanged(self):
        item = self.item("Wheels", "Odyssey Hazard Lite Rim", "BMX Rims")
        self.assertEqual(headings.heading("bmx", item), "Wheels & Hubs")
        self.assertNotIn("kind", headings.regroup({"k": [item]}, "bmx")["k"][0]["technical_offers"][0]["specs"])


if __name__ == "__main__":
    unittest.main()
