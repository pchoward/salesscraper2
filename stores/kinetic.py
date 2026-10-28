"""Kinetic Skateboarding sale listings (kineticskateboarding.com, Shopify).

Read with the shared Shopify code from ``/collections/sale/products.json``
(robots.txt blocks only admin, cart, and checkout). The sale is mostly
footwear and apparel: "Footwear" is Sneakers (tracked models only), and
"Skateboards" and untyped products get their part from the title, so a
deck and a complete filed together are told apart. Apparel, snowboards,
and other types are skipped.

``python -m stores.kinetic`` previews what a run would keep.
"""

from stores import shopify

SHOP = shopify.ShopifyStore(
    "Kinetic",
    "Kinetic Skateboarding",
    "https://kineticskateboarding.com",
    extra_types={
        "footwear": "Sneakers",
        "footwear midtop": "Sneakers",
        "footwear mid top": "Sneakers",
        "skateboards": shopify.BY_TITLE,
        "skateboard": shopify.BY_TITLE,
        "default": shopify.BY_TITLE,
        "": shopify.BY_TITLE,
    },
    own_vendor="kinetic",
)


def scrapers():
    return shopify.scrapers_for(SHOP)


if __name__ == "__main__":
    raise SystemExit(shopify.preview(SHOP))
