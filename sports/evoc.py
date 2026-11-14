"""EVOC's US shop, evocsports.us (owner, 2026-11-14).

Shopify, prices in dollars; robots.txt is Shopify's standard file and leaves
products and collections open. (evocsports.com is EVOC's European shop, in
euros, so it isn't used.) Markdowns sit in the "outlet" collection and here
and there in the rest of a small catalog (about 220 products), so the whole
catalog is read too; only marked-down variants count, as everywhere.

MTB reads EVOC's bike packs (protector, hydration, hip and day packs) and
its body, knee and elbow armor. Ski reads its snow backpacks, which stay on
the Ski tab (sports/packs.py). The general packs show on every tab, like
other stores' packs. Bike bags, travel cases, duffels, gloves and clothing
are left out.
"""

from sports import brands
from stores import shopify

BASE = "https://evocsports.us"
NAME = "EVOC"

MTB_TYPES = {
    "protector backpacks": "Packs",
    "hydration bags": "Packs",
    "hydration vest": "Packs",
    "hip packs": "Packs",
    "backpacks": "Packs",
    "body armor": "Protection",
    "knee guards": "Protection",
    "elbow and forearm guards": "Protection",
    "shin guards": "Protection",
}
SKI_TYPES = {
    "snow backpacks": "Packs",
    "avalanche backpacks": "Packs",
}


def store(sport, types):
    return shopify.ShopifyStore(NAME, NAME, BASE, collection="outlet", whole_site=True, types=dict(types),
                                type_part=lambda kind: None, only_types=set(types),
                                brand_of=brands.for_sport(sport), track_exclusions=True)
