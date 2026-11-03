"""The Lost Co. (owner, 2026-11-03): MTB parts by its clean types; tools,
lubes and consumables stay out. No network."""

import unittest

from sports import brands
import sports
from sports.mtb import stores


class LostCoTests(unittest.TestCase):
    def test_types(self):
        for kind, part in {"Tires": "Tires", "Fork Parts": "Forks & Shocks", "Rear Shocks": "Forks & Shocks",
                           "Cranksets - Mountain": "Drivetrain", "Bottom Brackets": "Drivetrain", "Grips": "Cockpit",
                           "Dropper Parts": "Cockpit", "Helmets": "Protection", "Full Suspension Bikes": "Bikes"}.items():
            self.assertEqual(stores.lost_co_part(kind), part, kind)
        for kind in ("General Tools", "Suspension Oil", "Chain Lubes", "Brake Tools", "Tubeless Sealant", "Bearings",
                     "Number Plates", "Brake Fluid", "Shock Pumps", "Fenders"):
            self.assertIsNone(stores.lost_co_part(kind), kind)

    def test_store(self):
        self.assertIn(stores.LOST_CO, stores.STORES)
        self.assertEqual([u.split("/collections/")[1].split("/")[0] for u in stores.LOST_CO.sale_jsons],
                         ["mtb-parts-on-sale", "clearance-mountain-bike-parts"])
        canonical = brands.for_sport(sports.MTB)
        self.assertEqual({canonical("Stans No Tubes"), canonical("Stan's No Tubes")}, {"Stan's NoTubes"})
        self.assertEqual(canonical("RaceFace"), "Race Face")


if __name__ == "__main__":
    unittest.main()
