"""Multisport protection brands as Skate stores (owner, 2026-11-03).

Triple 8, 187 Killer Pads, Demon and G-Form sell one catalog for skate, BMX,
bike and snow. Skate reads their sale collections (``sports.protection.
BRAND_STORES``) for Protection only; a piece belongs when it suits skating
(no snow, baseball, soccer or moto gear) and Skate's own protective-gear rules
keep it (``protection.classify``). Only marked-down variants are listed.
"""

import re

import sports
from sports import protection as multisport
from stores import shopify

NAMES = ("Triple 8", "187 Killer Pads", "Demon", "G-Form")


# Mountain-bike gear isn't skate gear (owner, 2026-11-26: Demon's Podium
# full-face, "MTB" in its name, showed under Skate > Helmets).
_BIKE = re.compile(r"\b(?:mtb|mountain\s*bik(?:e|ing)|downhill|enduro|e-?bike|e-?mtb)\b", re.I)


def part_of(title):
    if not multisport.suits("skate", title) or _BIKE.search(title or ""):
        return None
    return "Protection"


def part_of_brand(name):
    """``part_of`` for one brand. Demon's helmets are made for bikes (its
    Podium is a downhill full-face; its loadouts pair a helmet with bike
    shorts), so a Demon helmet is skate gear only when its name says so."""
    def part(title):
        found = part_of(title)
        if found and name == "Demon" and "Helmets" in multisport.protects(title or "") \
                and not re.search(r"\bskate", title or "", re.I):
            return None
        return found
    return part


# TSG through its US distributor, filed by Zeitbike's own sport tags.
from sports import zeitbike

STORES = tuple(multisport.brand_store(name, sports.SKATE, part_of_brand(name)) for name in NAMES) + (zeitbike.store(sports.SKATE),)


def scrapers():
    return [shopify.ShopifyScraper(store, "Protection") for store in STORES]
