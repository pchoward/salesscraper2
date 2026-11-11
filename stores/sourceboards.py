"""Sourceboards sale skateboard gear (sourceboards.com, Shopify).

A Canadian shop (store probe, 2026-11-11, owner approved). Its default store
prices in CAD, so this reads the US storefront (``/en-us``), whose feed and
product pages are in USD; robots.txt allows both. Its sale is mostly apparel
and snow gear, so only the skate sale collections are read. Product types are
paths ("Skateboards - Skate Decks - Sale Skate Decks 25% Off"); the part
comes from the path. That day: 36 decks marked down and in stock; the truck,
wheel and complete sales were empty or sold out.

``python -m stores.sourceboards`` previews what a run would keep.
"""

import re

from stores import shopify

_PATH_PARTS = (
    (r"\bskate\s*decks?\b", "Decks"),
    (r"\bcomplete", "Completes"),
    (r"\bskate\s*trucks?\b|\btrucks?\b", "Trucks"),
    (r"\bskate\s*wheels?\b|\bwheels?\b", "Wheels"),
    (r"\bbearings?\b", "Bearings"),
    (r"\bgrip\s*tape\b|\bhardware\b|\bskate\s*tools?\b|\brisers?\b|\bbushings?\b|\bwax\b", "Accessories"),
)


def path_part(product_type):
    """Sourceboards' type path -> Skate part; cruisers, longboards, snow and apparel stay out."""
    path = str(product_type or "")
    if not re.match(r"\s*skateboard", path, re.I) or re.search(r"cruiser|longboard|surf\s*skate", path, re.I):
        return None
    for pattern, part in _PATH_PARTS:
        if re.search(pattern, path, re.I):
            return part
    return None


SHOP = shopify.ShopifyStore(
    "Sourceboards",
    "Sourceboards",
    "https://www.sourceboards.com/en-us",
    collection="skate-decks-sale",
    more_collections=("sale-skate-decks-25-off", "sale-skate-decks-70", "sale-skateboard-completes",
                      "sale-skate-trucks", "sale-trucks-and-wheels", "sale-skate-tools-and-parts"),
    types={},
    type_part=path_part,
    raw_type_part=True,
    own_vendor="source",
)


def scrapers():
    return shopify.scrapers_for(SHOP)


if __name__ == "__main__":
    raise SystemExit(shopify.preview(SHOP))
