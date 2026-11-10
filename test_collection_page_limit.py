"""Big category collections get more pages (audit 2026-11-10: evo ski-boots
and Cambria sale-components passed 20 pages and every listing in them left
the page)."""

import unittest

from sports.mtb import stores as mtb_stores
from sports.ski import stores as ski_stores
from stores import shopify


def fetcher(pages):
    def fetch(url):
        page = int(url.rsplit("page=", 1)[1])
        size = shopify.PAGE_LIMIT if page < pages else 10
        return {"products": [{"id": f"{page}-{n}", "handle": f"p{page}-{n}"} for n in range(size)]}
    return fetch


class CollectionPageLimitTests(unittest.TestCase):
    def test_default_limit_still_fails_a_runaway_collection(self):
        store = shopify.ShopifyStore("Test", "Test", "https://example.com", collection="sale")
        self.assertIsNone(shopify._read_collection(store, store.sale_json, fetcher(25), lambda _: None))

    def test_store_with_more_pages_reads_it_all(self):
        store = shopify.ShopifyStore("Test", "Test", "https://example.com", collection="ski-boots", max_pages=60)
        products = shopify._read_collection(store, store.sale_json, fetcher(25), lambda _: None)
        self.assertEqual(len(products), 24 * shopify.PAGE_LIMIT + 10)

    def test_evo_and_cambria(self):
        self.assertEqual(ski_stores.EVO.max_pages, 60)
        self.assertEqual(mtb_stores.CAMBRIA.max_pages, 60)


if __name__ == "__main__":
    unittest.main()
