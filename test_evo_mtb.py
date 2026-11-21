import unittest
from urllib import robotparser

from sports.mtb import stores
from stores import shopify


class EvoMtb(unittest.TestCase):
    def part(self, product_type, title="Some Part"):
        return shopify.part_for(stores.EVO, product_type, title)

    def test_evo_is_an_mtb_store(self):
        self.assertIn(stores.EVO, stores.STORES)

    def test_bikes_and_e_mtbs(self):
        self.assertEqual(self.part("Mountain Completes", "Devinci Troy Deore Complete Mountain Bike 2026"), "Bikes")
        self.assertEqual(self.part("e-Mountain Completes", "Specialized Turbo Levo 4 Expert Carbon E-Mountain Bike"), "Bikes")
        self.assertEqual(self.part("Mountain Frames", "Santa Cruz Nomad 6 CC MX Frame 2025"), "Frames")
        self.assertIsNone(self.part("Gravel Completes", "Some Gravel Bike"))

    def test_evo_pads_are_brake_pads(self):
        self.assertEqual(self.part("Pads", "SRAM Code Metallic Disc Brake Pads"), "Brakes")
        self.assertEqual(self.part("Body Armor", "Race Face Indy Knee Pads"), "Protection")

    def test_snow_armor_and_small_parts_stay_out(self):
        self.assertIsNone(self.part("Armor", "Burton Impact Short"))
        self.assertIsNone(self.part("Wrist Guards", "Burton Wrist Guards"))
        for kind in ("Sealant", "Valves", "Bar Tape", "Brake Small Parts", "Cables"):
            self.assertIsNone(self.part(kind), kind)
        self.assertFalse(any("/collections/body-armor/" in url for url in stores.EVO.sale_jsons))

    def test_collections_are_allowed_by_evos_robots_rules(self):
        rules = robotparser.RobotFileParser()
        rules.parse([
            "User-agent: *",
            "Disallow: /collections/*sort_by*",
            "Disallow: /collections/*+*",
            "Disallow: /collections/*filter*&*filter*",
        ])
        urls = stores.EVO.sale_jsons
        for url in urls:
            self.assertTrue(rules.can_fetch(shopify._USER_AGENT, url + "?limit=250&page=2"), url)


if __name__ == "__main__":
    unittest.main()
