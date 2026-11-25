"""Packs: backpacks and hydration packs, on every sport (owner, 2026-11-12).

The heading sits after Protection at the bottom of every menu
(docs/menu-wireframe.md). Each pack shows where it's used (owner,
2026-11-14), whichever store sells it (``home``): ski and avalanche packs on
Ski, hydration/hip/protector packs on MTB, a sport's own brands (Shadow,
Spitfire) on that sport. Everyday packs are shared within two pairs of tabs
(``FAMILY``): skate+BMX shops' streetwear packs, ski+bike shops' outdoor
packs. ``pool`` does this when a page is built; stored data keeps every pack
the stores file.

Duffels, travel, ski, board and boot bags, bike bags (saddle, handlebar,
frame), slings, totes and hydration bladders on their own are not packs, and
neither are "3-pack" pads, sticker packs or battery packs.
"""

import json
import re

PART = "Packs"

# Filed under packs by a store but not packs (owner, 2026-11-14): disc golf
# bags, a beach chair, a flask, crossbodies, camera bags, bum bags, sticker
# packs and goggle tear-offs. Also checked when a page is built, so listings
# saved under older rules drop off too.
JUNK = (r"\bdisc\s*golf\b|\bchairs?\b|\bflasks?\b|\bcross\s*body\b|\bcamera\s*bags?\b|\bbum\s*bags?\b|"
        r"\btear[\s-]*offs?\b|\bstickers?\b|\bpad\s*sets?\b")
_JUNK = re.compile(JUNK, re.I)

_PACK = re.compile(
    r"\bback\s*packs?\b|\bbackpacks?\b|\bdaypacks?\b|\brucksacks?\b|\bhydration\s+(?:packs?|vests?|bags?)\b|"
    r"\b(?:day|ride|riding|trail|bike|skate|ski|snow|avalanche|avy|airbag|hip|lumbar|race)\s*packs?\b|"
    r"\b\d{1,2}\s*l(?:iter|itre)?\s+(?:back)?packs?\b|\bpacks?\s+\d{1,2}\s*l\b|\bavalanche\s+airbag\b",
    re.I)
_TYPE = re.compile(r"\bback\s*packs?\b|\bbackpacks?\b|\bhydration\b|\bday\s*packs?\b|\bairbags?\b", re.I)
_NOT_PACK = re.compile(
    r"\bduff(?:el|le)s?\b|\btravel\b|\broller\b|\bwheeled\b|\bluggage\b|\b(?:ski|board|snowboard|boot|gear|helmet|"
    r"saddle|seat|handlebar|frame|top\s*tube|tool|wash|shoe|cooler|lunch)\s*bags?\b|\btool\s*rolls?\b|"
    r"\bsticker\b|\bpad\s*(?:sets?|packs?)\b|\b\d+\s*-?\s*packs?\b|\bsix\s*packs?\b|\bpacks?\s+of\b|"
    r"\bbattery\b|\b(?:ice|gel)\s*packs?\b|\b(?:reservoir|bladder)s?\b(?!.*\bpack)|\brain\s*cover\b|"
    r"\bslings?\b|\btotes?\b|\bfanny\b|\bwallets?\b|\bpouch(?:es)?\b|\bkey\s*chains?\b|\bstraps?\b|"
    r"\breplacement\b|\bpatch(?:es)?\b|\bsocks?\b|\bshirts?\b|\btees?\b|\bhoodies?\b|\bbeanies?\b|" + JUNK,
    re.I)

# Words that make a pack Ski-only: avalanche safety packs.
_SKI_ONLY = re.compile(r"\bavalanche\b|\bavy\b|\bairbag\b|\balpride\b|\bjet\s*force\b|\bavabag\b", re.I)

# BMX's own brands (not the multisport ones on the BMX brand list).
BMX_BRANDS = ("Shadow Conspiracy", "The Shadow Conspiracy", "Shadow", "Odyssey", "Cult", "Kink", "Sunday", "Fit",
              "Fiend", "BSD", "Subrosa", "Haro", "We The People", "Wethepeople", "S&M", "Eclat", "Primo", "Federal",
              "Stranger", "Colony", "Kunstform", "Animal", "Merritt", "Profile", "Rant", "Total BMX", "Deluxe BMX",
              "Stay Strong", "Box", "Chase", "Supercross", "Answer", "Tangent", "Alienation", "Fly Racing",
              "Mongoose", "Verde", "Eastern", "Premium", "Volume", "Demolition", "Bone Deth", "Gsport", "G-Sport")
# Skate's own brands: the deck, wheel, truck and bearing lists (filters.py),
# plus skate media and apparel brands. Santa Cruz also makes mountain bikes,
# so a Santa Cruz pack stays general.
_SKATE_EXTRA = ("Thrasher", "Independent", "Indy", "Spitfire", "Bones", "Bronson", "Andale", "Fucking Awesome",
                "Hockey", "Polar", "Quasi", "Toy Machine", "Zero", "Krooked", "Primitive", "Shake Junt", "Mob",
                "Diamond Supply", "Grizzly", "Lakai", "Last Resort", "Pass~Port", "Passport", "Huf", "Theories",
                "Palace", "Dime", "GX1000", "Hammers", "Skate Mental", "Heroin", "Pizza", "Antihero", "Anti Hero",
                "Anti-Hero")


def _skate_brands():
    import filters
    names = set(filters.DECK_BRANDS) | set(filters.WHEEL_BRANDS) | set(filters.TRUCK_BRANDS)
    names |= set(getattr(filters, "BEARING_BRANDS", ()))
    names |= set(_SKATE_EXTRA)
    return tuple(sorted(names - {"Santa Cruz"}, key=len, reverse=True))


def _key(text):
    return re.sub(r"[^a-z0-9&]+", " ", str(text or "").casefold()).strip()


def _starts_with(text, names):
    key = _key(text)
    for name in names:
        brand = _key(name)
        if brand and (key == brand or key.startswith(brand + " ")):
            return True
    return False


def is_pack(title, product_type="", tags=()):
    """True for a backpack or hydration pack: its title, or a store type or
    tag that says so ("Odyssey Switch Pack" is tagged Backpacks)."""
    title, kind = str(title or ""), str(product_type or "")
    if _NOT_PACK.search(title):
        return False
    if _PACK.search(title):
        return True
    if isinstance(tags, str):
        tags = tags.split(",")
    labels = [kind] + [str(tag) for tag in tags or ()]
    return any(_TYPE.search(label) and not _NOT_PACK.search(label) for label in labels)


# Pack size (owner, 2026-11-25: "add size when it's available, many are 28L,
# smaller or larger"), from the litres the title or description states. A
# hydration pack's reservoir ("12L pack with 3L reservoir") isn't the pack.
VOLUME_SIZES = ("Under 15L", "15–24L", "25–34L", "35L+")
_LITRES = re.compile(r"(?<![\d.])(\d{1,2}(?:\.\d)?)\s*(?:l|liters?|litres?|ltr)\b", re.I)
_RESERVOIR_AFTER = re.compile(r"^\W{0,3}(?:\w+\W+){0,2}?(?:reservoir|bladder|water|hydration\s+(?:bladder|reservoir))\b",
                              re.I)
_RESERVOIR_BEFORE = re.compile(r"(?:\bwith|\+|\band|\bincl(?:udes|uding|\.)?)\s*(?:an?\s+)?$", re.I)


# Brands whose model names carry the litres as a bare number: Osprey
# "Sopris 32", CamelBak "M.U.L.E. 12 100oz", EVOC "Stage 6 + 2L Bladder",
# Deuter "Trans Alpine 30", Gregory "Targhee 32". A labeled convention, like
# a ski's waist width read from its model number.
_LITRE_NAMED = re.compile(r"^\s*(?:osprey|camelbak|camel\s*bak|evoc|deuter|gregory)\b", re.I)
_BARE_NUMBER = re.compile(r"(?<![\w.\-/+])(\d{1,2})(?![\w.%°/-])(?!\s*(?:(?:oz|l|liters?|litres?|mm|in)\b(?!-)|\"|”))", re.I)


def _named_litres(name):
    if not _LITRE_NAMED.search(name):
        return None
    head = re.split(r"\s+[-–]\s+|\s\+\s|\bwith\b", name, maxsplit=1)[0]  # not "+ 2L Bladder", "- Kids'"
    found = {int(m.group(1)) for m in _BARE_NUMBER.finditer(head) if 4 <= int(m.group(1)) <= 80}
    return found.pop() if len(found) == 1 else None


def volume_litres(name, description=""):
    """The pack's own volume in litres (4-80), or None when it isn't stated
    once and clearly. The title wins over the description."""
    named = _named_litres(str(name or ""))
    if named and not _LITRES.search(str(name or "").split("+")[0]):
        return named
    for text in (str(name or ""), str(description or "")):
        found = set()
        for match in _LITRES.finditer(text):
            value = float(match.group(1))
            if not 4 <= value <= 80:
                continue
            if _RESERVOIR_AFTER.search(text[match.end():match.end() + 30]):
                continue
            if _RESERVOIR_BEFORE.search(text[max(0, match.start() - 14):match.start()]):
                continue
            found.add(int(value) if value.is_integer() else value)
        if len(found) == 1:
            return found.pop()
        if found:
            return None  # "20L S/M, 22L M/L": two sizes in one listing
    return None


def volume_size(litres):
    """The Size filter's range for a volume: "Under 15L" .. "35L+"."""
    if litres is None:
        return None
    if litres < 15:
        return VOLUME_SIZES[0]
    if litres < 25:
        return VOLUME_SIZES[1]
    if litres < 35:
        return VOLUME_SIZES[2]
    return VOLUME_SIZES[3]


def facet_field(prefix):
    """The Packs heading's Size filter for one sport's sidebar."""
    return {"key": "pack_volume", "label": "Size (liters)", "param": f"{prefix}_packsize", "categories": (PART,),
            "order": list(VOLUME_SIZES)}


def technical_offers(item):
    """``item``'s spec offers with its pack size added, built from the
    listing itself when the store gave none (a skate shop's pack pooled onto
    BMX). Read when a page is built; stored data is unchanged."""
    size = volume_size(volume_litres(item.get("name"), item.get("description")))
    offers = [offer for offer in item.get("technical_offers") or [] if isinstance(offer, dict)]
    if not size:
        return offers
    if not offers:
        def amount(value):
            try:
                return float(str(value).replace("$", "").replace(",", ""))
            except (TypeError, ValueError):
                return None
        offers = [{"price": amount(item.get("price_new")), "compare": amount(item.get("price_old")),
                   "available": None, "specs": {}}]
    return [dict(offer, specs=dict(offer.get("specs") or {}, pack_volume=[size])) for offer in offers]


def sport_of(title, brand="", product_type=""):
    """"bmx", "skate" or "ski" for a sport's own pack, or None for a general one.
    A store type that says snow ("Snow Backpacks", EVOC) makes it Ski's."""
    title, brand = str(title or ""), str(brand or "")
    if _SKI_ONLY.search(title) or re.search(r"\b(?:snow|avalanche|ski)\b", str(product_type or ""), re.I):
        return "ski"
    for text in (brand, title):
        if not text:
            continue
        if _starts_with(text, BMX_BRANDS):
            return "bmx"
        if _starts_with(text, _skate_brands()):
            return "skate"
    return None


# Where a pack is used (owner, 2026-11-14: "ski packs in BMX or skate ...
# don't make sense"). Snow packs belong on Ski, bike packs on MTB; the store's
# own category decides first, then known models and brands.
_SNOW_TYPE = re.compile(r"\b(?:ski|skis|snow|snowboard|avalanche|airbags?)\b", re.I)
_SNOW_TITLE = re.compile(
    r"\b(?:ski|snowboard|splitboard|backcountry|heli|poacher|sopris|soelden|kamber|ortovox|arva|bca|ras|"
    r"tour\s*rider|switchback)\b", re.I)
_BIKE = re.compile(r"\bhydration\b|\bhip\s*packs?\b|\blumbar\b|\bwaist\s*packs?\b|\bprotector\b|\bbladder\b|"
                   r"\bfanny\b|\bbike\b|\benduro\b|\bmtb\b", re.I)
BIKE_BRANDS = ("EVOC", "CamelBak", "USWE", "High Above")


def home(name, brand="", product_type=""):
    """The sport a pack belongs on ("ski", "mtb", "bmx", "skate"), or None
    for an everyday pack that suits every tab."""
    owner = sport_of(name, brand, product_type)
    if owner:
        return owner
    name, kind = str(name or ""), str(product_type or "")
    if _SNOW_TYPE.search(kind) or _SNOW_TITLE.search(name):
        return "ski"
    if _BIKE.search(kind) or _BIKE.search(name) or _starts_with(brand or name, BIKE_BRANDS):
        return "mtb"
    return None


# Tabs that share their everyday packs: the skate and BMX shops' streetwear
# packs (Jansport, Vans, Herschel) go on Skate and BMX; the ski and bike
# shops' outdoor packs (Arc'teryx, Topo, Dakine Campus) on Ski and MTB.
FAMILY = {"skate": "street", "bmx": "street", "ski": "outdoor", "mtb": "outdoor"}


def shown_on(item, sport_id, source=None):
    """True when this listing belongs on ``sport_id``'s page. Anything that
    isn't a pack stays. A pack with a home sport (ski, bike, a sport's own
    brand) shows only there; an everyday pack shows on the tabs of its
    store's family. ``source`` is the sport whose store sold it (default:
    this one)."""
    if not isinstance(item, dict) or item.get("part") != PART:
        return True
    name, kind = str(item.get("name") or ""), item.get("product_type")
    if _JUNK.search(name) or _JUNK.search(str(kind or "")):
        return False
    owner = home(name, item.get("brand"), kind)
    if owner:
        return owner == sport_id
    return FAMILY.get(source or sport_id) == FAMILY.get(sport_id)


def rule_reason(sport_id, name, brand=""):
    """A reason when this pack belongs to another sport, else None."""
    owner = sport_of(name, brand)
    if owner and owner != sport_id:
        return f"{owner} pack"
    return None


def _items(data):
    for key, items in (data or {}).items():
        for item in items or []:
            if isinstance(item, dict) and item.get("part") == PART:
                yield key, item


def pool(data, sport_id, load=None):
    """The packs ``sport_id``'s page shows (``shown_on``): its own stores'
    packs that belong here, plus the other sports' packs that do (evo's
    hydration packs on MTB, Tactics' ski packs on Ski, the skate shops'
    everyday packs on BMX), each under its own store key ("<Store>_Packs"),
    each listing once. Read-only: stored data keeps every pack the stores file.
    ``load(sport) -> data`` reads a sport's stored catalog (default: its
    previous_data.json)."""
    import sports
    load = load or _load_catalog
    merged = {}
    for key, items in (data or {}).items():
        merged[key] = [item for item in items if shown_on(item, sport_id)] if isinstance(items, list) else items
    seen = {item.get("url") for _, item in _items(merged)}
    for other in sports.SPORTS.values():
        if other.id == sport_id:
            continue
        for key, item in _items(load(other)):
            url = item.get("url")
            if not url or url in seen or not shown_on(item, sport_id, other.id):
                continue
            seen.add(url)
            merged.setdefault(key, []).append(dict(item, pooled_from=other.id))
    return merged


def _load_catalog(sport):
    path = sport.data_path() / "previous_data.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
