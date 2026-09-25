"""Shared sale filters for every store parser and for compare/report.

Keep rules here so a store-specific scraper cannot quietly reintroduce
cruiser, apparel, or off-brand noise into the HTML report.
"""

import re
import unicodedata

# Wheels: case-insensitive, word boundaries (so "OJ" does not match inside
# another token, and "Powell" still matches "Powell-Peralta").
WHEEL_BRANDS = ("Bones", "Powell", "Spitfire", "OJ")

# Trucks. "Ace" and "Indy" are matched as whole words so "Space" / "Face"
# and the interior of "Independent" do not false-hit.
TRUCK_BRANDS = ("Independent", "Indy", "Ace", "Thunder", "Venture", "Slappy")

# Bearings. Anything else (SKF, Modus, unbranded ABEC packs) is rejected.
BEARING_BRANDS = (
    "Bones",
    "Bones Swiss",
    "Bronson",
    "CeramicSpeed",
    "Ceramic Speed",
    "Independent",
    "Zealous",
    "Andale",
    "Pixel",
)

# Known street-deck brands get a lower discount floor (≥10%).
# Unknown brands must be ≥15% off. Matching is case-insensitive with
# word boundaries; "Real", "Girl", "Flip", and "Element" are included
# because they are deck brands, not because those English words are special.
DECK_BRANDS = (
    "Baker",
    "Deathwish",
    "Death Wish",
    "Creature",
    "Anti-Hero",
    "Anti Hero",
    "Antihero",
    "Girl",
    "Chocolate",
    "Real",
    "Element",
    "Habitat",
    "Welcome",
    "Birdhouse",
    "Flip",
    "Almost",
    "Plan B",
    "Santa Cruz",
    "Powell",
    "Blind",
    "Enjoi",
    "DGK",
    "Primitive",
    "Zero",
    "Toy Machine",
    "Krooked",
    "Polar",
    "Heroin",
    "Madness",
    "Foundation",
    "Hockey",
    "Black Label",
    "Alien Workshop",
    "World Industries",
    "Shorty's",
    "Shortys",
    "Quasi",
    "Palace",
    "Opera",
    "Jacuzzi",
    "Fucking Awesome",
    "Sci-Fi Fantasy",
    "Sci Fi Fantasy",
    "Snack",
    "Blood Wizard",
    "Doom Sayers",
    "Fancy Lad",
    "Mini Logo",
)

# Whole-word apparel / soft goods. "dress" must not match "Dressen",
# and "short" must not match "Shorty's".
APPAREL_PATTERNS = (
    r"\bhats?\b",
    r"\bcaps?\b",
    r"\bshirts?\b",
    r"\btees?\b",
    r"\bt-?shirts?\b",
    r"\bhoodies?\b",
    r"\bjackets?\b",
    r"\bpants?\b",
    r"\bshorts?\b(?!['’])",
    r"\bshoes?\b",
    r"\bsneakers?\b",
    r"\bsocks?\b",
    r"\bbackpacks?\b",
    r"\bbags?\b",
    r"\bbeanies?\b",
    r"\bgloves?\b",
    r"\bdress(?:es)?\b",
)

KNOWN_DECK_MIN_PERCENT = 10.0
UNKNOWN_DECK_MIN_PERCENT = 15.0

# Street deck widths we keep. "Roughly 7.5–9.0": minis under 7.5" are out,
# and widths above 9.5" are treated as old-school / cruiser widths.
# 10.x must parse correctly so those listings are excluded rather than
# slipping through with no size.
MIN_DECK_WIDTH = 7.5
MAX_DECK_WIDTH = 9.5

# A "W x L" length at or above this is a longboard, not a street deck.
# Common street lengths in the catalog are about 31–32.5".
MAX_STREET_LENGTH = 34.0

# A single dimension this large is a board length (Loaded 30.75"), not a width.
LONE_LENGTH_THRESHOLD = 15.0

# Meaningful sale-price drop versus the previous tracked sale price.
MIN_DROP_DOLLARS = 2.0
MIN_DROP_PERCENT = 5.0

_PREFIX_WORDS = re.compile(r"^(?:(?:clearance|sale)\s+)+", re.IGNORECASE)
_PREFIX_PERCENT = re.compile(r"^-?\s*\d{1,3}%\s*", re.IGNORECASE)
_WIDTH_BY_LENGTH = re.compile(
    r"\b(\d{1,2}(?:\.\d+)?)\s*x\s*(\d{1,2}(?:\.\d+)?)\b",
    re.IGNORECASE,
)
_INCH_MARKED = re.compile(
    r"\b(\d{1,2}(?:\.\d+)?)\s*[\"\u201d\u2033]"
)
_DECIMAL_INCH = re.compile(r"\b(\d{1,2}\.\d+)\b")


def _fold(text):
    """Casefold and strip accents so Andalé and Andale match the same brand."""
    if not text:
        return ""
    decomposed = unicodedata.normalize("NFKD", str(text))
    without_marks = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return without_marks.casefold()


def _phrase_pattern(phrase):
    parts = [re.escape(part) for part in re.split(r"[\s\-]+", phrase.strip()) if part]
    body = r"[\s\-]*".join(parts)
    return re.compile(rf"\b{body}\b", re.IGNORECASE)


_WHEEL_RES = tuple(_phrase_pattern(brand) for brand in WHEEL_BRANDS)
_TRUCK_RES = tuple(_phrase_pattern(brand) for brand in TRUCK_BRANDS)
_BEARING_RES = tuple(_phrase_pattern(brand) for brand in BEARING_BRANDS)
_DECK_RES = tuple(_phrase_pattern(brand) for brand in DECK_BRANDS)
_APPAREL_RES = tuple(re.compile(pattern, re.IGNORECASE) for pattern in APPAREL_PATTERNS)

_CRUISER_RE = re.compile(r"\bcruisers?\b", re.IGNORECASE)
_LONGBOARD_RE = re.compile(r"\blongboards?\b", re.IGNORECASE)
_MINI_DECK_RE = re.compile(r"\bmini[\s\-]*decks?\b", re.IGNORECASE)
_PENNY_BOARD_RE = re.compile(
    r"\bpenny(?:\s+(?:boards?|skateboards?|cruisers?|nickels?))?\b",
    re.IGNORECASE,
)
_COMPLETE_RE = re.compile(r"\bcompletes?\b", re.IGNORECASE)
_DECK_WORD_RE = re.compile(r"\bdecks?\b", re.IGNORECASE)
_FULL_COMPLETE_RE = re.compile(
    r"\bcomplete\s+skateboards?\b|\bskateboards?\s+complete\b|\bcompletes?\b",
    re.IGNORECASE,
)


def normalize_product_name(name):
    """Strip Skate Warehouse clearance prefixes glued onto the product name.

    Examples:
    ``Clearance\\xa0-10%April ...`` → ``April ...``
    ``Sale\\xa0-24%Madness ...`` → ``Madness ...``
    """
    if not name:
        return ""
    text = str(name).replace("\xa0", " ").replace("\u200b", "")
    text = re.sub(r"\s+", " ", text).strip()
    while True:
        updated = _PREFIX_WORDS.sub("", text).strip()
        updated = _PREFIX_PERCENT.sub("", updated).strip()
        if updated == text:
            return text
        text = updated


def normalize_url(url):
    return re.sub(r"\s+", "", str(url or "")).strip()


def _matches_any(text, patterns):
    folded = _fold(text)
    return any(pattern.search(folded) for pattern in patterns)


def is_known_deck_brand(name):
    return _matches_any(normalize_product_name(name), _DECK_RES)


def percent_off_value(price_new, price_old):
    try:
        new = float(price_new)
        old = float(price_old)
    except (TypeError, ValueError):
        return None
    if old <= 0:
        return None
    return ((old - new) / old) * 100


def calculate_percent_off(price_new, price_old):
    percent = percent_off_value(price_new, price_old)
    if percent is None:
        return "N/A"
    return f"{percent:.0f}%"


def is_meaningful_drop(old_price, new_price):
    """True when the sale price fell by ≥$2 or ≥5% versus the prior sale price."""
    try:
        old = float(old_price)
        new = float(new_price)
    except (TypeError, ValueError):
        return False
    if old <= 0 or new >= old:
        return False
    delta = old - new
    percent = (delta / old) * 100
    return delta >= MIN_DROP_DOLLARS or percent >= MIN_DROP_PERCENT


def extract_deck_dimensions(name):
    """Return ``(width, length)`` in inches.

    Width is the first dimension of ``W x L``, an inch-marked number, or a
    decimal that looks like a width. A lone value ≥ 15 (``30.75``) is returned
    as a length so longboard listings are not treated as missing a size.
    Two-digit widths such as ``10.25`` are included.
    """
    text = normalize_product_name(name)
    if not text:
        return None, None

    pair = _WIDTH_BY_LENGTH.search(text)
    if pair:
        return float(pair.group(1)), float(pair.group(2))

    marked = [float(value) for value in _INCH_MARKED.findall(text)]
    decimals = [float(value) for value in _DECIMAL_INCH.findall(text)]
    candidates = marked or decimals
    if not candidates:
        return None, None

    widths = [value for value in candidates if value < LONE_LENGTH_THRESHOLD]
    lengths = [value for value in candidates if value >= LONE_LENGTH_THRESHOLD]
    width = widths[0] if widths else None
    length = lengths[0] if lengths else None
    return width, length


def extract_deck_size(name):
    """Deck width string for the report, or None when it is not a width."""
    width, _length = extract_deck_dimensions(name)
    if width is None:
        return None
    if width < 6 or width > 12:
        return None
    return f"{width:.2f}".rstrip("0").rstrip(".")


def _as_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _is_penny_board(text, name):
    if not _PENNY_BOARD_RE.search(text):
        return False
    # "Flip Penny" / "Tom Penny" pro models are street decks, not Penny boards.
    if is_known_deck_brand(name) and not re.search(
        r"\bpenny\s+(?:boards?|skateboards?|cruisers?|nickels?)\b",
        text,
        re.IGNORECASE,
    ):
        return False
    return True


def _is_complete_board(name, url):
    text = f"{name} {url}"
    if not _COMPLETE_RE.search(text):
        return False
    # A listing that is clearly the deck only (the word "deck", and not a
    # complete-skateboard setup) stays in.
    if _DECK_WORD_RE.search(name) and not re.search(
        r"\bcomplete\s+skateboards?\b|\bskateboards?\s+completes?\b",
        text,
        re.IGNORECASE,
    ):
        return False
    if _FULL_COMPLETE_RE.search(url) and not _DECK_WORD_RE.search(name):
        return True
    return True


def _deck_size_reason(name):
    width, length = extract_deck_dimensions(name)
    if length is not None and length >= MAX_STREET_LENGTH:
        return f"longboard length {length:g}\""
    if width is None and length is not None and length >= LONE_LENGTH_THRESHOLD:
        return f"longboard length {length:g}\""
    if width is None:
        return None
    if width < MIN_DECK_WIDTH:
        return f"mini width {width:g}\" (< {MIN_DECK_WIDTH:g}\")"
    if width > MAX_DECK_WIDTH:
        return f"width {width:g}\" above {MAX_DECK_WIDTH:g}\""
    return None


def _deck_discount_reason(name, price_new, price_old):
    percent = percent_off_value(price_new, price_old)
    if percent is None:
        return "deck discount unknown"
    if is_known_deck_brand(name):
        if percent < KNOWN_DECK_MIN_PERCENT:
            return f"known-brand deck {percent:.0f}% off (< {KNOWN_DECK_MIN_PERCENT:.0f}%)"
        return None
    if percent < UNKNOWN_DECK_MIN_PERCENT:
        return f"unknown-brand deck {percent:.0f}% off (< {UNKNOWN_DECK_MIN_PERCENT:.0f}%)"
    return None


def filter_reason(name, part, url="", price_new=None, price_old=None):
    """Return None if the listing should be kept, else a short reason."""
    name = normalize_product_name(name)
    url = normalize_url(url)
    if not name:
        return "missing name"

    text = f"{name} {url}"
    part_key = (part or "").strip().casefold()

    if _matches_any(text, _APPAREL_RES):
        return "apparel"

    if _CRUISER_RE.search(text):
        return "cruiser"
    if _LONGBOARD_RE.search(text):
        return "longboard"
    if _MINI_DECK_RE.search(text):
        return "mini deck"
    if _is_penny_board(text, name):
        return "penny board"
    if part_key == "decks" and _is_complete_board(name, url):
        return "complete"

    if part_key == "wheels":
        if not _matches_any(name, _WHEEL_RES):
            return "wheel brand not allowed"
        return None

    if part_key == "trucks":
        if not _matches_any(name, _TRUCK_RES):
            return "truck brand not allowed"
        return None

    if part_key == "bearings":
        if not _matches_any(name, _BEARING_RES):
            return "bearing brand not allowed"
        return None

    if part_key == "decks":
        size_reason = _deck_size_reason(name)
        if size_reason:
            return size_reason
        return _deck_discount_reason(name, price_new, price_old)

    return "unknown part"


def passes_filters(name, part, url="", price_new=None, price_old=None):
    """True when this listing belongs in the catalog and the report."""
    return filter_reason(name, part, url, price_new, price_old) is None


def item_passes_filters(item):
    if not item:
        return False
    return passes_filters(
        item.get("name", ""),
        item.get("part", ""),
        item.get("url", ""),
        item.get("price_new"),
        item.get("price_old"),
    )
