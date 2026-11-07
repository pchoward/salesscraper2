"""Zeitbike: TSG's US distributor (owner, 2026-11-07).

TSG's own shop (ridetsg.com) ships only within Europe, and the US partner it
links to is a parked domain. Zeitbike carries TSG's whole US line and files
each piece by sport in its tags ("Category_Products/Helmets (Skate)",
"Pads (Bike)", "Helmets (Snow)"), which is surer than reading titles: a
downhill full face and a skate lid both just say "Helmet". Spare parts
(cheek pads, visors, liners, recaps, replacement lenses) and shop displays
are left out. A piece is listed only while it is marked down.

MTB also gets NEWMEN's wheels, bars, stems and posts; Zeitbike's other
brands (Ergotec city parts, Mondraker spares) aren't read.
"""

import re

BASE = "https://www.zeitbike.com"
NAME = "Zeitbike"

_SPARE_TYPES = {"protective spareparts", "banners", "accessories", "clothing", "helmet rack", "helmet hanger"}
_SPARE = re.compile(r"\b(?:cheek\s*pads?|pad\s*kits?|ear\s*pads?|liners?|visors?|recaps?|replacement|spare"
                    r"|display|hangers?|racks?|banners?|covers?)\b", re.I)
_FULL_FACE = re.compile(r"\bfull[\s-]*face\b|\bsentinel\b|\bdownhill\b", re.I)


def _categories(tags):
    return {str(tag).split("/", 1)[1] for tag in tags or () if str(tag).startswith("Category_Products/")}


def part(sport_id, product_type, title, tags):
    """The sport's category for a Zeitbike TSG product, or None."""
    kind = " ".join(str(product_type or "").lower().split())
    if kind in _SPARE_TYPES or _SPARE.search(str(title or "")):
        return None
    cats = _categories(tags)
    tags = {str(tag).lower() for tag in tags or ()}
    if "model_sales-support" in tags or "protective-spareparts" in tags:
        return None
    if sport_id == "skate":
        return "Protection" if cats & {"Helmets (Skate)", "Pads (Skate)"} else None
    if sport_id == "bmx":
        if cats & {"Helmets (Skate)", "Pads (Skate)", "Pads (Bike)"}:
            return "Protection"
        # BMX racing wears full face; trail and road lids stay out.
        return "Protection" if "Helmets (Bike)" in cats and _FULL_FACE.search(title or "") else None
    if sport_id == "mtb":
        return "Protection" if cats & {"Helmets (Bike)", "Pads (Bike)"} else None
    if sport_id == "ski":
        if "Helmets (Snow)" in cats:
            return "Helmets"
        if kind == "eyewear" and "activity_snowboarding" in tags:
            return "Protection"           # winter goggles
        return None
    return None


def is_tsg(tags):
    return any(str(tag) == "Category_Brands/TSG" for tag in tags or ()) or "tsg" in {str(t).lower() for t in tags or ()}


def store(sport, collections=("tsg",), fallback=None, **options):
    """Zeitbike as a ``sport`` store: TSG by its tags; other brands (MTB's
    NEWMEN) by ``fallback(product_type, title)``."""
    from sports import brands
    from stores import shopify

    def product_part(product_type, title, tags):
        if is_tsg(tags) or re.match(r"\s*tsg\b", str(title or ""), re.I):
            return part(sport.id, product_type, title, tags)
        return fallback(product_type, title) if fallback else None

    return shopify.ShopifyStore(NAME, NAME, BASE, collection=collections[0], more_collections=tuple(collections[1:]),
                                types={}, brand_of=brands.for_sport(sport), product_part=product_part,
                                track_exclusions=True, **options)
