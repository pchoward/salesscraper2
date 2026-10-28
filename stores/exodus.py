"""Exodus Ride Shop sale listings (exodusrideshop.com, Shopify).

Read with the shared Shopify code from ``/collections/sale-1/products.json``.
The storefront's filtered sale page
(``?filter.p.product_type=Decks&filter.p.product_type=...``) is never
requested: Shopify stores disallow multi-filter URLs in robots.txt, so the
feed is filtered by product type here instead. Exodus also sells snow and
apparel; only skate types are candidates, and shoes only for tracked models.

``python -m stores.exodus`` previews what a run would keep.
"""

from stores import shopify

SHOP = shopify.ShopifyStore(
    "Exodus",
    "Exodus Ride Shop",
    "https://exodusrideshop.com",
    collection="sale-1",
    extra_types={
        "shoes": "Sneakers",
        "skate shoes": "Sneakers",
        "footwear": "Sneakers",
        "skateboards": shopify.BY_TITLE,
        "skateboard": shopify.BY_TITLE,
        "complete skateboards": "Completes",
    },
    own_vendor="exodus",
)


def scrapers():
    return shopify.scrapers_for(SHOP)


if __name__ == "__main__":
    raise SystemExit(shopify.preview(SHOP))
