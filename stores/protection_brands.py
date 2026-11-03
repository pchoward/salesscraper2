"""Multisport protection brands as Skate stores (owner, 2026-11-03).

Triple 8, 187 Killer Pads, Demon and G-Form sell one catalog for skate, BMX,
bike and snow. Skate reads their sale collections (``sports.protection.
BRAND_STORES``) for Protection only; a piece belongs when it suits skating
(no snow, baseball, soccer or moto gear) and Skate's own protective-gear rules
keep it (``protection.classify``). Only marked-down variants are listed.
"""

import sports
from sports import protection as multisport
from stores import shopify

NAMES = ("Triple 8", "187 Killer Pads", "Demon", "G-Form")


def part_of(title):
    return "Protection" if multisport.suits("skate", title) else None


STORES = tuple(multisport.brand_store(name, sports.SKATE, part_of) for name in NAMES)


def scrapers():
    return [shopify.ShopifyScraper(store, "Protection") for store in STORES]
