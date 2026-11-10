"""BMX leaves out roller/derby gear and skate pad packs, keeps single
hard-cap knee pads (owner, 2026-11-10)."""

import unittest

import sports
from filters import filter_reason


class BmxSkatePadTests(unittest.TestCase):
    def reason(self, name):
        with sports.BMX.active():
            return filter_reason(name, "Protection", "", 10, 20)

    def test_left_out(self):
        for name in ("187 Killer Pads PRO DERBY KNEE PAD - Black/Grey",
                     "Impala Rollerskates Protective Set - Knee Pads, Elbow, Wrist Guards - Pink - Youth Small",
                     "187 Adult Six Pack Pad Set - Moxi Jade",
                     "187 Killer Pads KNEE & ELBOW PAD COMBO PACK - Black",
                     "Triple 8 Saver Series Pad Set (3-Pack)",
                     "Pro-Tec Street Knee/Elbow Set of Pads - Camo",
                     "S-One Skateboard Pads Park Series Set (Knee and Elbow) Retro"):
            self.assertIsNotNone(self.reason(name), name)

    def test_kept(self):
        for name in ("Triple 8 KP 22 Knee Pads", "Triple 8 Street Knee Pads - Grey With White Cap",
                     "187 Killer Pads Slim Knee Pads - black", "Triple 8 Covert Elbow Pads - Moxi Edition",
                     "Triple 8 The Certified Sweatsaver Helmet - Moxi Signature Edition",
                     "Fuse Stealth Knee Pad Combo", "Demon Bend & Send Kit — Knee + Elbow Pads",
                     "G-Form Lil G Knee And Elbow Guard Set - Kids"):
            self.assertIsNone(self.reason(name), name)

    def test_skate_tab_unchanged(self):
        self.assertIsNone(filter_reason("187 Killer Pads KNEE & ELBOW PAD COMBO PACK - Black", "Protection", "", 10, 20))


if __name__ == "__main__":
    unittest.main()
