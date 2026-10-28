"""Skate Park of Tampa (SPoT) sale listings (skateparkoftampa.com, Shopify).

Read with the shared Shopify code from ``/collections/sale/products.json``
(robots.txt blocks only admin, cart, and checkout). SPoT files shoes as
"Shoes" (Sneakers, tracked models only) and decks as "Deck"; T-shirts,
pants, stickers, and other apparel types are skipped.

``python -m stores.spot`` previews what a run would keep.
"""

from stores import shopify

SHOP = shopify.ShopifyStore(
    "SPoT",
    "Skate Park of Tampa",
    "https://skateparkoftampa.com",
    extra_types={"shoes": "Sneakers", "skateboards": shopify.BY_TITLE, "skateboard": shopify.BY_TITLE},
    own_vendor="spot",
)


def scrapers():
    return shopify.scrapers_for(SHOP)


if __name__ == "__main__":
    raise SystemExit(shopify.preview(SHOP))
