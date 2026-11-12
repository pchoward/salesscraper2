"""Card name cleanup (audit 2026-11-12): ALL CAPS, spec dumps, doubled brands."""

import unittest

import names
import sports
from sports import brands
from stores import shopify


class NameTests(unittest.TestCase):
    def test_all_caps_to_title_case(self):
        cases = {
            "SUNDAY NIGHTSHIFT FRAME": "Sunday Nightshift Frame",
            "BILLET BMX DEEZ NUTS 12 POINT THREADLESS HEADSET KIT 1-1/8":
                "Billet BMX Deez Nuts 12 Point Threadless Headset Kit 1-1/8",
            "MERRITT P1 PC PEDALS": "Merritt P1 PC Pedals",
            "ROSSIGNOL NOVA 2 SKIS W/ XP 10 BINDINGS": "Rossignol Nova 2 Skis w/ XP 10 Bindings",
            "K2 WOMEN'S BFC BOA 85 SKI BOOTS": "K2 Women's BFC BOA 85 Ski Boots",
            "SHADOW INVISA LITE SHIN/ANKLE COMBO": "Shadow Invisa Lite Shin/Ankle Combo",
            "SRAM REAR DERAILLEUR PULLEY KIT XX T-TYPE EAGLE AXS (INCLUDES 14T UPPER AND 16T LOWER BLACK METAL "
            "SPIDER PULLEY, 2 ALUMINUM PULLEY SCREWS )": "SRAM Rear Derailleur Pulley Kit XX T-Type Eagle AXS",
        }
        for shouted, shown in cases.items():
            self.assertEqual(names.tidy(shouted), shown)

    def test_ordinary_names_untouched(self):
        for name in ("Shadow Conspiracy SHADOW DEADBOLT BAR ENDS",  # mixed case: left alone
                     "We The People Helix Rear Hub - Freecoaster, 36H, Black, RHD",
                     "Volkl Flair 7.2 (with vMotion 10 GW Lady System Bindings) Womens Skis 2025",
                     "Nike SB Dunk Low Pro WC (Saffron Quartz/Saffron Quartz-Pear)",
                     "Santa Cruz x Stranger Things Meek Slasher Eddie Reveal Skateboard Complete - Glow In The Dark - 10.10\""):
            self.assertEqual(names.tidy(name), name)

    def test_spec_dumps_trimmed_to_fit(self):
        long = ("Schwalbe Shredda Front Tire - 29 x 2.50, Tubeless, Folding, Black, Evolution Line, Gravity Pro, "
                "Addix Ultra Soft, Radial, E-50")
        shown = names.tidy(long)
        self.assertLessEqual(len(shown), names.LIMIT)
        self.assertTrue(shown.startswith("Schwalbe Shredda Front Tire - 29 x 2.50, Tubeless"))
        self.assertEqual(names.tidy("FOX DHX Live Valve Neo Factory Rear Shock - Metric, 230 x 60 mm, Hard Chromoly "
                                    "Stanchion, Black"),
                         "FOX DHX Live Valve Neo Factory Rear Shock - Metric, 230 x 60 mm, Hard Chromoly Stanchion")

    def test_tidy_items_counts_changes(self):
        data = {"A_Bikes": [{"name": "SUNDAY NIGHTSHIFT FRAME"}, {"name": "Sunday Primer"}]}
        self.assertEqual(names.tidy_items(data), 1)
        self.assertEqual(data["A_Bikes"][0]["name"], "Sunday Nightshift Frame")

    def test_no_doubled_brand(self):
        brand_of = brands.for_sport(sports.BMX)
        cases = {("Shadow Metal Pedal", "Shadow Conspiracy"): "Shadow Metal Pedal",
                 ("Demon Podium Helmet w/MIPS", "Demon United"): "Demon Podium Helmet w/MIPS",
                 ("SE RACING NARLER RETRO STEM", "SE Bikes"): "SE RACING NARLER RETRO STEM",
                 ("Crank brothers Egg Beater 2 Pedals", "crank bros"): "Crank brothers Egg Beater 2 Pedals",
                 ("Formula Four Classic 54mm", "Spitfire"): "Spitfire Formula Four Classic 54mm",
                 ("Session Backpack", "Shadow Conspiracy"): "Shadow Conspiracy Session Backpack"}
        for (title, vendor), shown in cases.items():
            self.assertEqual(shopify.title_with_brand({"title": title, "vendor": vendor}, "", brand_of), shown)


if __name__ == "__main__":
    unittest.main()
