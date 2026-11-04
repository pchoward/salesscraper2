"""Zumiez decks (2026-11-04): the whole deck category (the Sale flag misses
markdowns and robots.txt disallows the "% off" filter), and a short page is
looked at once more before the walk ends (page 2 painted 51 of 60 cards with
no pager and the run stopped at 98 of 270 decks)."""

import unittest

from stores import zumiez


def page(urls, next_page=None):
    cards = "".join(f'<li class="ProductCard"><a class="ProductCard-Link" href="/p/{u}.html">x</a></li>' for u in urls)
    pager = f'<a class="PaginationLink" href="?page={next_page}">{next_page}</a>' if next_page else ""
    return f"<ul>{cards}</ul>{pager}"


class Walk(zumiez.ZumiezScraper):
    def __init__(self, pages):
        super().__init__("Zumiez", zumiez.DECKS_URL, "Decks")
        self.pages, self.calls = pages, []

    def _fetch_grid(self, url):
        self.calls.append(url)
        key = int(url.rsplit("page=", 1)[1]) if "page=" in url else 1
        queue = self.pages[key]
        return queue.pop(0) if len(queue) > 1 else queue[0]

    def parse(self, html):
        return [{"url": u} for u in zumiez.listing_urls(html)]


class ZumiezPagesTests(unittest.TestCase):
    def test_decks_read_the_whole_category(self):
        self.assertEqual(zumiez.ZumiezDecksScraper().url, "https://www.zumiez.com/skate/skateboard-decks.html")
        self.assertNotIn("percent_off_facet", zumiez.DECKS_URL)

    def test_a_half_painted_page_is_read_again(self):
        first = [f"a{n}" for n in range(60)]
        second_full = [f"b{n}" for n in range(60)]
        walk = Walk({1: [page(first, 2)], 2: [page(second_full[:51]), page(second_full, 3)], 3: [page(["c1", "c2"])]})
        items = walk.scrape()
        self.assertEqual(len(items), 122)

    def test_a_real_last_page_ends_after_one_more_look(self):
        walk = Walk({1: [page([f"a{n}" for n in range(60)], 2)], 2: [page(["b1", "b2", "b3"])]})
        self.assertEqual(len(walk.scrape()), 63)
        self.assertEqual(len(walk.calls), 3, "page 1, page 2, and one more look at page 2")


if __name__ == "__main__":
    unittest.main()
