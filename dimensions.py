"""Deck dimension parsing and normalization.

``8.5``, ``8.50``, and ``8.50"`` are the same width. Values keep up to four
decimal places, so ``8.125`` stays distinct from ``8.12``.
"""

import re

from filters import extract_deck_dimensions, normalize_product_name

_NUMBER = re.compile(
    r"^\s*(\d{1,2}(?:\.\d+)?)\s*(?:\"|\u201d|\u2033|in(?:ch(?:es)?)?)?\s*$",
    re.IGNORECASE,
)
# A wheelbase as stores write it: 14.25, 14 1/4, 14-1/4, or 14¼, maybe with
# an inch mark. Fractions are eighths or quarters in practice.
_WB_VALUE = r"(\d{2}(?:\.\d+)?(?:[\s-]+\d/\d{1,2}|[\u00bc\u00bd\u00be\u215b\u215c\u215d\u215e])?)"
_WB_LABEL = r"(?:wheel[\s-]?base|\bwb\b)"
_WB_LABEL_FIRST = re.compile(
    _WB_LABEL + r"\s*(?:\((?:in|inches)\)|\[(?:in|inches)\])?\s*[:=\-\u2013|]?\s*(?:is\s+)?" + _WB_VALUE,
    re.IGNORECASE,
)
_WB_NUMBER_FIRST = re.compile(
    r"\b" + _WB_VALUE + r"\s*(?:\"|\u201d|\u2033|in(?:ch(?:es)?)?\b)?\s*" + _WB_LABEL,
    re.IGNORECASE,
)
# "Wheelbase: 14" & 14.62"": decks drilled for two wheelbases list both.
_WB_MORE = re.compile(r"\s*(?:\"|\u201d|\u2033|in\b)?\s*(?:&|and|or|/)\s*" + _WB_VALUE, re.IGNORECASE)
_FRACTIONS = {"\u00bc": 0.25, "\u00bd": 0.5, "\u00be": 0.75, "\u215b": 0.125, "\u215c": 0.375, "\u215d": 0.625, "\u215e": 0.875}
# Street and park decks run about 13-15.5"; anything outside this is not a
# deck wheelbase (or not one we should trust).
WHEELBASE_RANGE = (12.0, 17.0)


def _wb_number(text):
    text = text.strip()
    if text and text[-1] in _FRACTIONS:
        return float(text[:-1]) + _FRACTIONS[text[-1]]
    match = re.match(r"^(\d{2})[\s-]+(\d)/(\d{1,2})$", text)
    if match:
        whole, top, bottom = (int(group) for group in match.groups())
        return whole + top / bottom if bottom and top < bottom else None
    return float(text)


def parse_dimension(value):
    """Return a float for a width, length, or wheelbase, or None.

    Trailing zeros do not matter: ``8.5`` and ``8.50`` both return ``8.5``.
    """
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        number = float(value)
    else:
        text = str(value).strip()
        match = _NUMBER.match(text)
        if not match:
            return None
        number = float(match.group(1))
    if number <= 0 or number > 40:
        return None
    return round(number, 4)


def normalize_dimension(value):
    """Alias for :func:`parse_dimension`. ``8.5`` matches ``8.50``."""
    return parse_dimension(value)


def dimension_key(value):
    """Stable text key. ``8.50`` and ``8.5`` both become ``8.5``."""
    number = parse_dimension(value)
    if number is None:
        return ""
    return f"{number:.4f}".rstrip("0").rstrip(".")


def dimensions_match(left, right):
    """True when both values parse and normalize to the same key."""
    left_key = dimension_key(left)
    right_key = dimension_key(right)
    return bool(left_key) and left_key == right_key


def dimension_label(value):
    """Short label such as ``8.25`` or ``8.5``. Empty when it does not parse."""
    return dimension_key(value)


def wheelbases_in(text):
    """``[(position, value)]`` for every wheelbase the text states, in order."""
    found = []
    for pattern in (_WB_LABEL_FIRST, _WB_NUMBER_FIRST):
        for match in pattern.finditer(text or ""):
            try:
                value = _wb_number(match.group(1))
            except ValueError:
                continue
            if value is not None and WHEELBASE_RANGE[0] <= value <= WHEELBASE_RANGE[1]:
                found.append((match.start(), round(value, 4)))
            more = _WB_MORE.match(text, match.end()) if pattern is _WB_LABEL_FIRST else None
            if more:
                try:
                    other = _wb_number(more.group(1))
                except ValueError:
                    other = None
                if other is not None and WHEELBASE_RANGE[0] <= other <= WHEELBASE_RANGE[1]:
                    found.append((match.start(), round(other, 4)))
    return sorted(set(found))


# The width a size block states: "Width: 8.25"" or "8.25" x 32"". A bare
# number is not trusted; nose and tail lengths (6.5-7.25") look like widths.
_WIDTH_LABEL = re.compile(r"\bwidth\b\s*[:=\-]?\s*(\d{1,2}(?:\.\d{1,4})?)", re.IGNORECASE)
_WIDTH_BY_LENGTH = re.compile(r"(?<![\d.])(\d{1,2}(?:\.\d{1,4})?)\s*(?:\"|\u201d|\u2033)?\s*x\s*\d", re.IGNORECASE)


def _width_before(text):
    """The last width stated in ``text``, or None."""
    found = [(match.start(), float(match.group(1))) for pattern in (_WIDTH_LABEL, _WIDTH_BY_LENGTH)
             for match in pattern.finditer(text)]
    found = [item for item in found if 6.5 <= item[1] <= 11.5]
    return max(found)[1] if found else None


def wheelbase_options(text, width=None):
    """Every wheelbase this deck is drilled for, smallest first; [] when unsure.

    One label can list two ("Wheelbase: 14" & 14.62""): a deck drilled for
    both, and both are kept. A page listing several sizes ("8.0 ... WB 14",
    "8.25 ... WB 14.25") gives each size its own; then the set after the
    deck's own width is used, and without such a pairing nothing is guessed.
    """
    groups = {}
    for position, value in wheelbases_in(text):
        groups.setdefault(position, set()).add(value)
    sets = {frozenset(values) for values in groups.values()}
    if len(sets) == 1:
        return sorted(sets.pop())
    if not sets or width is None:
        return []
    paired = set()
    for position, values in groups.items():
        own = _width_before(text[max(0, position - 160):position])
        if own is not None and abs(own - width) < 0.001:
            paired.add(frozenset(values))
    return sorted(paired.pop()) if len(paired) == 1 else []


def extract_specs(name, extra_text=""):
    """Width, length, and wheelbase from a product name and nearby text.

    Width and length come from the existing deck parser (``W x L``, an inch
    mark, or a width-like decimal). Wheelbase is read only when the text says
    ``wheelbase`` or ``WB``, so a width is never treated as one.
    """
    name = normalize_product_name(name)
    extra = normalize_product_name(extra_text)
    width, length = extract_deck_dimensions(name)
    if width is None and length is None and extra:
        width, length = extract_deck_dimensions(extra)
    elif extra and length is None:
        _extra_width, extra_length = extract_deck_dimensions(extra)
        if extra_length is not None:
            length = extra_length
        if width is None:
            width = _extra_width
    # Pair a multi-size page only by the listing's own width (its name), never
    # by a width read from that same page.
    own_width = extract_deck_dimensions(name)[0]
    options = wheelbase_options(name, own_width) or wheelbase_options(extra, own_width)
    return {
        "width": width,
        "length": length,
        "wheelbase": options[0] if options else None,
        # Two or more only for a deck drilled for several (see wheelbase_options).
        "wheelbases": options if len(options) > 1 else [],
    }


def set_wheelbase(item, text):
    """Put the deck's wheelbase on ``item`` when ``text`` states one for it.

    For stores that already have the product description in hand (Shopify
    feeds), so it costs no extra request. Decks and completes only.
    """
    if item.get("part") not in ("Decks", "Completes") or item.get("wheelbase") not in (None, ""):
        return item
    specs = extract_specs(item.get("name") or "", text or "")
    if specs["wheelbase"] is not None:
        item["wheelbase"] = specs["wheelbase"]
    if specs["wheelbases"]:
        item["wheelbases"] = specs["wheelbases"]
    return item
