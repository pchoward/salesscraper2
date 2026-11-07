"""Cult BMX (store probe, 2026-11-07): the brand's own store, USD with
renamed types ("Hubs / Wheels"); complete bikes with no markdown today.
No network."""

import unittest

from sports import brands
import sports
from sports.bmx import stores


class CultStoreTests(unittest.TestCase):
    def test_store(self):
        self.assertIn(stores.CULT, stores.STORES)
        self.assertEqual([u.split("/collections/")[1].split("/")[0] for u in stores.CULT.sale_jsons],
                         ["cult-complete-bikes", "black-friday"])
        self.assertTrue(stores.CULT.track_exclusions)
        self.assertEqual(stores.CULT.types["hubs wheels"], "Wheel Parts")
        self.assertEqual(stores.CULT.types["bikes"], "Bikes")
        # Cult's softgoods stay out; there is no Extras/Tools part in BMX.
        self.assertNotIn("extras", stores.CULT.types)

    def test_brand_from_cult_crew_vendor(self):
        canonical = brands.for_sport(sports.BMX)
        self.assertEqual(canonical("CULT CREW"), "Cult")
        self.assertEqual(canonical("Cult"), "Cult")

    def test_probe_types_dispatch_to_the_right_parts(self):
        """Types recorded by the store probe land in the right catalog parts
        (product_type is authoritative; the title only breaks ties)."""
        from stores import shopify

        checks = (("Bikes", 'ACCESS / black', "Bikes"),
                  ("Bikes", '12" Push Bike / black', "Bikes"),
                  ("Pegs", 'Butter Peg / new sizes', "Wheel Parts"),
                  ("Hubs / Wheels", '14" Juvi Front Wheel', "Wheel Parts"),
                  ("Merch", 'Cult Crew T-Shirt', None),
                  ("Softgoods", 'Cult Crew Hoodie', None),
                  ("Extras", 'Pocket Tool', None))
        for kind, title, expected in checks:
            with self.subTest(kind=kind, title=title):
                got = shopify.part_for(stores.CULT, kind, title)
                self.assertEqual(got, expected, f"{kind} / {title}")


if __name__ == "__main__":
    unittest.main()
