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
from sports import brands, offers, protection
from sports.bmx import dans, facets, specs
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

# Protection (2026-11-03): helmets, pads, gloves and goggles from every store.
TYPES.update({kind: "Protection" for kind in (
    "protection", "safety gear", "helmets", "helmet", "bmx helmets", "full face helmets", "race helmets",
    "freestyle helmets", "gloves", "glove", "bmx gloves", "pads", "bmx pads", "pad sets", "knee pads",
    "shin pads", "shin guards", "elbow pads", "ankle guards", "wrist guards", "goggles", "padded shirts",
    "body armor")})

# Vague types: the category comes from the title's words.
TYPES.update({"parts": shopify.BY_TITLE, "": shopify.BY_TITLE, "none": shopify.BY_TITLE,
              "codes": shopify.BY_TITLE})  # Albe's files some pads as "codes"


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
    # Keys are the sidebar fields in sports/bmx/facets.py.
    shared = {field["key"]: [item[field["key"]]] for field in facets.FIELDS if item.get(field["key"])}
    # Dan's-style fields: the title's for the whole listing, then each
    # variant's own (a frame's top tube, a hub's drive side, a colour).
    title = product.get("title") or item.get("name") or ""
    shared.update({key: [value] for key, value in dans.listing_fields(title, item.get("part")).items()})
    # Labelled specs from the description: bar rise, crank length, axle, top tube.
    for key, values in dans.description_fields(shopify._plain(product.get("body_html") or ""), item.get("part")).items():
        shared.setdefault(key, values)
    # What a piece protects, helmet style, rotational system (sports/protection.py).
    if item.get("part") == "Protection":
        shared.update(protection.fields(title, product.get("product_type") or "",
                                        shopify._plain(product.get("body_html") or ""), "bmx"))
    offers.attach(item, offers.technical_offers(
        shopify.sale_variants(product), lambda variant: dans.variant_fields(product, variant, item.get("part")),
        shared=shared))


# Each store's protection collections (store probe, 2026-11-03). They hold
# full-price gear too; only marked-down variants are listed, as everywhere.
ALBES_PROTECTION = ("bmx-safety-gear", "bmx-helmets", "bmx-gloves", "bmx-pad-sets", "bmx-knee-pads",
                    "bmx-shin-guards", "bmx-elbow-pads", "bmx-ankle-guards", "fuse-protection", "wrist-guards")
POWERS_PROTECTION = ("protection", "helmets", "freestyle-helmets", "race-helmets", "protection-full-face-helmets",
                     "pads", "pad-sets", "gloves", "goggles", "padded-shirts")
SOURCE_PROTECTION = ("bmx-protection", "bmx-helmets", "bmx-race-helmets", "bmx-pads", "bmx-gloves")

ALBES = shopify.ShopifyStore(
    "Albe's BMX",
    "Albe's BMX",
    "https://www.albes.com",
    collection="bmx-sale-bikes-parts",
    # Its separate bike sale holds ~30 bikes the combined collection misses
    # (store probe, 2026-11-01).
    more_collections=("bmx-bike-sale",) + ALBES_PROTECTION,
    types=TYPES,
    brand_of=brands.for_sport(sports.BMX),
    own_vendor="albe",  # the shop's own name as a vendor is not a brand
    title_part=title_part,
    details=details,
    track_exclusions=True,
)

CIRCUIT = shopify.ShopifyStore(
    "Circuit BMX",
    "Circuit BMX",
    "https://www.circuitbmx.com",
    collection="sale-items",
    more_collections=("protective-wear-and-pads", "helmets"),
    types=TYPES,
    brand_of=brands.for_sport(sports.BMX),
    own_vendor="circuit",
    title_part=title_part,
    details=details,
    track_exclusions=True,
    unknown_by_title=True,
)

# Race and freestyle; sale is "clearance", plus a seasonal Black Friday
# collection while it lasts (a missing collection is skipped, not a failure).
POWERS = shopify.ShopifyStore(
    "Powers BMX",
    "Powers BMX",
    "https://www.powersbmx.com",
    collection="clearance",
    more_collections=("black-friday-deals",) + POWERS_PROTECTION,
    types=TYPES,
    brand_of=brands.for_sport(sports.BMX),
    own_vendor="powers",
    title_part=title_part,
    details=details,
    track_exclusions=True,
    unknown_by_title=True,
)

# Source BMX's US store (separate from the UK site). Its sale is split by
# section; clothing and race-wear sales are left out.
SOURCE_US = shopify.ShopifyStore(
    "Source BMX US",
    "Source BMX (US)",
    "https://us.sourcebmx.com",
    collection="bmx-parts-sale",
    more_collections=("bmx-wheel-sale", "bmx-frame-sale", "bmx-bike-sale") + SOURCE_PROTECTION,
    types=TYPES,
    brand_of=brands.for_sport(sports.BMX),
    own_vendor="source",
    title_part=title_part,
    details=details,
    track_exclusions=True,
    unknown_by_title=True,
)

# Multisport protection brands (owner, 2026-11-03): helmets and pads made for
# skate, BMX and bike alike; snow-only and other sports' gear stays out.
def multisport_part(title):
    if not protection.suits("bmx", title):
        return None
    # Helmets: skate, dirt jump / BMX or full face; not road, trail or snow ones.
    found = protection.fields(title, sport="bmx")
    if "Helmets" in found.get("protects", ()) and set(found.get("helmet_style", ())) & {
            "Road / commuter", "Trail / half shell", "Snow"}:
        return None
    return "Protection"


BRAND_STORES = tuple(protection.brand_store(name, sports.BMX, multisport_part, details=details)
                     for name in ("Triple 8", "187 Killer Pads", "Kali", "Demon", "G-Form"))  # Bern's are commuter lids

# Bike shops' BMX-style protection (owner, 2026-11-03: "very few helmets in
# BMX ... the one thing people wear, then shin or knee guards"). Helmets only
# when dirt jump / BMX or full face (BMX racing needs full face); pads for
# knees, shins, elbows, ankles and hips. Trail, road and snow helmets stay out.
_BMX_PADS = {"Knees", "Shins", "Elbows", "Ankles", "Hips & Tailbone", "Wrists", "Pad Sets", "Chest & Ribs", "Back & Spine"}
_BMX_HELMETS = {"Full face", "Dirt jump / BMX"}
_SHOP_TYPES = {"dirt jump helmets": "Protection", "full face helmets": "Protection", "knee pads": "Protection",
               "knee & shin pads": "Protection", "knee shin pads": "Protection", "arm pads": "Protection",
               "ankle & wrist supports": "Protection", "body armor underwear": "Protection"}


def bike_shop_part(title):
    found = protection.fields(title, sport="bmx")
    kinds = set(found.get("protects", ()))
    if not kinds or not protection.suits("bmx", title):
        return None
    if "Helmets" in kinds:
        return "Protection" if set(found.get("helmet_style", ())) & _BMX_HELMETS else None
    return "Protection" if kinds & _BMX_PADS else None


def bike_shop_type(kind):
    """A bike shop's own type ("Dirt Jump Helmets", "Knee & Shin Pads") decides
    when it says BMX-style; anything else is read from the title."""
    key = " ".join(str(kind or "").lower().split())
    if key in _SHOP_TYPES:
        return _SHOP_TYPES[key]
    # "P23 Helmet", "Bike - Full Face - Zoka": the type names a full-face or
    # dirt jump helmet.
    if "helmet" in key or "full face" in key:
        style = protection.helmet_style("", key)
        if style in _BMX_HELMETS and protection.suits("bmx", key + " helmet"):
            return "Protection"
    # A generic type ("HELMETS", "MTB Helmets"): the title must show it.
    return shopify.BY_TITLE


def bike_shop(name, base, handles):
    return shopify.ShopifyStore(name, name, base, collection=handles[0], more_collections=tuple(handles[1:]), types={},
                                type_part=bike_shop_type, raw_type_part=True, title_part=bike_shop_part,
                                unknown_by_title=True, brand_of=brands.for_sport(sports.BMX), details=details,
                                track_exclusions=True)


BIKE_SHOPS = (
    bike_shop("Colorado Cyclist", "https://www.coloradocyclist.com", ("sale-helmets", "sale-body-armor")),
    bike_shop("Cambria", "https://cambriabike.com", ("dirt-jump-helmets", "full-face-helmets", "knee-pads", "knee-shin-pads")),
    bike_shop("7iDP", "https://7idp.com", ("sale",)),
    bike_shop("Troy Lee Designs", "https://www.troyleedesigns.com", ("troys-garage-bike-sale",)),
    bike_shop("Bikes Online", "https://www.bikesonline.com", ("helmets-on-sale", "cycling-knee-pads", "cycling-body-armor")),
)

STORES = (ALBES, CIRCUIT, POWERS, SOURCE_US) + BRAND_STORES + BIKE_SHOPS

PARTS = sports.BMX.parts


class SkateShopProtection:
    """A Skate shop's Protection scraper, read for BMX (owner, 2026-11-03:
    "show Skate shops' protection in BMX too"). The same helmets and pads
    serve both; snow, road/trail helmets and other sports' gear stay out, and
    each listing gets BMX's protection filters."""

    def __init__(self, inner):
        self.inner = inner
        self.name, self.part, self.url = inner.name, "Protection", getattr(inner, "url", "")

    @property
    def candidates(self):
        return getattr(self.inner, "candidates", 0)

    def scrape(self):
        from stores import skatepro
        items = self.inner.scrape()
        if items is None:
            return None
        kept = []
        for item in items:
            if multisport_part(item.get("name", "")) != "Protection":
                continue
            item = dict(item, part="Protection")
            for key in ("technical_offers", "technical_specs", "kind", "prot_type", "prot_sizes"):
                item.pop(key, None)
            skatepro.bmx_extra(item)
            kept.append(item)
        return kept


def skate_shop_scrapers():
    """The Skate shops that read over plain HTTP (Zumiez and Skate Warehouse
    need a browser, which the BMX/Ski/MTB scrape doesn't run)."""
    from stores import ccs, deathgear, exodus, kinetic, socal, spot, tactics, tgm
    found = []
    for module in (ccs, tactics, tgm, deathgear, kinetic, spot, exodus, socal):
        found.extend(SkateShopProtection(s) for s in module.scrapers() if getattr(s, "part", "") == "Protection")
    return found


def scrapers():
    from stores import skatepro
    shops = [scraper for store in STORES for scraper in shopify.scrapers_for(store, PARTS)]
    return (shops + skatepro.scrapers("bmx", skatepro.bmx_extra)  # BMX helmets, pads, padded shorts
            + skate_shop_scrapers())


def preview(store=ALBES):
    with sports.BMX.active():
        return shopify.preview(store, PARTS)
