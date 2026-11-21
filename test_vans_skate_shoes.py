import unittest

import tracked


class VansSkateShoes(unittest.TestCase):
    def rule(self, name, description=""):
        return tracked.sneaker_rule(name, description)

    def test_vans_skate_line_is_tracked(self):
        for name in ["Vans Skate Old Skool 36+ Shoes - Blackout",
                     "Vans Skate Half Cab (Golden Brown/ Gum)",
                     "Vans Skate 2 Wayvee Shoes",
                     "Vans Skate Estazzo Skateboard Shoe - Brown/White"]:
            self.assertEqual(self.rule(name), "vans-skate", name)

    def test_skate_models_named_without_skate_use_the_description(self):
        self.assertEqual(self.rule("Vans Rowan Shoes - Asphalt/White",
                                   "Suede and Canvas Upper Low-Top Skate Shoe Design"), "vans-skate")
        self.assertEqual(self.rule("Vans Sk8-Hi 2-Tone (Navy/Port)",
                                   "Vans Skate Sk8-Hi (Navy/Port) Fully redesigned"), "vans-skate")

    def test_existing_rules_still_win(self):
        self.assertEqual(self.rule("Vans BMX Proof Wafflecup Shoes"), "vans-wafflecup")

    def test_other_vans_and_other_brands_stay_out(self):
        self.assertEqual(self.rule("Vans Classic Slip-On Kids Shoes", "Canvas upper"), "")
        self.assertEqual(self.rule("Nike Air Max 90", "a classic skate shoe look"), "")


if __name__ == "__main__":
    unittest.main()
