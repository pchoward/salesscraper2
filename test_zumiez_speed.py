"""Zumiez sneaker queries follow tracked.yaml and robots.txt. No network."""

import os
import unittest

from stores.zumiez import (
    SHOE_SALE,
    brand_sale_url,
    choose_sneaker_urls,
    explicitly_allowed,
    star_rules,
)
from tracked import load_tracked

FIXTURE = os.path.join(os.path.dirname(__file__), "tests", "fixtures", "zumiez_robots.txt")


def _robots():
    with open(FIXTURE, encoding="utf-8") as handle:
        return handle.read()


class ZumiezRobotsTests(unittest.TestCase):
    def setUp(self):
        self.rules = star_rules(_robots())

    def test_sale_and_brand_filters_are_explicitly_allowed(self):
        self.assertTrue(explicitly_allowed(self.rules, SHOE_SALE))
        self.assertTrue(explicitly_allowed(self.rules, brand_sale_url("Vans")))
        self.assertTrue(explicitly_allowed(self.rules, brand_sale_url("Nike")))
        paged = brand_sale_url("Vans") + "&page=2"
        self.assertTrue(explicitly_allowed(self.rules, paged))

    def test_graphql_search_and_catalog_are_not_explicit_allows(self):
        self.assertFalse(explicitly_allowed(self.rules, "https://www.zumiez.com/graphql"))
        self.assertFalse(explicitly_allowed(self.rules, "https://www.zumiez.com/graphql?query=shoes"))
        self.assertFalse(explicitly_allowed(self.rules, "https://www.zumiez.com/catalogsearch/result/?q=wafflecup"))
        self.assertFalse(explicitly_allowed(self.rules, "https://www.zumiez.com/catalog/product/view/id/1"))

    def test_a_removed_brand_allow_falls_back_to_the_full_sale(self):
        text = "User-agent: *\nDisallow: /*?*customFilters=\nAllow: /*?customFilters=promotion_flag*Sale\n"
        catalog = {"sneakers": [{"id": "vans-wafflecup", "brand": "Vans", "all": [], "any": ["Wafflecup"]}]}
        self.assertEqual(choose_sneaker_urls(catalog, text), [SHOE_SALE])

    def test_a_failed_robots_read_keeps_the_full_sale(self):
        catalog = {"sneakers": [{"id": "vans-wafflecup", "brand": "Vans", "all": [], "any": ["Wafflecup"]}]}
        self.assertEqual(choose_sneaker_urls(catalog, ""), [SHOE_SALE])


class ZumiezSneakerQueryTests(unittest.TestCase):
    def test_tracked_brands_become_sale_queries(self):
        urls = choose_sneaker_urls(load_tracked(), _robots())
        self.assertEqual(
            urls,
            [
                "https://www.zumiez.com/shoes.html?customFilters=brand:Vans;promotion_flag:Sale",
                "https://www.zumiez.com/shoes.html?customFilters=brand:Nike;promotion_flag:Sale",
            ],
        )

    def test_a_new_model_adds_its_brand_without_a_code_change(self):
        catalog = {
            "sneakers": [
                {"id": "vans-wafflecup", "brand": "Vans", "all": [], "any": ["Wafflecup"]},
                {"id": "nike-sb-dunk", "brand": "Nike", "all": ["SB"], "any": ["Dunk Low"]},
                {"id": "emerica-reynolds", "brand": "Emerica", "all": [], "any": ["Reynolds"]},
            ]
        }
        urls = choose_sneaker_urls(catalog, _robots())
        self.assertEqual(urls[-1], brand_sale_url("Emerica"))
        self.assertEqual(len(urls), 3)

    def test_shared_brand_is_one_query_and_a_missing_brand_keeps_the_full_crawl(self):
        shared = {
            "sneakers": [
                {"id": "one", "brand": "Vans", "all": [], "any": ["Wafflecup"]},
                {"id": "two", "brand": "Vans", "all": [], "any": ["Half Cab"]},
            ]
        }
        self.assertEqual(choose_sneaker_urls(shared, _robots()), [brand_sale_url("Vans")])
        missing = {
            "sneakers": [
                {"id": "vans-wafflecup", "brand": "Vans", "all": [], "any": ["Wafflecup"]},
                {"id": "new-model", "brand": "", "all": [], "any": ["Busenitz"]},
            ]
        }
        self.assertEqual(choose_sneaker_urls(missing, _robots()), [SHOE_SALE])

    def test_nike_sb_is_allowed_but_is_not_the_facet_we_query(self):
        # The live facet for SB shoes is Nike. brand:Nike SB returns an empty
        # grid, so the catalog names the facet Nike.
        rules = star_rules(_robots())
        self.assertTrue(explicitly_allowed(rules, brand_sale_url("Nike SB")))
        self.assertIn("brand:Nike%20SB", brand_sale_url("Nike SB"))
        self.assertNotIn("Nike%20SB", "\n".join(choose_sneaker_urls(load_tracked(), _robots())))
