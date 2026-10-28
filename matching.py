"""Conservative cross-store product matching.

A group is the same part, the same brand, the same size, and the same
distinctive model words. Widths within about 0.015\" of a standard eighth
snap together (8.12 and 8.125, 8.38 and 8.375). Other widths snap to the
nearest 0.025\" so 8.475 does not collapse into 8.5.

Required sizes by part:

- Decks: width.
- Wheels: one diameter in mm (55.5mm is not 55mm) and a durometer. Two
  listings that both leave out the durometer could be 99a and 101a, so a
  missing durometer is not treated as a match.
- Trucks: one hanger number (149, 55) or one axle width (8.25).
- Bearings: no size; the model words carry the identity.

Brand spellings fold together (Indy and Independent, Death Wish and
Deathwish, Powell-Peralta and Powell, Jacuzzi Unlimited and Jacuzzi). Generic words (team, logo, formula,
four, colors) do not create a match by themselves, and they still keep two
colorways apart when a real model word is present. Standalone numbers that
are not the size (Sanbongi 2, Ripper OG 16, Barrio Triste 003) are model
words, so editions stay apart. Tokens have to be equal, not merely
overlapping, so a longer name does not attach to a shorter one. Only groups
that show up in two or more stores are returned.

``describe_item`` lists every attribute an item is matched on and what is
missing; ``explain_match`` compares two items attribute by attribute;
``match_diagnostics`` summarizes a whole catalog. Run ``python matching.py``
for that summary on ``previous_data.json`` and ``price_history.json``.
"""

import re
import unicodedata

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
STORE_ORDER = ("Zumiez", "SkateWarehouse", "CCS", "Tactics", "TGM", "Deathgear", "Kinetic", "SPoT", "Skate Deluxe", "Muir Skate")

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

# Category and filler words dropped from the model entirely.
_DROPPED_TOKENS = frozenset(
    {
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
    }
)

# Store abbreviations seen in the catalog, spelled out so both sides agree.
_ABBREVIATIONS = {"frgd": "forged", "blk": "black", "wht": "white"}

# Brand spellings that are the same company. Keys are folded with spaces
# and hyphens removed.
_BRAND_ALIASES = {"indy": "independent", "powellperalta": "powell"}

_MM_RE = re.compile(r"\b(\d{2}(?:\.\d{1,2})?)\s*mm\b", re.IGNORECASE)
_DURO_RE = re.compile(r"\b(\d{2,3})\s*([abd])\b", re.IGNORECASE)
_PAIR_RE = re.compile(r"\b\d+(?:\.\d+)?\s*x\s*\d+(?:\.\d+)?\b", re.IGNORECASE)
# Independent, Ace, and Thunder hanger numbers.
_HANGER_RE = re.compile(
    r"\b(22|33|44|55|60|66|77|80|109|129|136|139|143|144|145|146|147|148|149|151|159|161|166|169|215)\b"
)
_AXLE_RE = re.compile(r"\b(\d{1,2}\.\d+)\b")
_STAGE_RE = re.compile(r"\bstage[\s\-]*(\d{1,2})\b", re.IGNORECASE)
# Skate Warehouse writes Stage 11 as "S11".
_STAGE_SHORT_RE = re.compile(r"\bs(\d{1,2})\b", re.IGNORECASE)
_AF1_RE = re.compile(r"\baf[\s\-]*1\b", re.IGNORECASE)
# Full company names that stores shorten. Folded to the short brand before
# matching so the leftover word does not become a model word.
_BRAND_LONG_NAMES = (
    (re.compile(r"\bpowell[\s\-]+peralta\b", re.IGNORECASE), "Powell"),
    (re.compile(r"\bjacuzzi[\s\-]+unlimited\b", re.IGNORECASE), "Jacuzzi"),
)
_APOSTROPHE_RE = re.compile(r"['’]")


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


def _fmt_number(value):
    return f"{value:.2f}".rstrip("0").rstrip(".")


def _price(value):
    try:
        return round(float(value), 2)
    except (TypeError, ValueError):
        return None


def brand_key(brand):
    """One key per company: case, accents, spaces, hyphens, and aliases fold."""
    folded = re.sub(r"[\s\-]+", "", _fold(brand or ""))
    return _BRAND_ALIASES.get(folded, folded)


def _strip_accents(text):
    """Andalé -> Andale, keeping case for labels. Brand lookup already folds
    accents, so removing the brand from the name has to see the same letters."""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def _prepare_text(name, part_key=""):
    text = _strip_accents(normalize_product_name(name))
    text = _APOSTROPHE_RE.sub("", text)
    for pattern, short in _BRAND_LONG_NAMES:
        text = pattern.sub(short, text)
    text = _STAGE_RE.sub(r"stage\1", text)
    if part_key == "trucks":
        text = _STAGE_SHORT_RE.sub(r"stage\1", text)
    text = _AF1_RE.sub("af1", text)
    return text


def _token_is_specific(token):
    if token in WEAK_TOKENS:
        return False
    if len(token) >= 3 and not token.isdigit():
        return True
    # Short model codes such as G3 or V5. Plain two-letter words and bare
    # numbers are not enough on their own.
    return len(token) >= 2 and any(ch.isdigit() for ch in token) and any(ch.isalpha() for ch in token)


def _specific(tokens):
    return any(_token_is_specific(token) for token in tokens)


def _model_tokens(text, skip_numbers=()):
    """Return ``(display_words, folded_key_tuple)``.

    A standalone whole number is a model word (Sanbongi 2, OG 16) unless it
    is in ``skip_numbers`` (the item's own size). Leading zeros fold, so
    #003 and 003 agree. Decimals are dimensions and are dropped.
    """
    display = []
    folded = []
    seen = set()
    for raw in re.findall(r"[A-Za-z0-9]+(?:\.\d+)?", text):
        token = _fold(raw)
        token = _ABBREVIATIONS.get(token, token)
        if re.fullmatch(r"\d+\.\d+", token):
            continue
        if token.isdigit():
            number = int(token)
            if number in skip_numbers:
                continue
            token = str(number)
            raw = token
        elif len(token) < 2:
            continue
        if token in _DROPPED_TOKENS:
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


def _wheel_diameters(text):
    values = []
    for raw in _MM_RE.findall(text):
        shown = _fmt_number(float(raw))
        if shown not in values:
            values.append(shown)
    return values


def _wheel_duro(text):
    duros = {f"{number}{letter.lower()}" for number, letter in _DURO_RE.findall(text)}
    return "+".join(sorted(duros))


def _truck_sizes(text):
    """Hanger numbers if any are named, otherwise axle widths."""
    hangers = []
    for match in _HANGER_RE.findall(text):
        if match not in hangers:
            hangers.append(match)
    if hangers:
        return hangers
    axles = []
    for raw in _AXLE_RE.findall(text):
        value = float(raw)
        if 4.5 <= value <= 12.0:
            shown = _fmt_number(value)
            if shown not in axles:
                axles.append(shown)
    return axles


def _unknown_deck_brand(text):
    tokens = re.findall(r"[A-Za-z0-9]+", text)
    if not tokens:
        return None
    first = tokens[0]
    if len(first) < 3 or _fold(first) in WEAK_TOKENS:
        return None
    return first


def _whole(value):
    """``{int(value)}`` when value is a whole number, else an empty set."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return set()
    return {int(number)} if number == int(number) else set()


def describe_item(item):
    """Every attribute an item is matched on, and why it cannot be matched.

    Returns a dict with ``part``, ``brand``, ``brand_key``, ``sizes`` (an
    ordered list of ``(attribute, value)``), ``model`` (folded words) and
    ``model_words`` (as written), ``label``, ``key``, and ``problems``.
    ``key`` is None whenever ``problems`` is not empty. Nothing here is
    guessed: a size or brand that is not in the name is reported missing.
    """
    info = {
        "part": "",
        "brand": None,
        "brand_key": "",
        "sizes": [],
        "model": (),
        "model_words": [],
        "label": "",
        "key": None,
        "problems": [],
    }
    problems = info["problems"]
    if not isinstance(item, dict):
        problems.append("not a product")
        return info
    part = (item.get("part") or "").strip()
    part_key = part.casefold()
    info["part"] = part
    if part_key not in {"decks", "wheels", "trucks", "bearings"}:
        problems.append(f"{part or 'this part'} is not matched across stores")
        return info
    text = _prepare_text(item.get("name") or "", part_key)
    if not text:
        problems.append("no product name")
        return info

    sizes = info["sizes"]
    size_key = ""
    size_label = ""
    skip_numbers = set()
    strip_patterns = [_MM_RE, _DURO_RE, _PAIR_RE]
    if part_key == "decks":
        brand = find_brand(text, DECK_BRANDS) or _unknown_deck_brand(text)
        width, length = extract_deck_dimensions(text)
        if width is None:
            problems.append("no deck width in the name")
        else:
            snapped = canonical_width(width)
            size_key = f"{snapped:.3f}"
            size_label = _fmt_width(snapped)
            sizes.append(("width", size_label))
            skip_numbers = _whole(width) | _whole(length)
    elif part_key == "wheels":
        brand = find_brand(text, WHEEL_BRANDS)
        diameters = _wheel_diameters(text)
        duro = _wheel_duro(text)
        if not diameters:
            problems.append("no wheel diameter (mm) in the name")
        elif len(diameters) > 1:
            problems.append("more than one wheel diameter: " + ", ".join(d + "mm" for d in diameters))
        else:
            sizes.append(("diameter", diameters[0] + "mm"))
            skip_numbers = _whole(diameters[0])
        if not duro:
            problems.append("no durometer in the name")
        else:
            sizes.append(("durometer", duro))
        if len(sizes) == 2:
            size_key = f"{diameters[0]}|{duro}"
            size_label = f"{diameters[0]}mm {duro}"
    elif part_key == "trucks":
        brand = find_brand(text, TRUCK_BRANDS)
        found = _truck_sizes(text)
        if not found:
            problems.append("no truck hanger or axle size in the name")
        elif len(found) > 1:
            problems.append("more than one truck size: " + ", ".join(found))
        else:
            size_key = size_label = found[0]
            sizes.append(("truck size", size_key))
            # Whole decimals first, so "8.0" does not leave a stray "0".
            strip_patterns.append(_AXLE_RE)
            strip_patterns.append(re.compile(rf"\b{re.escape(size_key)}\b"))
    else:
        brand = find_brand(text, BEARING_BRANDS)

    if brand is None:
        problems.append("brand not recognized")
        return info
    info["brand"] = brand
    info["brand_key"] = brand_key(brand)

    stripped = _strip_brand(text, brand)
    for pattern in strip_patterns:
        stripped = pattern.sub(" ", stripped)
    display, tokens = _model_tokens(stripped, skip_numbers)
    info["model"] = tokens
    info["model_words"] = display
    label_bits = [brand, " ".join(display)]
    if size_label:
        label_bits.append(size_label)
    info["label"] = " ".join(bit for bit in label_bits if bit).strip()

    if not tokens and part_key == "bearings" and re.search(r"[\s\-]", brand):
        # "Bones Swiss" is the whole product name. A one-word brand alone is not.
        pass
    elif not _specific(tokens):
        shown = ", ".join(display) if display else "none"
        problems.append(f"model words are too generic to match on ({shown})")
    if problems:
        return info
    info["key"] = "|".join([part_key, info["brand_key"], size_key, *tokens])
    return info


def product_identity(item):
    """Return a match identity, or None when the name is too vague to group."""
    info = describe_item(item)
    if info["key"] is None:
        return None
    return {
        "key": info["key"],
        "part": info["part"],
        "label": info["label"],
        "brand": info["brand"],
    }


def explain_match(left, right):
    """Compare two items attribute by attribute.

    Returns ``match`` (True exactly when both items have the same identity
    key), ``matched`` attributes, ``blocked`` attributes that differ,
    ``incomplete`` attributes or problems that rule a match out, and a
    one-line ``summary``.
    """
    a = describe_item(left)
    b = describe_item(right)
    matched = []
    blocked = []
    incomplete = []

    def compare(attribute, value_a, value_b):
        if value_a and value_b:
            if value_a == value_b:
                matched.append({"attribute": attribute, "value": value_a})
            else:
                blocked.append({"attribute": attribute, "left": value_a, "right": value_b})
        elif value_a or value_b:
            incomplete.append(
                {
                    "attribute": attribute,
                    "left": value_a or None,
                    "right": value_b or None,
                }
            )

    if a["part"].casefold() == b["part"].casefold():
        matched.append({"attribute": "part", "value": a["part"]})
    else:
        blocked.append({"attribute": "part", "left": a["part"], "right": b["part"]})
    if a["brand_key"] and b["brand_key"]:
        if a["brand_key"] == b["brand_key"]:
            matched.append({"attribute": "brand", "value": a["brand"]})
        else:
            blocked.append({"attribute": "brand", "left": a["brand"], "right": b["brand"]})
    sizes_a = dict(a["sizes"])
    sizes_b = dict(b["sizes"])
    for attribute in [name for name, _ in a["sizes"]] + [n for n, _ in b["sizes"] if n not in sizes_a]:
        compare(attribute, sizes_a.get(attribute), sizes_b.get(attribute))
    if a["model"] or b["model"]:
        if a["model"] == b["model"]:
            matched.append({"attribute": "model words", "value": " ".join(a["model_words"])})
        elif a["model"] and b["model"]:
            only_a = [word for word in a["model"] if word not in b["model"]]
            only_b = [word for word in b["model"] if word not in a["model"]]
            blocked.append(
                {
                    "attribute": "model words",
                    "left": " ".join(only_a) or "(none extra)",
                    "right": " ".join(only_b) or "(none extra)",
                }
            )
        else:
            compare("model words", " ".join(a["model_words"]), " ".join(b["model_words"]))
    for side, info in (("left", a), ("right", b)):
        for problem in info["problems"]:
            incomplete.append({"attribute": "item", side: problem})

    match = a["key"] is not None and a["key"] == b["key"]
    if match:
        summary = "Match on " + ", ".join(entry["attribute"] for entry in matched)
    elif blocked:
        summary = "No match: different " + ", ".join(entry["attribute"] for entry in blocked)
    else:
        summary = "No match: not enough information"
    return {
        "match": match,
        "matched": matched,
        "blocked": blocked,
        "incomplete": incomplete,
        "left": a,
        "right": b,
        "summary": summary,
    }


def cross_store_groups(items, explain=False, apply_filters=True):
    """Groups of the same product in at least two stores. Cheapest price included.

    With ``explain=True`` each group also carries ``explanation``: the part,
    brand, sizes, and model words every offer in it shares.
    ``apply_filters=False`` skips the store filters, for reviewing price
    history, which has no original prices.
    """
    buckets = {}
    labels = {}
    for item in items or []:
        if apply_filters and not item_passes_filters(item):
            continue
        try:
            info = describe_item(item)
        except Exception:
            continue
        if info["key"] is None:
            continue
        price = _price(item.get("price_new"))
        store = item.get("store") or ""
        if price is None or not store:
            continue
        key = info["key"]
        offer = {
            "store": store,
            "price": price,
            "url": item.get("url") or "",
            "name": normalize_product_name(item.get("name") or ""),
        }
        currency = item.get("currency")
        if currency and str(currency).upper() != "USD":
            offer["currency"] = currency
        # Ties go to the earlier URL so input order never changes the result.
        current = buckets.setdefault(key, {}).get(store)
        if current is None or (price, offer["url"]) < (current["price"], current["url"]):
            buckets[key][store] = offer
            labels.setdefault(key, {})[store] = info

    groups = []
    for key, by_store in buckets.items():
        if len(by_store) < 2:
            continue
        ordered = [by_store[store] for store in STORE_ORDER if store in by_store]
        ordered.extend(by_store[store] for store in sorted(by_store) if store not in STORE_ORDER)
        cheapest = min(offer["price"] for offer in ordered)
        # The label comes from the first store in display order.
        info = labels[key][ordered[0]["store"]]
        group = {
            "key": key,
            "part": info["part"],
            "label": info["label"],
            "offers": ordered,
            "cheapest_price": cheapest,
        }
        if explain:
            group["explanation"] = {
                "part": info["part"],
                "brand": info["brand"],
                "sizes": dict(info["sizes"]),
                "model_words": list(info["model_words"]),
            }
        groups.append(group)

    def sort_key(group):
        part = group["part"]
        part_index = PART_ORDER.index(part) if part in PART_ORDER else len(PART_ORDER)
        prices = [offer["price"] for offer in group["offers"]]
        gap = max(prices) - min(prices)
        return (part_index, -gap, group["label"], group["key"])

    groups.sort(key=sort_key)
    return groups


def _problem_kind(problem):
    return problem.split(":", 1)[0].split(" (", 1)[0]


def match_diagnostics(items, near_miss_limit=50, apply_filters=True):
    """Catalog-wide matching summary for review. Deterministic.

    ``unmatchable`` counts why items have no identity, per part.
    ``near_misses`` are pairs from different stores with the same part and
    brand, complete information, and exactly one blocking attribute (for
    model words, only pairs sharing at least half of the shorter name's
    words): the places where a naming difference may be hiding a real
    match, or where the matcher correctly kept two variants apart.
    """
    unmatchable = {}
    candidates = {}
    seen = set()
    for item in items or []:
        if not isinstance(item, dict) or (apply_filters and not item_passes_filters(item)):
            continue
        info = describe_item(item)
        part = info["part"]
        if part not in PART_ORDER:
            continue
        if info["key"] is None:
            counts = unmatchable.setdefault(part, {})
            for problem in info["problems"]:
                kind = _problem_kind(problem)
                counts[kind] = counts.get(kind, 0) + 1
            continue
        name = normalize_product_name(item.get("name") or "")
        store = item.get("store") or ""
        if (store, name) in seen:
            continue
        seen.add((store, name))
        candidates.setdefault((part, info["brand_key"]), []).append((store, name, item))

    near_misses = []
    for (part, _brand), entries in sorted(candidates.items()):
        entries.sort(key=lambda entry: (entry[0], entry[1]))
        for i, (store_a, name_a, item_a) in enumerate(entries):
            for store_b, name_b, item_b in entries[i + 1 :]:
                if store_a == store_b:
                    continue
                result = explain_match(item_a, item_b)
                if result["match"] or result["incomplete"] or len(result["blocked"]) != 1:
                    continue
                if result["blocked"][0]["attribute"] == "model words":
                    # Two unrelated decks of one brand and width differ only
                    # in model words too; keep pairs that share most words.
                    words_a = set(result["left"]["model"])
                    words_b = set(result["right"]["model"])
                    if 2 * len(words_a & words_b) < min(len(words_a), len(words_b)):
                        continue
                near_misses.append(
                    {
                        "part": part,
                        "left": f"{store_a}: {name_a}",
                        "right": f"{store_b}: {name_b}",
                        "blocked": result["blocked"][0],
                    }
                )
    near_misses.sort(key=lambda row: (PART_ORDER.index(row["part"]), row["blocked"]["attribute"], row["left"], row["right"]))
    groups = cross_store_groups(items, explain=True, apply_filters=apply_filters)
    return {
        "groups": groups,
        "unmatchable": unmatchable,
        "near_miss_count": len(near_misses),
        "near_misses": near_misses[:near_miss_limit],
    }


def _history_items(history):
    """Price-history entries as catalog items, one per URL."""
    items = []
    for url, entry in (history or {}).items():
        if isinstance(entry, dict) and entry.get("name"):
            items.append(
                {
                    "name": entry["name"],
                    "store": entry.get("store"),
                    "part": entry.get("part"),
                    "url": url,
                    "price_new": entry.get("all_time_low"),
                }
            )
    return items


def _print_diagnostics(title, items, apply_filters=True):
    report = match_diagnostics(items, near_miss_limit=25, apply_filters=apply_filters)
    print(f"== {title}: {len(report['groups'])} cross-store groups")
    for group in report["groups"]:
        stores = " | ".join(f"{offer['store']}: {offer['name']}" for offer in group["offers"])
        print(f"  {group['part']}: {group['label']}  <-  {stores}")
    for part in PART_ORDER:
        counts = report["unmatchable"].get(part)
        if counts:
            shown = ", ".join(f"{kind} {count}" for kind, count in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])))
            print(f"  {part} without an identity: {shown}")
    print(f"  near misses (one attribute apart): {report['near_miss_count']}")
    for row in report["near_misses"]:
        blocked = row["blocked"]
        print(f"    [{blocked['attribute']}: {blocked['left']} / {blocked['right']}] {row['left']}  ~  {row['right']}")


if __name__ == "__main__":
    import json
    import os
    import sys

    here = os.path.dirname(os.path.abspath(__file__))
    catalog_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(here, "previous_data.json")
    history_path = os.path.join(here, "price_history.json")
    with open(catalog_path, encoding="utf-8") as handle:
        catalog = json.load(handle)
    _print_diagnostics("current catalog", [item for rows in catalog.values() for item in rows or []])
    if len(sys.argv) <= 1 and os.path.exists(history_path):
        with open(history_path, encoding="utf-8") as handle:
            history_items = _history_items(json.load(handle))
        _print_diagnostics("every item in price history (store filters skipped)", history_items, apply_filters=False)
