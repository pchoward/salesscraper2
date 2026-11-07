import unittest

import report
from product_specs import enrich

PRODUCT = {"options": [{"name": "Size"}, {"name": "Color"}]}
VARIANTS = [
    {"id": 1, "option1": "149", "option2": "Silver", "available": True, "price": "54.95", "compare_at_price": "64.95"},
    {"id": 2, "option1": "159", "option2": "Silver", "available": False, "price": "56.95"},
    {"id": 3, "option1": "166", "option2": "Silver", "available": True, "price": "58.95"},
]


class TruckOffersTest(unittest.TestCase):
    def test_each_size_keeps_its_own_stock_and_price(self):
        item = enrich({"part": "Trucks", "name": "Independent Stage 11 Standard Truck"}, "", PRODUCT, VARIANTS)
        self.assertEqual([offer["truck_size"] for offer in item["spec_offers"]], ["149", "159", "166"])
        self.assertEqual(item["spec_offers"][2]["price"], 58.95)
        self.assertIs(item["spec_offers"][1]["available"], False)
        self.assertEqual(item["truck_sizes"], ["149", "166"])          # sold-out 159 left out

    def test_no_size_option_adds_nothing(self):
        item = enrich({"part": "Trucks", "name": "Ace AF1 55"}, "", {"options": [{"name": "Title"}]},
                      [{"id": 9, "title": "Default Title", "available": True, "price": "50"}])
        self.assertNotIn("spec_offers", item)
        colors = enrich({"part": "Trucks", "name": "Thunder 148"}, "", {"options": [{"name": "Color"}]},
                        [{"id": 9, "option1": "Black", "available": True, "price": "50"}])
        self.assertNotIn("spec_offers", colors)

    def test_page_still_renders_trucks_with_offers(self):
        item = enrich({"part": "Trucks", "name": "Independent Stage 11 Standard Truck", "store": "TGM",
                       "url": "https://shop.test/indy", "price_new": "54.95", "price_old": "64.95"}, "", PRODUCT, VARIANTS)
        html = report.build_report_html({"TGM_Trucks": [item]}, {}, {}, set(), generated_at="2026-11-07T10:00:00+00:00")
        self.assertIn('data-part="Trucks" data-count="1"', html)


if __name__ == "__main__":
    unittest.main()
