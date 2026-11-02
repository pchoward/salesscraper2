"""Dan's Comp-style BMX filters (docs/multi-sport-plan.md section 3):
Hub Type, Toptube Length, Drive Side, Material and Color.

Read only from what the store states: the title for a listing's own specs
(Freecoaster, RHD, Chromoly), and each variant's option values for what
varies by variant (a frame's top tube, a hub's drive side, a colour).
Nothing is guessed from model names; a field is left out when not stated.
Colour is never read from titles ("Black Ops" is a brand).
"""

import re

HUB_TYPES = (("Freecoaster", re.compile(r"\bfree ?coaster\b|\bfc\b", re.I)),
             ("Cassette", re.compile(r"\bcassette\b|\bcass\b", re.I)))
DRIVE_SIDES = (("Right (RHD)", re.compile(r"\b(rhd|rsd|right[- ]?hand(?:[- ]drive)?|right[- ]side(?:[- ]drive)?)\b", re.I)),
               ("Left (LHD)", re.compile(r"\b(lhd|lsd|left[- ]?hand(?:[- ]drive)?|left[- ]side(?:[- ]drive)?)\b", re.I)))
MATERIALS = (("Chromoly", re.compile(r"\bchromoly\b|\bchro-?moly\b|\bcr-?mo\b|\b4130\b", re.I)),
             ("Carbon", re.compile(r"\bcarbon\b", re.I)),
             ("Titanium", re.compile(r"\btitanium\b", re.I)),
             ("Aluminum", re.compile(r"\balumin(?:um|ium)\b|\balloy\b|\b6061\b|\b7075\b", re.I)),
             ("Hi-Ten", re.compile(r"\bhi-?ten(?:sile)?\b", re.I)),
             ("Nylon / Plastic", re.compile(r"\bnylon\b|\bplastic\b|\bpc\b|\bpolycarbonate\b", re.I)))
# Basic colours, as the colour filter shows them. First match wins, so
# specific finishes come before the plain colour words they contain.
COLORS = (("Oil Slick", r"oil ?slick|rainbow|iridescent"), ("Chrome / Polished", r"chrome|polished|silver|raw|clear coat"),
          ("Black", r"black|matte black|gloss black|blk"), ("White", r"white"), ("Red", r"red|crimson"),
          ("Blue", r"blue|navy|cyan"), ("Green", r"green|olive|army"), ("Yellow", r"yellow"),
          ("Orange", r"orange"), ("Purple", r"purple|violet|lavender"), ("Pink", r"pink|magenta"),
          ("Grey", r"gr[ae]y|gunmetal|charcoal|graphite"), ("Gold", r"gold|bronze|copper"),
          ("Brown", r"brown|tan|gum|sand|khaki"), ("Teal", r"teal|turquoise|mint"))
_COLORS = tuple((label, re.compile(r"\b(?:" + words + r")\b", re.I)) for label, words in COLORS)
_TOP_TUBE = re.compile(r"^\s*(\d{2}(?:\.\d{1,3})?)\s*(?:\"|”|″|''|in(?:ch(?:es)?)?)?\s*(?:tt|top ?tube)?\s*$", re.I)
_TT_IN_VALUE = re.compile(r"(\d{2}(?:\.\d{1,3})?)\s*(?:\"|”|″|in)?\s*(?:tt\b|top ?tube)", re.I)


def _first(patterns, text):
    for label, pattern in patterns:
        if pattern.search(text or ""):
            return label
    return None


def _options(product, variant):
    """[(option name, value)] for this variant, from the store's option names."""
    pairs = []
    for index, option in enumerate(product.get("options") or [], start=1):
        name = option.get("name") if isinstance(option, dict) else option
        value = variant.get(f"option{index}")
        if value:
            pairs.append((str(name or "").strip().casefold(), str(value)))
    return pairs


def _top_tube(name, value, part):
    """A top tube in inches (18-22.5) from a variant option, or None."""
    match = _TT_IN_VALUE.search(value)
    if match:
        number = float(match.group(1))
        return match.group(1) if 18 <= number <= 22.5 else None
    match = _TOP_TUBE.match(value)
    if not match:
        return None
    number = float(match.group(1))
    named = "top tube" in name or name in ("tt", "toptube", "top tube length")
    # A frame's size option is its top tube; a bike's bare "20" is a wheel size.
    if named or (part == "Frames & Forks" and name in ("size", "options", "option", "frame size", "length")
                 and ("." in match.group(1) or number not in (18, 20, 22))):
        return match.group(1) if 18 <= number <= 22.5 else None
    return None


def listing_fields(title, part):
    """Specs the title states for the whole listing."""
    fields = {}
    hub = _first(HUB_TYPES, title) if part in ("Bikes", "Wheels", "Wheel Parts") else None
    if hub:
        fields["hub_type"] = hub
    side = _first(DRIVE_SIDES, title)
    if side:
        fields["drive_side"] = side
    material = _first(MATERIALS, title)
    if material:
        fields["material"] = material
    return fields


def variant_fields(product, variant, part):
    """Specs this variant's options state: colour, top tube, drive side, hub type."""
    fields = {}
    for name, value in _options(product, variant):
        if name in ("color", "colour", "colors", "colours", "color/finish", "finish") or "colo" in name:
            color = _first(_COLORS, value)
            if color:
                fields.setdefault("color", set()).add(color)
            continue
        top_tube = _top_tube(name, value, part)
        if top_tube and part in ("Bikes", "Frames & Forks"):
            fields.setdefault("top_tube", set()).add(top_tube + '"')
            continue
        side = _first(DRIVE_SIDES, value)
        if side:
            fields.setdefault("drive_side", set()).add(side)
        if part in ("Bikes", "Wheels", "Wheel Parts"):
            hub = _first(HUB_TYPES, value)
            if hub:
                fields.setdefault("hub_type", set()).add(hub)
        # A generic option ("Options", "Style") naming a colour: "RSD / Black".
        if name in ("options", "option", "style", "title"):
            color = _first(_COLORS, value)
            if color:
                fields.setdefault("color", set()).add(color)
    return {key: sorted(values) for key, values in fields.items()}


# ---- from the product description (Codex's bmx-catalog-quality approach) ----

_NUM = r"(\d{1,2}(?:\.\d{1,3})?)"
_IN = r"\s*(?:\"|”|″|''|in(?:ch(?:es)?)?\b)"
_TT_TEXT = (re.compile(r"\b(?:top\s*tube|tt)(?:\s*length)?\s*[:=\-]?\s*" + _NUM + _IN, re.I),
            re.compile(_NUM + _IN + r"\s*(?:top\s*tube|tt)\b", re.I))
_RISE = (re.compile(r"\brise\s*[:=\-]?\s*" + _NUM + _IN, re.I),
         re.compile(_NUM + _IN + r"\s*rise\b", re.I))
_CRANK = (re.compile(r"\b(?:crank\s*)?(?:arm\s*)?length\s*[:=\-]?\s*(1[5-8]\d(?:\.\d)?)\s*mm\b", re.I),
          re.compile(r"\b(1[5-8]\d(?:\.\d)?)\s*mm\s*(?:crank|arm|length|long)", re.I))
_SENTENCE_BREAK = re.compile(r"(?<!\d)[.;!?](?!\d)|\n")
_MENTIONS_TT = re.compile(r"\b(?:top\s*tube|tt)\b", re.I)
_INCHES = re.compile(_NUM + _IN)


def _top_tube_text(text):
    """One top tube stated in the sentence(s) that mention it; a sentence
    listing several sizes ("20.5\", 20.75\" and 21\" top tube") gives none."""
    found = set()
    for sentence in (part for part in _SENTENCE_BREAK.split(text) if _MENTIONS_TT.search(part)):
        for value in _INCHES.findall(sentence):
            if 18 <= float(value) <= 22.5:
                found.add(value)
    return found
_AXLE = (("14mm", re.compile(r"\b14\s*mm\s*(?:female\s*|male\s*|chromoly\s*|cr-?mo\s*)?axle", re.I)),
         ("10mm", re.compile(r"\b10\s*mm\s*(?:female\s*|male\s*|chromoly\s*|cr-?mo\s*)?axle", re.I)),
         ("3/8\"", re.compile(r"\b3/8\s*(?:\"|”|in(?:ch)?)?\s*(?:female\s*|male\s*)?axle", re.I)))


def _numbers(patterns, text, low, high):
    found = set()
    for pattern in patterns:
        for value in pattern.findall(text):
            number = float(value)
            if low <= number <= high:
                found.add(value.rstrip("0").rstrip(".") if "." in value else value)
    return found


def description_fields(text, part):
    """Labelled specs from a description; a field with two different
    values is left out (a description listing every size is not one spec)."""
    text = " ".join(str(text or "").split())
    fields = {}
    if part in ("Bikes", "Frames & Forks"):
        values = _top_tube_text(text)
        if len(values) == 1:
            fields["top_tube"] = [values.pop() + '"']
    checks = (
        ("bar_rise", _RISE, 4, 15, ("Steering",), '"'),
        ("crank_length", _CRANK, 150, 185, ("Drivetrain",), " mm"),
    )
    for key, patterns, low, high, parts, unit in checks:
        if part not in parts:
            continue
        values = _numbers(patterns, text, low, high)
        if len(values) == 1:
            fields[key] = [values.pop() + unit]
    if part in ("Wheels", "Wheel Parts", "Frames & Forks", "Bikes"):
        axles = [label for label, pattern in _AXLE if pattern.search(text)]
        if len(axles) == 1:
            fields["axle"] = axles
    return fields
