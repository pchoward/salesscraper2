"""Bike Mart (MTB, 2026-11-11) and the road names the MTB rules now drop."""

import unittest

from sports.mtb import stores
from sports.mtb.rules import filter_reason
from stores import shopify


class BikeMartTests(unittest.TestCase):
    def part(self, kind, title="Thing"):
        return shopify.part_for(stores.BIKE_MART, kind, title)

    def test_bikes_and_frames(self):
        self.assertEqual(self.part("Full Suspension Mountain Bike"), "Bikes")
        self.assertEqual(self.part("Electric Full Suspension Mountain Bike"), "Bikes")
        self.assertEqual(self.part("Hardtail Mountain Bike"), "Bikes")
        self.assertEqual(self.part("Full Suspension Mountain Frameset"), "Frames")
        for kind in ("Hybrid Bike", "Endurance Road Bike", "Gravel Road Bike", "Road Frameset", "12-Inch Kids Bike"):
            self.assertIsNone(self.part(kind), kind)

    def test_parts(self):
        self.assertEqual(self.part("Tires", "Maxxis Aspen Tire - 29\" Tubeless"), "Tires")
        self.assertEqual(self.part("Stems", "Cane Creek GXC Stem"), "Cockpit")
        self.assertEqual(self.part("Pedals", "VP Grind Pedals"), "Pedals")

    def test_road_names_dropped(self):
        for name, part in (("Campagnolo Super Record Chains - 12-Speed", "Drivetrain"), ("Schwalbe One Tires", "Tires"),
                           ("Shimano 105 5800 11 Speed Pulley Set", "Drivetrain"),
                           ("Continental Grand Prix 5000 Tire", "Tires")):
            self.assertEqual(filter_reason(name, part), "explicit non-MTB equipment", name)
        self.assertIsNone(filter_reason("SRAM GX Eagle Chain", "Drivetrain"))
        self.assertIsNone(filter_reason("Maxxis Aspen Tire - 29\" Tubeless", "Tires"))

    def test_registered(self):
        self.assertIn(stores.BIKE_MART, stores.STORES)


if __name__ == "__main__":
    unittest.main()
