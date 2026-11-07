"""Menu headings: how each sport's deals are grouped on its page (owner,
2026-11-07: the menus and filters proposal).

Stores and scrapers keep their own categories (``Sport.parts``): price
history, scrape health, alerts and old links all use them. The page groups
the same deals under headings people shop by:

* Ski: Goggles and Body Armor come out of Protection (93% of it was goggles).
* MTB: Helmets come out of Protection; Forks & Shocks reads Suspension.
* BMX: Helmets come out of Protection, the rest is Pads & Gloves; Wheels and
  Wheel Parts are one Wheels & Hubs; BMX shop words for the rest.

A heading is a thing to shop for. Types within it (ski type, hub vs rim)
are filters, not more headings, so the menu stays short on a phone.
"""

import re

from sports.protection import protects as _protects

HEADINGS = {
    "ski": ("Skis", "Boots", "Bindings", "Poles", "Helmets", "Goggles", "Body Armor"),
    "mtb": ("Bikes", "Frames", "Suspension", "Wheels", "Tires", "Drivetrain", "Brakes", "Cockpit", "Pedals",
            "Helmets", "Protection"),
    "bmx": ("Bikes", "Frames & Forks", "Bars & Steering", "Drivetrain", "Wheels & Hubs", "Tires & Tubes",
            "Seats & Posts", "Brakes", "Helmets", "Pads & Gloves"),
}

# Store category -> heading, where it is a plain rename or merge.
_RENAMED = {
    "mtb": {"Forks & Shocks": "Suspension"},
    "bmx": {"Steering": "Bars & Steering", "Wheels": "Wheels & Hubs", "Wheel Parts": "Wheels & Hubs",
            "Tires": "Tires & Tubes", "Seating": "Seats & Posts", "Braking": "Brakes"},
}

# Old ?type= links keep working: the old category's slug opens its heading.
ALIASES = {
    "ski": {"protection": "Goggles"},
    "mtb": {"forks-shocks": "Suspension"},
    "bmx": {"steering": "Bars & Steering", "wheels": "Wheels & Hubs", "wheel-parts": "Wheels & Hubs",
            "tires": "Tires & Tubes", "seating": "Seats & Posts", "braking": "Brakes", "protection": "Pads & Gloves"},
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
        if sport_id == "ski":
            return "Goggles" if kinds & {"Goggles", "Goggle lenses"} or re.search(r"\bgoggles?\b", item.get("name") or "", re.I) \
                else "Body Armor"
        if sport_id in ("mtb", "bmx"):
            if "Helmets" in kinds:
                return "Helmets"
            return "Protection" if sport_id == "mtb" else "Pads & Gloves"
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
