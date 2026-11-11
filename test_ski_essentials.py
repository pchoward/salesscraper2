"""Ski Essentials (2026-11-11): headless Shopify read from its .data pages."""

import json
import unittest

import sports
from sports.ski import skiessentials, stores
from stores import shopify, turbo_stream


def page(products):
    """A minimal turbo-stream page: arr[0] is the root, keys are referenced by index."""
    table = [None]

    def add(value):
        table.append(value)
        return len(table) - 1

    def encode(value):
        if isinstance(value, dict):
            index = add(None)
            table[index] = {f"_{add(key)}": encode(item) for key, item in value.items()}
            return index
        if isinstance(value, list):
            index = add(None)
            table[index] = [encode(item) for item in value]
            return index
        return add(value)

    root = {"collection": {"products": {"nodes": products, "pageInfo": {"hasNextPage": False}}}}
    table[0] = table[encode(root)]
    return json.dumps(table) + "\n"


BOOT = {"id": 1, "handle": "nordica-cruise-65", "title": "2023 Nordica Cruise 65 Women's Ski Boots", "vendor": "Nordica",
        "productType": "Alpine Ski > Boot > Alpine", "tags": ["GENDER:Women"], "description": "",
        "featuredImage": {"url": "https://cdn.shopify.com/boot.jpg"}, "images": [],
        "metafields": [{"key": "online_variant_prices", "value": json.dumps({"0506|24": 99, "0506|25": 99})}],
        "variants": [{"id": 11, "title": "24", "sku": "0506|24", "available": True, "compareAtPrice": "249.99",
                      "priceV2": {"amount": "249.99"}, "selectedOptions": [{"name": "size", "value": "24"}]},
                     {"id": 12, "title": "25", "sku": "0506|25", "available": False, "compareAtPrice": "249.99",
                      "priceV2": {"amount": "249.99"}, "selectedOptions": [{"name": "size", "value": "25"}]}]}
NORDIC = dict(BOOT, id=2, handle="xc-boot", title="Alpina Classic Boot", productType="Nordic > Boot > Classic")


class SkiEssentialsTests(unittest.TestCase):
    def test_decode_and_sale_price_from_metafield(self):
        tree = turbo_stream.decode(page([BOOT]))
        nodes = turbo_stream.find(tree, "productType")
        product = skiessentials.to_product(nodes[0])
        self.assertEqual(product["variants"][0]["price"], "99.00")
        self.assertEqual(product["variants"][0]["compare_at_price"], "249.99")
        self.assertEqual(product["options"], [{"name": "size"}])
        self.assertEqual(product["images"], [{"src": "https://cdn.shopify.com/boot.jpg"}])

    def test_no_online_price_means_no_markdown(self):
        plain = dict(BOOT, metafields=[])
        product = skiessentials.to_product(plain)
        self.assertIsNone(product["variants"][0]["compare_at_price"])

    def test_paths(self):
        self.assertEqual(skiessentials.path_part("Alpine Ski > Ski > Alpine > Flat"), "Skis")
        self.assertEqual(skiessentials.path_part("Alpine Ski > Helmet > Snowsport > Non Visor"), "Helmets")
        self.assertIsNone(skiessentials.path_part("Nordic > Boot > Classic"))
        self.assertIsNone(skiessentials.path_part("Alpine Ski > Sock > Over The Calf"))

    def test_store_lists_marked_down_alpine_gear(self):
        pages = {f"{skiessentials.BASE}/collections/{h}.data": page([BOOT, NORDIC]) for h in skiessentials.COLLECTIONS}
        products = skiessentials.load_products(fetch=pages.get, sleep=lambda _: None)
        self.assertEqual(len(products), 2)  # each product once across collections
        shop = stores.SKI_ESSENTIALS
        with sports.SKI.active():
            scraper = [s for s in shopify.scrapers_for(shop, stores.PARTS) if s.part == "Boots"][0]
            items = scraper.products_from(products)
        self.assertEqual([(i["name"], i["price_new"], i["price_old"]) for i in items],
                         [("2023 Nordica Cruise 65 Women's Ski Boots", "99.00", "249.99")])

    def test_failed_first_collection_fails_the_store(self):
        self.assertIsNone(skiessentials.load_products(fetch=lambda url: None, sleep=lambda _: None))

    def test_registered(self):
        self.assertIn(stores.SKI_ESSENTIALS, stores.STORES)


if __name__ == "__main__":
    unittest.main()
