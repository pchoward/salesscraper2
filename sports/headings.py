"""Menu headings: how each sport's deals are grouped on its page (owner,
2026-11-07: the menus and filters proposal).

Stores and scrapers keep their own categories (``Sport.parts``): price
history, scrape health, alerts and old links all use them. The page groups
the same deals under headings people shop by:

* Every sport: Helmets, Goggles and Gloves come out of Protection, which
  keeps pads, armor, impact shorts and wrist guards (GEAR, below).
* MTB: Forks & Shocks reads Suspension. Each heading's own parts stay in it
  as a Type value (Fork Parts, Hub Parts, Brake Parts: sports/mtb/kinds.py);
  tools, pumps, lubes and cleaners from any heading show under Tools & Care,
  and brake items a store filed under Wheels or Cockpit show under Brakes
  (owner, 2026-11-26).
* BMX: Wheels and Wheel Parts are one Wheels & Hubs; BMX shop words for the rest.
  Spares get their own Type (Fork Parts, Crank Parts, Brake Pads:
  sports/bmx/kinds.py) and tools and lubes show under Tools & Care
  (owner, 2026-11-26).
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

# Packs reads the way the stores say it (owner, 2026-11-26): ski, skate and
# BMX shops say "Backpacks"; bike shops lead with hydration (Fanatik's "Packs
# & Hydration", evo's "Hydration Packs & Bags"). The store category stays
# Packs. Skate's menu is built in page.py/page.js (Codex's task 25).
PACKS = "Packs"
PACKS_HEADING = {"ski": "Backpacks", "bmx": "Backpacks", "mtb": "Packs & Hydration"}
PACKS_HEADINGS = (PACKS,) + tuple(sorted(set(PACKS_HEADING.values())))


def _gear(sport_id):
    return tuple(PACKS_HEADING.get(sport_id, PACKS) if name == PACKS else name for name in GEAR)


HEADINGS = {
    "skate": ("Decks", "Completes", "Trucks", "Wheels", "Bearings", "Accessories") + GEAR + ("Sneakers",),
    "ski": ("Skis", "Boots", "Bindings", "Poles") + _gear("ski"),
    "mtb": ("Bikes", "Frames", "Suspension", "Wheels", "Tires", "Drivetrain", "Brakes", "Cockpit", "Pedals",
            "Tools & Care") + _gear("mtb"),
    "bmx": ("Bikes", "Frames & Forks", "Bars & Steering", "Drivetrain", "Wheels & Hubs", "Tires & Tubes",
            "Seats & Posts", "Brakes", "Tools & Care") + _gear("bmx"),
}

# Store category -> heading, where it is a plain rename or merge.
_RENAMED = {
    "ski": {PACKS: PACKS_HEADING["ski"]},
    "mtb": {"Forks & Shocks": "Suspension", PACKS: PACKS_HEADING["mtb"]},
    "bmx": {"Steering": "Bars & Steering", "Wheels": "Wheels & Hubs", "Wheel Parts": "Wheels & Hubs",
            "Tires": "Tires & Tubes", "Seating": "Seats & Posts", "Braking": "Brakes", PACKS: PACKS_HEADING["bmx"]},
}

# Old ?type= links keep working: the old category's slug opens its heading.
ALIASES = {
    "ski": {"body-armor": "Protection", "packs": PACKS_HEADING["ski"], "pack": PACKS_HEADING["ski"]},
    "mtb": {"forks-shocks": "Suspension", "packs": PACKS_HEADING["mtb"], "pack": PACKS_HEADING["mtb"]},
    "bmx": {"steering": "Bars & Steering", "wheels": "Wheels & Hubs", "wheel-parts": "Wheels & Hubs",
            "tires": "Tires & Tubes", "seating": "Seats & Posts", "braking": "Brakes", "pads-gloves": "Protection",
            "packs": PACKS_HEADING["bmx"], "pack": PACKS_HEADING["bmx"]},
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


TOOLS_AND_CARE = "Tools & Care"
# MTB store categories whose listings get a Type (sports/mtb/kinds.py).
_MTB_TYPED = ("Forks & Shocks", "Wheels", "Tires", "Drivetrain", "Brakes", "Cockpit", "Pedals")


def _mtb_place(item):
    """(store category shown, type) for an MTB listing: tools and care
    items, and brake items filed elsewhere, move; parts keep their heading."""
    from sports.mtb import kinds
    part = item.get("part") or ""
    if part not in _MTB_TYPED:
        return part, None
    name, kind = item.get("name") or "", item.get("product_type") or ""
    if kinds.is_tools_and_care(name, kind):
        return TOOLS_AND_CARE, None
    shown = kinds.heading_part(part, name, kind)
    return shown, kinds.kind(part, name, kind)


_GEAR_PARTS = ("Protection", "Packs", "Bikes", "Frames")


def _bmx_place(item):
    """(store category shown, kind) for a BMX listing: tools and lubes move
    to Tools & Care; spares keep their heading under their own kind."""
    from sports.bmx import kinds as bmx_kinds
    from sports.mtb import kinds
    part = item.get("part") or ""
    if part in _GEAR_PARTS:
        return part, None
    name, kind = item.get("name") or "", item.get("product_type") or ""
    if kinds.is_tools_and_care(name, kind):
        return TOOLS_AND_CARE, None
    stored = item.get("kind")
    refined = bmx_kinds.refine(stored, name, kind) if stored else None
    return part, refined if refined != stored else None


def heading(sport_id, item):
    """The heading a deal (or price-history row) is shown under."""
    part = (item or {}).get("part") or ""
    if sport_id == "mtb" and part in _MTB_TYPED:
        part = _mtb_place(item)[0]
    elif sport_id == "bmx" and part not in _GEAR_PARTS:
        part = _bmx_place(item)[0]
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


def _with_kind(item, kind):
    """A copy of an MTB listing with its Type on every offer, so the
    sidebar's Type filter (``kind``) reads it like any other spec."""
    if not kind:
        return item
    offers = [dict(offer, specs=dict(offer.get("specs") or {}, kind=[kind])) if isinstance(offer, dict) else offer
              for offer in item.get("technical_offers") or []]
    specs = dict(item.get("technical_specs") or {}, kind=[kind])
    return dict(item, technical_offers=offers, technical_specs=specs)


def _regrouped(item, sport_id):
    shown = dict(item, part=heading(sport_id, item), store_part=item.get("part"))
    if sport_id == "mtb":
        shown = _with_kind(shown, _mtb_place(item)[1])
    elif sport_id == "bmx" and shown["part"] != TOOLS_AND_CARE:
        refined = _bmx_place(item)[1]
        if refined:
            shown = dict(_with_kind(shown, refined), kind=refined)
    return shown


def regroup(data, sport_id):
    """A copy of a run's {key: [items]} with each item under its heading."""
    if sport_id not in HEADINGS:
        return data
    return {key: [_regrouped(item, sport_id) if isinstance(item, dict) else item for item in items or []]
            for key, items in (data or {}).items()}


def regroup_history(history, sport_id):
    """A copy of the price history with each row under its heading."""
    if sport_id not in HEADINGS or not isinstance(history, dict):
        return history
    return {url: dict(entry, part=heading(sport_id, entry), store_part=entry["part"])
            if isinstance(entry, dict) and entry.get("part") else entry
            for url, entry in history.items()}
