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

    def test_nearly_full_pages_are_not_the_last(self):
        # evo, 2026-11-26: pages of 247, 240, 237 ... then 183. Stopping at
        # the first page short of 250 read only page 1 of each collection.
        sizes = [247, 240, 237, 238, 183]
        pages = []

        def fetch(url):
            page = int(url.rsplit("page=", 1)[1])
            pages.append(page)
            size = sizes[page - 1] if page <= len(sizes) else 0
            return {"products": [{"id": f"{page}-{n}"} for n in range(size)]}

        store = shopify.ShopifyStore("evo", "evo", "https://www.evo.com", collection="skateboards")
        products = shopify._read_collection(store, store.sale_json, fetch, lambda _: None)
        self.assertEqual(len(products), sum(sizes))
        self.assertEqual(pages, [1, 2, 3, 4, 5])  # 183 is under LAST_PAGE_UNDER: no extra request

    def test_a_nearly_full_last_page_costs_one_empty_page(self):
        sizes = [250, 241]
        pages = []

        def fetch(url):
            page = int(url.rsplit("page=", 1)[1])
            pages.append(page)
            return {"products": [{"id": f"{page}-{n}"} for n in range(sizes[page - 1] if page <= 2 else 0)]}

        store = shopify.ShopifyStore("Test", "Test", "https://example.com", collection="sale")
        self.assertEqual(len(shopify._read_collection(store, store.sale_json, fetch, lambda _: None)), 491)
        self.assertEqual(pages, [1, 2, 3])

    def test_evo_and_cambria(self):
        self.assertEqual(ski_stores.EVO.max_pages, 60)
        self.assertEqual(mtb_stores.CAMBRIA.max_pages, 60)


if __name__ == "__main__":
    unittest.main()
