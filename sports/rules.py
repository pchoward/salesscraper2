"""Which listings belong in each new sport's catalog (filters.filter_reason's signature).

Skate's rules (filters.py) are mostly about what is not a skateboard part:
cruisers, longboards, apparel, wheel brands. The new sports start simpler: a
named listing in one of the sport's categories that is not apparel. Store
adapters choose the sale sections; markdowns are decided there and by the
shared deal checks. A sport outgrows this by getting its own function here.
"""

import re

from filters import normalize_product_name

_APPAREL = ("t-shirt", " tee ", "hoodie", "sweatshirt", "socks", " hat ", "beanie", "sticker", "gift card")


def _basic(sport, name, part):
    name = normalize_product_name(name)
    if not name:
        return "missing name"
    if part not in sport.parts:
        return f"not a {sport.label} category"
    text = f" {name.casefold()} "
    if any(word in text for word in _APPAREL):
        return "apparel"
    return None


# Electric bikes aren't BMX (owner, 2026-11-05: Haro Skwad Electric listed
# under BMX Bikes from Albe's bike sale). "Electric" alone is often a colour
# ("Electric Blue" grips), so it counts only next to bike/BMX.
_EBIKE = re.compile(r"\belectric\s+(?:bikes?|bmx|balance\s+bikes?)\b|\be-?bikes?\b|\bpedal[\s-]+assist|\be-?bmx\b", re.I)


# Skate pads BMX riders don't wear (owner, 2026-11-10). Roller-skate and
# derby gear, and skate brands' knee + elbow (+ wrist) packs. Single hard-cap
# knee pads (Triple 8 KP 22, 187 Slim) stay: some park riders wear them.
# "Moxi" alone is a signature colourway (a Triple 8 helmet), not roller gear.
_ROLLER = re.compile(r"\b(?:derby|roller\s*skates?|rollerskates?|quad\s+skates?|impala)\b", re.I)
_SKATE_PAD_BRAND = re.compile(r"^(?:187(?:\s+killer\s+pads)?|triple\s*(?:8|eight)|pro-?tec|s-?one)\b", re.I)
_PAD_PACK = re.compile(r"\b(?:combo\s+pack|six\s+pack|\d\s*-?\s*pack|pack\s+of|saver\s+series|set\s+of\s+pads|"
                       r"pads?\s+set|knee\s*(?:/|&|and|\+)\s*elbow)\b", re.I)


def skate_only_pads(name):
    """A reason when BMX should leave this protection out, else None."""
    name = str(name or "")
    if _ROLLER.search(name):
        return "roller-skate or derby gear"
    if _SKATE_PAD_BRAND.search(name) and _PAD_PACK.search(name):
        return "skate pad pack"
    return None


def bmx(name, part, url="", price_new=None, price_old=None, description="", product_type=""):
    import sports
    if _EBIKE.search(f"{name} {product_type}"):
        return "electric bike"
    reason = _basic(sports.BMX, name, part)
    if reason is None and part == "Protection":
        # Helmet replacement pads, visors, straps: protection only when it
        # says what it protects (owner, 2026-11-03).
        from sports.protection import protects
        if not protects(name, product_type):
            return "not protective gear"
        skate = skate_only_pads(name)
        if skate:
            return skate
    return reason


# Bike gear sold by snow brands (Smith's "Rhythm MTB" goggle) isn't Ski.
_BIKE_WORDS = re.compile(r"\b(?:mtb|bike|cycling|mountain\s+bike)\b", re.I)


def ski(name, part, url="", price_new=None, price_old=None, description="", product_type=""):
    import sports
    if _BIKE_WORDS.search(name or ""):
        return "bike gear"
    return _basic(sports.SKI, name, part)


def mtb(name, part, url="", price_new=None, price_old=None, description="", product_type=""):
    import sports
    return _basic(sports.MTB, name, part)
