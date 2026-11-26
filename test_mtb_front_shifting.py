"""MTB drops front derailleurs and left-only shifters (owner, 2026-11-26:
mountain bikes are 1x; Fanatik, an MTB-only shop, carries none)."""

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


if __name__ == "__main__":
    unittest.main()
