"""BMX listing details the filters use, read from the store's data.

* ``kind``: the type within a category (Hubs inside Wheel Parts, Stems
  inside Steering), with labels following docs/multi-sport-plan.md section 3.
* ``wheel_size``: 12, 14, 16, 18, 20, 22, 24, 26, 27.5 or 29 (inches), from
  the title ('20"', '20 inch', '20in') or a Shopify tag like 'Wsize_20"'. Left
  out when it isn't stated; it is never guessed (most parts fit any size).
* ``category_for_title``: the category a title names, for products a store
  files under a vague type ("PARTS" or none), using the category words in
  aliases.json.
"""

import functools
import json
import re

WHEEL_SIZES = ("12", "14", "16", "18", "20", "22", "24", "26", "27.5", "29")
_SIZE = re.compile(r'(?<![\d.])(12|14|16|18|20|22|24|26|27\.5|29)\s*(?:"|”|″|\'\'|-?\s?inch(?:es)?\b|in\b)', re.I)
# Tire sizes: 20 x 2.4, 20x1.95.
_TIRE = re.compile(r'(?<![\d.])(12|14|16|18|20|22|24|26|27\.5|29)\s*[x×]\s*\d(?:\.\d+)?\b', re.I)
_TAG = re.compile(r'^w(?:heel)?[\s_-]*size[\s_:-]*(12|14|16|18|20|22|24|26|27\.5|29)\b', re.I)

# Shopify product_type (as stores/shopify.type_key gives it) -> kind.
KINDS = {
    "bmx bikes": "Complete Bikes", "bmx bike": "Complete Bikes", "bikes": "Complete Bikes", "bmx race bikes": "Complete Bikes",
    "complete bikes": "Complete Bikes",
    "frames": "Frames", "frame": "Frames", "bmx frames": "Frames", "bmx race frames": "Frames",
    "forks": "Forks", "fork": "Forks", "bmx forks": "Forks", "bmx fork top caps": "Forks",
    "bars": "Handlebars", "handlebars": "Handlebars", "handlebar": "Handlebars", "bmx bars": "Handlebars",
    "bmx handlebars": "Handlebars",
    "stems": "Stems", "stem": "Stems", "bmx stems": "Stems",
    "headsets": "Headsets", "headset": "Headsets", "bmx headsets": "Headsets",
    "grips": "Grips & Bar Ends", "bar ends": "Grips & Bar Ends", "grips bar ends": "Grips & Bar Ends",
    "detanglers": "Detanglers", "gyros": "Detanglers",
    "cranks": "Cranks", "crank": "Cranks", "bmx cranks": "Cranks", "cranksets": "Cranks", "crank arms": "Cranks", "spindles": "Cranks",
    "sprockets": "Sprockets", "sprocket": "Sprockets", "chainrings": "Sprockets", "bmx sprockets": "Sprockets",
    "chainring": "Sprockets", "bmx crank spindles etc": "Cranks", "bmx bottom brackets": "Bottom Brackets",
    "bmx chains": "Chains", "bmx grips": "Grips & Bar Ends", "bmx bar ends": "Grips & Bar Ends", "bar end": "Grips & Bar Ends",
    "bmx gyro kits": "Detanglers", "bmx gyro cables": "Detanglers", "bmx spokes": "Spokes & Nipples",
    "freewheel cogs": "Drivers & Freewheels", "bmx brake spares": "Brakes & Accessories", "bmx disc brakes": "Brakes & Accessories",
    "race bmx mini": "Complete Bikes", "race bmx": "Complete Bikes",
    "bottom brackets": "Bottom Brackets", "bottom bracket": "Bottom Brackets", "bb": "Bottom Brackets",
    "chains": "Chains", "chain": "Chains",
    "chain tensioners": "Chain Tensioners", "chain tensioner": "Chain Tensioners", "tensioners": "Chain Tensioners",
    "pedals": "Pedals", "pedal": "Pedals", "bmx pedals": "Pedals",
    "hubs": "Hubs", "hub": "Hubs", "bmx hubs": "Hubs", "hubsets": "Hubs", "bmx rear hubs": "Hubs",
    "bmx front hubs": "Hubs", "hub parts": "Hub Parts", "bmx hub spares": "Hub Parts",
    "drivers": "Drivers & Freewheels", "freewheels": "Drivers & Freewheels",
    "rims": "Rims & Rim Strips", "rim": "Rims & Rim Strips", "bmx rims": "Rims & Rim Strips", "rim strips": "Rims & Rim Strips",
    "rim strip": "Rims & Rim Strips",
    "spokes": "Spokes & Nipples", "spoke": "Spokes & Nipples", "spokes nipples": "Spokes & Nipples",
    "nipples": "Spokes & Nipples",
    "axles": "Axles",
    "hub guards": "Hub Guards", "hub guard": "Hub Guards", "hubguards": "Hub Guards",
    "pegs": "Pegs", "peg": "Pegs",
    "valve caps": "Valve Caps", "valve cap": "Valve Caps",
    "tires": "Tires", "tire": "Tires", "bmx tires": "Tires", "bmx tyres": "Tires", "tyres": "Tires",
    "tubes": "Tubes", "tube": "Tubes", "bmx innertubes": "Tubes", "innertubes": "Tubes",
    "seats": "Seats", "seat": "Seats", "bmx seats": "Seats",
    "seat posts": "Seat Posts", "seat post": "Seat Posts", "seatposts": "Seat Posts",
    "seat clamps": "Seat Post Clamps", "seat clamp": "Seat Post Clamps", "seat post clamps": "Seat Post Clamps",
    "seat post clamp": "Seat Post Clamps", "seat posts clamps": "Seat Post Clamps", "bmx seat clamps": "Seat Post Clamps",
    "brakes": "Brakes & Accessories", "brake": "Brakes & Accessories", "brake levers": "Brakes & Accessories",
    "levers": "Brakes & Accessories", "brake cables": "Brakes & Accessories", "cables": "Brakes & Accessories",
    "brake parts": "Brakes & Accessories", "brake pads": "Brakes & Accessories", "bmx brakes": "Brakes & Accessories",
    "bmx brake cables": "Brakes & Accessories", "bmx brake levers": "Brakes & Accessories",
}

_KIND_WORDS = tuple(sorted((word for word in KINDS if word not in ("bikes", "bmx bikes", "bmx bike", "cables", "levers")),
                           key=len, reverse=True))

# Kinds read from the title when the store's type is only the category
# ("Wheels" -> Front / Rear), or vague.
_TITLE_KINDS = (
    ("Wheels", "Front Wheels", re.compile(r"\bfront\b", re.I)),
    ("Wheels", "Rear Wheels", re.compile(r"\b(rear|back)\b|freecoaster wheel|cassette wheel", re.I)),
    ("Wheels", "Wheelsets", re.compile(r"\bwheel ?sets?\b|\bpair\b", re.I)),
)


def wheel_size(title, tags=()):
    for tag in tags or ():
        match = _TAG.match(str(tag).strip())
        if match:
            return match.group(1)
    text = str(title or "")
    sizes = {match.group(1) for pattern in (_SIZE, _TIRE) for match in pattern.finditer(text)}
    return sizes.pop() if len(sizes) == 1 else None


def kind_for(type_key, title, category):
    if category == "Wheels":
        return "Wheels"  # front / rear not split yet (owner, 2026-11-01)
    if category == "Bikes":
        return "Complete Bikes"
    kind = KINDS.get(type_key)
    if kind:
        return kind
    for wanted, label, pattern in _TITLE_KINDS:
        if category == wanted and pattern.search(title or ""):
            return label
    # A vague store type ("PARTS"): a type word in the title, longest first.
    text = " " + re.sub(r"[^a-z0-9]+", " ", str(title or "").casefold()) + " "
    for word in _KIND_WORDS:
        if f" {word} " in text:
            return KINDS[word]
    return None


@functools.lru_cache(maxsize=None)
def _category_words(aliases_path):
    try:
        with open(aliases_path, encoding="utf-8") as handle:
            categories = json.load(handle).get("categories") or {}
    except (OSError, ValueError):
        return ()
    words = [(word.casefold(), category) for category, others in categories.items() for word in others or ()]
    # Longest first, so "wheel parts" wins over "wheel".
    return tuple(sorted(words, key=lambda pair: -len(pair[0])))


def category_for_title(title, aliases_path):
    text = " " + re.sub(r"[^a-z0-9]+", " ", str(title or "").casefold()) + " "
    for word, category in _category_words(str(aliases_path)):
        if f" {word} " in text:
            return category
    return None
