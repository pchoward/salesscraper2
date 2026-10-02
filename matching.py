"""Conservative cross-store product matching.

A group is the same part, the same brand, the same size, and the same
distinctive model words. Widths within about 0.015\" of a standard eighth
snap together (8.12 and 8.125, 8.38 and 8.375). Other widths snap to the
nearest 0.025\" so 8.475 does not collapse into 8.5.

Generic words (team, logo, formula, four, colors) do not create a match by
themselves, and they still keep two colorways apart when a real model word
is present. Tokens have to be equal, not merely overlapping, so a longer
name does not attach to a shorter one. Items that are missing a required
size (deck width, wheel diameter, truck hanger or axle) are not matched.
Only groups that show up in two or more stores are returned.
"""

import re

from filters import (
    BEARING_BRANDS,
    DECK_BRANDS,
    TRUCK_BRANDS,
    WHEEL_BRANDS,
    _fold,
    _phrase_pattern,
    extract_deck_dimensions,
    find_brand,
    item_passes_filters,
    normalize_product_name,
)

PART_ORDER = ("Decks", "Wheels", "Trucks", "Bearings")
STORE_ORDER = ("Zumiez", "SkateWarehouse", "CCS", "Tactics", "Skate Deluxe", "Muir Skate")

# Words that describe a line, a color, or a category. They are kept when a
# real model word is present (so colorways stay apart) but a key made only
# of these words is rejected.
WEAK_TOKENS = frozenset(
    {
        "formula",
        "four",
        "team",
        "logo",
        "logos",
        "pro",
        "model",
        "models",
        "series",
        "classic",
        "og",
        "new",
        "full",
        "original",
        "complete",
        "skate",
        "skateboard",
        "skateboards",
        "deck",
        "decks",
        "wheel",
        "wheels",
        "truck",
        "trucks",
        "bearing",
        "bearings",
        "sale",
        "clearance",
        "the",
        "and",
        "with",
        "for",
        "set",
        "pack",
        "pair",
        "inch",
        "inches",
        "size",
        "mm",
        "shape",
        "elite",
        "elites",
        "white",
        "black",
        "silver",
        "gold",
        "red",
        "blue",
        "green",
        "yellow",
        "orange",
        "pink",
        "purple",
        "brown",
        "grey",
        "gray",
        "natural",
        "clear",
        "polished",
        "raw",
        "chrome",
        "foil",
        "multi",
        "assorted",
    }
)

_MM_RE = re.compile(r"\b(\d{2})\s*mm\b", re.IGNORECASE)
_DURO_RE = re.compile(r"\b(\d{2,3})\s*([abd])\b", re.IGNORECASE)
_PAIR_RE = re.compile(r"\b\d+(?:\.\d+)?\s*x\s*\d+(?:\.\d+)?\b", re.IGNORECASE)
_HANGER_RE = re.compile(
    r"\b(22|33|44|55|66|109|129|136|139|144|145|147|148|149|151|159|169|215)\b"
)
_AXLE_RE = re.compile(r"\b(\d{1,2}\.\d+)\b")
_STAGE_RE = re.compile(r"\bstage[\s\-]*(\d{1,2})\b", re.IGNORECASE)
_AF1_RE = re.compile(r"\baf[\s\-]*1\b", re.IGNORECASE)


def canonical_width(width):
    """Snap a deck width to a stable bucket. See the module docstring."""
    width = float(width)
    eighth = round(width * 8) / 8
    if abs(width - eighth) <= 0.015:
        return round(eighth + 0.0, 3)
    thousandths = int(round(width * 1000))
    snapped = int(round(thousandths / 25.0)) * 25
    return snapped / 1000.0


def _fmt_width(width):
    text = f"{width:.3f}".rstrip("0").rstrip(".")
    return f'{text}"'


def _price(value):
    try:
        return round(float(value), 2)
    except (TypeError, ValueError):
        return None


def _prepare_text(name):
    text = normalize_product_name(name)
    text = _STAGE_RE.sub(r"stage\1", text)
    text = _AF1_RE.sub("af1", text)
    return text


def _token_is_specific(token):
    if token in WEAK_TOKENS:
        return False
    if len(token) >= 3:
        return True
    # Short model codes such as G3 or V5. Plain two-letter words are not enough.
    return len(token) >= 2 and any(character.isdigit() for character in token)


def _specific(tokens):
    return any(_token_is_specific(token) for token in tokens)


def _model_tokens(text):
    """Return ``(display_words, folded_key_tuple)``."""
    display = []
    folded = []
    seen = set()
    for raw in re.findall(r"[A-Za-z0-9]+", text):
        token = _fold(raw)
        if len(token) < 2:
            continue
        if token in WEAK_TOKENS and token in {
            "deck",
            "decks",
            "wheel",
            "wheels",
            "truck",
            "trucks",
            "bearing",
            "bearings",
            "skate",
            "skateboard",
            "skateboards",
            "sale",
            "clearance",
            "the",
            "and",
            "with",
            "for",
            "mm",
            "inch",
            "inches",
            "size",
        }:
            continue
        if re.fullmatch(r"\d+", token) or re.fullmatch(r"\d+\.\d+", token):
            continue
        if re.fullmatch(r"\d{2,3}[abd]", token) or re.fullmatch(r"\d+mm", token):
            continue
        if token in seen:
            continue
        seen.add(token)
        display.append(raw)
        folded.append(token)
    return display, tuple(sorted(folded))


def _strip_brand(text, brand):
    if not brand:
        return text
    return _phrase_pattern(brand).sub(" ", text, count=1)


def _wheel_size(text):
    millimeters = sorted(set(_MM_RE.findall(text)))
    if len(millimeters) != 1:
        return None
    duros = [f"{number}{letter.lower()}" for number, letter in _DURO_RE.findall(text)]
    duro = "+".join(sorted(set(duros)))
    return millimeters[0], duro


def _truck_size(text):
    hangers = []
    for match in _HANGER_RE.findall(text):
        if match not in hangers:
            hangers.append(match)
    if len(hangers) > 1:
        return None
    if len(hangers) == 1:
        return hangers[0]
    axles = []
    for raw in _AXLE_RE.findall(text):
        try:
            value = float(raw)
        except ValueError:
            continue
        if 4.5 <= value <= 12.0:
            shown = f"{value:.2f}".rstrip("0").rstrip(".")
            if shown not in axles:
                axles.append(shown)
    if len(axles) == 1:
        return axles[0]
    return None


def _unknown_deck_brand(text):
    tokens = re.findall(r"[A-Za-z0-9]+", text)
    if not tokens:
        return None
    first = tokens[0]
    if len(first) < 3 or _fold(first) in WEAK_TOKENS:
        return None
    return first


def product_identity(item):
    """Return a match identity, or None when the name is too vague to group."""
    if not isinstance(item, dict):
        return None
    part = (item.get("part") or "").strip()
    part_key = part.casefold()
    if part_key not in {"decks", "wheels", "trucks", "bearings"}:
        return None
    text = _prepare_text(item.get("name") or "")
    if not text:
        return None

    size_key = ""
    size_label = ""
    if part_key == "decks":
        brand = find_brand(text, DECK_BRANDS) or _unknown_deck_brand(text)
        width, _length = extract_deck_dimensions(text)
        if brand is None or width is None:
            return None
        snapped = canonical_width(width)
        size_key = f"{snapped:.3f}"
        size_label = _fmt_width(snapped)
    elif part_key == "wheels":
        brand = find_brand(text, WHEEL_BRANDS)
        sized = _wheel_size(text)
        if brand is None or sized is None:
            return None
        millimeters, duro = sized
        size_key = millimeters if not duro else f"{millimeters}|{duro}"
        size_label = f"{millimeters}mm" + (f" {duro}" if duro else "")
    elif part_key == "trucks":
        brand = find_brand(text, TRUCK_BRANDS)
        size_key = _truck_size(text) or ""
        if brand is None or not size_key:
            return None
        size_label = size_key
    else:
        brand = find_brand(text, BEARING_BRANDS)
        if brand is None:
            return None

    stripped = _strip_brand(text, brand)
    stripped = _MM_RE.sub(" ", stripped)
    stripped = _DURO_RE.sub(" ", stripped)
    stripped = _PAIR_RE.sub(" ", stripped)
    if part_key == "trucks" and size_key:
        stripped = re.sub(rf"\b{re.escape(size_key)}\b", " ", stripped)
    display, tokens = _model_tokens(stripped)
    if not tokens and part_key == "bearings" and re.search(r"[\s\-]", brand or ""):
        # "Bones Swiss" is the whole product name. A one-word brand alone is not.
        pass
    elif not _specific(tokens):
        return None
    # Bearings are often a single line name ("Swiss", "Reds"). Other parts
    # need the same: one distinctive word is enough, two weak words are not.
    brand_key = _fold(brand)
    key = "|".join([part_key, brand_key, size_key, *tokens])
    label_bits = [brand, " ".join(display)]
    if size_label:
        label_bits.append(size_label)
    return {
        "key": key,
        "part": part,
        "label": " ".join(bit for bit in label_bits if bit).strip(),
        "brand": brand,
    }


def cross_store_groups(items):
    """Groups of the same product in at least two stores. Cheapest price included."""
    buckets = {}
    labels = {}
    for item in items or []:
        if not item_passes_filters(item):
            continue
        try:
            identity = product_identity(item)
        except Exception:
            continue
        if not identity:
            continue
        price = _price(item.get("price_new"))
        store = item.get("store") or ""
        if price is None or not store:
            continue
        key = identity["key"]
        labels.setdefault(key, identity)
        offer = {
            "store": store,
            "price": price,
            "url": item.get("url") or "",
            "name": normalize_product_name(item.get("name") or ""),
        }
        currency = item.get("currency")
        if currency and str(currency).upper() != "USD":
            offer["currency"] = currency
        current = buckets.setdefault(key, {}).get(store)
        if current is None or price < current["price"]:
            buckets[key][store] = offer

    groups = []
    for key, by_store in buckets.items():
        if len(by_store) < 2:
            continue
        ordered = [by_store[store] for store in STORE_ORDER if store in by_store]
        ordered.extend(by_store[store] for store in by_store if store not in STORE_ORDER)
        cheapest = min(offer["price"] for offer in ordered)
        identity = labels[key]
        groups.append(
            {
                "key": key,
                "part": identity["part"],
                "label": identity["label"],
                "offers": ordered,
                "cheapest_price": cheapest,
            }
        )

    def sort_key(group):
        part = group["part"]
        part_index = PART_ORDER.index(part) if part in PART_ORDER else len(PART_ORDER)
        prices = [offer["price"] for offer in group["offers"]]
        gap = max(prices) - min(prices)
        return (part_index, -gap, group["label"])

    groups.sort(key=sort_key)
    return groups
