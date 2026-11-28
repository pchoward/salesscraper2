"""The stock check paces each store (store monitor, 2026-11-27): evo
answered 429 to product pages read ~75 ms apart, then refused robots.txt."""

import unittest
from urllib import robotparser

from stores import stock


def allow_all(disallow=""):
    parser = robotparser.RobotFileParser()
    parser.parse(["User-agent: *", f"Disallow: {disallow}"])
    return lambda host: (parser, 0)


class PolitePagesTests(unittest.TestCase):
    def test_spaced_capped_and_robots_checked(self):
        urls = [f"https://www.evo.com/products/{n}" for n in range(5)] + ["https://shop.example/products/a"]
        waits, read = [], []
        pages = stock.polite_pages(urls, fetch=lambda url: read.append(url) or "<html>", policy=allow_all(),
                                   sleep=waits.append, per_store=3)
        self.assertEqual(read, urls[:3] + urls[5:])
        self.assertEqual(waits, [stock.STOCK_DELAY] * 2)  # between one store's pages only
        self.assertEqual(set(pages), set(urls[:3] + urls[5:]))

    def test_a_store_that_says_slow_down_is_left_alone(self):
        urls = [f"https://www.evo.com/products/{n}" for n in range(4)]
        read = []

        def fetch(url):
            read.append(url)
            if len(read) == 2:
                raise stock._Refused(429)
            return "<html>"

        pages = stock.polite_pages(urls, fetch=fetch, policy=allow_all(), sleep=lambda _: None)
        self.assertEqual(read, urls[:2])
        self.assertEqual(list(pages), urls[:1])

    def test_robots_rules_and_unreadable_robots(self):
        urls = ["https://www.evo.com/products/a", "https://www.evo.com/private/b"]
        pages = stock.polite_pages(urls, fetch=lambda url: "<html>", policy=allow_all("/private"), sleep=lambda _: None)
        self.assertEqual(list(pages), urls[:1])
        self.assertEqual(stock.polite_pages(urls, fetch=lambda url: self.fail(url), policy=lambda host: None), {})


if __name__ == "__main__":
    unittest.main()
