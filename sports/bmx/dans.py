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
        labelled = {value for pattern in _TT_TEXT for value in pattern.findall(sentence)}
        for value in _INCHES.findall(sentence):
            if not 18 <= float(value) <= 22.5:
                continue
            # A whole wheel size ("20\" wheels") in the same sentence is not a
            # top tube unless it is the labelled one ("Top tube: 20\"").
            if float(value) in (18, 20, 22) and value not in labelled:
                continue
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


# ---- Dan's Comp filters by product kind (owner, 2026-11-21) ------------------
# Sprocket teeth, crank length, tire size, hub holes and driver, seat style,
# stem type and reach, fork offset. The same stated-only rule as above: the
# title or a variant's option, or a description that names exactly one value.
# The kind decides what a generic "Size" option means (25T on a sprocket,
# 170mm on a crank, 20x2.35 on a tire, 50mm on a stem).

SEAT_STYLES = (("Pivotal", re.compile(r"\bpivotal\b", re.I)), ("Tripod", re.compile(r"\btripod\b", re.I)),
               ("Railed", re.compile(r"\brail(?:ed|s)?\b(?!\s*clamps?\b)", re.I)))
STEM_TYPES = (("Front load", re.compile(r"\bfront[\s-]*load\b", re.I)), ("Top load", re.compile(r"\btop[\s-]*load\b", re.I)))
_TEETH_TITLE = re.compile(r"(?<![\d.])(\d{2})\s?t(?:ooth|eeth)?\b", re.I)
_TEETH_OPTION = re.compile(r"^\s*(\d{2})\s?(?:t(?:ooth|eeth)?\b|\s+\d/\d|$)", re.I)    # 25T, 37, 37 3/8
_TIRE_SIZE = re.compile(r"(?<![\d.])(12|14|16|18|20|22|24|26)\s?[x×]\s?(\d\.\d{1,2})\b")
_HOLES = re.compile(r"(?<![\d.])(20|28|32|36|48)\s?h(?:oles?)?\b", re.I)
_DRIVER = (re.compile(r"(?<![\d.])(\d{1,2})\s?t\s*(?:driver|cog)\b", re.I),
           re.compile(r"\bdriver\s*[:=\-]?\s*(\d{1,2})\s?t\b", re.I))
_OFFSET = (re.compile(r"(?<![\d.])(\d{2})\s?mm\s+(?:of\s+)?offset\b", re.I),
           re.compile(r"\boffset\s*[:=\-]?\s*(\d{2})\s?mm\b", re.I))
_MM_OPTION = re.compile(r"^\s*(\d{2,3}(?:\.\d)?)\s?mm\s*$", re.I)


def _one(labels):
    labels = set(labels)
    return labels.pop() if len(labels) == 1 else None


def _width(value):
    return f"{float(value):.2f}".rstrip("0").rstrip(".") + '"'


def kind_fields(kind, title, text=""):
    """Listing-wide Dan's filters for this kind of part."""
    title, text = str(title or ""), " ".join(str(text or "").split())
    fields = {}

    def stated(found_in_title, found_in_text):
        """The title's single value, else the description's single value."""
        return _one(found_in_title) or (None if found_in_title else _one(found_in_text))

    if kind == "Sprockets":
        value = stated([m for m in _TEETH_TITLE.findall(title) if 15 <= int(m) <= 60],
                       [m for m in _TEETH_TITLE.findall(text) if 15 <= int(m) <= 60])
        if value:
            fields["teeth"] = [f"{int(value)}T"]
    elif kind == "Tires":
        value = stated([w for _, w in _TIRE_SIZE.findall(title)], [w for _, w in _TIRE_SIZE.findall(text)])
        if value:
            fields["tire_width"] = [_width(value)]
    elif kind == "Seats":
        style = stated([label for label, p in SEAT_STYLES if p.search(title)],
                       [label for label, p in SEAT_STYLES if p.search(text)])
        if style:
            fields["seat_style"] = [style]
    elif kind == "Stems":
        load = stated([label for label, p in STEM_TYPES if p.search(title)],
                      [label for label, p in STEM_TYPES if p.search(text)])
        if load:
            fields["stem_type"] = [load]
    elif kind in ("Hubs", "Wheels"):
        holes = _one(_HOLES.findall(title))
        if holes:
            fields["hub_holes"] = [f"{holes}H"]
        driver = stated([m for p in _DRIVER for m in p.findall(title) if 6 <= int(m) <= 12],
                        [m for p in _DRIVER for m in p.findall(text) if 6 <= int(m) <= 12])
        if driver:
            fields["driver"] = [f"{int(driver)}T"]
    elif kind == "Forks":
        offset = stated([m for p in _OFFSET for m in p.findall(title) if 15 <= int(m) <= 35],
                        [m for p in _OFFSET for m in p.findall(text) if 15 <= int(m) <= 35])
        if offset:
            fields["fork_offset"] = [f"{int(offset)} mm"]
    return fields


def kind_variant_fields(kind, product, variant):
    """Dan's filters a variant's options state, read by this kind of part."""
    fields = {}
    for name, value in _options(product, variant):
        if "colo" in name:
            continue
        if kind == "Sprockets" and name in ("size", "teeth", "tooth count", "gear", "options"):
            match = _TEETH_OPTION.match(value)
            if match and 15 <= int(match.group(1)) <= 60:
                fields.setdefault("teeth", set()).add(f"{int(match.group(1))}T")
        elif kind == "Cranks" and name in ("size", "length", "crank length", "arm length", "options"):
            match = _MM_OPTION.match(value)
            if match and 140 <= float(match.group(1)) <= 185:
                fields.setdefault("crank_length", set()).add(match.group(1).rstrip("0").rstrip(".") + " mm"
                                                             if "." in match.group(1) else match.group(1) + " mm")
        elif kind == "Tires":
            match = _TIRE_SIZE.search(value)
            if match:
                fields.setdefault("tire_width", set()).add(_width(match.group(2)))
        elif kind in ("Hubs", "Wheels"):
            holes = _HOLES.findall(value)
            if len(set(holes)) == 1:
                fields.setdefault("hub_holes", set()).add(f"{holes[0]}H")
        elif kind == "Stems" and name in ("size", "reach", "length", "stem reach", "options"):
            match = _MM_OPTION.match(value)
            if match and 25 <= float(match.group(1)) <= 75:
                fields.setdefault("stem_reach", set()).add(f"{int(float(match.group(1)))} mm")
    return {key: sorted(values) for key, values in fields.items()}
