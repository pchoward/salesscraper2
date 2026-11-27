"""MTB drops front derailleurs and left-only shifters, triples and rim
brakes (owner, 2026-11-26: mountain bikes are 1x and disc; Fanatik, an
MTB-only shop, carries no front derailleur)."""

import unittest

from sports.mtb.rules import filter_reason

DROPPED = "front derailleur or front shifter"


class FrontShiftingTests(unittest.TestCase):
    def test_front_derailleurs_go(self):
        for name, kind in (
            ("SRAM XX Direct Mount 2x10 Front Derailleur", "MTB Front Derailleurs"),
            ("Shimano Altus CT92 3x8 Speed Front Derailleur - E-Type - Black-Silver", "MTB Front Derailleurs"),
            ("Shimano XTR M9070 Di2 11 Speed Front Derailleur - OE", "Electronic Gear Shifting"),
            ("SRAM XX High Clamp Bottom Pull Front Derailleur (10-Speed)", "COMPONENTS/DERAILLEURS/FRONT DERAILLEURS MTB"),
        ):
            self.assertEqual(filter_reason(name, "Drivetrain", product_type=kind), DROPPED, name)

    def test_left_only_shifters_go(self):
        for name, kind in (
            ("Shimano Saint M800 Shift/Brake Dual Control - Left Hand - Gray - OE", "MTB Gear Shifters"),
            ("Shimano Alivio M4050 Hydraulic Brake/Shift Lever (Left)", "COMPONENTS/SHIFTERS/FLAT BAR LEFT"),
            ("SRAM MRX Comp Microfriction Front Shifter", "COMPONENTS/SHIFTERS/FLAT BAR LEFT"),
            ("microSHIFT Mezzo Left Thumb-Tap Shifter", "MTB Gear Shifters"),
            ("Shimano XT Di2 M8050 Front Shifter", "Electronic Gear Shifting"),
        ):
            self.assertEqual(filter_reason(name, "Drivetrain", product_type=kind), DROPPED, name)

    def test_1x_parts_stay(self):
        for name, kind in (
            ("SRAM Pod AXS Controller Bridge Clamp - Left", "Shifter Parts"),  # dropper or 1x shifting
            ("SRAM AXS Pod Controller Ultimate Infinite Clamp - Left or Right", "Shifter Parts"),
            ("SRAM MatchMaker X Mounting Bracket - Left Side", "Shifter Parts"),
            ("Shimano SW-E7000-L Left Switch", "Electronic Gear Shifting"),  # e-bike assist switch
            ("Shimano Deore M6100 12-Speed Shifter - Right", "MTB Gear Shifters"),
            ("SRAM MRX Comp Twist Shifter Set", "COMPONENTS/SHIFTERS/FLAT BAR RIGHT"),
            ("SRAM GX Eagle Trigger Shifter", "Shifters"),
            ("Shimano XT M8100 Rear Derailleur", "Rear Derailleurs"),
            ("Wheels Manufacturing Derailleur Hanger", "Derailleur Hangers"),
        ):
            self.assertIsNone(filter_reason(name, "Drivetrain", product_type=kind), name)


class TriplesAndRimBrakesTests(unittest.TestCase):
    """Owner, 2026-11-26: triples, V-brakes and road leftovers go too."""

    def test_triples_go(self):
        for name, part, kind in (
            ("Shimano Acera M361 Square Taper Triple Crankset - Black", "Drivetrain", "MTB Cranksets"),
            ("Origin8 Alloy Triple Crank Arm Set 165mm 113.5mm Square Taper JIS crankset", "Drivetrain", "Cranksets and Arms"),
            ("Shimano SLX M665/M660 36T 9-speed Middle Chainring - 104BCD", "Drivetrain", "Chainrings"),
            ("SRAM X4 3x8 Spd Trigger Shifter Set", "Drivetrain", "MTB Gear Shifters"),
            ("SunRace M406 ST Trigger Brake/Shift Lever Set - 3x7-Speed For V-Brakes Black", "Brakes", "Brake/Shift Lever"),
        ):
            self.assertIsNotNone(filter_reason(name, part, product_type=kind), name)

    def test_rim_brakes_go(self):
        for name, part, kind in (
            ("Shimano BR-T610 V-Brake - Front - Black", "Brakes", "MTB V-Brakes"),
            ("Tektro 855AL Linear Pull Brake - Front or Rear Black", "Brakes", "Linear Pull Brakes"),
            ("Origin8 Pro Force Cantilever Frt or Rr Black", "Brakes", "Brakes"),
            ("Shimano T4000 MTB Brake Levers - Pair - Black", "Brakes", "MTB V-Brake Levers"),
            ("Avid 20R V-Brake Pads", "Wheels", "Rim Brake Parts"),
            ("Zipp Speed Weaponry Tangente Platinum Pro Evo Brake Pad Inserts", "Wheels", "COMPONENTS/BRAKES/RIM PADS"),
        ):
            self.assertEqual(filter_reason(name, part, product_type=kind), "V-brake or rim brake part", name)

    def test_modern_parts_stay(self):
        for name, part, kind in (
            ("Race Face Turbine Cinch 30 2x11 Crankset", "Drivetrain", "MTB Cranksets"),
            ("SRAM Eagle 1x12 Trigger", "Drivetrain", "Shifters"),
            ("Shimano Deore M6100 Disc Brake", "Brakes", "Disc Brakes"),
            ("Origin8 Alloy braze-on Insert Mech. Disc or V-Brake Black", "Brakes", "Cables and Housing"),
            ("VP Components VP-S1 Triple Trainer Exercise Pedal Kit - Black", "Pedals", "Flat Pedals"),
            ("Shimano Deore M6100 Brake Pads - Resin", "Brakes", "Disc Brake Pads"),
        ):
            self.assertIsNone(filter_reason(name, part, product_type=kind), name)



class RoadLeftoversTests(unittest.TestCase):
    """The first specialist shop check (owner, 2026-11-27): road and gravel
    wheels and road Di2/eTap parts under MTB."""

    def test_road_and_gravel_parts_go(self):
        for name, part, kind in (
            ("Zipp Speed Weaponry 353 NSW Tubeless Disc Wheels", "Wheels", "COMPONENTS/WHEELS/PERFORMANCE WHEELS CARBON"),
            ("Reserve 40|44 GR Wheelset + Vittoria Terreno T40 Tire Bundle", "Wheels", "PERFORMANCE WHEELS CARBON"),
            ("Reserve 34|37 SL Turbulent Aero Wheelset", "Wheels", "PERFORMANCE WHEELS CARBON"),
            ("SRAM eTap Blip Shift Buttons", "Drivetrain", "Electronic Gear Shifting"),
            ("Shimano Di2 R610 Sprinter Shifter Set", "Drivetrain", "Electronic Gear Shifting"),
            ("Shimano RS910 Bar End Junction-A Box", "Drivetrain", "Electronic Gear Shifting"),
            ("Shimano SPD-SL Pedals PD-R550", "Pedals", "Pedals"),
        ):
            self.assertEqual(filter_reason(name, part, product_type=kind), "explicit non-MTB equipment", name)

    def test_mtb_parts_stay(self):
        for name, part, kind in (
            ("Reserve 30|HD Wheelset", "Wheels", "PERFORMANCE WHEELS CARBON"),
            ("Reserve E 30|HD 31|DH Wheelset (XD)", "Wheels", "PERFORMANCE WHEELS CARBON"),
            ("SRAM eTap and eTap AXS Battery", "Drivetrain", "Electronic Gear Shifting"),  # MTB AXS uses it
            ("Shimano XT MT800 Di2 Digital Display Unit", "Drivetrain", "Electronic Gear Shifting"),
            ("Origin8 SM-20 brake pad Origin8 Vise Hyd-Mech / Shimano Alfine R505- Deore M535-", "Brakes", "Brake Pads"),
            ("Zipp 3ZERO MOTO Carbon Wheelset", "Wheels", "Wheels"),
        ):
            self.assertIsNone(filter_reason(name, part, product_type=kind), name)


if __name__ == "__main__":
    unittest.main()
