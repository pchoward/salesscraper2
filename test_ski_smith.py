"""Smith snow goggles and helmets in Ski (owner, 2026-11-06)."""

import unittest

from stores import shopify


class SkiSmithTests(unittest.TestCase):
    def test_smith_snow_goggles_and_helmets_only(self):
        from sports.ski import stores as ski
        from sports import rules
        cases = {("Smith 4D MAG - Past Season", "Goggles"): "Protection",
                 ("Smith Survey Mips® - Past Season", "Helmet"): "Helmets",
                 ("Smith Method Round Contour Fit - Past Season", "Helmet"): "Helmets",
                 ("Smith Forefront 3 Mips® - Past Season", "Helmet"): None,  # bike helmet
                 ("Smith Lowdown 2", "Sunglass"): None}
        for (title, kind), part in cases.items():
            self.assertEqual(shopify.part_for(ski.SMITH, kind, title), part, title)
        self.assertEqual(rules.ski("Smith Rhythm MTB - Past Season", "Protection"), "bike gear")
        self.assertIsNone(rules.ski("Smith Squad MAG - Past Season", "Protection"))
        self.assertIn(ski.SMITH, ski.STORES)
        self.assertTrue(ski.SMITH.whole_site)


if __name__ == "__main__":
    unittest.main()
