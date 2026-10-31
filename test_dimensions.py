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

    def test_wheelbase_as_stores_write_it(self):
        for text in ('Wheelbase: 14.25"', "WB 14.25", '14.25" WB', "Wheel Base: 14.25", "wheel-base 14.25",
                     "Wheelbase (in) 14.25", "Wheelbase - 14.25 inches", 'Wheelbase: 14 1/4"', "wheelbase 14-1/4",
                     "Wheelbase: 14\u00bc\"", "14.25 inch wheelbase", "The wheelbase is 14.25"):
            self.assertEqual(extract_specs("Baker Deck 8.25", text)["wheelbase"], 14.25, text)

    def test_wheelbase_is_never_a_guess(self):
        # A width or length next to "WB" is not a wheelbase.
        self.assertIsNone(extract_specs("Baker Deck 8.25", "wb 8.25")["wheelbase"])
        self.assertIsNone(extract_specs("Baker Deck 8.25", "8.25 x 31.875 WB")["wheelbase"])
        # A page with every size: the deck's own width picks its wheelbase.
        sizes = '8.0" x 31.5" WB 14 | 8.25" x 31.875" WB 14.25 | 8.5" x 32" WB 14.38'
        self.assertEqual(extract_specs("Baker Deck 8.25", sizes)["wheelbase"], 14.25)
        self.assertEqual(extract_specs("Baker Deck 8.5", sizes)["wheelbase"], 14.38)
        self.assertEqual(extract_specs("Baker Deck 8.0", sizes)["wheelbase"], 14.0)
        # Several wheelbases and no matching width: nothing rather than a wrong one.
        self.assertIsNone(extract_specs("Baker Deck 8.6", sizes)["wheelbase"])
        self.assertIsNone(extract_specs("Baker Deck", sizes)["wheelbase"])
        # CCS lists each shape's specs; nose and tail (7.00") are not widths.
        shapes = ('Width: 8.0" Length: 31.75" Nose: 7.00" Tail: 6.50" Wheelbase: 14.25" "Agile 8" Shape. '
                  'Width: 8.5" Length: 32.50" Nose: 7.25" Tail: 6.75" Wheelbase: 14.125" "Sect 8.5" Shape')
        self.assertEqual(extract_specs("Habitat Deck 8.0", shapes)["wheelbase"], 14.25)
        self.assertEqual(extract_specs("Habitat Deck 8.5", shapes)["wheelbase"], 14.125)
        self.assertIsNone(extract_specs("Habitat Deck 7.0", shapes)["wheelbase"])
        self.assertIsNone(extract_specs("Habitat Skateboard Deck", shapes)["wheelbase"], "no width of its own: no guess")
        # The same value said twice is still one wheelbase.
        self.assertEqual(extract_specs("Baker Deck 8.25", "Wheelbase: 14.25. WB 14.25")["wheelbase"], 14.25)


if __name__ == "__main__":
    unittest.main()
