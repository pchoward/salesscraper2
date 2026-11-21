"""MTB Frames shows frames only (owner, 2026-11-21)."""

import unittest

from sports.mtb.rules import filter_reason


class FrameTests(unittest.TestCase):
    def test_frame_accessories_left_out(self):
        for name, kind in (("RideWrap Ripley Gen 4 Frame Protection Kit", "Frame Protection"),
                           ("RideWrap 2020-2022 Turbo Levo SL Frame Protection", "Frame Protection"),
                           ("ODI DH Race Number Plate - Black", "Frame Protection"),
                           ("All Mountain Style Frame Guard Extra", "Frames")):
            self.assertEqual(filter_reason(name, "Frames", product_type=kind), "frame accessory, not a frame", name)
        self.assertIsNotNone(filter_reason("Specialized S-Works Shiv TT Disc Module - FACT 11r Carbon", "Frames",
                                           product_type="Framesets"))

    def test_real_frames_kept(self):
        for name, kind in (("Transition Sentinel Carbon Frame - 2026", "Trail/AM Frames"),
                           ("Santa Cruz Nomad Carbon CC Frameset - 2025", "AM/Enduro Frames"),
                           ("Intense Spider Frame + Shock - Oxblood - 2026", "Full Suspension Frames"),
                           ("Specialized S-Works Turbo Levo 4 Frameset", "Framesets")):
            self.assertIsNone(filter_reason(name, "Frames", product_type=kind), name)


if __name__ == "__main__":
    unittest.main()
