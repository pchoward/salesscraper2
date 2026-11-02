"""Static sale report.

The published page is one HTML file. Filters, sorting, stars, and the price
drawer run in the browser. A problem in one section is logged and skipped.
"""

import datetime
import json
import logging
import math
import os
import re
from pathlib import Path
from urllib.parse import parse_qs, quote, urlsplit
from html import escape
from zoneinfo import ZoneInfo

import sports
from media import product_image_urls
from badges import classify_badges
from charts import CHART_NOTE, listing_series
from dimensions import dimension_key, extract_specs, parse_dimension
from filters import (
    BEARING_BRANDS,
    DECK_BRANDS,
    TRUCK_BRANDS,
    WHEEL_BRANDS,
    calculate_percent_off,
    find_brand,
    item_passes_filters,
    normalize_product_name,
    normalize_url,
    percent_off_value,
)

from history import (
    STAGE_LABEL,
    all_time_low_status,
    days_at_price,
    last_drop_date,
    listing_stage,
    price_trend,
    recently_gone,
    summarize_entry,
)
from intel import intelligence_summary
from matching import cross_store_groups
from part_specs import (
    CONSTRUCTION_LABELS,
    CONSTRUCTIONS,
    DIAMETER_BANDS,
    HEIGHT_LABELS,
    HEIGHTS,
    SHAPE_LABELS,
    SHAPES,
    bearing_specs,
    diameter_band,
    diameter_tip,
    ordered_shoe_sizes,
    section_ready,
    shoe_sizes_in,
    size_tip,
    truck_specs,
    wheel_specs,
)
from protection import SIZES as PROTECTION_SIZES
from protection import SUBTYPE_TOKENS, ordered_sizes as ordered_protection_sizes
from protection import classify as classify_protection
from protection import sizes_in as protection_sizes_in
from query_state import STARTER_VIEWS, WIDTH_RANGES, bucket_for_width
from score import FORMULA, SCORE_LEGEND, deal_score, score_band
from site_sales import activity_line, describe_sales, display_name, load_state
from watchlist import load_watchlist, rule_matches

logger = logging.getLogger("page")

_HERE = os.path.dirname(os.path.abspath(__file__))
_BRANDS = {
    "decks": DECK_BRANDS + ("Powell Peralta",),
    "wheels": WHEEL_BRANDS + ("Powell Peralta",),
    "trucks": TRUCK_BRANDS,
    "bearings": BEARING_BRANDS,
    "sneakers": ("Nike SB", "Nike", "Vans"),
}
PART_ORDER = ("Decks", "Trucks", "Wheels", "Bearings", "Sneakers", "Accessories", "Completes", "Protection")
# First screen of cards. The rest stay out of the grid until the reader scrolls
# or asks for more, so a wide catalog does not lay out every card on load.
CARD_PAGE_SIZE = 24
# Lower end included, upper end not. 30.0" is 30–31", not 29–30".
LENGTH_BOUNDARY_TIP = (
    'Deck length in inches. Each range includes its lower end and stops before '
    'the next inch, so 30.0" is in 30\u201331", not 29\u201330".'
)
# Quarter-inch wheelbase ranges. 14.25" starts 14.25–14.5", it does not
# finish 14–14.25". A tidy row is eight chips; a longer span folds the
# smaller end into "under X"" or "X"+".
WHEELBASE_BOUNDARY_TIP = (
    'Wheelbase in inches. Each range is a quarter inch, includes its lower '
    'end, and stops before the next quarter, so 14.25" is in 14.25\u201314.5", '
    'not 14\u201314.25".'
)
WHEELBASE_QUARTER = 0.25
WHEELBASE_CHIP_CAP = 8
# Short palette for deck stain and wheel urethane. Ids are stable in the
# URL. Swatches are the sidebar dots; clear and multi are drawn in CSS.
COLOR_PALETTE = (
    ("black-stain", "Black Stain", "#5c4033"),
    ("black", "Black", "#171717"),
    ("white", "White", "#f8fafc"),
    ("blue", "Blue", "#2563eb"),
    ("red", "Red", "#dc2626"),
    ("green", "Green", "#16a34a"),
    ("orange", "Orange", "#ea580c"),
    ("yellow", "Yellow", "#eab308"),
    ("pink", "Pink", "#db2777"),
    ("purple", "Purple", "#7c3aed"),
    ("natural", "Natural/Wood", "#d4a574"),
    ("clear", "Clear", ""),
    ("multi", "Multi", ""),
)
_COLOR_LABELS = {color_id: label for color_id, label, _swatch in COLOR_PALETTE}
_COLOR_SWATCH = {color_id: swatch for color_id, _label, swatch in COLOR_PALETTE}
# Words that normalize onto the palette. Bare "wood" is only a color when a
# variant field says so; in a title it is usually a name (Trey Wood).
_COLOR_WORDS = {
    "black": "black",
    "white": "white",
    "blue": "blue",
    "navy": "blue",
    "teal": "blue",
    "red": "red",
    "green": "green",
    "olive": "green",
    "lime": "green",
    "orange": "orange",
    "yellow": "yellow",
    "pink": "pink",
    "magenta": "pink",
    "purple": "purple",
    "violet": "purple",
    "natural": "natural",
    "clear": "clear",
    "transparent": "clear",
    "multi": "multi",
    "rainbow": "multi",
}
# Skate Warehouse variant codes that are a palette color. Silver, grey, and
# gold are not on the palette, so those codes do not invent a color.
_COLOR_CODES = {
    "WH": "white",
    "WHT": "white",
    "BK": "black",
    "BLK": "black",
    "BL": "blue",
    "BLU": "blue",
    "RD": "red",
    "GR": "green",
    "GN": "green",
    "OR": "orange",
    "ORG": "orange",
    "YL": "yellow",
    "YE": "yellow",
    "YEL": "yellow",
    "PK": "pink",
    "PU": "purple",
    "PR": "purple",
    "NA": "natural",
    "NT": "natural",
    "CL": "clear",
    "CLR": "clear",
    "MU": "multi",
    "MT": "multi",
}
_COLOR_WORD = (
    r"(?:black|white|blue|navy|teal|red|green|olive|lime|orange|yellow|pink|"
    r"magenta|purple|violet|natural|clear|transparent|multi|rainbow)"
)
_COLOR_OTHER = r"(?:grey|gray|gold|silver|gum|cream|tan|brown)"
_STAIN_RE = re.compile(
    r"\b(black|blue|red|green|orange|yellow|pink|purple|white|natural)\s+stains?\b"
    r"|\bstains?\s+(black|blue|red|green|orange|yellow|pink|purple|white|natural)\b",
    re.IGNORECASE,
)
_WOOD_RE = re.compile(r"\b(?:natural|raw)\s+wood\b", re.IGNORECASE)
_CHAIN_RE = re.compile(
    rf"\b{_COLOR_WORD}\b(?:\s*(?:/|&|,|\band\b)\s*\b(?:{_COLOR_WORD}|{_COLOR_OTHER})\b)+",
    re.IGNORECASE,
)
_TOKEN_RE = re.compile(r"[A-Za-z]+|\d+(?:\.\d+)?")
# The next word makes it a graphic name, not a finish: Purple Haze, Red Eye,
# Yellow Man, Black Sheep, Green Lady.
_BLOCK_NEXT = {"haze", "eye", "eyes", "man", "men", "sheep", "lady", "house"}
_BLOCK_PREV = {"big"}
_STRONG_NEXT = {
    "deck", "decks", "wheel", "wheels", "skateboard", "skateboards",
    "dip", "dipped", "foil", "fade", "swirl", "holographic", "egg",
}
_COLOR_FIELD_NAMES = {"color", "colour"}

# Email alerts (docs/alerts-api.md). Both values are public by design: the
# browser calls the Worker URL, and Turnstile site keys are meant to be seen.
# Secrets never go here. The Worker is in staging mode, so it only accepts
# its allowlisted address. An empty apiBase shows "Email alerts coming soon".
ALERTS_UI_CONFIG = {
    "apiBase": "https://skatedeals-alerts.pchoward.workers.dev",
    "turnstileSiteKey": "0x4AAAAAAFjwOIPFNNUHi29X",
}
_BRAND_ALIAS = {
    "anti hero": "Anti-Hero",
    "antihero": "Anti-Hero",
    "anti-hero": "Anti-Hero",
}
_PLACEHOLDER = (
    '<svg viewBox="0 0 64 64" width="84" height="84" aria-hidden="true">'
    '<rect width="64" height="64" fill="#e2e8f0"/>'
    '<rect x="8" y="28" width="48" height="8" rx="2" fill="#94a3b8"/>'
    "</svg>"
)


def _alerts_config_script(config=None):
    """``window.SKATEDEALS_ALERTS`` for page.js, or "" when alerts are off."""
    config = ALERTS_UI_CONFIG if config is None else config
    public = {key: str(config.get(key) or "").strip() for key in ("apiBase", "turnstileSiteKey")}
    if not public["apiBase"]:
        return ""
    literal = json.dumps({key: value for key, value in public.items() if value}, sort_keys=True)
    return "<script>window.SKATEDEALS_ALERTS = " + literal.replace("</", "<\\/") + ";</script>"


def _search_aliases(path=None):
    """A sport's search vocabulary as a script literal: compact, and nothing in it can end the <script>."""
    aliases = json.loads(Path(path).read_text(encoding="utf-8") if path else _read_asset("search/aliases.json"))
    return json.dumps(aliases, separators=(",", ":"), ensure_ascii=False).replace("<", "\\u003c")


def _read_asset(name):
    path = os.path.join(_HERE, name)
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


def parse_length(value):
    """Inches for a deck length. ``31.75"``, ``30.0``, and ``30`` are accepted."""
    return parse_dimension(value)


def _length_label_number(number):
    if abs(number - round(number)) < 1e-9:
        return str(int(round(number)))
    return f"{number:.4f}".rstrip("0").rstrip(".")


def build_length_buckets(values):
    """One-inch deck-length buckets for the values that actually occur.

    The lower end of a range is included and the upper end is not.
    ``30.0`` belongs to ``30–31"``. ``"31.75\\""`` parses as 31.75 and belongs
    to ``31–32"``. The top bucket is open (``33"+``) so ``33.0`` is included
    there, not in ``32–33"``.

    The ends follow the data. A catalog whose shortest deck is 29.1" and whose
    longest is 33.3" gets ``29–30"`` through ``32–33"`` and ``33"+``. Nothing
    under 29" means that chip is left out. A shorter deck adds its own inch
    (28.5" is ``28–29"``) instead of being folded into the next range.
    """
    numbers = []
    for value in values or []:
        number = parse_length(value)
        if number is not None:
            numbers.append(number)
    if not numbers:
        return []
    low = math.floor(min(numbers))
    high = math.floor(max(numbers))
    buckets = []
    if any(number < low - 1e-9 for number in numbers):
        buckets.append(_length_bucket(None, low))
    if high == low:
        buckets.append(_length_bucket(low, low + 1))
        return buckets
    for inch in range(low, high):
        buckets.append(_length_bucket(inch, inch + 1))
    buckets.append(_length_bucket(high, None))
    return buckets


def _length_bucket(low, high):
    """One bucket. ``high`` None is the open top. ``low`` None is the open bottom."""
    if low is None:
        label = f'under {_length_label_number(high)}"'
        bucket_id = f"under-{_length_label_number(high)}"
        tip = (
            f'Under {_length_label_number(high)}". '
            f'{_length_label_number(high)}.0" is in the next range, not this one. '
            + LENGTH_BOUNDARY_TIP
        )
    elif high is None:
        label = f'{_length_label_number(low)}"+'
        bucket_id = f"{_length_label_number(low)}+"
        tip = (
            f'{_length_label_number(low)}" and longer. '
            f'{_length_label_number(low)}.0" is included. '
            + LENGTH_BOUNDARY_TIP
        )
    else:
        label = f'{_length_label_number(low)}\u2013{_length_label_number(high)}"'
        bucket_id = f"{_length_label_number(low)}-{_length_label_number(high)}"
        tip = (
            f'{_length_label_number(low)}" up to but not including {_length_label_number(high)}". '
            + LENGTH_BOUNDARY_TIP
        )
    return {"id": bucket_id, "label": label, "min": low, "max": high, "tip": tip}


def length_bucket_for(value, buckets):
    """The bucket id for ``value``, or "" when it parses but fits none."""
    number = parse_length(value)
    if number is None:
        return ""
    for bucket in buckets or []:
        low = bucket.get("min")
        high = bucket.get("max")
        if low is not None and number < low - 1e-9:
            continue
        if high is not None and number >= high - 1e-9:
            continue
        return bucket.get("id") or ""
    return ""


def _wheelbase_numbers(values):
    """Floats for wheelbase keys. ``14,14.62`` is two wheelbases."""
    numbers = []
    for value in values or []:
        if isinstance(value, (list, tuple)):
            numbers.extend(_wheelbase_numbers(value))
            continue
        text = str(value).strip()
        if not text:
            continue
        parts = text.split(",") if "," in text else [text]
        for part in parts:
            number = parse_dimension(part)
            if number is not None:
                numbers.append(number)
    return numbers


def _quarter_start(number):
    """Inclusive lower bound of the quarter-inch that holds ``number``."""
    index = math.floor((float(number) + 1e-9) / WHEELBASE_QUARTER)
    return round(index * WHEELBASE_QUARTER, 4)


def build_wheelbase_buckets(values):
    """Quarter-inch wheelbase buckets for the values that actually occur.

    The lower end is included and the upper end is not. ``14.25`` belongs to
    ``14.25–14.5"``, not ``14–14.25"``. Empty quarters are left out, so a
    catalog does not grow a tail of blank chips. When the occupied quarters
    would run past :data:`WHEELBASE_CHIP_CAP`, the smaller end folds into
    ``under X"`` or ``X"+``.
    """
    numbers = _wheelbase_numbers(values)
    if not numbers:
        return []
    counts = {}
    for number in numbers:
        start = _quarter_start(number)
        counts[start] = counts.get(start, 0) + 1
    pieces = [
        {"kind": "quarter", "start": start, "count": counts[start]}
        for start in sorted(counts)
    ]
    while len(pieces) > WHEELBASE_CHIP_CAP and len(pieces) > 1:
        if pieces[0]["count"] <= pieces[-1]["count"]:
            _fold_wheelbase_left(pieces)
        else:
            _fold_wheelbase_right(pieces)
    return [_wheelbase_piece(piece) for piece in pieces]


def _fold_wheelbase_left(pieces):
    """Absorb the leftmost quarter into an ``under X"`` chip."""
    if pieces[0]["kind"] == "under":
        under = pieces[0]
        quarter = pieces.pop(1)
        under["count"] += quarter["count"]
        following = pieces[1] if len(pieces) > 1 else None
        if following and following["kind"] == "quarter":
            under["max"] = following["start"]
        else:
            under["max"] = round(quarter["start"] + WHEELBASE_QUARTER, 4)
        return
    quarter = pieces.pop(0)
    following = pieces[0]
    edge = following["start"] if following["kind"] == "quarter" else following["max"]
    pieces.insert(0, {"kind": "under", "max": edge, "count": quarter["count"]})


def _fold_wheelbase_right(pieces):
    """Absorb the rightmost quarter into an ``X"+`` chip."""
    if pieces[-1]["kind"] == "plus":
        plus = pieces[-1]
        quarter = pieces.pop(-2)
        plus["count"] += quarter["count"]
        plus["min"] = quarter["start"]
        return
    quarter = pieces.pop()
    pieces.append({"kind": "plus", "min": quarter["start"], "count": quarter["count"]})


def _wheelbase_piece(piece):
    if piece["kind"] == "under":
        return _length_bucket(None, piece["max"]) | {"tip": _wheelbase_tip(None, piece["max"])}
    if piece["kind"] == "plus":
        bucket = _length_bucket(piece["min"], None)
        bucket["tip"] = _wheelbase_tip(piece["min"], None)
        return bucket
    high = round(piece["start"] + WHEELBASE_QUARTER, 4)
    bucket = _length_bucket(piece["start"], high)
    bucket["tip"] = _wheelbase_tip(piece["start"], high)
    return bucket


def _wheelbase_tip(low, high):
    if low is None:
        label = _length_label_number(high)
        return f'Under {label}". {label}" is in the next range, not this one. ' + WHEELBASE_BOUNDARY_TIP
    if high is None:
        label = _length_label_number(low)
        return f'{label}" and longer. {label}" is included. ' + WHEELBASE_BOUNDARY_TIP
    return (
        f'{_length_label_number(low)}" up to but not including {_length_label_number(high)}". '
        + WHEELBASE_BOUNDARY_TIP
    )


def wheelbase_bucket_for(value, buckets):
    """The bucket id for one wheelbase, or "" when it fits none."""
    number = parse_dimension(value)
    if number is None:
        return ""
    for bucket in buckets or []:
        low = bucket.get("min")
        high = bucket.get("max")
        if low is not None and number < low - 1e-9:
            continue
        if high is not None and number >= high - 1e-9:
            continue
        return bucket.get("id") or ""
    return ""


def _color_tokens(text):
    return [match.group(0) for match in _TOKEN_RE.finditer(text or "")]


def _stain_ids(text):
    found = []
    if _WOOD_RE.search(text or ""):
        found.append("natural")
    for match in _STAIN_RE.finditer(text or ""):
        word = (match.group(1) or match.group(2) or "").lower()
        if word == "black":
            found.append("black-stain")
        elif word == "natural":
            found.append("natural")
        elif word in _COLOR_WORDS:
            found.append(_COLOR_WORDS[word])
    return found


def _chain_ids(text):
    found = []
    for match in _CHAIN_RE.finditer(text or ""):
        for token in _color_tokens(match.group(0)):
            color_id = _COLOR_WORDS.get(token.lower())
            if color_id:
                found.append(color_id)
    return found


def _loose_color_ids(text, allow_wood=False):
    """Palette ids for color words, skipping graphic bigrams such as Yellow Man."""
    tokens = _color_tokens(text)
    found = []
    for index, token in enumerate(tokens):
        if not token.isalpha():
            continue
        prev = tokens[index - 1].lower() if index else ""
        nxt = tokens[index + 1].lower() if index + 1 < len(tokens) else ""
        if prev in _BLOCK_PREV or nxt in _BLOCK_NEXT:
            continue
        lowered = token.lower()
        if allow_wood and lowered in ("wood", "raw"):
            found.append("natural")
            continue
        color_id = _COLOR_WORDS.get(lowered)
        if color_id:
            found.append(color_id)
    return found


def _positioned_color_ids(text):
    """Color words sitting where a finish goes: before the size, or before Deck/Wheels."""
    tokens = _color_tokens(text)
    found = []
    for index, token in enumerate(tokens):
        if not token.isalpha():
            continue
        prev = tokens[index - 1].lower() if index else ""
        nxt = tokens[index + 1].lower() if index + 1 < len(tokens) else ""
        if prev in _BLOCK_PREV or nxt in _BLOCK_NEXT:
            continue
        color_id = _COLOR_WORDS.get(token.lower())
        if not color_id:
            continue
        strong = not nxt or nxt in _STRONG_NEXT or _TOKEN_RE.fullmatch(nxt) and nxt[0].isdigit()
        if strong:
            found.append(color_id)
    return found


def _suffix_chunks(text):
    chunks = []
    for mark in (" - ", " \u2013 ", " \u2014 "):
        if mark in (text or ""):
            chunks.append(text.rsplit(mark, 1)[1])
            break
    chunks.extend(re.findall(r"\(([^)]*)\)", text or ""))
    return chunks


def _unique_colors(found):
    ordered = []
    for color_id in found or []:
        if color_id and color_id not in ordered:
            ordered.append(color_id)
    return ordered


def _collapse_colors(found):
    """One palette id. Two different colors are Multi."""
    ordered = _unique_colors(found)
    if not ordered:
        return ""
    if len(ordered) > 1 or "multi" in ordered:
        return "multi"
    return ordered[0]


def _colors_from_phrase(text, allow_wood=False):
    stains = _stain_ids(text)
    if stains:
        return stains
    chains = _chain_ids(text)
    if chains:
        return chains
    return _loose_color_ids(text, allow_wood=allow_wood)


def _colors_from_title(title):
    """Color words in a product title. Photos are not consulted."""
    text = title or ""
    stains = _stain_ids(text)
    if stains:
        return stains
    chains = _chain_ids(text)
    if chains:
        return chains
    for chunk in _suffix_chunks(text):
        loose = _loose_color_ids(chunk)
        if loose:
            return loose
    return _positioned_color_ids(text)


def _explicit_color_text(item):
    """A color a store already stored on the item, or ""."""
    item = item or {}
    for key in ("color", "colour", "variant_color", "variant_colour"):
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    for name_key, value_key in (
        ("option1_name", "option1"),
        ("option2_name", "option2"),
        ("option3_name", "option3"),
    ):
        name = str(item.get(name_key) or "").strip().casefold()
        if name in _COLOR_FIELD_NAMES:
            value = item.get(value_key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    options = item.get("options")
    if isinstance(options, dict):
        for key, value in options.items():
            if str(key).strip().casefold() in _COLOR_FIELD_NAMES and str(value or "").strip():
                return str(value).strip()
    if isinstance(options, list):
        for option in options:
            if not isinstance(option, dict):
                continue
            name = str(option.get("name") or option.get("label") or "").strip().casefold()
            if name not in _COLOR_FIELD_NAMES:
                continue
            value = option.get("value")
            if value in (None, ""):
                values = option.get("values")
                if isinstance(values, list) and len(values) == 1:
                    value = values[0]
            if str(value or "").strip():
                return str(value).strip()
    variant = item.get("variant")
    if isinstance(variant, dict):
        for key in ("color", "colour"):
            value = variant.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        name = str(variant.get("option_name") or variant.get("name") or "").strip().casefold()
        if name in _COLOR_FIELD_NAMES:
            value = variant.get("value") or variant.get("title") or ""
            if str(value).strip():
                return str(value).strip()
    return ""


def _url_color_code(url):
    try:
        query = parse_qs(urlsplit(str(url or "")).query)
    except ValueError:
        return ""
    values = query.get("color") or query.get("colour") or []
    if not values:
        return ""
    return str(values[0]).strip().upper()


def listing_color(item):
    """Palette id for a deck or a wheel, or "" when no color is stated.

    A variant or option color wins when the catalog has one. Otherwise color
    words in the title (``Black Stain``, ``White``, ``Blue/Red``). Nothing is
    read from the photo. Other product types are left blank.
    """
    item = item or {}
    if item.get("part") not in ("Decks", "Wheels"):
        return ""
    explicit = _explicit_color_text(item)
    if explicit:
        found = _collapse_colors(_colors_from_phrase(explicit, allow_wood=True))
        if found:
            return found
    coded = _COLOR_CODES.get(_url_color_code(item.get("url") or ""))
    if coded:
        return coded
    return _collapse_colors(_colors_from_title(item.get("name") or ""))


def _price(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _money(value, currency=None):
    amount = _price(value)
    if amount is None:
        return "N/A"
    symbol = "€" if str(currency or "USD").upper() == "EUR" else "$"
    return f"{symbol}{amount:.2f}"


def _store_class(store):
    return "store-" + "".join(ch for ch in (store or "").lower() if ch.isalnum())


def _as_date(value):
    try:
        return datetime.date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _display_name(item):
    return normalize_product_name((item or {}).get("name", ""))


def _entry(history, url):
    if not isinstance(history, dict) or not url:
        return {}
    found = history.get(url) or history.get(normalize_url(url))
    return found if isinstance(found, dict) else {}


def _prefer_brand_label(labels):
    """One display spelling for labels that differ only by case.

    A mixed-case spelling wins over an all-lowercase one (``5Boro`` over
    ``5boro``). More capitals win next, then a stable casefold order.
    """

    def rank(label):
        uppers = sum(1 for char in label if char.isupper())
        return (uppers == 0, -uppers, label.casefold())

    return sorted(labels, key=rank)[0]


def _canonicalize_brands(records):
    """Merge brand labels that are the same ignoring case.

    Filtering stays an exact match on the chosen spelling. Only the case
    of the label changes.
    """
    groups = {}
    for record in records:
        brand = record.get("brand") or ""
        if brand:
            groups.setdefault(brand.casefold(), set()).add(brand)
    chosen = {key: _prefer_brand_label(labels) for key, labels in groups.items()}
    for record in records:
        brand = record.get("brand") or ""
        if not brand:
            continue
        canon = chosen.get(brand.casefold(), brand)
        if canon == brand:
            continue
        record["brand"] = canon
        item = record.get("item")
        if isinstance(item, dict):
            item["_brand"] = canon
        search = record.get("search") or ""
        if canon not in search:
            record["search"] = (search + " " + canon).strip()


def listing_brand(name, part):
    brands = _BRANDS.get((part or "").strip().casefold(), ())
    found = find_brand(name, brands) if brands else None
    if not found:
        tokens = normalize_product_name(name).split()
        found = tokens[0] if tokens else ""
    return _BRAND_ALIAS.get(found.casefold(), found)


def _discount_class(price_new, price_old):
    percent = percent_off_value(price_new, price_old)
    if percent is None:
        return "low"
    if percent >= 40:
        return "high"
    if percent >= 25:
        return "medium"
    return "low"


def _specs_for(item, entry):
    specs = extract_specs(item.get("name") or "")
    for field in ("width", "length", "wheelbase"):
        if item.get(field) not in (None, ""):
            try:
                specs[field] = float(item.get(field))
            except (TypeError, ValueError):
                pass
        elif entry.get(field) not in (None, "") and specs.get(field) is None:
            try:
                specs[field] = float(entry.get(field))
            except (TypeError, ValueError):
                pass
    # A deck drilled for several wheelbases: the listing's own list wins,
    # then history's, then whatever the name said.
    for source in (item, entry):
        options = source.get("wheelbases")
        if isinstance(options, list) and len(options) > 1:
            try:
                specs["wheelbases"] = sorted({float(value) for value in options})
            except (TypeError, ValueError):
                continue
            break
    return specs


def _image_of(item, entry):
    image = str(item.get("image") or entry.get("image") or "").strip()
    if image.startswith("http"):
        return image
    return ""


def _prices_of(entry):
    summary = summarize_entry(entry) if entry else {"prices": {}}
    prices = summary.get("prices") or {}
    return {day: float(prices[day]) for day in sorted(prices)}


def _chain(prices):
    points = []
    last = None
    for day in sorted(prices):
        price = float(prices[day])
        if last is None or abs(price - last) > 0.001:
            points.append([day, round(price, 2)])
            last = price
    return points


def _daily_points(prices):
    return [[day, round(float(prices[day]), 2)] for day in sorted(prices or {})]


_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def _month_day(iso):
    try:
        day = datetime.date.fromisoformat(str(iso or "")[:10])
    except ValueError:
        return ""
    return f"{_MONTHS[day.month - 1]} {day.day}"


def _window_average(prices, days=90, end=None):
    """Mean of the daily prices inside the chart window, or None when there are none."""
    points = clip_daily_prices(prices, days=days, end=end)
    if not points:
        return None
    return round(sum(price for _day, price in points) / len(points), 2)


def _prior_price(prices, since):
    """Last tracked price before the current run started, or None."""
    prior = None
    for day in sorted(prices or {}):
        if since and str(day) < str(since):
            prior = prices[day]
        else:
            break
    return prior


def _since_label(since, first, prices=None, current=None, symbol="$"):
    """Say whether this price is unchanged or a real move, with the date.

    Hours are not known. A drop uses the previous tracked price, not a guess.
    """
    since_text = _month_day(since)
    if since_text:
        prior = _prior_price(prices, since)
        try:
            current_value = float(current) if current is not None else None
            prior_value = float(prior) if prior is not None else None
        except (TypeError, ValueError):
            current_value = None
            prior_value = None
        if prior_value is not None and current_value is not None and abs(prior_value - current_value) > 0.001:
            shown = f"{symbol}{prior_value:.2f}"
            if prior_value > current_value:
                return f"Dropped from {shown} on {since_text}"
            return f"Up from {shown} on {since_text}"
        return f"Price unchanged since {since_text}"
    first_text = _month_day(first)
    if first_text:
        return f"First seen {first_text}"
    return ""


def _parse_generated(value):
    if isinstance(value, datetime.datetime):
        return value
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        pass
    try:
        return datetime.datetime.strptime(text[:19], "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None


def format_scan_et(value):
    """Exact scan time for the hover label, in US Eastern."""
    moment = _parse_generated(value)
    if moment is None:
        return str(value or "")
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=datetime.timezone.utc)
    local = moment.astimezone(ZoneInfo("America/New_York"))
    hour = local.strftime("%I").lstrip("0") or "12"
    return f"{local.strftime('%b')} {local.day}, {local.year} {hour}:{local.strftime('%M:%S %p')} ET"


def _held_label(days, at_days, price):
    label = f"{days}d tracked"
    if price is None:
        return label
    return f"{label} · {at_days}d @ ${float(price):.2f}"


# Same window as the chart buttons: a point is visible when its date is on or
# after (end - days). Color is the latest change inside that window, not the
# oldest price in the file.
SPARK_COLOR = {"down": "#15803d", "up": "#b91c1c", "flat": "#94a3b8"}


def clip_daily_prices(prices, days=90, end=None):
    """Daily ``(date, price)`` pairs inside the inclusive chart window."""
    cleaned = []
    for day, price in (prices or {}).items():
        text = str(day)[:10]
        if len(text) != 10:
            continue
        try:
            amount = round(float(price), 2)
            datetime.date.fromisoformat(text)
        except (TypeError, ValueError):
            continue
        cleaned.append((text, amount))
    cleaned.sort()
    if not cleaned:
        return []
    end_text = str(end)[:10] if end else cleaned[-1][0]
    try:
        end_day = datetime.date.fromisoformat(end_text)
    except ValueError:
        return cleaned
    start_text = (end_day - datetime.timedelta(days=int(days))).isoformat()
    return [(day, price) for day, price in cleaned if start_text <= day <= end_text]


def sparkline_direction(prices, days=90, end=None):
    """``down``, ``up``, or ``flat`` from the latest change in the window.

    Prices outside the window are ignored. A window whose prices never move,
    or that has fewer than two prices, is flat. A drop then a flat tail is
    still ``down``, because the last change inside the window was a drop.
    """
    points = clip_daily_prices(prices, days=days, end=end)
    if len(points) < 2:
        return "flat"
    last = points[-1][1]
    for _day, price in reversed(points[:-1]):
        if abs(price - last) > 0.001:
            return "down" if last < price else "up"
    return "flat"


def sparkline_svg(prices, width=72, height=22, css="spark", days=90, end=None, stroke=1.6, radius=2.2, steps=False):
    ordered = clip_daily_prices(prices, days=days, end=end)
    if not ordered:
        return ""
    direction = sparkline_direction(prices, days=days, end=end)
    color = SPARK_COLOR[direction]
    values = [price for _day, price in ordered]
    low = min(values)
    high = max(values)
    span = high - low or 1
    last = max(len(ordered) - 1, 1)
    coords = []
    for index, value in enumerate(values):
        x_pos = 1 + (index / last) * (width - 2)
        y_pos = 1 + (height - 4) * (1 - (value - low) / span)
        coords.append((x_pos, y_pos))
    parts = [
        f'<svg class="{css}" data-direction="{direction}" viewBox="0 0 {width} {height}" '
        f'width="{width}" height="{height}" aria-hidden="true">'
    ]
    line = coords
    if steps and len(coords) >= 2:
        line = []
        for index, point in enumerate(coords):
            if index:
                line.append((point[0], coords[index - 1][1]))
            line.append(point)
    if len(line) >= 2 and direction != "flat":
        drawn = " ".join(f"{x_pos:.1f},{y_pos:.1f}" for x_pos, y_pos in line)
        parts.append(
            f'<polyline fill="none" stroke="{color}" stroke-width="{stroke}" points="{drawn}"/>'
        )
    elif len(coords) >= 2 and direction == "flat":
        drawn = " ".join(f"{x_pos:.1f},{y_pos:.1f}" for x_pos, y_pos in coords)
        parts.append(
            f'<polyline class="spark-flat" fill="none" stroke="{color}" stroke-width="1" points="{drawn}"/>'
        )
    x_pos, y_pos = coords[-1]
    parts.append(f'<circle cx="{x_pos:.1f}" cy="{y_pos:.1f}" r="{radius}" fill="{color}"/>')
    parts.append("</svg>")
    return "".join(parts)


def _availability_label(entry, present=True):
    """On sale, sold out, or gone. Stock comes from the product page, not shipping."""
    entry = entry if isinstance(entry, dict) else {}
    if not present:
        if entry.get("stock") == "out_of_stock":
            return "Sold out"
        if entry.get("stage") == "gone":
            return "Gone"
        return "No longer listed"
    if entry.get("stock") == "out_of_stock":
        return "Sold out"
    return "On sale"


def _trend_html(trend):
    trend = trend if trend in {"down", "up", "stable"} else "stable"
    symbol = {"down": "↓", "up": "↑", "stable": "→"}[trend]
    title = {"down": "Price down", "up": "Price up", "stable": "Price steady"}[trend]
    return f'<span class="trend trend-{trend}" title="{title}">{symbol}</span>'


def _thumb(image, alt, large=False):
    css = "hero" if large else "thumb"
    icon = _PLACEHOLDER
    if not image:
        return f'<span class="thumb-wrap{" hero-wrap" if large else ""}"><span class="{css} ph">{icon}</span></span>'
    safe = escape(image, quote=True)
    label = escape(alt or "", quote=True)
    size = 200 if large else 84
    return (
        f'<span class="thumb-wrap{" hero-wrap" if large else ""}">'
        f'<img class="{css}" src="{safe}" alt="{label}" width="{size}" height="{size}" '
        'loading="lazy" decoding="async" '
        'onerror="this.hidden=true;if(this.nextElementSibling)this.nextElementSibling.hidden=false">'
        f'<span class="{css} ph" hidden>{icon}</span></span>'
    )


def _product_link(item):
    name = escape(_display_name(item))
    url = escape(normalize_url(item.get("url", "")), quote=True)
    if not url:
        return name
    return f'<a class="product-link" href="{url}" target="_blank" rel="noopener">{name}</a>'


def _badge_html(badges, listed, limit=None):
    pills = []
    for badge in badges:
        kind = escape(badge.get("kind") or "new")
        pills.append(f'<span class="pill pill-{kind}">{escape(badge.get("label") or "")}</span>')
    if listed:
        pills.append('<span class="pill pill-list">Watchlist</span>')
    if limit is not None:
        pills = pills[:limit]
    if not pills:
        return ""
    return f'<div class="pills">{"".join(pills)}</div>'


def _option(value, label, selected=False, data_label=None):
    mark = " selected" if selected else ""
    extra = ""
    if data_label is not None:
        extra = f' data-label="{escape(str(data_label), quote=True)}"'
    return (
        f'<option value="{escape(str(value), quote=True)}"{mark}{extra}>'
        f"{escape(str(label))}</option>"
    )


def _buttons(group_id, attr, onclick, values, active="all"):
    rows = [
        f'<button type="button" class="filter-btn active" data-{attr}="all" '
        f'onclick="{onclick}(\'all\')">All</button>'
    ]
    for value in values:
        rows.append(
            f'<button type="button" class="filter-btn" data-{attr}="{escape(str(value), quote=True)}" '
            f'onclick="{onclick}(\'{escape(str(value), quote=True)}\')">{escape(str(value))}</button>'
        )
    return f'<div class="filter-group" id="{group_id}">{"".join(rows)}</div>'



def _data_attrs(pairs):
    chunks = []
    for key, value in pairs:
        text = "" if value is None else str(value)
        chunks.append(f'data-{key}="{escape(text, quote=True)}"')
    return " ".join(chunks)


def _price_attr(value):
    amount = _price(value)
    if amount is None:
        return ""
    return f"{amount:.2f}"


def _sort_headers(table_id, columns):
    cells = []
    for label, key in columns:
        cells.append(
            '<th><button type="button" data-sort="'
            + escape(key, quote=True)
            + f"\" onclick=\"sortSection('{table_id}','{key}')\">{escape(label)}</button></th>"
        )
    return "".join(cells)


def _atl_section(low_items, history):
    rows = [
        '<div class="section" id="atlSection">',
        '<div class="section-header collapsed" onclick="toggleSection(this)">',
        f'<h2>All-time lows <span class="badge">{len(low_items)}</span></h2>',
        '<span class="toggle-icon">▼</span></div>',
        '<div class="section-content collapsed">',
        '<p class="lede">Current sale price equals the lowest price tracked for that listing. '
        "A listing needs at least 3 observations spanning 7 days, so a brand-new deal is not "
        "flagged just because its first price is the only price. "
        "Column headers sort this table. Search, price, store, type, and brand use the same choices as All Deals.</p>",
        '<table id="atlTable"><thead><tr>',
        _sort_headers("atlTable", (
            ("Store", "store"),
            ("Part", "part"),
            ("Product", "name"),
            ("Sale price", "price"),
            ("Low since", "lowdate"),
            ("Observations", "observations"),
        )),
        "</tr></thead><tbody>",
    ]
    for item in low_items:
        try:
            status = all_time_low_status(item, history)
            store = item.get("store") or "Unknown"
            part = item.get("part") or ""
            name = item.get("name") or ""
            brand = item.get("_brand") or item.get("brand") or listing_brand(name, part)
            observations = status.get("observations")
            title = escape(status.get("title") or "All-time low", quote=True)
            search = " ".join(bit for bit in (name, store, part, brand, "all-time low") if bit)
            rows.append(
                "<tr "
                + _data_attrs((
                    ("store", store),
                    ("part", part),
                    ("brand", brand),
                    ("name", name),
                    ("price", _price_attr(item.get("price_new"))),
                    ("lowdate", status.get("low_date") or ""),
                    ("observations", "" if observations in (None, "") else observations),
                    ("search", search),
                ))
                + ">"
                f'<td><span class="store-badge {_store_class(store)}">{escape(store)}</span></td>'
                f'<td><span class="part-badge">{escape(part)}</span></td>'
                f'<td class="product-name">{_product_link(item)} '
                f'<span class="atl-badge" title="{title}">ALL-TIME LOW</span></td>'
                f'<td class="price price-new">{_money(item.get("price_new"))}</td>'
                f'<td>{escape(status.get("low_date") or "")}</td>'
                f'<td>{escape("" if observations in (None, "") else str(observations))}</td>'
                "</tr>"
            )
        except Exception as exc:
            logger.error("All-time low row failed: %s", exc)
    rows.append("</tbody></table></div></div>")
    return "\n".join(rows)


def _euro_note(groups):
    for group in groups or []:
        for offer in group.get("offers") or []:
            if offer.get("store") == "Skate Deluxe":
                return " Skate Deluxe prices are euros (no US dollar storefront) and are not converted."
    return ""


def _compare_section(groups):
    if not groups:
        return ""
    rows = [
        '<div class="section" id="compareSection">',
        '<div class="section-header" onclick="toggleSection(this)">',
        f'<h2>Across stores <span class="badge">{len(groups)}</span></h2>',
        '<span class="toggle-icon">▼</span></div>',
        '<div class="section-content">',
        '<p class="lede">Same brand, model, and size at two or more stores. '
        "The lowest price is highlighted. Matching is conservative, so some real duplicates stay separate."
        f"{_euro_note(groups)}</p>",
        '<div class="compare-grid">',
    ]
    for group in groups:
        offers = []
        for offer in group.get("offers") or []:
            price = offer.get("price")
            cheapest = price is not None and abs(price - group.get("cheapest_price", price)) < 0.001
            klass = "offer cheapest" if cheapest else "offer"
            store = offer.get("store") or ""
            name = escape(offer.get("name") or "")
            url = offer.get("url") or ""
            if url:
                name_html = (
                    f'<a href="{escape(url, quote=True)}" target="_blank" rel="noopener">{name}</a>'
                )
            else:
                name_html = name
            offers.append(
                f'<div class="{klass}" data-store="{escape(store, quote=True)}">'
                f'<div class="who"><span class="store-badge {_store_class(store)}">{escape(store)}</span></div>'
                f'<div class="amt">{_money(price, offer.get("currency"))}</div>'
                f'<div class="nm">{name_html}</div></div>'
            )
        rows.append(
            '<div class="compare-card">'
            f'<div class="compare-label">{escape(group.get("label") or "")} '
            f'<span class="part-badge">{escape(group.get("part") or "")}</span></div>'
            f'<div class="compare-offers">{"".join(offers)}</div></div>'
        )
    rows.append("</div></div></div>")
    return "\n".join(rows)


def _bar_rows(pairs, label_key="label"):
    if not pairs:
        return "<p class=\"empty\">Nothing to show.</p>"
    peak = max(value for _label, value in pairs) or 1
    rows = []
    for label, value in pairs:
        width = max(2, round(100 * value / peak))
        rows.append(
            '<div class="bar-row">'
            f"<span>{escape(str(label))}</span>"
            f'<span class="bar"><i style="width:{width}%"></i></span>'
            f"<span>{escape(str(value))}</span></div>"
        )
    return "".join(rows)


def _money_delta(amount):
    value = _price(amount)
    if value is None:
        return ""
    return f"−${value:.2f}"


def _intel_strip(summary):
    summary = summary or {}
    biggest = (summary.get("biggest_drops") or [None])[0]
    if biggest:
        drop_text = f'{_money_delta(biggest.get("delta"))} {biggest.get("name") or ""}'.strip()
    else:
        drop_text = "None today"
    leader = summary.get("discount_leader")
    if leader:
        avg_text = f'{leader.get("store")} {leader.get("average"):.0f}%'
    else:
        avg_text = "No discounts"
    good = summary.get("good_leader")
    if good:
        good_text = f'{good.get("store")} · {good.get("count")}'
    else:
        good_text = "None right now"
    return (
        '<div class="intel-strip" id="intelStrip">'
        f'<div><span>Biggest drop</span><strong>{escape(drop_text)}</strong></div>'
        f'<div><span>Highest average discount</span><strong>{escape(avg_text)}</strong></div>'
        f'<div><span>Most good discounts <button type="button" class="info-dot" aria-describedby="goodDef">?</button></span>'
        f'<strong>{escape(good_text)}</strong>'
        f'<span class="tip" id="goodDef" role="tooltip">{escape(summary.get("definition") or "")}</span></div>'
        "</div>"
    )


def _stats_html(products, history, intel=None):
    by_store = {}
    by_width = {}
    by_brand_count = {}
    by_brand_off = {}
    deck_prices = {}
    for item in products:
        store = item.get("store") or "Unknown"
        percent = percent_off_value(item.get("price_new"), item.get("price_old"))
        bucket = by_store.setdefault(store, [])
        if percent is not None:
            bucket.append(percent)
        if item.get("part") == "Decks":
            key = dimension_key((item.get("_specs") or {}).get("width"))
            if key:
                by_width[key] = by_width.get(key, 0) + 1
        brand = item.get("_brand") or ""
        if brand:
            by_brand_count[brand] = by_brand_count.get(brand, 0) + 1
            if percent is not None:
                by_brand_off.setdefault(brand, []).append(percent)
        if item.get("part") == "Decks" and brand and str(item.get("currency") or "USD").upper() != "EUR":
            price = _price(item.get("price_new"))
            if price is not None:
                deck_prices.setdefault(brand, []).append(price)

    store_avg = []
    for store, values in sorted(by_store.items()):
        if not values:
            continue
        store_avg.append((store, f"{sum(values) / len(values):.0f}%"))
    width_pairs = sorted(by_width.items(), key=lambda pair: float(pair[0]))
    width_pairs = [(label, count) for label, count in width_pairs]
    brand_pairs = sorted(by_brand_count.items(), key=lambda pair: (-pair[1], pair[0]))[:8]
    cheap = []
    for brand, prices in deck_prices.items():
        if len(prices) < 2:
            continue
        cheap.append((brand, sum(prices) / len(prices), len(prices)))
    cheap.sort(key=lambda row: (row[1], row[0]))
    cheap_rows = [
        f"<tr><td>{escape(brand)}</td><td>{_money(avg)}</td><td>{count}</td></tr>"
        for brand, avg, count in cheap[:8]
    ]
    weeks = {}
    if isinstance(history, dict):
        for entry in history.values():
            if not isinstance(entry, dict) or entry.get("part") != "Decks":
                continue
            if entry.get("store") == "Skate Deluxe":
                continue
            for day, price in (entry.get("prices") or {}).items():
                parsed = _as_date(day)
                amount = _price(price)
                if parsed is None or amount is None:
                    continue
                week = (parsed - datetime.timedelta(days=parsed.weekday())).isoformat()
                weeks.setdefault(week, []).append(amount)
    week_rows = []
    for week in sorted(weeks)[-12:]:
        values = weeks[week]
        week_rows.append(
            f"<tr><td>{escape(week)}</td><td>{_money(sum(values) / len(values))}</td><td>{len(values)}</td></tr>"
        )
    store_table = "".join(f"<tr><td>{escape(store)}</td><td>{escape(avg)}</td></tr>" for store, avg in store_avg)
    intel = intel or {}
    new_rows = []
    for deal in intel.get("new_deals") or []:
        price = _money(deal.get("price"))
        new_rows.append(
            f"<li>{escape(deal.get('store') or '')}: {escape(deal.get('name') or '')} {price}</li>"
        )
    drop_rows = []
    for deal in intel.get("biggest_drops") or []:
        drop_rows.append(
            "<li>"
            f"{escape(_money_delta(deal.get('delta')))} · {escape(deal.get('store') or '')}: "
            f"{escape(deal.get('name') or '')}</li>"
        )
    good_rows = []
    for row in intel.get("good_by_store") or []:
        good_rows.append(
            f"<tr><td>{escape(row.get('store') or '')}</td><td>{row.get('count')}</td>"
            f"<td>{row.get('average'):.0f}%</td></tr>"
        )
    definition = escape(intel.get("definition") or "")
    return (
        '<section id="statsPanel" hidden>'
        '<div class="section"><div class="section-header"><h2>Deals intelligence</h2></div><div class="section-content">'
        '<p class="lede">Stores are ranked by how many good discounts they have, '
        "then by how deep those discounts are. "
        f'<span class="tip-inline">{definition}</span></p>'
        '<div class="stat-block"><h3>New deals today</h3>'
        f'<ul class="intel-list">{"".join(new_rows) or "<li>No new deals in this scan.</li>"}</ul></div>'
        '<div class="stat-block"><h3>Biggest price drops</h3>'
        f'<ul class="intel-list">{"".join(drop_rows) or "<li>No price drops in this scan.</li>"}</ul></div>'
        '<div class="stat-block"><h3>Stores with the most good discounts</h3>'
        '<table><thead><tr><th>Store</th><th>Good deals</th><th>Avg discount</th></tr></thead>'
        f'<tbody>{"".join(good_rows) or "<tr><td colspan=3>No good discounts in this scan.</td></tr>"}</tbody></table></div>'
        '<div class="stat-block"><h3>Average discount by retailer</h3>'
        f'<table><tbody>{store_table or "<tr><td>No discounts</td></tr>"}</tbody></table></div>'
        '<div class="stat-block"><h3>Deals by width</h3>'
        f'{_bar_rows(width_pairs)}</div>'
        '<div class="stat-block"><h3>Brands with the most markdowns</h3>'
        f'{_bar_rows(brand_pairs)}</div>'
        '<div class="stat-block"><h3>Lowest average deck prices by brand</h3>'
        '<table><thead><tr><th>Brand</th><th>Average sale</th><th>Decks</th></tr></thead>'
        f'<tbody>{"".join(cheap_rows) or "<tr><td colspan=3>Need at least two decks.</td></tr>"}</tbody></table></div>'
        '<div class="stat-block"><h3>Historical deck sale prices</h3>'
        "<p class=\"lede\">Average tracked deck sale price by week, from price history.</p>"
        '<table><thead><tr><th>Week</th><th>Average</th><th>Prices</th></tr></thead>'
        f'<tbody>{"".join(week_rows) or "<tr><td colspan=3>No history yet.</td></tr>"}</tbody></table></div>'
        "</div></div></section>"
    )


def _default_rank(record):
    score = record["score"]["score"]
    if record["drop_amount"]:
        return (0, -record["drop_amount"], -score)
    if record["added"]:
        return (1, -score, record["name"])
    return (2, -score, record["name"])


def _default_sort_key(record):
    """page.js compareSort for DEFAULT_SORT ("discount", high first), ties by rank.

    Sold out goes last, then listings without a % off.
    """
    percent = record["percent"]
    rounded = round(percent, 1) if percent is not None else None
    return (bool(record.get("sold_out")), rounded is None, -(rounded or 0), record["rank"])


def _plural(count, singular, plural):
    return f"{count} {singular if count == 1 else plural}"


def render_page(data, changes, price_history=None, failed_keys=None, generated_at=None, digest=None, sport=None):
    from report import build_digest

    # The sport's categories, branding and search vocabulary (sports/).
    # Skate's page is built exactly as before and carries no sport settings.
    sport = sport or sports.SKATE
    part_order_for_sport = PART_ORDER if sport.is_default else sport.parts
    default_part = sport.default_part
    # Shared assets live at the site root; a page in bmx/ reaches them with ../
    asset_prefix = "../" * sport.page_path.count("/")

    price_history = price_history or {}
    failed_keys = list(failed_keys or [])
    if digest is None:
        digest = build_digest(changes, failed_keys)
    if generated_at is None:
        generated_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    today = str(generated_at)[:10]

    products = []
    for items in (data or {}).values():
        for item in items or []:
            if item_passes_filters(item):
                products.append(item)

    new_urls = set()
    for item in digest.new_items or []:
        url = normalize_url(item.get("url"))
        if url:
            new_urls.add(url)
    drop_by_url = {}
    for change in digest.drops or []:
        item = change.get("item") or {}
        url = normalize_url(item.get("url") or change.get("url"))
        if url:
            drop_by_url[url] = change

    try:
        rules = load_watchlist()
    except Exception as exc:
        logger.error("Watchlist load failed: %s", exc)
        rules = []
    try:
        sales = describe_sales(load_state(), today)
    except Exception as exc:
        logger.error("Site-sale line failed: %s", exc)
        sales = []
    try:
        groups = list(getattr(digest, "cross_store", None) or []) or cross_store_groups(products)
    except Exception as exc:
        logger.error("Cross-store groups failed: %s", exc)
        groups = []
    group_by_url = {}
    for group in groups:
        for offer in group.get("offers") or []:
            url = normalize_url(offer.get("url"))
            if url:
                group_by_url[url] = group

    records = []
    catalog_json = {}
    # Price history for the charts, keyed by listing URL. Published as
    # history.json (see write_page) and fetched when a chart first needs it.
    history_json = {}
    for item in products:
        try:
            url = normalize_url(item.get("url"))
            entry = _entry(price_history, url)
            specs = _specs_for(item, entry)
            prices = _prices_of(entry)
            drop = drop_by_url.get(url)
            added = url in new_urls
            badges = classify_badges(
                item,
                price_history,
                in_previous=not added,
                drop=drop,
                today=today,
            )
            status = all_time_low_status(item, price_history)
            score = deal_score(
                item,
                price_history,
                drop=drop,
                width=specs.get("width"),
                today=today,
            )
            first = str(entry.get("first_seen") or "")[:10]
            last = str(entry.get("last_seen") or "")[:10] or today
            first_day = _as_date(first)
            today_day = _as_date(today)
            days = (today_day - first_day).days if first_day and today_day else 0
            if days < 0:
                days = 0
            held = days_at_price(entry, today)
            at_days = held.get("days") or 0
            at_price = held.get("price")
            since = str(held.get("since") or "")[:10]
            drop_day = last_drop_date(entry) or ""
            average = _window_average(prices, 90, today)
            if at_price is None:
                at_price = _price(item.get("price_new"))
            try:
                stage = listing_stage(
                    entry,
                    True,
                    today=today,
                    at_low=bool(status.get("flagged")),
                )
            except Exception:
                stage = "new"
            listed = any(rule_matches(rule, item) for rule in rules)
            brand = item.get("brand") or listing_brand(item.get("name") or "", item.get("part"))
            hit_low = bool(status.get("flagged")) and (
                str(status.get("low_date") or "")[:10] == today or drop is not None
            )
            drop_amount = 0.0
            if drop is not None:
                try:
                    drop_amount = float(drop.get("delta") or 0)
                except (TypeError, ValueError):
                    drop_amount = 0.0
            image = _image_of(item, entry)
            try:
                trend = price_trend(entry)
            except Exception:
                trend = "stable"
            width_key = dimension_key(specs.get("width")) if item.get("part") == "Decks" else ""
            length_key = dimension_key(specs.get("length")) or ""
            # "14,14.62" for a deck drilled for both; page.js splits it.
            wheel_key = ",".join(
                key for key in (dimension_key(value) for value in (specs.get("wheelbases") or [specs.get("wheelbase")])) if key
            )
            # Variant/option color when the catalog has one, else title words.
            # Deck photos are not a color source.
            color = listing_color(item)
            diameter = ""
            duros = []
            shape = ""
            truck_size = ""
            truck_height = ""
            construction = ""
            abec = ""
            raw_name = item.get("name") or ""
            if item.get("part") == "Wheels":
                from product_specs import enrich
                enriched_specs = item if any(key in item for key in ("spec_offers", "diameters_mm", "durometers")) else enrich(dict(item))
                parsed = wheel_specs(raw_name)
                diameter = ",".join(dict.fromkeys(band for value in (enriched_specs.get("diameters_mm") or []) if (band := diameter_band(value))))
                if not diameter and not enriched_specs.get('diameters_mm'):
                    diameter = diameter_band(parsed.get("diameter_mm"))
                duros = [token.lower() for token in (enriched_specs.get("durometers") or parsed.get("durometers") or []) if re.fullmatch(r"\d{2,3}[abd]", token.lower())]
                shape = parsed.get("shape") or ""
            elif item.get("part") == "Trucks":
                parsed = truck_specs(raw_name)
                truck_size = parsed.get("size") or ""
                truck_height = parsed.get("height") or ""
                construction = parsed.get("construction") or ""
            elif item.get("part") == "Bearings":
                abec = bearing_specs(raw_name).get("abec") or ""
            shoe_sizes = []
            if item.get("part") == "Sneakers":
                # A scraper size list is the in-stock sizes. Name and description
                # text must not add a size the store cannot sell.
                if "shoe_sizes" in item:
                    shoe_sizes = ordered_shoe_sizes(item.get("shoe_sizes") or [])
                else:
                    found = []
                    found.extend(shoe_sizes_in(raw_name))
                    found.extend(shoe_sizes_in(item.get("description") or ""))
                    shoe_sizes = ordered_shoe_sizes(found)
            prot_type = ""
            prot_sizes = []
            if item.get("part") == "Protection":
                subtype = item.get("protection_type") or classify_protection(raw_name, item.get("product_type") or "")
                prot_type = SUBTYPE_TOKENS.get(subtype or "", "")
                # A store's size list is what it sells; else sizes printed in the name.
                sizes = item.get("protection_sizes") if "protection_sizes" in item else protection_sizes_in(raw_name)
                prot_sizes = [size.casefold() for size in ordered_protection_sizes(sizes)]
            current_price = _price(item.get("price_new"))
            tracked_low = status.get("low")
            at_tracked_low = False
            if current_price is not None and tracked_low is not None:
                try:
                    at_tracked_low = float(current_price) <= float(tracked_low) + 0.001
                except (TypeError, ValueError):
                    at_tracked_low = False
            percent = percent_off_value(item.get("price_new"), item.get("price_old"))
            record = {
                "item": item,
                "url": url,
                "name": _display_name(item),
                "store": item.get("store") or "Unknown",
                "part": item.get("part") or "",
                "brand": brand,
                "specs": specs,
                "badges": badges,
                "score": score,
                "days": days,
                "at_days": at_days,
                "at_price": at_price,
                "held": _held_label(days, at_days, at_price),
                "stage": stage,
                "first": first,
                "last": last,
                "since": since,
                "since_label": _since_label(
                    since,
                    first,
                    prices,
                    _price(item.get("price_new")),
                    "€" if str(item.get("currency") or "USD").upper() == "EUR" else "$",
                ),
                "average": average,
                "drop_day": drop_day,
                "fresh": any(badge.get("kind") == "new" for badge in badges),
                "back": any(badge.get("kind") == "back" for badge in badges),
                "hot": bool(score.get("hot")),
                "listed": listed,
                "added": added,
                "drop": drop,
                "drop_amount": drop_amount,
                "lowest": bool(status.get("flagged")),
                "at_tracked_low": at_tracked_low,
                "hit_low": hit_low,
                "image": image,
                "trend": trend,
                "availability": "Sold out" if item.get("stock") == "out_of_stock" else _availability_label(entry, present=True),
                "sold_out": item.get("stock") == "out_of_stock",
                "prices": prices,
                "spark_end": today,
                "chain": _chain(prices),
                "group": group_by_url.get(url),
                "width_key": width_key,
                "length_key": length_key,
                "wheel_key": wheel_key,
                "color": color,
                "diameter": diameter,
                "duros": duros,
                "shape": shape,
                "truck_size": truck_size,
                "truck_height": truck_height,
                "construction": construction,
                "abec": abec,
                "shoe_sizes": shoe_sizes,
                "prot_type": prot_type,
                "prot_sizes": prot_sizes,
                "percent": percent,
                "search": " ".join(
                    bit
                    for bit in (
                        _display_name(item),
                        item.get("store") or "",
                        item.get("part") or "",
                        brand,
                        width_key,
                    )
                    if bit
                ),
            }
            item["_specs"] = specs
            item["_brand"] = brand
            records.append(record)
        except Exception as exc:
            logger.error("Skipping report row %s: %s", (item or {}).get("url"), exc)

    _canonicalize_brands(records)
    records.sort(key=_default_rank)
    for index, record in enumerate(records):
        record["id"] = str(index)
        record["rank"] = index
        catalog_json[record["id"]] = {
            "name": record["name"],
            "url": record["url"],
            "store": record["store"],
            "part": record["part"],
            "size": record["width_key"],
            "length": record["length_key"],
            "wheelbase": record["wheel_key"],
            "held": record["held"],
            "first": record["first"],
            "last": record["last"],
            "stage": STAGE_LABEL.get(record.get("stage") or "", ""),
            "image": record["image"],
            "images": product_image_urls(record["item"], record["image"]),
        }
        # Other sports' filter fields (sports/bmx/specs.py); Skate has none.
        for key in ("kind", "wheel_size", "condition", "gender", "lengths", "sizes"):
            if record["item"].get(key):
                catalog_json[record["id"]][key] = record["item"][key]

    by_group = {}
    for record in records:
        group = record.get("group") or {}
        key = group.get("key") or ""
        if key:
            by_group.setdefault(key, []).append(record)
    for record in records:
        members = by_group.get((record.get("group") or {}).get("key") or "") or [record]
        series = []
        offers = []
        priced = []
        for member in members:
            amount = _price(member["item"].get("price_new"))
            if amount is not None:
                priced.append(amount)
            series.append(
                listing_series(
                    _entry(price_history, member["url"]),
                    member["url"],
                    member["store"],
                    member.get("availability") or "On sale",
                    member["item"].get("currency"),
                )
            )
        cheapest = min(priced) if priced else None
        for member in members:
            amount = _price(member["item"].get("price_new"))
            offers.append(
                {
                    "store": member["store"],
                    "url": member["url"],
                    "price": amount,
                    "availability": member.get("availability") or "On sale",
                    "currency": str(member["item"].get("currency") or "USD").upper(),
                    "cheapest": bool(
                        cheapest is not None
                        and amount is not None
                        and abs(amount - cheapest) < 0.001
                        and len(members) > 1
                    ),
                }
            )
        catalog_json[record["id"]]["offers"] = offers
        history_json[record["url"] or f"#{record['id']}"] = {
            "series": record["chain"],
            "daily": _daily_points(record["prices"]),
            "seriesList": series,
        }

    store_counts = {}
    part_counts = {}
    range_counts = {bucket.id: 0 for bucket in WIDTH_RANGES}
    brands = set()
    brand_counts = {}
    deck_lengths = []
    wheel_values = []
    length_hits = 0
    wheel_hits = 0
    deck_color_counts = {}
    wheel_color_counts = {}
    deck_color_hits = 0
    wheel_color_hits = 0
    diameter_counts = {}
    duro_counts = {}
    shape_counts = {}
    truck_size_counts = {}
    truck_height_counts = {}
    construction_counts = {}
    abec_counts = {}
    shoe_size_counts = {}
    shoe_hits = 0
    prot_type_counts = {}
    prot_size_counts = {}
    prot_size_hits = 0
    wheels_with_duro = 0
    for record in records:
        store_counts[record["store"]] = store_counts.get(record["store"], 0) + 1
        part_counts[record["part"]] = part_counts.get(record["part"], 0) + 1
        if record["part"] == "Decks":
            widths = record["item"].get("widths") or ([record["width_key"]] if record["width_key"] else [])
            buckets = {bucket.id for value in widths if (bucket := bucket_for_width(value)) is not None}
            for bucket_id in buckets:
                range_counts[bucket_id] += 1
        if record["brand"]:
            brands.add(record["brand"])
            brand_counts[record["brand"]] = brand_counts.get(record["brand"], 0) + 1
        if record["part"] == "Decks" and record["length_key"]:
            deck_lengths.append(record["length_key"])
            length_hits += 1
        if record["part"] == "Decks" and record["wheel_key"]:
            wheel_values.extend(record["wheel_key"].split(","))
            wheel_hits += 1
        if record.get("color") and record["part"] == "Decks":
            deck_color_hits += 1
            deck_color_counts[record["color"]] = deck_color_counts.get(record["color"], 0) + 1
        elif record.get("color") and record["part"] == "Wheels":
            wheel_color_hits += 1
            wheel_color_counts[record["color"]] = wheel_color_counts.get(record["color"], 0) + 1
        if record["part"] == "Wheels":
            if record["diameter"]:
                for band in record["diameter"].split(","):
                    diameter_counts[band] = diameter_counts.get(band, 0) + 1
            if record["duros"]:
                wheels_with_duro += 1
                for token in record["duros"]:
                    duro_counts[token] = duro_counts.get(token, 0) + 1
            if record["shape"]:
                shape_counts[record["shape"]] = shape_counts.get(record["shape"], 0) + 1
        elif record["part"] == "Trucks":
            if record["truck_size"]:
                truck_size_counts[record["truck_size"]] = truck_size_counts.get(record["truck_size"], 0) + 1
            if record["truck_height"]:
                truck_height_counts[record["truck_height"]] = truck_height_counts.get(record["truck_height"], 0) + 1
            if record.get("construction"):
                token = record["construction"]
                construction_counts[token] = construction_counts.get(token, 0) + 1
        elif record["part"] == "Bearings" and record["abec"]:
            abec_counts[record["abec"]] = abec_counts.get(record["abec"], 0) + 1
        elif record["part"] == "Sneakers" and record.get("shoe_sizes"):
            shoe_hits += 1
            for token in record["shoe_sizes"]:
                shoe_size_counts[token] = shoe_size_counts.get(token, 0) + 1
        elif record["part"] == "Protection":
            if record.get("prot_type"):
                prot_type_counts[record["prot_type"]] = prot_type_counts.get(record["prot_type"], 0) + 1
            if record.get("prot_sizes"):
                prot_size_hits += 1
                for token in record["prot_sizes"]:
                    prot_size_counts[token] = prot_size_counts.get(token, 0) + 1

    low_items = []
    try:
        low_items = [record["item"] for record in records if record["lowest"]]
        order = {"Decks": 0, "Wheels": 1, "Trucks": 2, "Bearings": 3, "Sneakers": 4, "Accessories": 5,
                 "Completes": 6, "Protection": 7}
        low_items.sort(key=lambda item: (order.get(item.get("part"), 9), _display_name(item)))
    except Exception as exc:
        logger.error("All-time low list failed: %s", exc)
        low_items = []

    new_count = len(digest.new_items or [])
    drop_count = len(digest.drops or [])
    gone_count = len(digest.removed or [])
    hit_count = sum(1 for record in records if record["hit_low"])
    try:
        intel = intelligence_summary(
            products,
            price_history,
            new_items=digest.new_items,
            drops=digest.drops,
        )
    except Exception as exc:
        logger.error("Deals intelligence failed: %s", exc)
        intel = intelligence_summary([], {})
    highlight_urls = set()
    for deal in list(intel.get("new_deals") or []) + list(intel.get("biggest_drops") or []):
        if isinstance(deal, dict):
            url = normalize_url(deal.get("url") or "")
            if url:
                highlight_urls.add(url)
    for record in records:
        record["highlight"] = record.get("url") in highlight_urls

    chunks = [
        "<!DOCTYPE html>",
        '<html lang="en">',
        "<head>",
        '<script>if(window.parent!==window&&!window.shredBridgeInstalled){'
        f'const bridge=document.createElement("script");bridge.src="{asset_prefix}navigation/skate-bridge.js";'
        'bridge.async=false;document.head.appendChild(bridge);}</script>',
        '<meta charset="UTF-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1.0">',
        f"<title>{escape(sport.brand)} | {escape(today)}</title>",
        f"<style>{_read_asset('page.css')}</style>",
        f"<style>{_read_asset('mobile.css')}</style>",
        "<script>try{if(localStorage.getItem('salesscraper2.layout')!=='table')document.documentElement.classList.add('layout-cards')}catch(e){document.documentElement.classList.add('layout-cards')}</script>",
        "</head><body>",
    ]
    store_options = ['<option value="all">All stores</option>']
    for store in sorted(store_counts):
        store_options.append(
            _option(store, f"{store} ({store_counts[store]})", data_label=store)
        )
    part_options = ['<option value="all"' + (" selected" if default_part == "all" else "") + ">All types</option>"]
    for part in part_order_for_sport:
        if part in part_counts or part == default_part:
            part_options.append(
                _option(
                    part,
                    f"{part} ({part_counts.get(part, 0)})",
                    selected=(part == default_part),
                    data_label=part,
                )
            )
    sorted_brands = sorted(brands, key=str.casefold)
    brand_options = ['<option value="all" data-label="All brands">All brands</option>']
    for brand in sorted_brands:
        brand_options.append(_option(brand, brand, data_label=brand))
    length_buckets = build_length_buckets(deck_lengths)
    length_select = ""
    if section_ready(length_hits) and length_buckets:
        options = ['<option value="all">All lengths</option>']
        length_chips = [
            '<button type="button" class="chip length-chip active" data-value="all" '
            f'data-count="{length_hits}" aria-pressed="true" '
            f'title="{escape(LENGTH_BOUNDARY_TIP, quote=True)}">'
            '<span class="spec-label">All</span>'
            f'<span class="spec-count">{length_hits}</span></button>'
        ]
        for bucket in length_buckets:
            count = sum(1 for value in deck_lengths if length_bucket_for(value, [bucket]) == bucket["id"])
            options.append(_option(bucket["id"], bucket["label"], data_label=bucket["label"]))
            zero = " is-zero" if count == 0 else ""
            hidden = " hidden" if count == 0 else ""
            length_chips.append(
                f'<button type="button" class="chip length-chip{zero}"{hidden} '
                f'data-value="{escape(bucket["id"], quote=True)}" data-count="{count}" '
                f'title="{escape(bucket["tip"], quote=True)}" aria-pressed="false">'
                f'<span class="spec-label">{escape(bucket["label"])}</span>'
                f'<span class="spec-count">{count}</span></button>'
            )
        length_select = (
            '<div class="filter-group spec-ranges" id="lengthFilters" role="group" '
            f'aria-label="Deck length" title="{escape(LENGTH_BOUNDARY_TIP, quote=True)}">'
            + "".join(length_chips)
            + "</div>"
            f'<select id="lengthSelect" class="sr-only">{"".join(options)}</select>'
        )
    wheel_buckets = build_wheelbase_buckets(wheel_values) if section_ready(wheel_hits) else []
    wheel_select = ""
    if wheel_buckets:
        options = ['<option value="all">All wheelbases</option>']
        wheel_chips = [
            '<button type="button" class="chip wheelbase-chip active" data-value="all" '
            f'data-count="{wheel_hits}" aria-pressed="true" '
            f'title="{escape(WHEELBASE_BOUNDARY_TIP, quote=True)}">'
            '<span class="spec-label">All</span>'
            f'<span class="spec-count">{wheel_hits}</span></button>'
        ]
        for bucket in wheel_buckets:
            count = 0
            for record in records:
                if record["part"] != "Decks" or not record["wheel_key"]:
                    continue
                if any(
                    wheelbase_bucket_for(piece, [bucket]) == bucket["id"]
                    for piece in record["wheel_key"].split(",")
                ):
                    count += 1
            options.append(_option(bucket["id"], bucket["label"], data_label=bucket["label"]))
            zero = " is-zero" if count == 0 else ""
            hidden = " hidden" if count == 0 else ""
            wheel_chips.append(
                f'<button type="button" class="chip wheelbase-chip{zero}"{hidden} '
                f'data-value="{escape(bucket["id"], quote=True)}" data-count="{count}" '
                f'title="{escape(bucket["tip"], quote=True)}" aria-pressed="false">'
                f'<span class="spec-label">{escape(bucket["label"])}</span>'
                f'<span class="spec-count">{count}</span></button>'
            )
        wheel_select = (
            '<div class="filter-group spec-ranges" id="wheelbaseFilters" role="group" '
            f'aria-label="Wheelbase" title="{escape(WHEELBASE_BOUNDARY_TIP, quote=True)}">'
            + "".join(wheel_chips)
            + "</div>"
            f'<select id="wheelbaseSelect" class="sr-only">{"".join(options)}</select>'
        )
    # Compact labels over the existing half-open buckets. Low is inclusive
    # and high is exclusive. Buckets under 7.5" stay in WIDTH_RANGES for
    # older links, and they are not shown as buttons.
    width_groups = (
        ("7.5", '7.5" up to but not including 7.75"', ("7.5-7.75",)),
        ("7.75", '7.75" up to but not including 8.0"', ("7.75-8.0",)),
        ("8.0", '8.0" up to but not including 8.25"', ("8.0-8.125", "8.125-8.25")),
        ("8.25", '8.25" up to but not including 8.5"', ("8.25-8.375", "8.375-8.5")),
        ("8.5", '8.5" up to but not including 8.75"', ("8.5-8.75",)),
        ("8.75", '8.75" up to but not including 9.0"', ("8.75-9.0",)),
        ("9.0", '9.0" up to but not including 10.0"', ("9.0-9.25", "9.25-9.5", "9.5-10.0")),
        ("10+", '10.0" and wider', ("10up",)),
    )
    chips = []
    for label, tip, bucket_ids in width_groups:
        count = sum(range_counts.get(bucket_id, 0) for bucket_id in bucket_ids)
        zero = " is-zero" if count == 0 else ""
        chips.append(
            f'<button type="button" class="chip width-chip{zero}" '
            f'data-buckets="{escape(",".join(bucket_ids), quote=True)}" '
            f'data-count="{count}" title="{escape(tip, quote=True)}" aria-pressed="false">'
            f'<span class="width-label">{escape(label)}</span>'
            f'<span class="width-count">{count}</span></button>'
        )
    sort_select = (
        '<label class="field sort-field"><span>Sort</span><select id="sortSelect">'
        '<option value="discount" selected>% off</option>'
        '<option value="rank">Today\'s drops &amp; new first</option>'
        '<option value="score">Deal score</option>'
        '<option value="price">Sale price, low to high</option>'
        '<option value="price-desc">Sale price, high to low</option>'
        '<option value="original">Original price</option>'
        '<option value="size">Size</option>'
        '<option value="store">Store</option>'
        '<option value="brand">Brand</option>'
        '<option value="days">Days tracked</option>'
        '<option value="daysat">Days at this price</option>'
        '<option value="relevance">Best match (search)</option>'
        "</select></label>"
    )
    brand_buttons = [
        '<button type="button" class="facet-value active" data-brand="all" '
        'aria-pressed="true"><span class="facet-name">All brands</span></button>'
    ]
    for brand in sorted_brands:
        count = brand_counts.get(brand, 0)
        classes = "facet-value is-zero" if count == 0 else "facet-value"
        brand_buttons.append(
            f'<button type="button" class="{classes}" '
            f'data-brand="{escape(brand, quote=True)}" data-count="{count}" aria-pressed="false">'
            f'<span class="facet-name">{escape(brand)}</span>'
            f'<span class="facet-count">({count})</span></button>'
        )
    def _section(section_id, label, body, open_default=False, for_part="", tip=""):
        if not body:
            return ""
        classes = ["filter-section"]
        if open_default:
            classes.append("is-open")
        # Decks is the fresh-visit default, so those sections start visible.
        if for_part and for_part != "Decks":
            classes.append("is-type-hidden")
        expanded = "true" if open_default else "false"
        for_attr = f' data-for="{escape(for_part, quote=True)}"' if for_part else ""
        tip_attr = f' title="{escape(tip, quote=True)}"' if tip else ""
        return (
            f'<section class="{" ".join(classes)}" data-section="{section_id}"{for_attr}{tip_attr}>'
            f'<button type="button" class="section-toggle" aria-expanded="{expanded}" '
            f'aria-controls="section-{section_id}"{tip_attr}>{escape(label)}</button>'
            f'<div class="section-body" id="section-{section_id}">{body}</div>'
            "</section>"
        )

    def _spec_button(value, label, count, tip):
        zero = " is-zero" if count == 0 else ""
        return (
            f'<button type="button" class="chip spec-chip{zero}" '
            f'data-value="{escape(str(value), quote=True)}" data-count="{count}" '
            f'title="{escape(tip, quote=True)}" aria-pressed="false">'
            f'<span class="spec-label">{escape(str(label))}</span>'
            f'<span class="spec-count">{count}</span></button>'
        )

    def _spec_body(group_id, label, buttons, note):
        if not buttons:
            return ""
        note_html = f'<p class="section-note">{escape(note)}</p>' if note else ""
        return (
            f'<div class="filter-group spec-ranges" id="{group_id}" role="group" '
            f'aria-label="{escape(label, quote=True)}">{"".join(buttons)}</div>{note_html}'
        )

    brand_facet = (
        '<div class="facet brand-facet" id="brandFacet">'
        f'<select id="brandSelect" class="sr-only" aria-label="Brand">{"".join(brand_options)}</select>'
        '<input id="brandSearch" class="brand-search" type="search" placeholder="Find a brand" '
        'aria-label="Find a brand" autocomplete="off">'
        f'<div class="facet-list" id="brandList" tabindex="0" aria-label="Brands">'
        f'{"".join(brand_buttons)}</div></div>'
    )

    sale_prices = [
        amount
        for record in records
        if (amount := _price(record["item"].get("price_new"))) is not None
    ]
    price_cap = int(math.ceil(max(sale_prices))) if sale_prices else 1
    if price_cap < 1:
        price_cap = 1
    interval_buttons = []
    for key, label in (
        ("all", "All"),
        ("day", "Day"),
        ("week", "Week"),
        ("month", "Month"),
        ("quarter", "3 Months"),
    ):
        pressed = "true" if key == "all" else "false"
        interval_buttons.append(
            f'<button type="button" class="interval-btn" data-interval="{key}" aria-pressed="{pressed}">'
            f'{label} <span class="facet-count"></span></button>'
        )
    kind_buttons = []
    for key, label, dot in (
        ("highlights", "Highlights", "kind-highlights"),
        ("new", "New", "kind-new"),
        ("drop", "Price drop", "kind-drop"),
        ("low", "All-time low", "kind-low"),
        ("back", "Back in stock", "kind-back"),
        ("watch", "Watching", "kind-watch"),
        ("hot", "Hot", "kind-hot"),
    ):
        kind_buttons.append(
            f'<button type="button" class="kind-btn" data-kind="{key}" aria-pressed="false">'
            f'<span class="kind-dot {dot}" aria-hidden="true"></span>{label} '
            f'<span class="facet-count"></span></button>'
        )

    def _gated(section_id, label, part, buttons, note, hits):
        if not section_ready(hits) or not buttons:
            return ""
        return _section(
            section_id,
            label,
            _spec_body(section_id + "Filters", label, buttons, note),
            open_default=True,
            for_part=part,
        )

    diameter_buttons = [
        _spec_button(band_id, band_id, diameter_counts[band_id], diameter_tip(band_id))
        for band_id, _low, _high in DIAMETER_BANDS
        if diameter_counts.get(band_id)
    ]
    duro_buttons = [
        _spec_button(token, token, duro_counts[token], f"Durometer {token} printed in the name")
        for token in sorted(duro_counts, key=lambda token: (int(token[:-1]), token[-1]))
    ]
    shape_buttons = [
        _spec_button(
            token,
            SHAPE_LABELS[token],
            shape_counts[token],
            f"{SHAPE_LABELS[token]} is named in the listing",
        )
        for token in SHAPES
        if shape_counts.get(token)
    ]
    size_buttons = [
        _spec_button(token, token, truck_size_counts[token], size_tip(token))
        for token in sorted(truck_size_counts, key=float)
    ]
    height_buttons = [
        _spec_button(
            token,
            HEIGHT_LABELS[token],
            truck_height_counts[token],
            f"The name says {token}",
        )
        for token in HEIGHTS
        if truck_height_counts.get(token)
    ]
    abec_buttons = [
        _spec_button(token, f"ABEC {token}", abec_counts[token], f"ABEC {token} printed in the name")
        for token in sorted(abec_counts, key=int)
    ]
    diameter_section = _gated(
        "diameter",
        "Wheel Diameter",
        "Wheels",
        diameter_buttons,
        "Taken from mm in the name.",
        sum(diameter_counts.values()),
    )
    duro_section = _gated(
        "duro",
        "Durometer",
        "Wheels",
        duro_buttons,
        "Hardness printed in the name. A wheel with two ratings matches either.",
        wheels_with_duro,
    )
    shape_section = _gated(
        "shape",
        "Wheel Shape",
        "Wheels",
        shape_buttons,
        "Only a shape word printed in the name.",
        sum(shape_counts.values()),
    )
    truck_size_section = _gated(
        "trucksize",
        "Truck Size",
        "Trucks",
        size_buttons,
        "Hanger size, Ace size, inch width, or axle width printed in the name.",
        sum(truck_size_counts.values()),
    )
    truck_height_section = _gated(
        "truckheight",
        "Truck Height",
        "Trucks",
        height_buttons,
        "Only when the name says low, mid, or high.",
        sum(truck_height_counts.values()),
    )
    abec_section = _gated(
        "abec",
        "ABEC",
        "Bearings",
        abec_buttons,
        "ABEC rating printed in the name.",
        sum(abec_counts.values()),
    )
    shoe_buttons = [
        _spec_button(token, token, shoe_size_counts[token], f"US men's {token}")
        for token in sorted(shoe_size_counts, key=float)
    ]
    shoe_section = _gated(
        "shoesize",
        "Size",
        "Sneakers",
        shoe_buttons,
        "US men's size only when that size is in stock.",
        shoe_hits,
    )
    prot_labels = {token: subtype for subtype, token in SUBTYPE_TOKENS.items()}
    prot_type_section = _gated(
        "prottype",
        "Protection Type",
        "Protection",
        [
            _spec_button(token, prot_labels[token], prot_type_counts[token], prot_labels[token])
            for token in SUBTYPE_TOKENS.values()
            if prot_type_counts.get(token)
        ],
        "Helmets, pads, wrist guards, pad sets, and other gear such as impact shorts.",
        sum(prot_type_counts.values()),
    )
    prot_size_section = _gated(
        "protsize",
        "Size",
        "Protection",
        [
            _spec_button(size.casefold(), size, prot_size_counts[size.casefold()], f"Size {size}")
            for size in PROTECTION_SIZES
            if prot_size_counts.get(size.casefold())
        ],
        "Only when the store lists the size.",
        prot_size_hits,
    )
    construction_buttons = [
        _spec_button(
            token,
            CONSTRUCTION_LABELS[token],
            construction_counts[token],
            f"{CONSTRUCTION_LABELS[token]} printed in the name",
        )
        for token in CONSTRUCTIONS
        if construction_counts.get(token)
    ]
    construction_section = _gated(
        "construction",
        "Construction",
        "Trucks",
        construction_buttons,
        "Only when the name says hollow or standard.",
        sum(construction_counts.values()),
    )

    def _quick_chip(attr, value, label, count, pressed=False, order=0, home="row"):
        on = "true" if pressed else "false"
        active = " active" if pressed else ""
        zero = " is-zero" if count == 0 else ""
        return (
            f'<button type="button" class="chip quick-chip{active}{zero}" '
            f'data-order="{order}" data-home="{home}" '
            f'data-{attr}="{escape(str(value), quote=True)}" data-count="{count}" '
            f'aria-pressed="{on}">'
            f'<span class="quick-name">{escape(str(label))}</span>'
            f'<span class="quick-count">{count}</span></button>'
        )

    def _more_menu(menu_id, label, buttons):
        hidden = "" if buttons else " hidden"
        return (
            f'<div class="more-menu" id="{menu_id}"{hidden}>'
            f'<button type="button" class="chip more-toggle" aria-expanded="false" '
            f'aria-controls="{menu_id}List">{escape(label)}</button>'
            f'<div class="more-list" id="{menu_id}List" hidden>'
            + "".join(buttons)
            + "</div></div>"
        )

    primary_stores = ("Zumiez", "Tactics", "SkateWarehouse", "CCS", "TGM", "Deathgear", "Kinetic", "SPoT", "Exodus", "SoCal")
    store_total = sum(store_counts.values())
    store_buttons = [_quick_chip("store", "all", "All stores", store_total, pressed=True, order=0)]
    for store in primary_stores:
        if store in store_counts:
            store_buttons.append(
                _quick_chip("store", store, store, store_counts[store], order=len(store_buttons))
            )
    extra_stores = [store for store in sorted(store_counts) if store not in primary_stores]
    store_more = [
        _quick_chip(
            "store", store, store, store_counts[store],
            order=len(store_buttons) + index, home="more",
        )
        for index, store in enumerate(extra_stores)
    ]
    store_row = (
        '<div class="nav-cluster quick-filters" id="storeFilters">'
        '<span class="quick-label">Stores</span>'
        '<div class="quick-row" role="group" aria-label="Store">'
        + "".join(store_buttons)
        + _more_menu("moreStores", "+ More stores", store_more)
        + "</div>"
        f'<select id="storeSelect" class="sr-only" aria-label="Store">{"".join(store_options)}</select>'
        "</div>"
    )
    part_order = part_order_for_sport
    part_total = sum(part_counts.values())
    part_buttons = [_quick_chip("part", "all", "All", part_total, pressed=(default_part == "all"), order=0)]
    shown_parts = []
    for part in part_order:
        if part not in part_counts and part != default_part:
            continue
        shown_parts.append(part)
        part_buttons.append(
            _quick_chip(
                "part", part, part, part_counts.get(part, 0),
                pressed=(part == default_part), order=len(part_buttons),
            )
        )
    extra_parts = [part for part in sorted(part_counts) if part not in shown_parts]
    for part in extra_parts:
        part_options.append(
            _option(part, f"{part} ({part_counts.get(part, 0)})", data_label=part)
        )
    part_more = [
        _quick_chip(
            "part", part, part, part_counts.get(part, 0),
            order=len(part_buttons) + index, home="more",
        )
        for index, part in enumerate(extra_parts)
    ]
    part_row = (
        '<div class="nav-cluster quick-filters" id="partFilters">'
        '<span class="quick-label">Products</span>'
        '<div class="quick-row" role="group" aria-label="Product type">'
        + "".join(part_buttons)
        + _more_menu("moreParts", "+ More", part_more)
        + "</div>"
        f'<select id="partSelect" class="sr-only" aria-label="Product type">{"".join(part_options)}</select>'
        "</div>"
    )
    def _color_section(section_id, group_id, part, counts, hits):
        # A handful of parsed colors is enough to be a filter. Below that the
        # section stays off, the same bar as the other spec sections.
        if not section_ready(hits):
            return ""
        buttons = [
            '<button type="button" class="chip color-swatch color-all active" data-value="all" '
            f'data-count="{hits}" aria-pressed="true" title="All colors">'
            '<span class="spec-label">All</span>'
            f'<span class="spec-count">{hits}</span></button>'
        ]
        for color_id, label, swatch in COLOR_PALETTE:
            count = counts.get(color_id, 0)
            if count <= 0:
                continue
            swatch_class = "swatch"
            style = ""
            if color_id == "clear":
                swatch_class += " swatch-clear"
            elif color_id == "multi":
                swatch_class += " swatch-multi"
            elif swatch:
                style = f' style="--swatch:{escape(swatch, quote=True)}"'
            buttons.append(
                f'<button type="button" class="color-swatch" data-value="{escape(color_id, quote=True)}" '
                f'data-count="{count}" title="{escape(label, quote=True)}" aria-pressed="false">'
                f'<span class="{swatch_class}"{style} aria-hidden="true"></span>'
                f'<span class="spec-count">{count}</span></button>'
            )
        body = (
            f'<div class="filter-group color-swatches" id="{group_id}" role="group" aria-label="Color">'
            + "".join(buttons)
            + "</div>"
        )
        return _section(section_id, "Color", body, open_default=True, for_part=part)

    # Brand is rendered ahead of this block. Inside it, each type's main size
    # comes before that type's secondary specs (length, durometer, height, …).
    # Color follows that type's size filters. Hidden types drop out, so a
    # Trucks visit still reads Brand, Truck Size, Truck Height, Construction.
    context_specs = (
        '<div id="contextSpecs">'
        + _section(
            "width",
            "Deck Width",
            '<div class="filter-group width-ranges" id="sizeFilters" role="group" aria-label="Deck width">'
            f'{"".join(chips)}</div>',
            open_default=True,
            for_part="Decks",
        )
        + truck_size_section
        + diameter_section
        + _color_section("wheelcolor", "wheelColorFilters", "Wheels", wheel_color_counts, wheel_color_hits)
        + shoe_section
        + prot_size_section
        + abec_section
        + _section(
            "length",
            "Deck Length",
            length_select,
            open_default=True,
            for_part="Decks",
            tip=LENGTH_BOUNDARY_TIP,
        )
        + _section(
            "wheelbase",
            "Wheelbase",
            wheel_select,
            open_default=True,
            for_part="Decks",
            tip=WHEELBASE_BOUNDARY_TIP,
        )
        + _color_section("deckcolor", "deckColorFilters", "Decks", deck_color_counts, deck_color_hits)
        + truck_height_section
        + construction_section
        + duro_section
        + shape_section
        + prot_type_section
        + "</div>"
    )
    if sport.facets:
        from sports.facets import sidebar
        context_specs = sidebar(data, _section, sport)
    sidebar_html = (
        '<aside class="sidebar" id="filterDrawer">'
        '<div class="drawer-head"><strong>Filters</strong>'
        '<button type="button" class="quick-close filters-done" id="filtersClose" aria-label="Close filters">×</button></div>'
        '<div class="filter-head"><span>Filter deals</span>'
        '<button type="button" class="text-btn" id="clearAll" onclick="clearFilters()">Clear all</button></div>'
        + '<div class="side-group" id="specGroup" aria-label="Product specifications">'
        + _section("brand", "Brand", brand_facet, open_default=True)
        + context_specs
        + '<section class="filter-section" id="productSpecs" data-section="specs" hidden>'
        '<button type="button" class="section-toggle" aria-expanded="false" '
        'aria-controls="productSpecsBody">Product specifications</button>'
        '<div class="section-body" id="productSpecsBody">'
        '<p class="section-note">Pick a spec to switch to that product type.</p>'
        "</div></section>"
        + "</div>"
        + '<div class="side-group" aria-label="Shopping filters">'
        + '<div class="more-filters" id="morePanel">'
        '<span class="sr-only">More filters</span>'
        + _section(
            "price",
            "Price",
            '<div class="field-pair">'
            '<label class="field"><span>Min</span><input id="priceMin" type="number" min="0" step="1" inputmode="decimal"></label>'
            '<label class="field"><span>Max</span><input id="priceMax" type="number" min="0" step="1" inputmode="decimal"></label>'
            "</div>"
            + _dual_html("priceMin", "priceMax", 0, price_cap, "$", "Any price", "Minimum price", "Maximum price"),
        )
        + _section(
            "discount",
            "Discount",
            '<div class="field-pair">'
            '<label class="field"><span>Min %</span><input id="discountMin" type="number" min="0" max="100" step="1"></label>'
            '<label class="field"><span>Max %</span><input id="discountMax" type="number" min="0" max="100" step="1"></label>'
            "</div>"
            + _dual_html(
                "discountMin", "discountMax", 0, 100, "", "Any discount",
                "Minimum percent off", "Maximum percent off", suffix="%",
            ),
        )
        + "</div></div>"
        + '<div class="side-group" aria-label="Deal intelligence">'
        + _section(
            "score",
            "Deal quality",
            '<div class="field-pair">'
            '<label class="field"><span>Min</span><input id="scoreMin" type="number" min="0" max="100" step="1"></label>'
            '<label class="field"><span>Max</span><input id="scoreMax" type="number" min="0" max="100" step="1"></label>'
            "</div>"
            + _dual_html("scoreMin", "scoreMax", 0, 100, "", "Any score", "Minimum score", "Maximum score"),
        )
        + _section(
            "deals",
            "Deal Type",
            '<div class="kind-list" id="dealTypes" role="group" aria-label="Deal type">'
            + "".join(kind_buttons)
            + "</div>",
        )
        + _section(
            "interval",
            "Drop Interval",
            '<div class="interval-list" id="dropInterval" role="group" aria-label="Drop interval">'
            + "".join(interval_buttons)
            + "</div>"
            '<p class="section-note">A drop is at least $2 or 5% below the previous tracked price. '
            "Day is today or yesterday.</p>",
        )
        + "</div>"
        + '<div class="side-group" aria-label="Personal tools">'
        + _section(
            "views",
            "Saved Views",
            '<div class="saved-views">'
            '<form class="save-view" id="saveViewForm" hidden>'
            '<input id="viewNameInput" type="text" maxlength="80" placeholder="Name this view" aria-label="View name">'
            '<button type="submit" class="text-btn">Save</button>'
            '<button type="button" class="text-btn" id="viewCancel">Cancel</button>'
            "</form>"
            '<div class="view-row" id="viewRow"></div></div>',
        )
        + _section(
            "watching",
            "Watching",
            '<div class="tool-row">'
            '<button type="button" class="text-btn" id="watchingToggle" aria-pressed="false" '
            'onclick="toggleWatching()">Watching</button></div>',
        )
        + _section(
            "bookmarks",
            "Bookmarks",
            '<div class="tool-row">'
            '<button type="button" class="text-btn" id="saveView">Save view</button>'
            '<button type="button" class="text-btn" id="bookmarkView">Bookmark this selection</button>'
            "</div>",
        )
        + "</div>"
        + '<button type="button" class="text-btn show-results filters-done">Show results</button>'
        "</aside>"
    )
    store_names = []
    for key in data or {}:
        store_name = str(key).rsplit("_", 1)[0]
        if store_name and store_name not in store_names:
            store_names.append(store_name)
    for store_name in store_counts:
        if store_name not in store_names:
            store_names.append(store_name)
    store_cards = ['<div class="stats-grid" hidden>']
    for store in sorted(store_names):
        count = store_counts.get(store, 0)
        card_class = "stat-card"
        badge = ""
        store_cards.append(
            f'<button type="button" class="{card_class}" data-card="store" '
            f'data-store="{escape(store, quote=True)}" aria-pressed="false" '
            f"onclick=\"toggleCard('store', '{escape(store, quote=True)}')\">"
            f'<span class="number">{count}</span><span class="label">{escape(store)}</span>{badge}</button>'
        )
    store_cards.append("</div>")
    chunks.append(
        '<header id="stickyBar">'
        '<div class="topnav">'
        '<h1 class="brand"><button type="button" class="brand-home" id="homeReset" title="Back to default view">'
        '<svg class="brand-mark" viewBox="0 0 24 24" width="22" height="22" aria-hidden="true">'
        '<rect x="2" y="8" width="20" height="5.5" rx="1.4" fill="none" stroke="currentColor" stroke-width="1.7"/>'
        '<circle cx="7.2" cy="17.2" r="1.7" fill="currentColor"/>'
        '<circle cx="16.8" cy="17.2" r="1.7" fill="currentColor"/>'
        f"</svg>{escape(sport.brand)}</button></h1>"
        '<div class="topnav-links" role="group" aria-label="Sections">'
        '<button type="button" class="nav-link" id="navDeals" aria-pressed="true">Deals</button>'
        '<button type="button" class="nav-link" id="navTrack" aria-pressed="false">Track</button>'
        '<button type="button" class="nav-link" id="navInsights" aria-pressed="false">Insights</button>'
        "</div>"
        '<span class="scan-wrap">last scan <time id="lastScan" datetime="'
        f'{escape(str(generated_at), quote=True)}">{escape(format_scan_et(generated_at))}</time>'
        f'<span class="scan-exact" id="scanExact">{escape(format_scan_et(generated_at))}</span></span>'
        '<span class="fresh-note" id="freshness"></span>'
        '<button type="button" class="text-btn filters-open" id="filtersOpen">Filters</button>'
        "</div>"
        '<div class="nav-row" id="navPills">'
        + part_row
        + store_row
        + "</div>"
        '<div class="tool-line">'
        # A combobox: suggestions in #searchSuggest, filters read from the
        # query as chips in #searchChips (search/search-ui.js).
        '<div class="search-box tool-search"><div class="search-field">'
        '<input type="text" id="searchInput" role="combobox" aria-autocomplete="list" aria-expanded="false" '
        'aria-controls="searchSuggest" aria-describedby="searchHelp" autocomplete="off" spellcheck="false" '
        'placeholder="Search deals (brand, product, keyword...)" aria-label="Search deals">'
        '<div id="searchSuggest" class="search-suggest" role="listbox" aria-label="Search suggestions" hidden></div>'
        "</div>"
        '<p id="searchHelp" class="sr-only">Type a brand, product, size or price, like spitfire 54mm 99a under 30. '
        "Press slash to search from anywhere.</p>"
        '<div id="searchChips" class="search-chips" aria-label="Filters read from your search" hidden></div></div>'
        '<div class="tool-deals">'
        '<p class="lede digest" id="changeLine" '
        f'data-new="{new_count}" data-drops="{drop_count}" data-lows="{hit_count}" data-gone="{gone_count}" '
        'data-baseline="previous-scrape">'
        '<span class="digest-label sr-only">Digest of what changed since the previous daily scrape. '
        'New, price drops, hit lowest, and disappeared use that fixed baseline.</span> '
        '<span class="baseline-note" id="changePrefix">vs previous scrape</span>'
        '<span class="segment" role="group" aria-label="What changed">'
        '<button type="button" class="change-btn active" id="btnAll" data-change="all" '
        'aria-pressed="true" onclick="setChange(\'all\')">All deals</button> '
        f'<button type="button" class="change-btn" id="btnNew" data-change="new" aria-pressed="false" '
        f"onclick=\"setChange('new')\">New {new_count}</button> "
        f'<button type="button" class="change-btn" id="btnDrop" data-change="drop" aria-pressed="false" '
        f"onclick=\"setChange('drop')\">Price drops {drop_count}</button> "
        f'<button type="button" class="change-btn" id="btnLow" data-change="lowest" aria-pressed="false" '
        f"onclick=\"setChange('lowest')\">Hit lowest {hit_count}</button> "
        f'<button type="button" class="change-btn" id="btnGone" data-change="removed" aria-pressed="false" '
        f"onclick=\"setChange('removed')\">Disappeared {gone_count}</button>"
        "</span></p>"
        f'<p class="result-count"><span id="statusCounts">{len(records)} deals</span></p>'
        "</div>"
        f"{sort_select}"
        '<div class="tool-display">'
        '<div class="layout-toggle" role="group" aria-label="Layout">'
        '<button type="button" id="layoutTable" aria-pressed="false">Table</button>'
        '<button type="button" id="layoutCards" aria-pressed="true">Cards</button>'
        "</div>"
        '<button type="button" class="text-btn group-toggle" id="groupToggle" aria-pressed="false" '
        'onclick="toggleGrouped()">Group across stores</button>'
        "</div>"
        '<div class="active-filters" id="activeFilters" hidden>'
        '<div class="active-row" id="activeChips"></div>'
        '<button type="button" class="text-btn" onclick="clearFilters()">Clear all</button></div>'
        "</div>"
        "</header>"
        '<div class="shell">'
        '<div class="rail">'
    )
    chunks.append(sidebar_html)
    chunks.append(
        '</div>'
        '<div class="board">'
        + "".join(store_cards)
    )
    try:
        stats_html = _stats_html(products, price_history, intel)
    except Exception as exc:
        logger.error("Stats section failed: %s", exc)
        stats_html = ""
    stats_html = stats_html.replace(
        '<section id="statsPanel" hidden>',
        '<section id="statsPanel" hidden>'
        + _intel_strip(intel)
        + '<button type="button" class="text-btn" id="statsToggle" aria-pressed="false" '
        + 'onclick="toggleStats()">Deals intelligence</button>',
        1,
    )

    header_cells = [
        ("", ""),
        ("", ""),
        ("Store", "store"),
        ("Brand", "brand"),
        ("Type", "part"),
        ("Size", "size"),
        ("Product", "name"),
        ("Sale price", "price"),
        ("Original", "original"),
        ("% off", "discount"),
        ("Days", "days"),
        ("Score", "score"),
    ]
    head = []
    for label, key in header_cells:
        if not key:
            head.append("<th></th>")
        elif key == "days":
            head.append(
                '<th class="days-head">'
                '<button type="button" data-sort="days" onclick="sortBy(\'days\')">Tracked</button>'
                '<button type="button" data-sort="daysat" onclick="sortBy(\'daysat\')">At price</button>'
                "</th>"
            )
        elif key == "score":
            head.append(
                '<th data-sort="score" onclick="sortBy(\'score\')">Score '
                f'<button type="button" class="info-dot" id="scoreInfo">?</button>'
                f'<span class="tip" id="scoreTip" role="tooltip">{escape(SCORE_LEGEND)}</span></th>'
            )
        else:
            head.append(
                f'<th data-sort="{key}" onclick="sortBy(\'{key}\')">{escape(label)}</th>'
            )
    chunks.append(
        '<div class="section" id="dealsSection">'
        '<h2 class="sr-only">All Deals</h2>'
        + '<div class="section-content">'
        '<div id="emptyState" class="empty-state" hidden></div>'
    )
    chunks.append(f'<div class="table-wrap"><table id="mainTable"><thead><tr>{"".join(head)}</tr></thead><tbody>')
    # Each table row is only its <tr> with the data-* attributes page.js
    # filters and sorts on. The cells wait as raw text in #tableRows (not
    # parsed, so they cost no DOM) until the Table layout is first shown.
    cell_chunks = []
    card_chunks = ['<div class="card-grid" id="cardGrid">']
    pool_chunks = ['<template id="cardPool">']
    shown_decks = 0
    pooled_decks = 0
    # Built in the default sort (% off) so the first cards are right before
    # page.js runs; it re-sorts the same way. ``rank`` keeps the drops-first
    # order for the "Today's drops & new first" option.
    for record in sorted(records, key=_default_sort_key):
        try:
            row_html = _row_html(record)
            card_html = _card_html(record)
            chunks.append(row_html[: row_html.index(">") + 1] + "</tr>")
            cell_chunks.append(row_html)
            # The fresh visit is Decks, in this same rank order. The first
            # page of those cards is in the grid; everything else waits.
            if record["part"] == "Decks" and shown_decks < CARD_PAGE_SIZE:
                card_chunks.append(card_html)
                shown_decks += 1
            else:
                if record["part"] == "Decks":
                    pooled_decks += 1
                pool_chunks.append(card_html)
        except Exception as exc:
            logger.error("Row render failed for %s: %s", record.get("url"), exc)
    try:
        removed_feed = _removed_feed(digest, products, price_history)
    except Exception as exc:
        logger.error("Disappeared feed failed: %s", exc)
        removed_feed = []
    for index, removed in enumerate(removed_feed):
        row_id = f"g{index}"
        try:
            chunks.append(_removed_row_html(removed, row_id))
            pool_chunks.append(_removed_card_html(removed, row_id))
            catalog_json[row_id] = {
                "name": removed["name"],
                "url": removed["url"],
                "store": removed["store"],
                "part": removed["part"],
                "image": removed.get("image") or "",
                "images": product_image_urls(removed["item"], removed.get("image") or ""),
                "daily": [],
                "series": [],
            }
        except Exception as exc:
            logger.error("Disappeared row failed for %s: %s", removed.get("url"), exc)
    chunks.append("</tbody></table></div>")
    chunks.append(f'<script type="text/html" id="tableRows">{_script_text("".join(cell_chunks))}</script>')
    card_chunks.append("</div>")
    more_hidden = "" if pooled_decks else " hidden"
    card_chunks.append(
        f'<button type="button" class="show-more-cards" id="showMoreCards"{more_hidden}>'
        "Show more</button>"
    )
    card_chunks.extend(pool_chunks)
    card_chunks.append("</template>")
    chunks.append("".join(card_chunks))
    chunks.append(_group_board(records))
    chunks.append("</div></div>")
    chunks.append(stats_html)

    try:
        chunks.append(_atl_section(low_items, price_history))
    except Exception as exc:
        logger.error("All-time low section failed: %s", exc)
    try:
        chunks.append(_gone_section(price_history, data, today, failed_keys))
    except Exception as exc:
        logger.error("Recently gone section failed: %s", exc)
    try:
        chunks.append(_compare_section(groups))
    except Exception as exc:
        logger.error("Across-stores section failed: %s", exc)
    try:
        chunks.append(_activity_html(sales, generated_at))
    except Exception as exc:
        logger.error("Retailer activity panel failed: %s", exc)

    if sport.is_default:
        chunks.append(
            "<footer><p>Zumiez, Skate Warehouse, CCS, Tactics, TGM Skateboards, Deathgear, Kinetic, Skate Park of Tampa, Exodus Ride Shop, and SoCal Skateshop. "
            "Decks stay at 10% off or more for known street brands and 15% otherwise, "
            "7.5 inches and wider. Named cruiser and longboard listings are still excluded. "
            f"{escape(FORMULA)} "
            "Stars are saved in this browser. "
            "A site-wide sale is a day when a store's sale count is at least 2.5× its recent median and 30 items higher, "
            "after 7 quieter days. Skate Warehouse is seeded at 2026-07-04 until a later day clears that bar.</p>"
            "</footer></div></div>"
        )
    else:
        stores_line = f"Deals from {', '.join(sorted(store_counts))}. " if store_counts else "No stores yet. "
        chunks.append(
            f"<footer><p>{escape(stores_line)}{escape(FORMULA)} "
            "Stars are saved in this browser. "
            "A site-wide sale is a day when a store's sale count is at least 2.5× its recent median and 30 items higher, "
            "after 7 quieter days.</p>"
            "</footer></div></div>"
        )
    chunks.append(
        '<div id="quickView" hidden>'
        '<div class="quick-panel" role="dialog" aria-labelledby="quickLabel">'
        '<div id="quickBody"></div>'
        "</div></div>"
    )
    payload = json.dumps(
        {
            "generated": str(generated_at),
            "scanLabel": format_scan_et(generated_at),
            "chartNote": CHART_NOTE,
            "views": list(STARTER_VIEWS),
            "items": catalog_json,
        }
    ).replace("<", "\\u003c")
    chunks.append(
        '<div id="sparkPanel" hidden>'
        '<p class="spark-title" id="sparkPanelTitle"></p>'
        '<p class="spark-chain" id="sparkPanelText"></p>'
        "</div>"
        '<div id="sparkTip" hidden></div>'
    )
    chunks.append(f'<script type="application/json" id="catalogJson">{payload}</script>')
    history_payload = json.dumps({"generated": str(generated_at), "items": history_json}).replace("<", "\\u003c")
    chunks.append(f'<script type="application/json" id="historyJson">{history_payload}</script>')
    ranges_literal = json.dumps(
        [
            {"id": bucket.id, "label": bucket.label, "min": bucket.min, "max": bucket.max}
            for bucket in WIDTH_RANGES
        ]
    )
    # Subscriber alerts are Skate-only until a sport opts in (sports/__init__.py
    # delivery); without the config page.js shows alerts as "coming soon".
    chunks.append(_alerts_config_script() if sport.delivery else "")
    length_literal = json.dumps(
        [
            {
                "id": bucket["id"],
                "label": bucket["label"],
                "min": bucket["min"],
                "max": bucket["max"],
            }
            for bucket in length_buckets
        ]
    )
    chunks.append(
        # Search: MiniSearch (vendored, MIT) and SkateDeals' search module.
        f"<script>{_read_asset('search/vendor/minisearch.js')}\n{_read_asset('search/search.js')}\n"
        f"SkateSearch.configure({_search_aliases(sport.aliases_file())});</script>"
    )
    if sport.facets:
        from sports.facets import script
        chunks.append(script(data, sport))
    chunks.append(
        "<script>"
        + (
            ""
            if sport.is_default
            else "const SPORT_SETTINGS = "
            + json.dumps({"id": sport.id, "label": sport.label, "defaultPart": default_part, "parts": list(sport.parts), "alerts": bool(sport.delivery)}).replace("<", "\\u003c")
            + ";\n"
        )
        + f"const WIDTH_RANGES = {ranges_literal};\n"
        f"const LENGTH_BUCKETS = {length_literal};\n"
        f"const WHEELBASE_BUCKETS = {json.dumps([{key: bucket[key] for key in ('id', 'label', 'min', 'max')} for bucket in wheel_buckets])};\n"
        f"const CARD_PAGE_SIZE = {CARD_PAGE_SIZE};\n"
        f"{_read_asset('page.js')}</script>"
    )
    chunks.append(f"<script>{_read_asset('search/search-ui.js')}</script>")
    chunks.append('''<!-- Cloudflare Web Analytics --><script type='module' src='https://static.cloudflareinsights.com/beacon.min.js' data-cf-beacon='{"token": "542cbf4d24534b70be3715cefe0e6a8e"}'></script><!-- End Cloudflare Web Analytics -->''')
    chunks.append("</body></html>")
    return "\n".join(chunk for chunk in chunks if chunk)


HISTORY_FILE = "history.json"
_HISTORY_BLOCK = re.compile(r'\n?<script type="application/json" id="historyJson">(.*?)</script>', re.S)


def split_history(html):
    """``(page, history)``: the page without its inline price history, and that history as JSON text.

    ``history`` is None when the page has none. page.js reads #historyJson
    when it is inline (tests, local previews) and fetches history.json when
    it is not.
    """
    match = _HISTORY_BLOCK.search(html)
    if not match:
        return html, None
    history = match.group(1)
    page = html[: match.start()] + html[match.end():]
    # Start the download while the page is still parsing. The URL is the
    # one page.js fetches ("?v=" + encodeURIComponent(generated)), so the
    # fetch reuses this response.
    generated = str(json.loads(history).get("generated") or "")
    preload = (
        f'<link rel="preload" href="{HISTORY_FILE}?v={quote(generated, safe="")}" '
        'as="fetch" crossorigin="anonymous">'
    )
    page = page.replace("</head>", preload + "</head>", 1)
    return page, history + "\n"


def _replace_text(path, text):
    """Write ``text`` atomically. True when the file changed."""
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as handle:
            if handle.read() == text:
                return False
    temporary = f"{path}.tmp"
    with open(temporary, "w", encoding="utf-8") as handle:
        handle.write(text)
    os.replace(temporary, path)
    return True


def write_page(html, page_path, history_path=None):
    """Publish the page and its history.json next to it. True when either changed.

    History first, so a published page never asks for a history file that is
    not there yet.
    """
    page, history = split_history(html)
    folder = os.path.dirname(page_path)
    if folder:
        os.makedirs(folder, exist_ok=True)  # a sport's first page (bmx/)
    changed = False
    if history is not None:
        target = history_path or os.path.join(os.path.dirname(page_path) or ".", HISTORY_FILE)
        changed = _replace_text(target, history)
    return _replace_text(page_path, page) or changed


_SCRIPT_BREAK = re.compile(r"</script|<!--", re.IGNORECASE)


def _script_text(html):
    """HTML kept as raw text in a <script>: nothing in it may end or confuse the element."""
    return _SCRIPT_BREAK.sub(lambda match: "<\\" + match.group(0)[1:], html)


def _attr(value):
    return escape("" if value is None else str(value), quote=True)


def _shoe_offer_attrs(record):
    """Per-size sale prices, included only when those prices are not all the same."""
    sizes = record.get("shoe_sizes") or []
    item = record.get("item") or {}
    parts = []
    for key, attr in (("shoe_prices", "shoeprices"), ("shoe_compares", "shoecompares")):
        mapping = item.get(key) or {}
        encoded = []
        for size in sizes:
            raw = mapping.get(size)
            if raw in (None, ""):
                continue
            encoded.append(f"{size}:{raw}")
        if encoded:
            parts.append(f'data-{attr}="{_attr(",".join(encoded))}"')
    return " ".join(parts)


def _offer_gap(record):
    offers = _shoe_offer_attrs(record)
    return f" {offers}" if offers else ""


def _deal_attrs(record):
    item = record["item"]
    original = _price(item.get("price_old"))
    group_key = ""
    if record["group"]:
        group_key = record["group"].get("key") or ""
    return (
        f'data-id="{record["id"]}" data-url="{_attr(record["url"])}" '
        f'data-soldout="{1 if record.get("sold_out") else 0}" '
        f'data-store="{_attr(record["store"])}" data-part="{_attr(record["part"])}" '
        f'data-size="{_attr(record["width_key"])}" data-brand="{_attr(record["brand"])}" '
        f'data-name="{_attr(record["name"])}" data-search="{_attr(record["search"])}" '
        f'data-price="{_attr(_price(item.get("price_new")))}" '
        f'data-original="{_attr(original if original is not None else "")}" '
        f'data-discount="{_attr(round(record["percent"], 1) if record["percent"] is not None else "")}" '
        f'data-days="{record["days"]}" data-daysat="{record["at_days"]}" '
        f'data-score="{record["score"]["score"]}" data-rank="{record["rank"]}" '
        f'data-stage="{_attr(record.get("stage") or "")}" '
        f'data-length="{_attr(record["length_key"])}" data-wheelbase="{_attr(record["wheel_key"])}" '
        f'data-color="{_attr(record.get("color") or "")}" '
        f'data-diameters="{_attr(",".join(str(v) for v in (item.get("diameters_mm") or ([item["diameter_mm"]] if item.get("diameter_mm") else []))))}" '
        f'data-widths="{_attr(",".join(str(v) for v in (item.get("widths") or [])))}" '
        f'data-spec-offers="{_attr(json.dumps(item.get("spec_offers") or [], separators=(",", ":")))}" '
        f'data-diameter="{_attr(record.get("diameter") or "")}" '
        f'data-duros="{_attr(",".join(record.get("duros") or []))}" '
        f'data-shape="{_attr(record.get("shape") or "")}" '
        f'data-trucksize="{_attr(record.get("truck_size") or "")}" '
        f'data-truckheight="{_attr(record.get("truck_height") or "")}" '
        f'data-construction="{_attr(record.get("construction") or "")}" '
        f'data-abec="{_attr(record.get("abec") or "")}" '
        f'data-shoesize="{_attr(",".join(record.get("shoe_sizes") or []))}"{_offer_gap(record)} '
        f'data-prottype="{_attr(record.get("prot_type") or "")}" '
        f'data-protsize="{_attr(",".join(record.get("prot_sizes") or []))}" '
        f'data-added="{1 if record["added"] else 0}" data-drop="{1 if record["drop"] is not None else 0}" '
        f'data-lowest="{1 if record["lowest"] else 0}" data-hitlow="{1 if record["hit_low"] else 0}" '
        f'data-fresh="{1 if record.get("fresh") else 0}" data-back="{1 if record.get("back") else 0}" '
        f'data-hot="{1 if record.get("hot") else 0}" data-dropday="{_attr(record.get("drop_day") or "")}" '
        f'data-highlight="{1 if record.get("highlight") else 0}" '
        f'data-group="{_attr(group_key)}"'
    )


def _row_html(record):
    item = record["item"]
    percent = calculate_percent_off(item.get("price_new"), item.get("price_old"))
    discount = _discount_class(item.get("price_new"), item.get("price_old"))
    size_html = f'<span class="size-badge">{escape(record["width_key"])}</span>' if record["width_key"] else "—"
    drop_html = ""
    listed = " on-list" if record["listed"] else ""
    currency = item.get("currency")
    symbol = "€" if str(currency or "USD").upper() == "EUR" else "$"
    if record["drop"] is not None and record["drop_amount"]:
        prior_percent = record["drop"].get("percent_vs_prior")
        try:
            percent_text = f"{float(prior_percent):.1f}"
        except (TypeError, ValueError):
            percent_text = "0.0"
        drop_html = (
            f'<div class="delta">\u2212{symbol}{record["drop_amount"]:.2f} '
            f'(\u2212{percent_text}% vs prior sale)</div>'
        )
    band = score_band(record["score"]["score"])
    return (
        f'<tr class="deal-row{listed}" tabindex="0" {_deal_attrs(record)}>'
        f'<td>{_thumb(record["image"], record["name"])}</td>'
        '<td><button type="button" class="star" aria-pressed="false" aria-label="Watch this item">☆</button></td>'
        f'<td><span class="store-badge {_store_class(record["store"])}">{escape(record["store"])}</span></td>'
        f'<td>{escape(record["brand"])}</td>'
        f'<td><span class="part-badge">{escape(record["part"])}</span></td>'
        f"<td>{size_html}</td>"
        f'<td class="product-name">{_product_link(item)}'
        f'<div class="row-meta">{_badge_html(_shown_badges(record), record["listed"])}'
        f'{_low_mark(record)}{_stage_html(record.get("stage"))}{_sold_out_pill(record)}</div></td>'
        f'<td class="price-cell"><button type="button" class="price-btn" data-id="{record["id"]}">'
        f'<span class="price price-new">{_money(item.get("price_new"), currency)}</span></button>'
        f'{_spark_html(record)}{drop_html}</td>'
        f'<td class="price price-old">{_money(item.get("price_old"), currency) if item.get("price_old") else "N/A"}</td>'
        f'<td><span class="discount {discount}">{escape(percent)}</span></td>'
        f'<td class="days-cell">{_trend_html(record.get("trend"))}{escape(record["held"])}</td>'
        f'<td class="score-cell"><button type="button" class="score-btn score-{band}" aria-expanded="false" '
        f'aria-controls="why-{record["id"]}">'
        f'{record["score"]["score"]}'
        + ('<span class="hot">HOT</span>' if record["score"]["hot"] else "")
        + '</button><button type="button" class="info-dot score-info" aria-expanded="false" '
        f'aria-controls="why-{record["id"]}" aria-label="Score breakdown">i</button>'
        f'{_why_html(record)}</td></tr>'
    )


def _drop_badge(record):
    drop = record.get("drop")
    amount = record.get("drop_amount") or 0
    if not isinstance(drop, dict) or not amount:
        return ""
    symbol = "€" if str(record["item"].get("currency") or "USD").upper() == "EUR" else "$"
    try:
        percent = float(drop.get("percent_vs_prior"))
        text = f"\u2212{percent:.0f}%"
    except (TypeError, ValueError):
        text = f"\u2212{symbol}{amount:.2f}"
    title = f"\u2212{symbol}{amount:.2f} vs prior sale"
    return f'<span class="drop-badge" title="{escape(title, quote=True)}">{escape(text)}</span>'


def _shown_badges(record):
    return [badge for badge in (record.get("badges") or []) if badge.get("kind") != "lowest"]


def _low_mark(record):
    """Three labels from the existing low rules. Only a new low is loud.

    New low: the qualified all-time low was reached in this scan (``hit_low``).
    Verified low: the 3-observation, 7-day all-time-low rule, and it is not new.
    At lowest tracked price: the sale price equals the tracked low, but the
    listing does not yet meet that rule.
    """
    if record.get("hit_low"):
        return (
            '<span class="pill pill-newlow" '
            'title="Reached the lowest tracked price in this scan">New low</span>'
        )
    if record.get("lowest"):
        return (
            '<span class="quiet-low" '
            'title="Lowest price since tracking began: at least 3 observations spanning 7 days. '
            'This is not a price from before tracking.">Verified low</span>'
        )
    if record.get("at_tracked_low"):
        return (
            '<span class="quiet-low" '
            'title="Matches the lowest price tracked so far. '
            'It does not yet meet the 3-observation, 7-day rule, and says nothing about prices from before tracking.">'
            "At lowest tracked price</span>"
        )
    return ""


def _card_status(record):
    """Loud marks only for a recent change, a hot score, or a new low."""
    parts = []
    kinds = set()
    for badge in record.get("badges") or []:
        kind = badge.get("kind") or ""
        if kind not in {"new", "back", "drop"}:
            continue
        kinds.add(kind)
        parts.append(
            f'<span class="pill pill-{escape(kind)}">{escape(badge.get("label") or "")}</span>'
        )
    age = None
    try:
        end = datetime.date.fromisoformat(str(record.get("spark_end") or "")[:10])
        drop_day = datetime.date.fromisoformat(str(record.get("drop_day") or "")[:10])
        age = (end - drop_day).days
    except ValueError:
        age = None
    if age is not None and 0 <= age <= 3 and "drop" not in kinds:
        parts.append(
            '<span class="pill pill-drop" title="Tracked price dropped in the last 3 days">Price drop</span>'
        )
    if record.get("hot"):
        parts.append('<span class="pill pill-hot">HOT</span>')
    if record.get("listed"):
        parts.append('<span class="pill pill-list">Watchlist</span>')
    low = _low_mark(record)
    if low:
        parts.append(low)
    if not parts:
        stage = _stage_html(record.get("stage"))
        if stage:
            parts.append(stage)
    return "".join(parts)


def _sold_out_pill(record):
    if not record.get("sold_out"):
        return ""
    return ' <span class="pill pill-soldout" title="The store\'s product page says out of stock">Sold out</span>'


def _removed_feed(digest, products, price_history):
    """Previous-scrape listings that are not in the current catalog.

    These are the Disappeared chip. They are not live deals, so the grid
    shows them only while that chip is on.
    """
    current = set()
    for item in products or []:
        url = normalize_url((item or {}).get("url"))
        if url:
            current.add(url)
    feed = []
    seen = set()
    for pair in getattr(digest, "removed", None) or []:
        site = ""
        item = None
        if isinstance(pair, (list, tuple)) and len(pair) >= 2:
            site, item = pair[0], pair[1]
        elif isinstance(pair, dict):
            nested = pair.get("item")
            item = nested if isinstance(nested, dict) else pair
            site = str(pair.get("site") or "")
        if not isinstance(item, dict):
            continue
        url = normalize_url(item.get("url"))
        if not url or url in current or url in seen:
            continue
        seen.add(url)
        entry = _entry(price_history, url)
        name = _display_name(item) or _display_name(entry)
        if not name:
            continue
        part = item.get("part") or entry.get("part") or ""
        store = item.get("store") or entry.get("store") or ""
        if not store and isinstance(site, str) and "_" in str(site):
            store = str(site).split("_", 1)[0]
        specs = _specs_for(item, entry)
        width_key = dimension_key(specs.get("width")) if part == "Decks" else ""
        price = item.get("price_new")
        if _price(price) is None:
            prices = entry.get("prices") if isinstance(entry.get("prices"), dict) else {}
            if prices:
                price = prices[sorted(prices)[-1]]
        feed.append({
            "item": item,
            "url": url,
            "name": name,
            "store": store or "Unknown",
            "part": part,
            "brand": item.get("brand") or listing_brand(name, part),
            "width_key": width_key,
            "price": price,
            "price_old": item.get("price_old"),
            "currency": item.get("currency"),
            "last_seen": str(entry.get("last_seen") or "")[:10],
            "image": item.get("image") or entry.get("image") or "",
        })
    return feed


def _removed_attrs(row, row_id):
    price = _price(row.get("price"))
    old = _price(row.get("price_old"))
    percent = percent_off_value(row.get("price"), row.get("price_old"))
    search = " ".join(
        bit for bit in (row.get("name"), row.get("store"), row.get("part"), row.get("brand"), "No longer in sale feed")
        if bit
    )
    return (
        f'data-id="{row_id}" data-url="{_attr(row["url"])}" data-removed="1" '
        f'data-soldout="0" data-store="{_attr(row["store"])}" data-part="{_attr(row["part"])}" '
        f'data-size="{_attr(row["width_key"])}" data-brand="{_attr(row["brand"])}" '
        f'data-name="{_attr(row["name"])}" data-search="{_attr(search)}" '
        f'data-price="{_attr("" if price is None else price)}" '
        f'data-original="{_attr("" if old is None else old)}" '
        f'data-discount="{_attr("" if percent is None else round(percent, 1))}" '
        f'data-seen="{_attr(row.get("last_seen") or "")}" '
        'data-added="0" data-drop="0" data-lowest="0" data-hitlow="0" '
        'data-fresh="0" data-back="0" data-hot="0" data-score="" data-group=""'
    )


def _removed_row_html(row, row_id):
    seen = row.get("last_seen") or ""
    size = escape(row["width_key"]) if row.get("width_key") else "—"
    return (
        f'<tr class="deal-row filtered-out" tabindex="0" {_removed_attrs(row, row_id)}>'
        f'<td>{_thumb(row.get("image"), row["name"])}</td>'
        '<td><button type="button" class="star" aria-pressed="false" aria-label="Watch this item">☆</button></td>'
        f'<td><span class="store-badge {_store_class(row["store"])}">{escape(row["store"])}</span></td>'
        f'<td>{escape(row.get("brand") or "")}</td>'
        f'<td><span class="part-badge">{escape(row.get("part") or "")}</span></td>'
        f"<td>{size}</td>"
        f'<td class="product-name">{_product_link(row["item"])}'
        '<div class="row-meta"><span class="gone-note">No longer in sale feed</span></div></td>'
        f'<td class="price-cell"><span class="price price-new">{_money(row.get("price"), row.get("currency"))}</span></td>'
        f'<td class="price price-old">{_money(row.get("price_old"), row.get("currency")) if row.get("price_old") else "N/A"}</td>'
        "<td></td>"
        f"<td>{escape(seen)}</td>"
        "<td></td></tr>"
    )


def _card_store_link(url, name, store):
    """Stretched retailer link. Action buttons stay siblings, not inside it."""
    if not url:
        return ""
    label = name or "Product"
    if store:
        label = f"{label} at {store}"
    return (
        f'<a class="card-store-link" href="{escape(url, quote=True)}" target="_blank" rel="noopener">'
        f'<span class="sr-only">{escape(label)}</span></a>'
    )


def _card_quick_button(name):
    label = f"Quick view: {name}" if name else "Quick view"
    return (
        '<button type="button" class="card-quick" aria-expanded="false" '
        f'aria-label="{escape(label, quote=True)}">Quick view</button>'
    )


def _removed_card_html(row, row_id):
    seen = _month_day(row.get("last_seen") or "")
    store = row["store"]
    name = row["name"]
    meta = f"Last seen {seen} · {store}" if seen else f"Last seen · {store}"
    price = _money(row.get("price"), row.get("currency"))
    return (
        f'<article class="deal-card filtered-out" {_removed_attrs(row, row_id)}>'
        f'{_card_store_link(row["url"], name, store)}'
        '<button type="button" class="star" aria-pressed="false" aria-label="Watch this item">☆</button>'
        '<button type="button" class="card-alert">Alert me</button>'
        f'<div class="media">{_thumb(row.get("image"), name, large=True)}'
        f'<span class="store-mark">{escape(store)}</span>'
        f'{_card_quick_button(name)}</div>'
        f'<h3 class="product-name">{escape(name)}</h3>'
        '<p class="gone-note">No longer in sale feed</p>'
        f'<p class="card-prices"><span class="now-price">Last {price}</span></p>'
        f'<p class="card-meta">{escape(meta)}</p>'
        "</article>"
    )


def _card_price_stat(record, symbol):
    """Comparison next to the sale price.

    Two or more tracked days use their average. Fewer than that is not an
    average (a first day would print the sale price twice), so the store's
    list price is shown instead: "Was $27.95 · Now $2.50". The percent off
    stays the store's claimed discount versus that list price.
    """
    points = clip_daily_prices(record.get("prices"), 90, record.get("spark_end"))
    if len(points) >= 2:
        average = record.get("average")
        if average is None:
            return ""
        return (
            f'<span class="avg-price" data-symbol="{symbol}">'
            f"Average {symbol}{float(average):.2f}</span>"
            '<span class="price-sep" aria-hidden="true">/</span>'
        )
    list_price = _price((record.get("item") or {}).get("price_old"))
    if list_price is not None and list_price > 0:
        return (
            f'<span class="avg-price" data-symbol="{symbol}">'
            f"Was {symbol}{list_price:.2f}</span>"
            '<span class="price-sep" aria-hidden="true">\u00b7</span>'
        )
    if points:
        # Nothing honest to show yet. The slot stays so a wider chart window
        # can fill in an average once a second day is inside it.
        return (
            f'<span class="avg-price" data-symbol="{symbol}" hidden></span>'
            '<span class="price-sep" aria-hidden="true" hidden>/</span>'
        )
    return ""


def _card_html(record):
    item = record["item"]
    percent = calculate_percent_off(item.get("price_new"), item.get("price_old"))
    discount = _discount_class(item.get("price_new"), item.get("price_old"))
    listed = " on-list" if record["listed"] else ""
    if record.get("sold_out"):
        listed += " sold-out"
    currency = item.get("currency")
    symbol = "€" if str(currency or "USD").upper() == "EUR" else "$"
    # The percent is the store's own markdown versus its list price.
    if percent == "N/A":
        off_html = (
            '<span class="discount card-off none" '
            'title="This store did not publish a list price, so there is no claimed discount.">'
            "No list price</span>"
        )
    else:
        off_html = (
            f'<span class="discount card-off {discount} card-drop" '
            'title="Store\'s claimed discount versus its list price, not a tracked market price.">'
            f"↓ {escape(percent)}</span>"
        )
    avg_html = _card_price_stat(record, symbol)
    found = _month_day(record.get("first") or record.get("spark_end") or "")
    store = record.get("store") or ""
    name = record["name"]
    meta = f"Found {found} · {store}" if found else store
    return (
        f'<article class="deal-card{listed}" {_deal_attrs(record)}>'
        f'{_card_store_link(record["url"], name, store)}'
        '<button type="button" class="star" aria-pressed="false" aria-label="Watch this item">☆</button>'
        '<button type="button" class="card-alert">Alert me</button>'
        f'<div class="media">{_thumb(record["image"], name, large=True)}'
        f'<span class="store-mark">{escape(store)}</span>'
        f'{_card_quick_button(name)}</div>'
        f'<h3 class="product-name">{escape(name)}</h3>'
        f'<div class="card-sparkline">{_spark_html(record, width=156, defer=True)}</div>'
        f'<p class="card-offer">{off_html}{_sold_out_pill(record)}</p>'
        '<p class="card-prices">'
        f'{avg_html}<span class="now-price">Now {_money(item.get("price_new"), currency)}</span></p>'
        f'<p class="card-meta">{escape(meta)}</p>'
        f'<div class="card-score" hidden>{_why_html(record, dom_id="why-card-" + str(record["id"]))}</div>'
        "</article>"
    )


def _spec_box(label, value):
    shown = dimension_key(value) if value not in (None, "") else ""
    if shown:
        shown = f'{shown}"'
    else:
        shown = "—"
    return f"<div><span>{escape(label)}</span>{escape(shown)}</div>"


def _detail_html(record):
    item = record["item"]
    specs = record["specs"]
    symbol = "€" if str(item.get("currency") or "USD").upper() == "EUR" else "$"
    chain = " → ".join(f"{symbol}{price:.2f}" for _day, price in record["chain"]) or "No price history yet."
    offers = []
    group = record["group"]
    if group:
        cheapest = group.get("cheapest_price")
        for offer in group.get("offers") or []:
            price = offer.get("price")
            cheap = price is not None and cheapest is not None and abs(float(price) - float(cheapest)) < 0.001
            klass = "mini-offer g-cheap" if cheap else "mini-offer"
            url = offer.get("url") or ""
            label = f'{escape(offer.get("store") or "")} {_money(price, offer.get("currency"))}'
            if url:
                inner = f'<a href="{escape(url, quote=True)}" target="_blank" rel="noopener">{label}</a>'
            else:
                inner = label
            offers.append(f'<div class="{klass}">{inner}</div>')
    else:
        offers.append('<div class="mini-offer">No other tracked store has this exact product.</div>')
    url = record["url"]
    retailer = ""
    if url:
        retailer = (
            f'<p><a class="product-link" href="{escape(url, quote=True)}" target="_blank" rel="noopener">'
            f'View at {escape(record["store"])}</a></p>'
        )
    return (
        f'<tr class="detail-row" data-for="{record["id"]}" hidden><td colspan="12">'
        '<div class="detail-panel">'
        f'{_thumb(record["image"], record["name"], large=True)}'
        "<div>"
        f'<strong>{escape(record["name"])}</strong>'
        f'<div class="specs">{_spec_box("Width", specs.get("width"))}'
        f'{_spec_box("Length", specs.get("length"))}'
        f'{_spec_box("Wheelbase", specs.get("wheelbase"))}'
        f'<div><span>First seen</span>{escape(record["first"] or "—")}</div>'
        f'<div><span>Last seen</span>{escape(record["last"] or "—")}</div>'
        f'<div><span>Days tracked</span>{escape(record["held"])}</div>'
        f'<div><span>Stage</span>{escape(STAGE_LABEL.get(record.get("stage"), ""))}</div></div>'
        f"{retailer}"
        f'<div class="chart-box">{sparkline_svg(record["prices"], width=280, height=64, days=90, end=record.get("spark_end"))}'
        f'<p class="chain">{escape(chain)}</p></div>'
        f'<div class="offers">{"".join(offers)}</div>'
        "</div></div></td></tr>"
    )


def _offer_link(offer):
    price = _money(offer.get("price"), offer.get("currency"))
    store = escape(offer.get("store") or "")
    label = f"{store} {price}"
    url = offer.get("url") or ""
    if not url:
        return label
    return f'<a href="{escape(url, quote=True)}" target="_blank" rel="noopener">{label}</a>'


def _member_line(record):
    item = record["item"]
    avail = escape(record.get("availability") or "On sale")
    price = _money(item.get("price_new"), item.get("currency"))
    store = escape(record["store"])
    label = f"{store} {price} · {avail}"
    url = record["url"]
    if not url:
        return label
    return f'<a href="{escape(url, quote=True)}" target="_blank" rel="noopener">{label}</a>'


def _group_board(records):
    cards = {}
    members = {}
    order = []
    for record in records:
        group = record["group"]
        if not group:
            continue
        key = group.get("key") or ""
        if key not in cards:
            cards[key] = group
            members[key] = []
            order.append(key)
        members[key].append(record)
    blocks = ['<div class="group-board" id="groupBoard" hidden>']
    if not order:
        blocks.append(
            '<p class="group-empty lede">No products are at more than one store under the conservative match. '
            "Rows stay separate.</p></div>"
        )
        return "\n".join(blocks)
    for key in order:
        group = cards[key]
        rows = sorted(
            members.get(key) or [],
            key=lambda record: (
                _price(record["item"].get("price_new")) if _price(record["item"].get("price_new")) is not None else 10**9,
                record["store"],
            ),
        )
        if not rows:
            continue
        best = rows[0]
        rest = rows[1:]
        count = len(rows)
        store_word = "store" if count == 1 else "stores"
        summary = (
            f'{escape(group.get("label") or "Product")} - from {_money(best["item"].get("price_new"))} - '
            f"{count} {store_word}"
        )
        others = "".join(
            f'<li class="offer-line">{_member_line(record)}</li>' for record in rest
        )
        blocks.append(
            f'<article class="group-card" data-key="{escape(key, quote=True)}">'
            f'<button type="button" class="group-summary" aria-expanded="false">{summary}</button>'
            '<div class="group-detail" hidden>'
            f'<p class="best">Best price: {_member_line(best)}</p>'
            f"<ul>{others}</ul>"
            f'<button type="button" class="text-btn group-chart" data-id="{escape(best["id"], quote=True)}">'
            "Price history</button></div></article>"
        )
    blocks.append("</div>")
    return "\n".join(blocks)


def _stage_html(stage):
    label = STAGE_LABEL.get(stage or "")
    if not label:
        return ""
    return f'<span class="stage stage-{escape(stage or "")}">{escape(label)}</span>'


def _why_html(record, dom_id=None):
    score = record["score"]
    parts = score.get("parts") or {}
    specific = {"discount": "", "lowest": "", "drop": "", "size": ""}
    notes = []
    for factor in score.get("breakdown") or []:
        label = factor.get("label") or ""
        if not label:
            continue
        if factor.get("points"):
            lowered = label.lower()
            if label.endswith("% off"):
                specific["discount"] = label
            elif "lowest" in lowered:
                specific["lowest"] = label
            elif "reduced" in lowered:
                specific["drop"] = label
            elif label == "Popular size":
                specific["size"] = label
        else:
            notes.append(label)

    def hint(title, key, generic):
        chosen = specific.get(key) or ""
        if chosen and chosen.casefold() != title.casefold():
            return chosen
        return generic

    factors = (
        ("Discount", parts.get("discount") or 0, hint("Discount", "discount", "Percent off, max 50")),
        (
            "Historical low",
            parts.get("lowest") or 0,
            hint(
                "Historical low",
                "lowest",
                "Points from the lowest price since tracking began. Not a price from before tracking.",
            ),
        ),
        ("Recent drop", parts.get("drop") or 0, hint("Recent drop", "drop", "Up to 15, or 4 for a smaller dip")),
        ("Popular size", parts.get("size") or 0, hint("Popular size", "size", "10 when the deck is 8.25–8.75")),
    )
    rows = []
    for label, points, detail in factors:
        rows.append(
            f'<li><span>{escape(label)} <em>{escape(detail)}</em></span><b>+{int(points)}</b></li>'
        )
    for label in notes:
        rows.append(f'<li class="why-note"><span>{escape(label)}</span><b>not scored</b></li>')
    return (
        f'<div class="why" id="{escape(dom_id or "why-" + str(record["id"]), quote=True)}" role="tooltip">'
        f'<strong>Why {score["score"]}?</strong><ul>{"".join(rows)}</ul>'
        "<p class=\"why-legend\">Discount, historical low, recent drop, and popular size are the whole score. "
        "Historical low uses only prices tracked here. Days tracked are not added. 70 or above is hot.</p></div>"
    )


def _category_strip(part_counts):
    order = ["Decks", "Trucks", "Wheels", "Bearings", "Sneakers", "Accessories", "Completes", "Protection"]
    names = [name for name in order if part_counts.get(name)]
    for name in part_counts:
        if name and name not in names:
            names.append(name)
    if not names:
        return ""
    buttons = [
        '<button type="button" data-part="all" aria-pressed="false">All '
        f'<span class="cat-count">{sum(part_counts.values())}</span></button>'
    ]
    for name in names:
        pressed = "true" if name == "Decks" else "false"
        buttons.append(
            f'<button type="button" data-part="{escape(name, quote=True)}" aria-pressed="{pressed}">'
            f'{escape(name)} <span class="cat-count">{part_counts.get(name, 0)}</span></button>'
        )
    return (
        '<div class="category-strip" id="categoryStrip" role="group" aria-label="Category">'
        + "".join(buttons)
        + "</div>"
    )


def _dual_html(min_id, max_id, floor, ceil, prefix, any_label, min_label, max_label, suffix=""):
    return (
        f'<div class="dual" data-min-input="{min_id}" data-max-input="{max_id}" '
        f'data-floor="{floor}" data-ceil="{ceil}" data-prefix="{escape(prefix, quote=True)}" '
        f'data-suffix="{escape(suffix, quote=True)}" data-any="{escape(any_label, quote=True)}">'
        f'<input type="range" class="dual-min" min="{floor}" max="{ceil}" step="1" value="{floor}" '
        f'aria-label="{escape(min_label, quote=True)}" aria-valuemin="{floor}" aria-valuemax="{ceil}">'
        f'<input type="range" class="dual-max" min="{floor}" max="{ceil}" step="1" value="{ceil}" '
        f'aria-label="{escape(max_label, quote=True)}" aria-valuemin="{floor}" aria-valuemax="{ceil}">'
        f'<span class="dual-readout">{escape(any_label)}</span></div>'
    )


def _spark_html(record, width=72, height=22, stroke=1.6, defer=False):
    card = " spark-card" if width > 80 else ""
    # Card charts are drawn when the card scrolls into view. The button is
    # reserved here so the card does not jump when the line appears.
    if defer:
        return (
            f'<button type="button" class="spark-hit{card}" data-id="{record["id"]}" '
            'aria-label="Price history"></button>'
        )
    radius = 2.2
    if width > 80:
        direction = sparkline_direction(record["prices"], days=90, end=record.get("spark_end"))
        if direction == "flat":
            height, stroke, radius = 12, 1.5, 1.5
        else:
            height, stroke, radius = 30, 2, 2.2
    spark = sparkline_svg(
        record["prices"],
        width=width,
        height=height,
        days=90,
        end=record.get("spark_end"),
        stroke=stroke,
        radius=radius,
        steps=width > 80,
    )
    if not spark:
        return ""
    return (
        f'<button type="button" class="spark-hit{card}" data-id="{record["id"]}" '
        'aria-label="Price history">'
        f"{spark}</button>"
    )


def _activity_html(sales, generated_at):
    if not sales:
        return ""
    banners = []
    for row in sales:
        if not row.get("detected_today") or row.get("extra_percent") is None:
            continue
        try:
            percent = int(row["extra_percent"])
        except (TypeError, ValueError):
            continue
        prefix = (
            f"🔥 {display_name(row.get('store'))} - site-wide sale detected "
            f"({percent}% more items on sale)"
        )
        banners.append(
            f'<p class="sale-banner" data-at="{escape(str(generated_at), quote=True)}">'
            f"{escape(prefix)} <span class=\"ago\">under an hour ago</span></p>"
        )
    items = "".join(f"<li>{escape(activity_line(row))}</li>" for row in sales)
    return (
        '<section class="activity" id="retailerActivity">'
        "<h2>Retailer activity</h2>"
        + "".join(banners)
        + f'<ul class="activity-list">{items}</ul></section>'
    )


def _gone_section(history, current_data, today, failed_keys):
    rows = recently_gone(history, current_data, today=today, skip_keys=failed_keys)
    body = []
    for row in rows:
        store = row.get("store") or "Unknown"
        part = row.get("part") or ""
        name = row.get("name") or ""
        brand = listing_brand(name, part)
        stage = STAGE_LABEL.get(row.get("stage") or "", "")
        search = " ".join(bit for bit in (name, store, part, brand, stage) if bit)
        body.append(
            "<tr "
            + _data_attrs((
                ("store", store),
                ("part", part),
                ("brand", brand),
                ("name", name),
                ("price", _price_attr(row.get("price"))),
                ("seen", row.get("last_seen") or ""),
                ("stage", stage),
                ("search", search),
            ))
            + ">"
            f'<td><span class="store-badge {_store_class(store)}">{escape(store)}</span></td>'
            f'<td><span class="part-badge">{escape(part)}</span></td>'
            f'<td class="product-name">{_product_link(row)}</td>'
            f'<td class="price">{_money(row.get("price"))}</td>'
            f'<td>{escape(row.get("last_seen") or "")}</td>'
            f'<td>{_stage_html(row.get("stage"))}</td>'
            "</tr>"
        )
    note = (
        "Kept for 7 days after a listing is missing from two successful scans in a row, "
        "with the last price and the last day it was seen. "
        "Sold out means the product page says out of stock. Otherwise the listing is no longer on the sale page. "
        "Column headers sort this table. Search, price, store, type, and brand use the same choices as All Deals."
    )
    if not rows:
        note = "Nothing has disappeared in the last 7 days. " + note
    return (
        '<div class="section gone-section" id="goneSection">'
        '<div class="section-header collapsed" onclick="toggleSection(this)">'
        f'<h2>Recently gone <span class="badge">{len(rows)}</span></h2>'
        '<span class="toggle-icon">▼</span></div>'
        '<div class="section-content collapsed">'
        f'<p class="lede">{escape(note)}</p>'
        '<div id="goneEmpty" class="empty-state" hidden></div>'
        '<table id="goneTable"><thead><tr>'
        + _sort_headers("goneTable", (
            ("Store", "store"),
            ("Part", "part"),
            ("Product", "name"),
            ("Last price", "price"),
            ("Last seen", "seen"),
            ("Stage", "stage"),
        ))
        + f"</tr></thead><tbody>{''.join(body)}</tbody></table></div></div>"
    )
