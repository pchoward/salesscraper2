"""Dimension normalization. 8.5 and 8.50 are the same width."""

import unittest

from dimensions import (
    dimension_key,
    dimensions_match,
    extract_specs,
    normalize_dimension,
    parse_dimension,
)


class DimensionTests(unittest.TestCase):
    def test_eight_five_matches_eight_fifty(self):
        for value in (8.5, "8.5", "8.50", "8.500", '8.50"', "8.5 in", "8.5 inches"):
            self.assertEqual(normalize_dimension(value), 8.5)
            self.assertTrue(dimensions_match(value, "8.50"))
            self.assertEqual(dimension_key(value), "8.5")

    def test_eighths_stay_distinct(self):
        self.assertEqual(dimension_key("8.25"), "8.25")
        self.assertEqual(dimension_key("8.125"), "8.125")
        self.assertFalse(dimensions_match("8.125", "8.12"))
        self.assertFalse(dimensions_match("8.5", "8.25"))
        self.assertIsNone(parse_dimension("about 8.5"))
        self.assertIsNone(parse_dimension(""))

    def test_width_length_and_wheelbase(self):
        specs = extract_specs("Baker Team Deck 8.25 x 32")
        self.assertEqual(specs["width"], 8.25)
        self.assertEqual(specs["length"], 32.0)
        self.assertIsNone(specs["wheelbase"])

        specs = extract_specs("Heroin Egg 8.75", "Wheelbase: 14.25 inches")
        self.assertEqual(specs["width"], 8.75)
        self.assertEqual(specs["wheelbase"], 14.25)

        specs = extract_specs("Anti Hero Caster Deck 8.6 WB 14.5")
        self.assertEqual(specs["width"], 8.6)
        self.assertEqual(specs["wheelbase"], 14.5)


if __name__ == "__main__":
    unittest.main()
