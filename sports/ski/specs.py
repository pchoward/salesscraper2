"""Ski listing details the filters use, read from the store's own data.

Nothing here is guessed: a field is left out when the store doesn't state it.

* ``lengths``: ski lengths in cm that are on sale and buyable ("164", "171"),
  from the variant options (Gear West's "Size" / "Ski Length").
* ``sizes``: boot mondo sizes on sale and buyable ("26.5"), from the variants.
* ``kind``: the style the store files it under: Park, Race, Touring, Telemark,
  All Mountain (from the product type or tags).
* ``gender``: Men, Women or Kids, from the product type or tags.
"""

import re

# Sidebar spec filters (key -> label), shaped like sports/mtb/specs.FIELDS on
# codex/mtb-catalog; PARAMS are their URL keys.
FIELDS = {"length_cm": "Ski length (cm)", "mondo": "Boot size (mondo)", "style": "Style", "gender": "Gender"}
PARAMS = {"length_cm": "ski_length", "mondo": "ski_mondo", "style": "ski_style", "gender": "ski_gender"}

_LENGTH = re.compile(r"^\s*(\d{2,3})(?:\s*cm)?\s*$", re.I)
_MONDO = re.compile(r"^\s*(\d{2}(?:\.5)?)(?:\s*mondo)?\s*$", re.I)
_STYLES = (
    ("Park", re.compile(r"\bpark\b|\bfreestyle\b|\btwin ?tip\b", re.I)),
    ("Race", re.compile(r"\brace\b|\bracing\b", re.I)),
    ("Touring", re.compile(r"\btouring\b|\bbackcountry\b|\bskimo\b", re.I)),
    ("Telemark", re.compile(r"\btelemark\b", re.I)),
    ("All Mountain", re.compile(r"\ball[ -]?mountain\b", re.I)),
)
_GENDERS = (
    ("Kids", re.compile(r"\bkids?\b|\bkid's\b|\bjunior\b|\bjr\b|\byouth\b", re.I)),
    ("Women", re.compile(r"\bwomen'?s?\b|\bwmn'?s\b|\bwomens\b", re.I)),
    ("Men", re.compile(r"\bmen'?s?\b|\bmens\b", re.I)),
)


def _option_values(product, variant, names):
    """This variant's values for options whose name is one of ``names``."""
    values = []
    for index, option in enumerate(product.get("options") or [], start=1):
        name = option.get("name") if isinstance(option, dict) else option
        if str(name or "").strip().casefold() in names:
            value = variant.get(f"option{index}")
            if value:
                values.append(str(value))
    return values


def variant_length(product, variant):
    return lengths(product, [variant])


def variant_mondo(product, variant):
    return boot_sizes(product, [variant])


def lengths(product, variants):
    found = set()
    for variant in variants:
        for value in _option_values(product, variant, {"size", "ski length", "length"}):
            match = _LENGTH.match(value)
            if match and 60 <= int(match.group(1)) <= 210:
                found.add(match.group(1))
    return sorted(found, key=int)


_TITLE_LENGTH = re.compile(r"(?<![\d.])(\d{2,3})\s?cm\b", re.I)


def title_length(title):
    """A ski length stated once in the title ("... SL 150cm R22 Race Ski")."""
    found = {match.group(1) for match in _TITLE_LENGTH.finditer(str(title or "")) if 60 <= int(match.group(1)) <= 210}
    return sorted(found) if len(found) == 1 else []


def boot_sizes(product, variants):
    found = set()
    for variant in variants:
        for value in _option_values(product, variant, {"size", "mondo boot size", "mondo", "boot size"}):
            match = _MONDO.match(value)
            if match and 15 <= float(match.group(1)) <= 33:
                found.add(match.group(1))
    return sorted(found, key=float)


def style(product_type, tags):
    for text in [str(product_type or "")] + [str(tag) for tag in tags or ()]:
        for label, pattern in _STYLES:
            if pattern.search(text):
                return label
    return None


def gender(product_type, tags):
    for text in [str(product_type or "")] + [str(tag) for tag in tags or ()]:
        for label, pattern in _GENDERS:
            if pattern.search(text):
                return label
    return None
