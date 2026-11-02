"""BMX stores. Each returns scrapers like stores/registry.py's skate stores.

Circuit BMX second (Shopify, a smaller sale collection); then Powers BMX
and Source BMX's US store, both Shopify with several sale collections. Its product types
weren't sampled yet, so types not in TYPES are sorted by title words; the
scrape log's feed summary shows what it holds.

Albe's BMX first: Shopify, with a sale collection of ~750 bikes and parts
(store probe, 2026-11-01). Its product types map to the BMX categories
(sports/__init__.py, grouped like Dan's Comp and Circuit BMX); types not
listed are skipped. ``python -c "from sports.bmx import stores;
stores.preview()"`` shows what a live run would keep without saving anything.
"""

import re

import sports
from sports import brands, offers
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

# Powers BMX and Source BMX (US) types, from the store probe (2026-11-01).
TYPES.update({
    "hubsets": "Wheel Parts", "hub parts": "Wheel Parts", "bmx hub spares": "Wheel Parts", "bmx rear hubs": "Wheel Parts",
    "bmx front hubs": "Wheel Parts", "bmx rims": "Wheel Parts", "rim": "Wheel Parts",
    "stock rear wheels": "Wheels", "stock front wheels": "Wheels", "bmx wheels": "Wheels", "bmx wheelsets": "Wheels",
    "bmx innertubes": "Tires", "innertubes": "Tires", "bmx tyres": "Tires", "tyres": "Tires", "bmx tires": "Tires",
    "bmx race frames": "Frames & Forks", "bmx forks": "Frames & Forks", "bmx fork top caps": "Frames & Forks",
    "bmx seats": "Seating", "bmx seat clamps": "Seating", "bmx seat posts": "Seating",
    "bmx sprockets": "Drivetrain", "bmx pedals": "Drivetrain", "bmx cranks": "Drivetrain", "bmx chains": "Drivetrain",
    "bmx bottom brackets": "Drivetrain",
    "bmx brakes": "Braking", "bmx brake cables": "Braking", "bmx brake levers": "Braking",
    "bmx handlebars": "Steering", "bmx stems": "Steering", "bmx headsets": "Steering", "bmx grips": "Steering",
    "bmx race bikes": "Bikes", "race bmx mini": "Bikes", "race bmx": "Bikes", "complete bike": "Bikes",
    "chainring": "Drivetrain", "freewheel cogs": "Wheel Parts", "bmx brake spares": "Braking",
    "bmx bar ends": "Steering", "bar end": "Steering", "bmx spokes": "Wheel Parts", "bmx gyro kits": "Steering",
    "bmx gyro cables": "Steering", "bmx crank spindles etc": "Drivetrain", "bmx brake pads": "Braking",
    "bmx disc brakes": "Braking", "bmx front hubs": "Wheel Parts", "bmx grips": "Steering", "bmx chains": "Drivetrain",
    "bmx frames": "Frames & Forks", "pegs": "Wheel Parts", "chains": "Drivetrain",
})

# Vague types: the category comes from the title's words.
TYPES.update({"parts": shopify.BY_TITLE, "": shopify.BY_TITLE, "none": shopify.BY_TITLE})


# A title names a whole bike only when it ends with "bike" (maybe a model
# year or colour after it) or says "complete bike". "Bikes" inside a brand
# ("SE Bikes Padset", "SE Bikes Bike Life Number plate") doesn't count.
_WHOLE_BIKE = re.compile(r"\bcomplete bike\b|\bbike(?:\s+(?:19|20)\d\d)?(?:\s+[a-z]+(?:/[a-z]+)+)?\s*$", re.I)


def title_part(title):
    """A category from the title, for vague or unknown store types."""
    category = specs.category_for_title(title, sports.BMX.aliases_file())
    if category == "Bikes" and not _WHOLE_BIKE.search(str(title or "").strip()):
        return None
    return category


def details(item, product, kind_key):
    """kind and wheel_size for the filters (sports/bmx/specs.py)."""
    kind = specs.kind_for(kind_key, item.get("name"), item.get("part"))
    if kind:
        item["kind"] = kind
    size = specs.wheel_size(product.get("title") or item.get("name"), product.get("tags") or ())
    if size:
        item["wheel_size"] = size
    # Dan's-style deal type: Source files these under the vendor "Scratch & Dent".
    marks = [str(product.get("vendor") or "")] + [str(tag) for tag in product.get("tags") or ()]
    if any("scratch" in mark.casefold() and "dent" in mark.casefold() for mark in marks):
        item["condition"] = "Scratch & Dent"
    # Per-variant offers for the sidebar spec filters (sports/offers.py).
    # BMX specs are the listing's own, so every sale variant shares them.
    offers.attach(item, offers.technical_offers(shopify.sale_variants(product), shared={
        key: [item[key]] for key in specs.FIELDS if item.get(key)}))


ALBES = shopify.ShopifyStore(
    "Albe's BMX",
    "Albe's BMX",
    "https://www.albes.com",
    collection="bmx-sale-bikes-parts",
    # Its separate bike sale holds ~30 bikes the combined collection misses
    # (store probe, 2026-11-01).
    more_collections=("bmx-bike-sale",),
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

# Race and freestyle; sale is "clearance", plus a seasonal Black Friday
# collection while it lasts (a missing collection is skipped, not a failure).
POWERS = shopify.ShopifyStore(
    "Powers BMX",
    "Powers BMX",
    "https://www.powersbmx.com",
    collection="clearance",
    more_collections=("black-friday-deals",),
    types=TYPES,
    brand_of=brands.for_sport(sports.BMX),
    own_vendor="powers",
    title_part=title_part,
    details=details,
    unknown_by_title=True,
)

# Source BMX's US store (separate from the UK site). Its sale is split by
# section; clothing and race-wear sales are left out.
SOURCE_US = shopify.ShopifyStore(
    "Source BMX US",
    "Source BMX (US)",
    "https://us.sourcebmx.com",
    collection="bmx-parts-sale",
    more_collections=("bmx-wheel-sale", "bmx-frame-sale", "bmx-bike-sale"),
    types=TYPES,
    brand_of=brands.for_sport(sports.BMX),
    own_vendor="source",
    title_part=title_part,
    details=details,
    unknown_by_title=True,
)

STORES = (ALBES, CIRCUIT, POWERS, SOURCE_US)

PARTS = ("Bikes", "Frames & Forks", "Steering", "Drivetrain", "Wheels", "Wheel Parts", "Tires", "Seating", "Braking")


def scrapers():
    return [scraper for store in STORES for scraper in shopify.scrapers_for(store, PARTS)]


def preview(store=ALBES):
    with sports.BMX.active():
        return shopify.preview(store, PARTS)
