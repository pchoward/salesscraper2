"""Packs: backpacks and hydration packs, on every sport (owner, 2026-11-12).

The heading sits after Protection at the bottom of every menu
(docs/menu-wireframe.md). Most packs suit any sport, so a general pack sold
by any store shows on all four tabs (``pool`` adds the other sports' general
packs when a page is built). A pack from a sport's own brands (Shadow for
BMX, Spitfire for Skate) or an avalanche pack (Ski) shows only on that sport.

Duffels, travel, ski, board and boot bags, bike bags (saddle, handlebar,
frame), slings, totes and hydration bladders on their own are not packs, and
neither are "3-pack" pads, sticker packs or battery packs.
"""

import json
import re

PART = "Packs"

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
    r"\breplacement\b|\bpatch(?:es)?\b|\bsocks?\b|\bshirts?\b|\btees?\b|\bhoodies?\b|\bbeanies?\b",
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
    """``data`` plus the other sports' general packs, each under its own
    store key ("<Store>_Packs"), skipping listings already there. Read-only:
    nothing is written back. ``load(sport) -> data`` reads a sport's stored
    catalog (default: its previous_data.json)."""
    import sports
    load = load or _load_catalog
    merged = {key: list(items) if isinstance(items, list) else items for key, items in (data or {}).items()}
    seen = {item.get("url") for _, item in _items(merged)}
    for other in sports.SPORTS.values():
        if other.id == sport_id:
            continue
        for key, item in _items(load(other)):
            url = item.get("url")
            if not url or url in seen or sport_of(item.get("name"), item.get("brand"), item.get("product_type")):
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
