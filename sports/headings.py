"""Menu headings: how each sport's deals are grouped on its page (owner,
2026-11-07: the menus and filters proposal).

Stores and scrapers keep their own categories (``Sport.parts``): price
history, scrape health, alerts and old links all use them. The page groups
the same deals under headings people shop by:

* Every sport: Helmets, Goggles and Gloves come out of Protection, which
  keeps pads, armor, impact shorts and wrist guards (GEAR, below).
* MTB: Forks & Shocks reads Suspension.
* BMX: Wheels and Wheel Parts are one Wheels & Hubs; BMX shop words for the rest.
* Skate: shop order, Helmets out of Protection.

A heading is a thing to shop for. Types within it (ski type, hub vs rim)
are filters, not more headings, so the menu stays short on a phone.
"""

import re

from sports.protection import protects as _protects

# The gear at the bottom of every menu has the same names on every sport
# (owner, 2026-11-07; the map is docs/menu-wireframe.md): Helmets, Goggles, Gloves,
# then Protection for pads, armor, impact shorts and wrist guards. A
# heading with no deals is not shown.
# Packs (owner, 2026-11-12): backpacks and hydration packs, after Protection.
GEAR = ("Helmets", "Goggles", "Gloves", "Protection", "Packs")

HEADINGS = {
    "skate": ("Decks", "Completes", "Trucks", "Wheels", "Bearings", "Accessories") + GEAR + ("Sneakers",),
    "ski": ("Skis", "Boots", "Bindings", "Poles") + GEAR,
    "mtb": ("Bikes", "Frames", "Suspension", "Wheels", "Tires", "Drivetrain", "Brakes", "Cockpit", "Pedals") + GEAR,
    "bmx": ("Bikes", "Frames & Forks", "Bars & Steering", "Drivetrain", "Wheels & Hubs", "Tires & Tubes",
            "Seats & Posts", "Brakes") + GEAR,
}

# Store category -> heading, where it is a plain rename or merge.
_RENAMED = {
    "mtb": {"Forks & Shocks": "Suspension"},
    "bmx": {"Steering": "Bars & Steering", "Wheels": "Wheels & Hubs", "Wheel Parts": "Wheels & Hubs",
            "Tires": "Tires & Tubes", "Seating": "Seats & Posts", "Braking": "Brakes"},
}

# Old ?type= links keep working: the old category's slug opens its heading.
ALIASES = {
    "ski": {"body-armor": "Protection"},
    "mtb": {"forks-shocks": "Suspension"},
    "bmx": {"steering": "Bars & Steering", "wheels": "Wheels & Hubs", "wheel-parts": "Wheels & Hubs",
            "tires": "Tires & Tubes", "seating": "Seats & Posts", "braking": "Brakes", "pads-gloves": "Protection"},
}


def headings(sport):
    """The sport's menu headings, in order (its store categories when it has
    no headings of its own: Skate)."""
    return HEADINGS.get(sport.id, tuple(sport.parts))


def _protected(item):
    specs = item.get("technical_specs") if isinstance(item.get("technical_specs"), dict) else {}
    found = specs.get("protects")
    if found:
        return set(found if isinstance(found, list) else [found])
    return set(_protects(item.get("name") or "", item.get("product_type") or ""))


def heading(sport_id, item):
    """The heading a deal (or price-history row) is shown under."""
    part = (item or {}).get("part") or ""
    if part == "Protection":
        kinds = _protected(item)
        if "Helmets" in kinds:
            return "Helmets"
        if kinds & {"Goggles", "Goggle lenses"} or re.search(r"\bgoggles?\b", item.get("name") or "", re.I):
            return "Goggles"
        if kinds == {"Gloves"}:
            return "Gloves"
        return "Protection"
    return _RENAMED.get(sport_id, {}).get(part, part)


def regroup(data, sport_id):
    """A copy of a run's {key: [items]} with each item under its heading."""
    if sport_id not in HEADINGS:
        return data
    return {key: [dict(item, part=heading(sport_id, item), store_part=item.get("part")) if isinstance(item, dict) else item
                  for item in items or []]
            for key, items in (data or {}).items()}


def regroup_history(history, sport_id):
    """A copy of the price history with each row under its heading."""
    if sport_id not in HEADINGS or not isinstance(history, dict):
        return history
    return {url: dict(entry, part=heading(sport_id, entry), store_part=entry["part"])
            if isinstance(entry, dict) and entry.get("part") else entry
            for url, entry in history.items()}
