"""Ski stores. Gear West first, then Utah Ski (tag-based categories). Gear West: Shopify, with alpine ski and boot closeout
collections (store probe, 2026-11-01: 229 skis, 145 marked down; 228 boots,
174 marked down). Its product types look like "ALPINE - ALPINE SKIS - Park
Skis"; anything not recognised is read from the title's words.
"""

import re

import sports
from sports import brands, offers
from sports.bmx.specs import category_for_title
from sports.ski import evo, specs
from stores import shopify

PARTS = sports.SKI.parts

TYPES = {
    "skis": "Skis", "kids skis": "Skis", "alpine skis": "Skis",
    "boots": "Boots", "touring boots": "Boots", "all mountain boots": "Boots", "park boots": "Boots",
    "race boots": "Boots", "telemark boots": "Boots", "alpine boots": "Boots",
    "bindings": "Bindings", "alpine bindings": "Bindings",
    "poles": "Poles", "alpine poles": "Poles",
    "helmets": "Helmets", "kids helmets": "Helmets",
    # Protection (2026-11-03): goggles and armor; "Eyewear" also holds sunglasses, so its title decides.
    "goggles": "Protection", "eyewear": shopify.BY_TITLE,
}


def type_part(type_key):
    """Gear West's three-level types: "ALPINE - ALPINE SKIS - Park Skis"."""
    for word, part in (("alpine skis", "Skis"), ("alpine boots", "Boots"), ("alpine bindings", "Bindings"),
                       ("alpine poles", "Poles"), ("helmets goggles helmets", "Helmets"),
                       ("helmets goggles goggles", "Protection")):
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
        # The filter groups lengths into 10 cm ranges; exact lengths stay in "lengths".
        own = lambda variant: {"length": [specs.length_range(cm) for cm in
                                          (specs.variant_length(product, variant) or title_cm)]}
    elif item.get("part") == "Boots":
        own = lambda variant: {"mondo": specs.variant_mondo(product, variant)}
    elif item.get("part") in ("Helmets", "Protection"):
        from sports import protection
        own = lambda variant: {"prot_size": protection.variant_size(product, variant)}
    # evo-style fields from the title, type, tags and description (sports/ski/evo.py).
    shared = evo.fields(item.get("part"), product.get("title") or item.get("name"), product.get("product_type"),
                        tags, shopify._plain(product.get("body_html") or ""))
    if who:
        shared["gender"] = [who]
    offers.attach(item, offers.technical_offers(variants, own, shared=shared))


GEAR_WEST = shopify.ShopifyStore(
    "Gear West",
    "Gear West",
    "https://www.gearwest.com",
    collection="closeout-alpine-skis",
    more_collections=("closeout-alpine-boots", "helmets-protection", "eyewear"),
    types=TYPES,
    type_part=type_part,
    brand_of=brands.for_sport(sports.SKI),
    own_vendor="gear west",
    title_part=title_part,
    details=details,
    track_exclusions=True,
    unknown_by_title=True,
)

def utah_part(tags):
    """Utah Ski files categories as tags ("Category: Skis", "Category: Demo
    Skis"); its product types are internal codes. Snowboard gear is out."""
    if isinstance(tags, str):
        tags = tags.split(",")
    for tag in tags or ():
        match = re.match(r"\s*category\s*:\s*(.+)", str(tag), re.I)
        if not match:
            continue
        category = match.group(1).casefold()
        if "snowboard" in category:
            return None
        for words, part in (("boot", "Boots"), ("binding", "Bindings"), ("pole", "Poles"), ("helmet", "Helmets"),
                            ("goggle", "Protection"), ("protect", "Protection"), ("ski", "Skis")):
            if words in category:
                return part
    return None


# Utah Ski (Shopify; store probe 2026-11-02): one big sale collection plus
# demo skis, with evo-like spec tags (waist width, rocker, best use, skill
# level, with bindings). Clothing and snowboard gear are left out.
UTAH_SKI = shopify.ShopifyStore(
    "Utah Ski",
    "Utah Ski",
    "https://www.utahskis.com",
    collection="sale",
    more_collections=("demos-sale", "sale-helmet-goggle"),
    types={},
    brand_of=brands.for_sport(sports.SKI),
    own_vendor="utah ski",
    details=details,
    track_exclusions=True,
    tag_part=utah_part,
)

# evo (Shopify): its "sale" collections come back empty to automated reads,
# but its category collections are readable with real compare-at prices
# (store probe, 2026-11-02: skis 245/250, boots 236/250, bindings 153/250,
# poles 178/250 marked down). Only marked-down, buyable variants are kept,
# as for every store.
EVO_TYPES = {
    "skis": "Skis",
    "alpine ski boots": "Boots", "alpine touring ski boots": "Boots", "telemark ski boots": "Boots",
    "alpine ski bindings": "Bindings", "alpine touring ski bindings": "Bindings", "telemark ski bindings": "Bindings",
    "ski poles": "Poles",
    "ski and snowboard helmets": "Helmets",
    "goggles": "Protection", "armor": "Protection",  # snow armor; evo's bike armor is "Body Armor"
}

EVO = shopify.ShopifyStore(
    "evo",
    "evo",
    "https://www.evo.com",
    collection="skis",
    more_collections=("ski-boots", "ski-bindings", "ski-poles",
                      # Protection (2026-11-03): helmets, goggles, back protectors, vests, impact shorts.
                      "helmets", "goggles", "body-armor", "d3o-back-protector-0avz03a",
                      "hip-protection-shorts-0avz06a", "childrens-ski-back-protector-0avz00a"),
    types=EVO_TYPES,
    brand_of=brands.for_sport(sports.SKI),
    own_vendor="evo",
    details=details,
    track_exclusions=True,
)

# Multisport protection brands (owner, 2026-11-03): snow helmets, and the
# impact shorts, wrist guards and back protectors skiers wear too.
def multisport_part(title):
    from sports import protection
    if not protection.suits("ski", title):
        return None
    return "Helmets" if "Helmets" in protection.protects(title) else "Protection"


def _brand_stores():
    from sports import protection
    return tuple(protection.brand_store(name, sports.SKI, multisport_part, details=details)
                 for name in ("Triple 8", "Bern", "Demon"))


BRAND_STORES = _brand_stores()

# Smith's snow goggles and helmets (owner, 2026-11-06). Its titles don't say
# what the product is ("4D MAG - Past Season") and past-season pieces leave
# the snow collections, but its product types do: Goggles are Protection
# (bike goggles like "Rhythm MTB" are dropped by the Ski rules), and a Helmet
# counts only when it is one of Smith's snow models; the bike helmets
# (Forefront, Mainline, Payroll, Session...) and unknown models stay out.
# Sunglasses and RX frames have no part. The catalog is ~3 pages: all of it.
SMITH_SNOW_HELMETS = frozenset(
    "survey method liberty descend level vantage altus mission nexus rodeo scout holt code mirage allure "
    "quantum maze gage zoom glide compass".split())


def smith_helmet_part(title):
    words = {word.casefold() for word in re.findall(r"[A-Za-z]+", str(title or ""))}
    return "Helmets" if words & SMITH_SNOW_HELMETS else None


SMITH = shopify.ShopifyStore(
    "Smith", "Smith", "https://www.smithoptics.com", collection="sale-goggles",
    types={"goggles": "Protection", "helmet": shopify.BY_TITLE}, title_part=smith_helmet_part,
    brand_of=brands.for_sport(sports.SKI), details=details, track_exclusions=True, whole_site=True)

STORES = (GEAR_WEST, UTAH_SKI, EVO) + BRAND_STORES + (SMITH,)


def scrapers():
    from sports.ski import christy, the_house

    shopify_scrapers = [scraper for store in STORES for scraper in shopify.scrapers_for(store, PARTS)]
    from stores import skatepro
    return (shopify_scrapers + the_house.scrapers() + christy.scrapers()
            + skatepro.scrapers("ski", skatepro.ski_extra))  # snow helmets, back protectors, impact shorts


def preview(store=GEAR_WEST):
    with sports.SKI.active():
        return shopify.preview(store, PARTS)
