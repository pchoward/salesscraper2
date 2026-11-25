"""robots.txt is checked on every Shopify scrape (owner, 2026-11-22)."""

import io
import unittest
from unittest.mock import patch
from urllib import robotparser
from urllib.error import HTTPError

from stores import shopify


def policy(text, delay=0):
    parser = robotparser.RobotFileParser()
    parser.parse(text.splitlines())
    return parser, max(shopify.PAGE_DELAY, delay)


def store():
    return shopify.ShopifyStore("Shop", "Shop", "https://shop.example", collection="sale")


PAGE = {"products": [{"id": 1, "handle": "a", "title": "A", "variants": []}]}


class RobotsEveryRun(unittest.TestCase):
    def test_disallowed_store_is_not_requested_and_counts_as_failed(self):
        shop = store()
        with patch("stores.shopify.robots_policy", return_value=policy("User-agent: *\nDisallow: /")), \
                patch("stores.shopify._fetch_json", return_value=PAGE) as fetch:
            self.assertIsNone(shopify.load_sale_products(shop, sleep=lambda s: None))
        fetch.assert_not_called()

    def test_unreadable_robots_fails_closed(self):
        shop = store()
        with patch("stores.shopify.robots_policy", return_value=None), \
                patch("stores.shopify._fetch_json", return_value=PAGE) as fetch:
            self.assertIsNone(shopify.load_sale_products(shop, sleep=lambda s: None))
        fetch.assert_not_called()

    def test_allowed_store_is_read_and_policy_read_once(self):
        shop = store()
        with patch("stores.shopify.robots_policy", return_value=policy("User-agent: *\nDisallow: /cart")) as read, \
                patch("stores.shopify._fetch_json", return_value=PAGE):
            self.assertEqual(len(shopify.load_sale_products(shop, sleep=lambda s: None)), 1)
            shopify.enrich_stock(shop, [], "Decks")
        self.assertEqual(read.call_count, 1)

    def test_crawl_delay_stretches_pauses(self):
        shop = store()
        shop.sale_jsons = [shop.sale_json, "https://shop.example/collections/more/products.json"]
        waits = []
        with patch("stores.shopify.robots_policy", return_value=policy("User-agent: *\nAllow: /", delay=7)), \
                patch("stores.shopify._fetch_json", return_value=PAGE):
            shopify.load_sale_products(shop, sleep=waits.append)
        self.assertEqual(waits, [7])

    def test_injected_fetch_is_left_alone(self):
        shop = store()
        with patch("stores.shopify.robots_policy") as read:
            self.assertEqual(len(shopify.load_sale_products(shop, fetch=lambda url: PAGE, sleep=lambda s: None)), 1)
        read.assert_not_called()

    def test_robots_policy_reading(self):
        def opened(body):
            class Response(io.BytesIO):
                def __enter__(self):
                    return self

                def __exit__(self, *args):
                    return False
            return Response(body.encode())

        with patch("urllib.request.urlopen", return_value=opened("User-agent: *\nDisallow: /\n")):
            parser, delay = shopify.robots_policy("https://shop.example")
            self.assertFalse(parser.can_fetch(shopify._USER_AGENT, "https://shop.example/collections/sale/products.json"))
        with patch("urllib.request.urlopen", return_value=opened("<html>Attention Required</html>")):
            self.assertIsNone(shopify.robots_policy("https://shop.example"))
        missing = HTTPError("https://shop.example/robots.txt", 404, "Not Found", {}, None)
        with patch("urllib.request.urlopen", side_effect=missing):
            parser, delay = shopify.robots_policy("https://shop.example")
            self.assertTrue(parser.can_fetch(shopify._USER_AGENT, "https://shop.example/collections/sale/products.json"))
        blocked = HTTPError("https://shop.example/robots.txt", 403, "Forbidden", {}, None)
        with patch("urllib.request.urlopen", side_effect=blocked):
            self.assertIsNone(shopify.robots_policy("https://shop.example"))


if __name__ == "__main__":
    unittest.main()
