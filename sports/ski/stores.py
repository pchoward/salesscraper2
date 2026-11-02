"""Ski stores. Gear West first: Shopify, with alpine ski and boot closeout
collections (store probe, 2026-11-01: 229 skis, 145 marked down; 228 boots,
174 marked down). Its product types look like "ALPINE - ALPINE SKIS - Park
Skis"; anything not recognised is read from the title's words.
"""

import sports
from sports import brands, offers
from sports.bmx.specs import category_for_title
from sports.ski import specs
from stores import shopify

PARTS = ("Skis", "Boots", "Bindings", "Poles", "Helmets")

TYPES = {
    "skis": "Skis", "kids skis": "Skis", "alpine skis": "Skis",
    "boots": "Boots", "touring boots": "Boots", "all mountain boots": "Boots", "park boots": "Boots",
    "race boots": "Boots", "telemark boots": "Boots", "alpine boots": "Boots",
    "bindings": "Bindings", "alpine bindings": "Bindings",
    "poles": "Poles", "alpine poles": "Poles",
    "helmets": "Helmets", "kids helmets": "Helmets",
}


def type_part(type_key):
    """Gear West's three-level types: "ALPINE - ALPINE SKIS - Park Skis"."""
    for word, part in (("alpine skis", "Skis"), ("alpine boots", "Boots"), ("alpine bindings", "Bindings"),
                       ("alpine poles", "Poles")):
        if word in type_key:
            return part
    return None


def title_part(title):
    return category_for_title(title, sports.SKI.aliases_file())


def details(item, product, type_key):
    variants = shopify.sale_variants(product)
    tags = product.get("tags") or ()
    if isinstance(tags, str):
        tags = [tag.strip() for tag in tags.split(",")]
    if item.get("part") == "Skis":
        found = specs.lengths(product, variants) or specs.title_length(product.get("title"))
        if found:
            item["lengths"] = found
    if item.get("part") == "Boots":
        found = specs.boot_sizes(product, variants)
        if found:
            item["sizes"] = found
    kind = specs.style(product.get("product_type"), tags)
    if kind:
        item["kind"] = kind
    who = specs.gender(product.get("product_type"), tags)
    if who:
        item["gender"] = who
    # Per-variant offers for the sidebar spec filters (sports/offers.py; keys
    # are the fields in sports/ski/facets.py): a
    # ski's length and a boot's mondo size belong to the variant, so a filter
    # shows that variant's price; style and gender are the listing's.
    own = None
    if item.get("part") == "Skis":
        title_cm = specs.title_length(product.get("title"))
        own = lambda variant: {"length": specs.variant_length(product, variant) or title_cm}
    elif item.get("part") == "Boots":
        own = lambda variant: {"mondo": specs.variant_mondo(product, variant)}
    offers.attach(item, offers.technical_offers(variants, own, shared={"style": [kind] if kind else [],
                                                                       "gender": [who] if who else []}))


GEAR_WEST = shopify.ShopifyStore(
    "Gear West",
    "Gear West",
    "https://www.gearwest.com",
    collection="closeout-alpine-skis",
    more_collections=("closeout-alpine-boots",),
    types=TYPES,
    type_part=type_part,
    brand_of=brands.for_sport(sports.SKI),
    own_vendor="gear west",
    title_part=title_part,
    details=details,
    track_exclusions=True,
    unknown_by_title=True,
)

STORES = (GEAR_WEST,)


def scrapers():
    return [scraper for store in STORES for scraper in shopify.scrapers_for(store, PARTS)]


def preview(store=GEAR_WEST):
    with sports.SKI.active():
        return shopify.preview(store, PARTS)
