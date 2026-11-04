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


# Vendor values that are a condition or a placeholder, not a brand.
NOT_BRANDS = {"scratch & dent", "scratch and dent", "scratch dent", "misc", "default", "unknown", "n a", "none"}


def canonical(vendor, aliases_path):
    vendor = " ".join(str(vendor or "").split())
    if not vendor or _key(vendor) in NOT_BRANDS:
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


@functools.lru_cache(maxsize=None)
def _prefixes(aliases_path):
    """(spelling key, canonical) pairs, longest spelling first."""
    pairs = [(spelling, canonical) for spelling, canonical in _table(aliases_path).items() if spelling]
    return tuple(sorted(pairs, key=lambda pair: -len(pair[0])))


def from_title(name, aliases_path):
    """The brand a listing's name starts with ("Pro-Tec Classic Helmet" ->
    "Pro-Tec", "Triple Eight Deep Cover" -> "Triple 8"), from the sport's
    brand list, or "" when it names none. The longest spelling wins, on word
    boundaries, so "Pro-Tec" is never "Pro" and "Profile" never "Pro"."""
    key = _key(name)
    for spelling, canonical in _prefixes(str(aliases_path)):
        if key == spelling or key.startswith(spelling + " "):
            return canonical
    return ""


def settle(items, aliases_path):
    """One spelling per brand for a run's listings (owner, 2026-11-04: 187,
    Pro-Tec and Triple 8 showed under two names). A listing without a brand
    gets the one its name starts with; a store's own spelling becomes the
    canonical one. Listings whose name starts with no known brand keep none."""
    for item in items or ():
        if not isinstance(item, dict):
            continue
        brand = item.get("brand") or ""
        if brand:
            item["brand"] = canonical(brand, aliases_path) or brand
        else:
            found = from_title(item.get("name") or "", aliases_path)
            if found:
                item["brand"] = found
    return items
