"""Protection filters shared by BMX, MTB and Ski (owner, 2026-11-03): what a
piece protects (helmets and each body part), the helmet's style, and its
rotational-impact system. Read from the title and store type first, then the
description, so "Knee/Shin/Ankle Combo" counts under all three.

Values are stated in the listing's own words, never guessed from a model name.
"""

import re

# Body part / kind, in sidebar order. Each pattern is matched against the
# title + store product type; several can apply (combo pads, pad sets).
PARTS = (
    ("Helmets", r"\bhelmets?\b|\bfull[- ]?face\b|\bbrain\s*buckets?\b"),
    ("Goggles", r"\bgoggles?\b|\bgoggle\s+lens(?:es)?\b"),
    ("Neck", r"\bneck\s*(?:brace|braces|guard|guards|roll|protector)s?\b"),
    ("Shoulders", r"\bshoulder\s*(?:pads?|guards?|protectors?|armou?r|supports?|braces?)\b"),
    ("Chest & Ribs", r"\bchest\s*(?:protectors?|guards?|plates?|pads?)\b|\broost\s*(?:guards?|deflectors?)\b"
                     r"|\brib\s*(?:protectors?|guards?|pads?)\b|\bbody\s*armou?r\b(?!\s*(?:underwear|shorts|pants))|\bpressure\s*suits?\b"
                     r"|\bpadded\s+(?:shirts?|tops?|jerseys?|jackets?|vests?|tees?)\b|\bprotective\s+(?:shirts?|tops?|jackets?|vests?)\b"
                     r"|\bupper\s*(?:body\s*)?(?:protective|protection|armou?r)\b"
                     r"|\bbody\s*protectors?\b|\bprotection\s+jackets?\b"
                     r"|\b(?:d3o|armou?red|protective|padded)\b[^;]*\b(?:jackets?|shirts?|vests?|tops?|jerseys?)\b"),
    ("Back & Spine", r"\bback\s*(?:protectors?|guards?|plates?|pads?|armou?r)\b|\bspine\s*(?:protectors?|guards?|pads?)\b"
                     r"|\bprotector\s+vests?\b|\bprotective\s+vests?\b|\bspine\b|\bbody\s*protectors?\b"),
    ("Elbows", r"\belbows?\b|\barm\s*(?:pads?|guards?|protectors?)\b"),
    ("Forearms", r"\bforearms?\b"),
    ("Wrists", r"\bwrists?\s*(?:guards?|braces?|pads?|protectors?|wraps?|supports?)\b|\bwristguards?\b"),
    ("Gloves", r"\bgloves?\b|\bmitts?\b|\bmittens?\b"),
    ("Hips & Tailbone", r"\bhips?\s*(?:pads?|guards?|protectors?)\b|\btailbone\b|\bcrash\s*(?:pants|shorts)\b"
                        r"|\bimpact\s*(?:shorts|pants|liners?|underwear)\b|\barmou?r\s*(?:underwear|shorts|pants)\b"
                        r"|\bprotective\s*(?:shorts|pants|underwear)\b|\bbum\s*(?:pads?|savers?)\b|\bbumsavers?\b"),
    ("Knees", r"\bknees?\b"),
    ("Shins", r"\bshins?\b"),
    ("Ankles", r"\bankles?\b"),
)
_PARTS = tuple((label, re.compile(pattern, re.I)) for label, pattern in PARTS)
_PAD_SET = re.compile(r"\bpad\s*-?sets?\b|\bpadsets?\b|(?=.*\b(?:pads?|guards?|protect\w*|saver)\b)(?:.*\b(?:3|three|6|six)[- ]?(?:pc|piece|pack)\b|.*\bcombo\b)", re.I)
# "Helmet Replacement Pads", "Visor", "Lens": parts for a piece, not the piece.
_SPARE = re.compile(r"\breplacement\b|\bspare\b|\bvisors?\b|\bpeaks?\b|\bliners?\b(?!\s*(?:shorts|pants))|\bcheek\s*pads?\b"
                    r"|\blens(?:es)?\b|\bstraps?\b|\bbuckles?\b|\bmount\b|\bparts?\b", re.I)

# Helmet style, from the title + type, then the description.
HELMET_STYLES = (
    # Plus full-face models whose names don't say so, as their makers sell
    # them (owner, 2026-11-03: BMX riders want these): 7iDP Project 23, Troy
    # Lee D3/D4, Bell Full-9/Full-10/Sanction, Fox Rampage/Proframe, Kali Zoka.
    ("Full face", r"\bfull[- ]?face\b|\bdownhill\s+helmet\b|\bdh\s+helmet\b|\bconvertible\b|\bchin\s*bar\b"
                  r"|\bproject[ .]?23\b|\bp23\b|\btroy\s+lee\b.*\bd[34]\b|\bd[34]\s+(?:composite|carbon|polyacrylite)\b"
                  r"|\bfull[- ]?(?:9|10)\b|\bsanction\b|\brampage\b|\bproframe\b|\bzoka\b"),
    ("Half shell (skate / BMX)", r"\bdirt\s*jump\b|\bbmx\b|\bskate(?:board)?\b|\bdual[- ]certified\b|\bdj\s+helmet\b|\bbucket\b"),
    ("Half shell (trail)", r"\b(?:mtb|mountain|trail|enduro|all[- ]?mountain|half[- ]?shell|open[- ]?face|xc)\b"),
    ("Snow", r"\bski\b|\bsnow(?:board)?\b"),
    ("Road / commuter", r"\broad\b|\bcommuter\b|\burban\b|\bcity\b|\brecreation(?:al)?\b"),
)
_HELMET_STYLES = tuple((label, re.compile(pattern, re.I)) for label, pattern in HELMET_STYLES)

# Helmet and pad certifications, named as standards bodies write them
# (owner, 2026-11-03: "certified, double certified (name the certs)"). Read
# from the title and description only: a listing that doesn't state one has
# none here, it is never assumed from the brand or model.
CERTIFICATIONS = (
    ("Dual certified (CPSC + ASTM F1492)", r"\b(?:dual|double|twin)[- ]certifi(?:ed|cation)\b"),
    ("CPSC (US bike)", r"\bcpsc\b|\b16\s*cfr\s*(?:part\s*)?1203\b"),
    ("ASTM F1492 (skate)", r"\bf[\s-]?1492\b"),
    ("ASTM F2032 (BMX)", r"\bf[\s-]?2032\b"),
    ("ASTM F1952 (downhill)", r"\bf[\s-]?1952\b"),
    ("ASTM F2040 (snow)", r"\bf[\s-]?2040\b"),
    ("EN 1078 (EU bike / skate)", r"\ben[\s-]?1078\b"),
    ("EN 1077 (EU snow)", r"\ben[\s-]?1077\b"),
    ("EN 1621 (CE impact armor)", r"\ben[\s-]?1621(?:-[12])?\b|\bce\s+level\s*[12]\b"),
    ("EN 14120 (roller sports pads)", r"\ben[\s-]?14120\b"),
)
_CERTIFICATIONS = tuple((label, re.compile(pattern, re.I)) for label, pattern in CERTIFICATIONS)
CERTIFIED_UNNAMED = "Certified (standard not named)"
CERTIFICATION_ORDER = [label for label, _ in CERTIFICATIONS] + [CERTIFIED_UNNAMED]


def certifications(title, description=""):
    """The certifications a listing states, in CERTIFICATION_ORDER."""
    text = f" {title or ''} ; {str(description or '')[:3000]} "
    found = [label for label, pattern in _CERTIFICATIONS if pattern.search(text)]
    if "CPSC (US bike)" in found and "ASTM F1492 (skate)" in found and CERTIFICATION_ORDER[0] not in found:
        found.insert(0, CERTIFICATION_ORDER[0])
    if not found and re.search(r"\bcertified\b", text, re.I):
        # "The Certified Sweatsaver": certified, but the standard isn't named.
        found = [CERTIFIED_UNNAMED]
    return found


AGE_ORDER = ["Adult", "Youth", "Kids"]
_KIDS = re.compile(r"\b(?:kids?|child(?:ren)?'?s?|toddlers?|little|lil|infant|baby|tike)\b", re.I)
_YOUTH = re.compile(r"\b(?:youth|junior|jr\.?|grom|teen)\b", re.I)


def age(title):
    """Adult, Youth or Kids, from the title (adult when it says neither)."""
    title = str(title or "")
    if _KIDS.search(title):
        return "Kids"
    if _YOUTH.search(title):
        return "Youth"
    return "Adult"


SIZE_ORDER = ["XS", "S", "M", "L", "XL", "XXL"]


def variant_size(product, variant):
    """Letter sizes (XS-XXL) a variant's Size option names: "S/M" is S and M."""
    from protection import size_tokens  # Skate's reader of size labels
    found = []
    for index, option in enumerate((product or {}).get("options") or [], start=1):
        name = option.get("name") if isinstance(option, dict) else option
        if "size" in str(name or "").lower():
            found.extend(size_tokens((variant or {}).get(f"option{index}")))
    return [size for size in SIZE_ORDER if size in found]

# Rotational-impact systems, as named by their makers.
ROTATIONAL = (
    ("MIPS", r"\bmips\b"),
    ("Spherical", r"\bspherical\b"),
    ("WaveCel", r"\bwavecel\b"),
    ("Kineticore", r"\bkineticore\b"),
    ("SPIN", r"\bspin\b"),
    ("FLAD / 6D ODS", r"\bods\b|\b6d\b"),
)
_ROTATIONAL = tuple((label, re.compile(pattern, re.I)) for label, pattern in ROTATIONAL)

FIELD_KEYS = ("protects", "helmet_style", "certification", "rotational", "prot_size", "age")


def _first(table, text):
    for label, pattern in table:
        if pattern.search(text):
            return label
    return None


def protects(title, product_type="", description=""):
    """The body parts / kinds a piece protects, in sidebar order."""
    text = f" {title or ''} ; {product_type or ''} "
    if re.search(r"\b(?:goggle|helmet)\s+parts\b|\bhelmet\s+bags?\b", text, re.I):
        return []  # spares and bags, not the piece
    # The title names the piece; the store's category ("Ankle & Wrist
    # Supports", "Knee & Shin Pads") only fills in when the title doesn't.
    found = [label for label, pattern in _PARTS if pattern.search(f" {title or ''} ")]
    if not found:
        found = [label for label, pattern in _PARTS if pattern.search(text)]
    if "Helmets" in found and _SPARE.search(title or ""):
        # A visor or replacement pads for a helmet is not a helmet.
        found.remove("Helmets")
    # "Goggle Replacement Lenses" / "Goggle Lens - Clear" are spares;
    # "Goggles with Bonus Lens" is a pair of goggles.
    lens_only = re.search(r"\b(?:replacement|spare)\s+lens", title or "", re.I) or (
        re.search(r"\blens(?:es)?\b", title or "", re.I) and not re.search(r"\bgoggles?\b(?!\s+lens)", title or "", re.I))
    if "Goggles" in found and lens_only:
        found.remove("Goggles")
        found.append("Goggle lenses")
    # Armor kits ("Zero PLUS Vest + Shorts", "X V7 Shorts + Knee Pads"): the
    # shorts in them are impact shorts. Chamois/bib shorts never are.
    if (found and "Hips & Tailbone" not in found and re.search(r"\bshorts\b", title or "", re.I)
            and not re.search(r"\b(?:chamois|bibs?|liner|cycling\s+shorts)\b", title or "", re.I)):
        found.append("Hips & Tailbone")
    if not found and _PAD_SET.search(text):
        # "Saver Series Pad Set (3-Pack)": knees, elbows and wrists.
        found = ["Pad Sets"]
    elif _PAD_SET.search(title or "") and len(found) <= 1 and "Helmets" not in found:
        found.append("Pad Sets")
    if not found and description:
        # A vague title ("Fuse Omega") whose description says what it is.
        found = [label for label, pattern in _PARTS[:1] + _PARTS[2:] if pattern.search(str(description)[:400])][:2]
    return found


def helmet_style(title, product_type="", description="", sport=""):
    text = f" {title or ''} ; {product_type or ''} "
    if sport == "ski":
        # Snow helmets describe "all-mountain" skiing, not trail riding.
        return "Full face" if _HELMET_STYLES[0][1].search(text) else "Snow"
    style = _first(_HELMET_STYLES, text)
    if style is None and description:
        style = _first(_HELMET_STYLES, str(description)[:600])
    if style is None and sport == "ski":
        style = "Snow"
    return style


def rotational(title, product_type="", description=""):
    text = f" {title or ''} ; {product_type or ''} ; {str(description or '')[:800]} "
    return [label for label, pattern in _ROTATIONAL if pattern.search(text)]


def fields(title, product_type="", description="", sport="", default=None):
    """{filter key: [values]} for one protection listing. ``default`` names
    the kind when the store's category already says it (Ski "Helmets")."""
    found = {}
    # When the store's category already names the kind, its description is
    # not mined for others ("...pairs well with our gloves").
    kinds = (protects(title, product_type) or [default]) if default else protects(title, product_type, description)
    if kinds:
        found["protects"] = kinds
        found["age"] = [age(title)]
        certs = certifications(title, description)
        if certs:
            found["certification"] = certs
    if "Helmets" in kinds:
        style = helmet_style(title, product_type, description, sport)
        if style:
            found["helmet_style"] = [style]
        systems = rotational(title, product_type, description)
        if systems:
            found["rotational"] = systems
    return found


def facet_fields(prefix, categories):
    """The protection sidebar fields for a sport, scoped to its protection
    categories: what it protects, helmet type, certifications, rotational
    system, size and age. ``order`` lists values in a natural order."""
    categories = tuple(categories)
    return (
        {"key": "protects", "label": "Protects", "param": prefix + "_protects", "categories": categories,
         "order": [label for label, _ in PARTS] + ["Goggle lenses", "Pad Sets"]},
        {"key": "helmet_style", "label": "Helmet type", "param": prefix + "_helmet", "categories": categories,
         "order": [label for label, _ in HELMET_STYLES]},
        {"key": "certification", "label": "Certification", "param": prefix + "_cert", "categories": categories,
         "order": CERTIFICATION_ORDER},
        {"key": "rotational", "label": "Rotational protection", "param": prefix + "_rotational",
         "categories": categories, "order": [label for label, _ in ROTATIONAL]},
        {"key": "prot_size", "label": "Size", "param": prefix + "_psize", "categories": categories,
         "order": SIZE_ORDER},
        {"key": "age", "label": "Age", "param": prefix + "_age", "categories": categories, "order": AGE_ORDER},
    )


# Multisport brands (Triple 8, 187, Kali, Bern, Demon, G-Form...) sell one
# catalog for several sports (owner, 2026-11-03: "most are made for
# multisport"). Which sport's Protection a piece belongs in, from its words.
_OTHER_SPORTS = re.compile(r"\b(?:baseball|softball|soccer|football|lacrosse|hockey|batter'?s?|catcher|moto|mx|motocross"
                           r"|motorcycle|equestrian|horse)\b", re.I)
_SNOW = re.compile(r"\b(?:snow|ski|skiing|winter|snowboard(?:ing)?)\b", re.I)
# Worn on snow too: impact shorts, wrist guards, back and body protectors.
_SNOW_BODY = {"Hips & Tailbone", "Wrists", "Back & Spine", "Chest & Ribs"}


def suits(sport_id, title, product_type=""):
    """True when a multisport brand's piece belongs in ``sport_id``'s Protection."""
    text = f" {title or ''} ; {product_type or ''} "
    kinds = set(protects(title, product_type))
    if not kinds or _OTHER_SPORTS.search(text):
        return False
    # A store's "SKI/SNOW" category doesn't pin impact shorts or wrist guards
    # to snow; only the title saying so does.
    body_only = kinds <= _SNOW_BODY
    snow = bool(_SNOW.search(f" {title or ''} " if body_only else text))
    if sport_id == "ski":
        return snow or body_only
    return not snow


# Multisport brand stores (Shopify sale collections, store probe 2026-11-03).
# Each sport reads the ones that suit it; ``suits`` picks the pieces. Pro-Tec
# and S1 aren't Shopify, TSG and Fuse didn't answer: their gear comes through
# the skate shops and BMX stores.
BRAND_STORES = {
    "Triple 8": ("https://www.triple8.com", ("yard-sale", "4th-of-july-sale", "sale")),
    "187 Killer Pads": ("https://www.187killerpads.com", ("all-products-sales-tax-must-manually-add-new-product-lines", "yard-sale")),
    "Kali": ("https://www.kaliprotectives.com", ("all",)),
    "Bern": ("https://www.bernunlimited.com", ("bern-barn", "bern-outlet")),
    "Demon": ("https://www.demonunited.com", ("sale", "discount-eligible")),
    "G-Form": ("https://www.g-form.com", ("sale-m2", "sale-included-products")),
}


def brand_store(name, sport, part_of, **options):
    """A Shopify store config for one multisport brand in ``sport``."""
    from sports import brands
    from stores import shopify
    base, handles = BRAND_STORES[name]
    return shopify.ShopifyStore(name, name, base, collection=handles[0], more_collections=handles[1:], types={},
                                type_part=lambda kind: shopify.BY_TITLE, title_part=part_of, unknown_by_title=True,
                                brand_of=brands.for_sport(sport), track_exclusions=True, **options)
