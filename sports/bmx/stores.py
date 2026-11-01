"""BMX stores. Each returns scrapers like stores/registry.py's skate stores.

Circuit BMX second (Shopify, a smaller sale collection). Its product types
weren't sampled yet, so types not in TYPES are sorted by title words; the
scrape log's feed summary shows what it holds.

Albe's BMX first: Shopify, with a sale collection of ~750 bikes and parts
(store probe, 2026-11-01). Its product types map to the BMX categories
(sports/__init__.py, grouped like Dan's Comp and Circuit BMX); types not
listed are skipped. ``python -c "from sports.bmx import stores;
stores.preview()"`` shows what a live run would keep without saving anything.
"""

import sports
from sports import brands
from sports.bmx import specs
from stores import shopify

# Shopify product_type (lowercased, punctuation dropped) -> BMX category.
TYPES = {
    "bmx bikes": "Bikes", "bmx bike": "Bikes", "bikes": "Bikes", "complete bikes": "Bikes",
    "frames": "Frames & Forks", "frame": "Frames & Forks", "forks": "Frames & Forks", "fork": "Frames & Forks",
    "bars": "Steering", "handlebars": "Steering", "stems": "Steering", "stem": "Steering", "grips": "Steering",
    "headsets": "Steering", "headset": "Steering", "bar ends": "Steering", "detanglers": "Steering",
    "gyros": "Steering",
    "cranks": "Drivetrain", "crank": "Drivetrain", "sprockets": "Drivetrain", "sprocket": "Drivetrain",
    "chains": "Drivetrain", "chain": "Drivetrain", "bottom brackets": "Drivetrain", "bottom bracket": "Drivetrain",
    "pedals": "Drivetrain", "chain tensioners": "Drivetrain", "tensioners": "Drivetrain",
    "wheels": "Wheels", "wheel": "Wheels", "wheelsets": "Wheels",
    "hubs": "Wheel Parts", "hub": "Wheel Parts", "rims": "Wheel Parts", "rim": "Wheel Parts",
    "spokes": "Wheel Parts", "spokes nipples": "Wheel Parts", "nipples": "Wheel Parts", "axles": "Wheel Parts",
    "hub guards": "Wheel Parts", "pegs": "Wheel Parts", "drivers": "Wheel Parts", "freewheels": "Wheel Parts",
    "rim strips": "Wheel Parts", "valve caps": "Wheel Parts",
    "tires": "Tires", "tire": "Tires", "tubes": "Tires", "tube": "Tires",
    "seats": "Seating", "seat": "Seating", "seat posts": "Seating", "seat post": "Seating",
    "seatposts": "Seating", "seat clamps": "Seating", "seat post clamps": "Seating",
    "brakes": "Braking", "brake": "Braking", "brake levers": "Braking", "levers": "Braking",
    "brake cables": "Braking", "cables": "Braking", "brake parts": "Braking", "brake pads": "Braking",
    "grips bar ends": "Steering", "bar ends": "Steering", "handlebar": "Steering", "bmx bars": "Steering",
    "bmx frames": "Frames & Forks", "bmx forks": "Frames & Forks", "bmx wheels": "Wheels",
    "bmx tires": "Tires", "bmx hubs": "Wheel Parts", "hubguards": "Wheel Parts", "hub guard": "Wheel Parts",
    "spoke": "Wheel Parts", "rim strip": "Wheel Parts", "valve cap": "Wheel Parts", "peg": "Wheel Parts",
    "seat clamp": "Seating", "seat post clamp": "Seating", "seatpost": "Seating", "seat posts clamps": "Seating",
    "cranksets": "Drivetrain", "crank arms": "Drivetrain", "spindles": "Drivetrain", "chainrings": "Drivetrain",
    "pedal": "Drivetrain", "chain tensioner": "Drivetrain", "bb": "Drivetrain",
}

# Vague types: the category comes from the title's words.
TYPES.update({"parts": shopify.BY_TITLE, "": shopify.BY_TITLE, "none": shopify.BY_TITLE})


def title_part(title):
    return specs.category_for_title(title, sports.BMX.aliases_file())


def details(item, product, kind_key):
    """kind and wheel_size for the filters (sports/bmx/specs.py)."""
    kind = specs.kind_for(kind_key, item.get("name"), item.get("part"))
    if kind:
        item["kind"] = kind
    size = specs.wheel_size(product.get("title") or item.get("name"), product.get("tags") or ())
    if size:
        item["wheel_size"] = size


ALBES = shopify.ShopifyStore(
    "Albe's BMX",
    "Albe's BMX",
    "https://www.albes.com",
    collection="bmx-sale-bikes-parts",
    types=TYPES,
    brand_of=brands.for_sport(sports.BMX),
    own_vendor="albe",  # the shop's own name as a vendor is not a brand
    title_part=title_part,
    details=details,
)

CIRCUIT = shopify.ShopifyStore(
    "Circuit BMX",
    "Circuit BMX",
    "https://www.circuitbmx.com",
    collection="sale-items",
    types=TYPES,
    brand_of=brands.for_sport(sports.BMX),
    own_vendor="circuit",
    title_part=title_part,
    details=details,
    unknown_by_title=True,
)

STORES = (ALBES, CIRCUIT)

PARTS = ("Bikes", "Frames & Forks", "Steering", "Drivetrain", "Wheels", "Wheel Parts", "Tires", "Seating", "Braking")


def scrapers():
    return [scraper for store in STORES for scraper in shopify.scrapers_for(store, PARTS)]


def preview(store=ALBES):
    with sports.BMX.active():
        return shopify.preview(store, PARTS)
