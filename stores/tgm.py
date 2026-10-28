"""TGM Skateboards sale listings (tgmskateboards.com, a US Shopify store).

The shared Shopify code (``stores/shopify.py``) reads
``/collections/sale/products.json?limit=250&page=N`` page by page. robots.txt
allows collections but disallows ``sort_by`` and multi-filter URLs, so the
storefront's filtered pages are never requested; products are sorted by
their Shopify ``product_type`` instead.

* Kept types: Decks, Wheels, Trucks, Bearings, Grip Tape, Hardware, Risers,
  and Tool (as Accessories), Completes, Mens Shoes (as Sneakers), and
  protective gear types such as Helmets, Combo Pads, and Elbow Pads (as
  Protection). Everything else (clothing, Disc, Roller Hockey, ...) is
  skipped before the filters.
* A variant is on sale only when ``compare_at_price`` is above ``price``.

``python -m stores.tgm`` previews what a run would keep without writing
anything.
"""

import time

from stores import shopify

STORE = "TGM"
DISPLAY_NAME = "TGM Skateboards"
BASE = "https://tgmskateboards.com"
SHOP = shopify.ShopifyStore(STORE, DISPLAY_NAME, BASE, extra_types={"mens shoes": "Sneakers"}, own_vendor="tgm")
SALE_JSON = SHOP.sale_json
PAGE_DELAY = shopify.PAGE_DELAY
PARTS = shopify.ALL_PARTS
PART_BY_TYPE = SHOP.types


def part_for_type(product_type):
    """The report part for a TGM product type, or None to skip it."""
    return shopify.part_for(SHOP, product_type)


def load_sale_products(fetch=None, sleep=time.sleep):
    return shopify.load_sale_products(SHOP, fetch, sleep)


def _title(product):
    return shopify.title_with_brand(product, SHOP.own_vendor)


class TGMScraper(shopify.ShopifyScraper):
    """One part from the shared TGM sale feed."""

    def __init__(self, part):
        super().__init__(SHOP, part)


def scrapers():
    return [TGMScraper(part) for part in PARTS]


def main():
    return shopify.preview(SHOP)


if __name__ == "__main__":
    raise SystemExit(main())
