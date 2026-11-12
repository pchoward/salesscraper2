"""BMX brands' own stores (2026-11-04): Kink, Haro and Fiend sale sections; Sparky's Brands (2026-11-12)."""

import unittest

from sports.bmx import stores
from stores import shopify


class BmxBrandShopTests(unittest.TestCase):
    def test_registered(self):
        self.assertEqual([(s.store, s.sale_json) for s in stores.BMX_BRANDS],
                         [("Kink", "https://www.kinkbmx.com/collections/sale/products.json"),
                          ("Haro", "https://www.harobikes.com/collections/summer-parts-sale/products.json"),
                          ("Fiend", "https://www.fiendbmx.com/collections/clearance/products.json"),
                          ("Sparky's Brands", "https://www.sparkysbrands.com/collections/sales/products.json")])
        sparkys = stores.BMX_BRANDS[3]
        self.assertTrue(sparkys.whole_site)
        self.assertEqual(shopify.part_for(sparkys, "BMX Forks", "Subrosa Simo 18 Forks"), "Frames & Forks")
        self.assertEqual(shopify.part_for(sparkys, "BMX Gloves", "Shadow Conspiracy Jolt Gloves"), "Protection")
        self.assertTrue(set(stores.BMX_BRANDS) <= set(stores.STORES))

    def test_their_product_types(self):
        store = stores.BMX_BRANDS[0]
        cases = {("Tires & Tubes", "Sever Tire"): "Tires", ("hubs & guards", "Sever Hub Guard"): "Wheel Parts",
                 ("Cranks & BB's", "Kink Valor Cranks"): "Drivetrain", ("Braking", "Kink Desist Brake"): "Braking",
                 ("Seats", "Kink Williams Seat"): "Seating", ("Forks", "Kink Williams Forks"): "Frames & Forks",
                 ("Seatpost", "Haro Pivotal Post"): "Seating"}
        for (kind, title), part in cases.items():
            self.assertEqual(shopify.part_for(store, kind, title), part, kind)
        self.assertIsNone(shopify.part_for(stores.BMX_BRANDS[1], "Accessories", "Haro Buzzard Internal Frame Bag"))
        self.assertEqual(shopify.part_for(stores.BMX_BRANDS[1], "Accessories", "Haro Baseline Seat Clamp"), "Seating")
        for kind, title in (("T-Shirts", "Kink Logo Tee"), ("Jackets", "Kink Coach Jacket")):
            self.assertIn(shopify.part_for(store, kind, title), (None, shopify.BY_TITLE, ""), kind)


if __name__ == "__main__":
    unittest.main()
