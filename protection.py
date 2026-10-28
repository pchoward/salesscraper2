"""Protective gear: which listings count, their subtype, and their sizes.

Every store's protective gear is the part ``"Protection"``, with one subtype:

    Helmet, Knee Pads, Elbow Pads, Wrist Guards, Pad Set, Other

``Other`` is impact shorts, hip and tailbone pads, and similar. Sizes are
the letter sizes XS–XXL, from a store's size options when it has them, else
from the name. Youth, kids, and "one size" labels are not sizes here.
"""

import re

PART = "Protection"
SUBTYPES = ("Helmet", "Knee Pads", "Elbow Pads", "Wrist Guards", "Pad Set", "Other")
# URL and filter tokens, in display order.
SUBTYPE_TOKENS = {
    "Helmet": "helmet",
    "Knee Pads": "knee",
    "Elbow Pads": "elbow",
    "Wrist Guards": "wrist",
    "Pad Set": "set",
    "Other": "other",
}
SIZES = ("XS", "S", "M", "L", "XL", "XXL")

_RE = lambda pattern: re.compile(pattern, re.IGNORECASE)  # noqa: E731
_KNEE = _RE(r"\bknee\s*(?:pads?|guards?|savers?|gaskets?|protectors?)\b|\bkneepads?\b")
_ELBOW = _RE(r"\belbow\s*(?:pads?|guards?|savers?|gaskets?|protectors?)\b|\belbowpads?\b")
_WRIST = _RE(r"\bwrist\s*(?:guards?|braces?|wraps?|protectors?|savers?)\b|\bwristguards?\b")
_HELMET = _RE(r"\bhelmets?\b")
_SET = _RE(
    r"\b(?:pads?|protective|protection|safety|gear)\s*(?:sets?|packs?|kits?|combos?)\b"
    r"|\bcombo\s*pads?\b|\bpad\s*combo\b"
    r"|\b(?:3|three|6|six)[\s-]*(?:pack|pk|piece|pc)\b"
)
_OTHER = _RE(
    r"\bimpact\s*shorts?\b|\bpadded\s*shorts?\b|\bcrash\s*(?:pads?|shorts?)\b"
    r"|\b(?:hip|tailbone|bum|butt|coccyx)\s*(?:pads?|protectors?|guards?|savers?)\b"
    r"|\bshin\s*guards?\b|\bankle\s*(?:guards?|braces?)\b"
)
# Pads that are not body protection: riser and shock pads are hardware.
_NOT_GEAR = _RE(r"\briser\b|\bshock\s*pads?\b|\bgrip\b|\bhelmet\s*(?:stickers?|bags?|cams?|mounts?)\b")
# A product type that says the whole product is protective gear.
_GEAR_TYPE = _RE(r"\b(?:protect\w*|pads?|helmets?|guards?|safety)\b")


def classify(name, product_type=""):
    """The subtype for a protective-gear listing, or None when it is not one."""
    name = str(name or "")
    kind = str(product_type or "")
    if _NOT_GEAR.search(name):
        return None
    text = f"{name} {kind}"
    bodies = sum(bool(pattern.search(text)) for pattern in (_KNEE, _ELBOW, _WRIST))
    # "Destroyer Pads Elbow and Knee": two body parts in one pads listing.
    loose = sum(bool(re.search(rf"\b{word}s?\b", text, re.IGNORECASE)) for word in ("knee", "elbow", "wrist"))
    if _SET.search(text) or bodies >= 2 or (loose >= 2 and re.search(r"\b(?:pads?|guards?)\b", text, re.IGNORECASE)):
        return "Pad Set"
    if _HELMET.search(text):
        return "Helmet"
    if _KNEE.search(text):
        return "Knee Pads"
    if _ELBOW.search(text):
        return "Elbow Pads"
    if _WRIST.search(text):
        return "Wrist Guards"
    if _OTHER.search(text):
        return "Other"
    if _GEAR_TYPE.search(kind) and re.search(r"\b(?:pads?|guards?|protect\w*)\b", name, re.IGNORECASE):
        return "Other"
    return None


_WORDS = (
    ("XXL", r"xxl|2xl|xx-?large|2x-?large|extra\s+extra\s+large"),
    ("XS", r"xs|x-?small|extra\s+small"),
    ("XL", r"xl|x-?large|extra\s+large"),
    ("S", r"s|sm|small"),
    ("M", r"m|md|med|medium"),
    ("L", r"l|lg|large"),
)
_TOKEN = [(size, re.compile(rf"^(?:{pattern})$", re.IGNORECASE)) for size, pattern in _WORDS]
# Spelled-out sizes anywhere in a name; one-letter sizes only after "size"
# or in parentheses, so the "S" in "S-One" is not a size.
_IN_NAME = re.compile(
    r"\bsize\s*:?\s*(xxl|xs|xl|s|m|l)\b"
    r"|\((xxl|xs|xl|s|m|l)\)"
    r"|\b(xx-?large|x-?large|extra\s+large|x-?small|extra\s+small|small|medium|large|xxl|xl|xs)\b",
    re.IGNORECASE,
)


def size_tokens(value):
    """Letter sizes in one size option: ``"S/M"`` is S and M. Others give []."""
    text = str(value or "").strip()
    # The whole label first, so "X-Large" is XL, not "X" and "Large".
    for size, pattern in _TOKEN:
        if pattern.match(text):
            return [size]
    found = []
    for piece in re.split(r"\s*(?:/|\s-\s|\bto\b|,)\s*|(?<=[a-z])-(?=[a-z]{1,3}$)", text, flags=re.IGNORECASE):
        piece = (piece or "").strip()
        for size, pattern in _TOKEN:
            if piece and pattern.match(piece):
                found.append(size)
                break
    return ordered_sizes(found)


def sizes_in(name):
    """Letter sizes stated in a product name."""
    found = []
    for match in _IN_NAME.finditer(str(name or "")):
        found.extend(size_tokens(next(group for group in match.groups() if group)))
    return ordered_sizes(found)


def ordered_sizes(sizes):
    chosen = set(sizes or ())
    return [size for size in SIZES if size in chosen]


def variant_sizes(variants):
    """Letter sizes from Shopify variant options, in size order."""
    found = []
    for variant in variants or []:
        if not isinstance(variant, dict):
            continue
        for field in ("option1", "option2", "option3", "title"):
            tokens = size_tokens(variant.get(field))
            if tokens:
                found.extend(tokens)
                break
    return ordered_sizes(found)


def ordered_type_tokens(values):
    """Subtype URL tokens (``helmet``, ``knee``, ...) in display order; others dropped."""
    chosen = {str(value or "").strip().casefold() for value in values or ()}
    return [token for token in SUBTYPE_TOKENS.values() if token in chosen]


def ordered_size_tokens(values):
    """Size URL tokens (``s``, ``xl``, ...) in size order; others dropped."""
    chosen = {str(value or "").strip().casefold() for value in values or ()}
    return [size.casefold() for size in SIZES if size.casefold() in chosen]
