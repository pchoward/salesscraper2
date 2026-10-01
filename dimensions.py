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
_WB_LABEL_FIRST = re.compile(
    r"\b(?:wheelbase|wb)\b\s*[:=]?\s*(\d{1,2}(?:\.\d+)?)",
    re.IGNORECASE,
)
_WB_NUMBER_FIRST = re.compile(
    r"\b(\d{1,2}(?:\.\d+)?)\s*(?:\"|\u201d|\u2033)?\s*(?:wheelbase|\bwb\b)",
    re.IGNORECASE,
)


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


def _wheelbase(text):
    if not text:
        return None
    match = _WB_LABEL_FIRST.search(text) or _WB_NUMBER_FIRST.search(text)
    if not match:
        return None
    return parse_dimension(match.group(1))


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
    wheelbase = _wheelbase(name) or _wheelbase(extra)
    return {
        "width": width,
        "length": length,
        "wheelbase": wheelbase,
    }
