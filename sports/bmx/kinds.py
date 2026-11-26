"""BMX Type (the `kind` field), with spares split out (owner, 2026-11-26).

The scrape stores a Dan's Comp-style kind for every listing
(``sports/bmx/specs.py``: Forks, Cranks, Headsets, Brakes & Accessories).
Powers, Source and Circuit keep spares next to the thing itself as their
own type: Source's Fork Top Caps and Crank Spares, Powers' Brake Kits,
Brake Parts, Pads, Levers and Cables. ``refine`` does the same when the page
is built, so the stored kind (and the Dan's filters keyed on it) stays as
scraped. Tools and lubes show under Tools & Care (``sports/mtb/kinds.py``).
"""

import re


def _has(pattern, text):
    return bool(re.search(pattern, text or "", re.I))


def _brakes(name, product_type):
    kind = str(product_type or "").lower()
    if _has(r"\bkits?\b", name) and not _has(r"\bhanger\s*kits?\b|\bspares?\b", name + " " + kind):
        return "Brake Kits"
    if _has(r"\bpads?\b|\binserts?\b|\bshoes?\b", name):
        return "Brake Pads"
    if _has(r"\bcables?\b|\bk-?shield\b|\bslic\b", name) and not _has(r"\bhangers?\b|\bstops?\b|\bends?\b|\bknarps?\b", name):
        return "Brake Cables"
    if _has(r"\blevers?\b|\bmonolever\b|\btrigger\b", name):
        return "Brake Levers"
    if _has(r"\bmounts?\b|\bhangers?\b|\bstops?\b|\bcaps?\b|\bknarps?\b|\bends?\b|\badapt(?:er|or)s?\b|\bbolts?\b|\breturn\s*springs?\b"
            r"|\bspares?\b|\bparts?\b|\bhardware\b", name + " " + kind):
        return "Brake Parts"
    return "Brakes"


# Spare words per stored kind. A name that also ends in the item itself
# ("Thunderbolt Cranks", "Race Fork", "Headset Kit") stays the item.
_SPARES = {
    "Forks": ("Fork Parts", r"\bspacers?\b|\btop\s*caps?\b|\bcompression\b|\bstar\s*nut\b|\bbolts?\b|\bparts?\b|\bcrown\s*race\b",
              r"\bforks?\s*$|\bfork\s*-"),
    "Cranks": ("Crank Parts", r"\bspindles?\b|\bbolts?\b|\bspacers?\b|\bwashers?\b|\bkit\b|\breplacement\b|\bspares?\b|\bbearings?\b",
               r"\bcranks?\s*(?:-|$)|\bcrankset\b"),
    "Headsets": ("Headset Parts", r"\bspacers?\b|\btop\s*caps?\b|\bstar\s*nut\b|\bbearings?\b|\bcups?\b|\bcompression\b|\bcrown\s*race\b",
                 r"\bheadset\s*(?:kit\b|-|$)|\brace\s*headset\b"),
    "Stems": ("Stem Parts", r"\bbolts?\b|\bparts?\b|\bcaps?\b|\breplacement\b", r"\bstem\s*(?:-|$)"),
    "Pedals": ("Pedal Parts", r"\bpins?\b|\baxles?\b|\bspares?\b|\bbearings?\b|\brebuild\b|\bparts?\b", r"\bpedals?\s*(?:-|$)"),
}


def refine(kind, name, product_type=""):
    """The kind shown on the page: the stored kind, or its spares type."""
    name = str(name or "")
    if kind == "Brakes & Accessories":
        return _brakes(name, product_type)
    spare = _SPARES.get(kind)
    if spare:
        label, words, whole = spare
        type_says_spare = _has(r"\bspares?\b|\bspindles?\b|\bspacers?\b|\btop\s*caps?\b|\bparts?\b", str(product_type or ""))
        if (_has(words, name) or type_says_spare) and not _has(whole, name):
            return label
    return kind
