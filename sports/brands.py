"""One spelling per brand, from a store's vendor field.

Stores spell brands their own way ("FIT", "Fit Bike Co", "Eastern Bikes",
"CINEMA"). A sport's aliases.json already lists each brand's canonical name
and other spellings, so the same list drives search and the Brand filter.
A vendor not in the list keeps its own spelling, except that an all-caps name
longer than three letters is title-cased ("CINEMA" -> "Cinema"; "BSD", "DK"
stay).
"""

import functools
import json
import re


def _key(text):
    return re.sub(r"[^a-z0-9&]+", " ", str(text or "").casefold()).strip()


@functools.lru_cache(maxsize=None)
def _table(aliases_path):
    try:
        with open(aliases_path, encoding="utf-8") as handle:
            brands = json.load(handle).get("brands") or {}
    except (OSError, ValueError):
        brands = {}
    table = {}
    for canonical, others in brands.items():
        for spelling in [canonical, *(others or [])]:
            table.setdefault(_key(spelling), canonical)
    return table


def canonical(vendor, aliases_path):
    vendor = " ".join(str(vendor or "").split())
    if not vendor:
        return ""
    table = _table(str(aliases_path))
    key = _key(vendor)
    if key in table:
        return table[key]
    # "Haro Bikes" / "Odyssey BMX": the brand without the trade word.
    trimmed = re.sub(r"\s+(bikes?|bmx|co\.?|company|inc\.?|usa)$", "", key)
    if trimmed in table:
        return table[trimmed]
    if vendor.isupper() and len(vendor.replace(" ", "")) > 3:
        return vendor.title()
    return vendor


def for_sport(sport):
    """A ``brand_of`` function for a store of ``sport``."""
    return lambda vendor: canonical(vendor, str(sport.aliases_file()))
