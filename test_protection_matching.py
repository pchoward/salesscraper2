"""Skate protective gear grouped across stores (matching.describe_item)."""

import unittest

from matching import cross_store_groups, describe_item


def _gear(name, store, price="40.00", old="60.00"):
    slug = name.lower().replace(" ", "-")
    return {"name": name, "part": "Protection", "store": store, "price_new": price, "price_old": old,
            "url": f"https://{store.lower()}.example/{slug}"}


def _key(name):
    return describe_item({"name": name, "part": "Protection"})["key"]


class ProtectionMatchingTests(unittest.TestCase):
    def test_same_helmet_and_colour_at_two_stores_groups(self):
        groups = cross_store_groups([
            _gear("Triple Eight Deep Cover Helmet - Navy Matte", "CCS", "87.50", "125.00"),
            _gear("Triple Eight Deep Cover Skate Helmet - navy matte", "Tactics", "100.95", "125.00"),
        ])
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]["part"], "Protection")
        self.assertEqual(groups[0]["cheapest_price"], 87.5)

    def test_brand_spellings_fold(self):
        self.assertEqual(_key("Pro-Tec Street Elbow Pads - Camo"), _key("ProTec Street Elbow Pads - camo"))
        self.assertEqual(_key("Pro Tec Street Elbow Pads - Camo"), _key("Pro-Tec Street Elbow Pads - Camo"))
        self.assertEqual(_key("Triple 8 Street Elbow Pads - Black"), _key("Triple Eight Street Elbow Pads - Black"))
        self.assertEqual(_key("187 Slim Elbow Pads - Black"), _key("187 Killer Pads Slim Elbow Pad - black"))
        self.assertEqual(_key("187 Slim Elbow Pads - Black"), _key("187killerpads SLIM ELBOW PAD - Black"))

    def test_wording_of_the_gear_type_does_not_matter(self):
        self.assertEqual(
            _key("Pro-Tec Street Knee/Elbow Open Back Set of Pads - Black"),
            _key("ProTec Street Knee & Elbow Open Back Skate Pad Set - black"),
        )
        self.assertEqual(_key("Pro-Tec Helmet - Gloss White Classic"), _key("ProTec Classic Skate Helmet - white gloss"))

    def test_colourways_stay_apart(self):
        self.assertNotEqual(_key("Triple Eight Deep Cover Helmet - Navy Matte"),
                            _key("Triple Eight Deep Cover Helmet - Mint Matte"))

    def test_certified_and_signature_editions_are_different_products(self):
        self.assertNotEqual(_key("Pro-Tec Classic Matte Black Skateboard Helmet"),
                            _key("ProTec Classic Certified EPS Skate Helmet - matte black"))
        self.assertNotEqual(_key("Triple 8 The Certified Sweatsaver Helmet - Moxi Signature Edition"),
                            _key("Triple Eight THE Certified Sweatsaver Skate Helmet - black matte"))

    def test_gear_type_and_age_are_part_of_identity(self):
        self.assertNotEqual(_key("187 Slim Elbow Pads - Black"), _key("187 Slim Knee Pads - Black"))
        self.assertNotEqual(_key("ProTec Classic Certified Helmet - matte black"),
                            _key("ProTec JR Classic Certified Helmet - matte black"))

    def test_letter_sizes_are_variants(self):
        self.assertEqual(_key("Pro Tec Gasket Elbow Pads Size XS"), _key("Pro-Tec Gasket Elbow Pads"))

    def test_model_codes_join(self):
        self.assertEqual(_key("Triple Eight EP 55 Elbow Pads - black"), _key("Triple 8 EP55 Elbow Pads - Black"))
        self.assertNotEqual(_key("Triple Eight EP 55 Elbow Pads - black"), _key("Triple Eight KP 22 Knee Pads - black"))

    def test_vague_open_box_and_unknown_brand_are_not_matched(self):
        self.assertIsNone(_key("Destroyer Knee Pads - Grey/Gold/Black"))
        self.assertIsNone(_key("Demon Podium Helmet w/MIPS - NO ORIGINAL PACKAGING"))
        self.assertIsNone(_key("Nobrand Super Knee Pads - Black"))
        self.assertIsNone(_key("Jason Markk Quick Wipes 3 Pack"))

    def test_one_store_alone_is_not_a_group(self):
        groups = cross_store_groups([
            _gear("Triple Eight Deep Cover Helmet - Navy Matte", "CCS"),
            _gear("Triple Eight Deep Cover Helmet - Navy Matte", "CCS", "35.00"),
        ])
        self.assertEqual(groups, [])


if __name__ == "__main__":
    unittest.main()
