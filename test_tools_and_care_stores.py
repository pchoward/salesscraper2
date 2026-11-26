"""MTB and BMX stores file tools, pumps, lubes and cleaners under Tools & Care (owner, 2026-11-26)."""

import unittest

import sports
from sports import rules
from sports.bmx import stores as bmx
from sports.mtb import rules as mtb_rules
from sports.mtb import stores as mtb
from stores import shopify


class ToolsAndCare(unittest.TestCase):
    def test_store_types_go_to_tools_and_care(self):
        cases = [
            (mtb.LOST_CO, "General Tools", "Park Tool PCS-10.3 Home Mechanic Repair Stand"),
            (mtb.LOST_CO, "Chain Lubes", "Muc-Off Dry Lube 120ml"),
            (mtb.LOST_CO, "Cleaners and Polish", "Muc-Off Nano Tech Bike Cleaner 1L"),
            (mtb.MIKES, "TOOLS AND LUBE/MULTI TOOLS", "Crankbrothers M19 Multi-Tool"),
            (mtb.MIKES, "ACCESSORIES/PUMPS/FRAME PUMPS", "Lezyne Pressure Drive"),
            (mtb.FANATIK, "Workstands", "Feedback Sports Pro Elite Repair Stand"),
            (bmx.SOURCE_US, "Tools", "Odyssey Chain Breaker"),
            (bmx.SOURCE_US, "Wax", "Odyssey Grind Wax"),
        ]
        for store, product_type, title in cases:
            self.assertEqual(shopify.part_for(store, product_type, title), "Tools & Care", title)

    def test_sealant_goes_with_tires_and_parts_stay(self):
        self.assertEqual(shopify.part_for(mtb.LOST_CO, "Tubeless Sealant", "Orange Seal Endurance 8oz"), "Tires")
        self.assertEqual(shopify.part_for(mtb.LOST_CO, "Forks", "RockShox Pike Ultimate"), "Forks & Shocks")

    def test_only_mtb_and_bmx_stores(self):
        self.assertFalse(getattr(shopify.ShopifyStore("x", "x", "https://shop.example"), "tools_and_care", False))
        self.assertTrue(all(getattr(store, "tools_and_care", False) for store in mtb.STORES + bmx.STORES))

    def test_a_category_on_both_sports(self):
        self.assertIn("Tools & Care", sports.MTB.parts)
        self.assertIn("Tools & Care", sports.BMX.parts)
        self.assertIn("Tools & Care", mtb_rules.PARTS)
        self.assertIsNone(mtb_rules.filter_reason("Crankbrothers M19 Multi-Tool", "Tools & Care", price_new="20", price_old="30"))
        with sports.BMX.active():
            self.assertIsNone(rules.bmx("Odyssey Chain Breaker", "Tools & Care"))


if __name__ == "__main__":
    unittest.main()
