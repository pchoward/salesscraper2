"""Condition labels from listing names (owner, 2026-11-12: label demo gear).

Demo skis and bikes (Utah Ski's demo skis, Mike's Bikes demos, Bikes Online
"Ex-Demo") are sold at a discount from the new price, like used gear but
less worn. They stay listed, labelled "Demo", and the Condition filter can
show or hide them. Demolition (a BMX brand) is not a demo. Used gear is left
out altogether (filters.py).
"""

import re

DEMO = "Demo"
_DEMO = re.compile(r"\b(?:ex-?\s*)?demo\b", re.I)


def is_demo(name):
    return bool(_DEMO.search(str(name or "")))


def label(item):
    """Set the listing's condition and add it to its filter specs. True when labelled."""
    if not isinstance(item, dict) or item.get("condition") or not is_demo(item.get("name")):
        return False
    item["condition"] = DEMO
    specs = item.get("technical_specs") if isinstance(item.get("technical_specs"), dict) else {}
    item["technical_specs"] = dict(specs, condition=[DEMO])
    for offer in item.get("technical_offers") or ():
        if isinstance(offer, dict):
            offer["specs"] = dict(offer.get("specs") or {}, condition=[DEMO])
    return True


def label_items(data):
    """Label every demo listing in a run's {key: [items]}; returns how many."""
    return sum(label(item) for items in (data or {}).values() for item in items or [])
