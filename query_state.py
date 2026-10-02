"""Filter state in the report URL.

The page reads and writes this query string with ``history.replaceState``.
Saved views store the same string. Defaults are omitted so an unfiltered
page has no query.

``type=deck`` is the part. ``discount=40`` is the minimum percent off.

Width is a list of range-chip ids in ``width``, comma-separated. An empty
list means All. Each chip is one bucket: the lower bound is inclusive and
the upper bound is exclusive, so 8.5" is ``8.5-8.75`` and 10.0" is ``10up``
(the chip labeled ``10.0+``).

Older links still resolve:

* ``width=8.25`` selects the one bucket that contains 8.25".
* ``width=8.25-8.5`` is the old inclusive min/max window. When that text is
  not itself a bucket id, every bucket that overlaps the closed interval is
  selected, so the bucket that holds the upper endpoint is included.
* A token that equals a bucket id selects that chip only. ``width=8.5-8.75``
  is the half-open chip, not an inclusive window through 8.75".

On the page, width ranges filter deck rows only. Wheels, trucks, and
bearings stay visible when a range is selected. They drop out only when
the type filter is also Decks. A deck with no parsed width does not fall
in any bucket, so it is hidden while any range is selected.
"""

from urllib.parse import parse_qsl, urlencode


class WidthRange(object):
    """One deck-width bucket. ``max`` is exclusive; ``None`` means unbounded."""

    def __init__(self, id, label, low, high):
        self.id = id
        self.label = label
        self.min = low
        self.max = high


# Lower bound inclusive, upper bound exclusive. 8.5 is "8.5 - 8.75".
# 10.0 is "10.0+". Ids that use ".0" do not collide with the old encoder,
# which wrote 8 and 10 rather than 8.0 and 10.0.
WIDTH_RANGES = (
    WidthRange("lt7", "< 7.0", None, 7.0),
    WidthRange("7.0-7.25", "7.0 - 7.25", 7.0, 7.25),
    WidthRange("7.25-7.5", "7.25 - 7.5", 7.25, 7.5),
    WidthRange("7.5-7.75", "7.5 - 7.75", 7.5, 7.75),
    WidthRange("7.75-8.0", "7.75 - 8.0", 7.75, 8.0),
    WidthRange("8.0-8.125", "8.0 - 8.125", 8.0, 8.125),
    WidthRange("8.125-8.25", "8.125 - 8.25", 8.125, 8.25),
    WidthRange("8.25-8.375", "8.25 - 8.375", 8.25, 8.375),
    WidthRange("8.375-8.5", "8.375 - 8.5", 8.375, 8.5),
    WidthRange("8.5-8.75", "8.5 - 8.75", 8.5, 8.75),
    WidthRange("8.75-9.0", "8.75 - 9.0", 8.75, 9.0),
    WidthRange("9.0-9.25", "9.0 - 9.25", 9.0, 9.25),
    WidthRange("9.25-9.5", "9.25 - 9.5", 9.25, 9.5),
    WidthRange("9.5-10.0", "9.5 - 10.0", 9.5, 10.0),
    WidthRange("10up", "10.0+", 10.0, None),
)
_WIDTH_IDS = {bucket.id: bucket for bucket in WIDTH_RANGES}
_WIDTH_ALIASES = {
    "<7": "lt7",
    "<7.0": "lt7",
    "10+": "10up",
    "10.0+": "10up",
}

STORE_SLUGS = {
    "zumiez": "Zumiez",
    "skatewarehouse": "SkateWarehouse",
    "ccs": "CCS",
    "tactics": "Tactics",
    "skatedeluxe": "Skate Deluxe",
    "muirskate": "Muir Skate",
}
STORE_TO_SLUG = {name: slug for slug, name in STORE_SLUGS.items()}

TYPE_SLUGS = {
    "deck": "Decks",
    "decks": "Decks",
    "wheel": "Wheels",
    "wheels": "Wheels",
    "truck": "Trucks",
    "trucks": "Trucks",
    "bearing": "Bearings",
    "bearings": "Bearings",
}
TYPE_TO_SLUG = {
    "Decks": "deck",
    "Wheels": "wheel",
    "Trucks": "truck",
    "Bearings": "bearing",
}

SORTS = (
    "rank",
    "score",
    "price",
    "price-desc",
    "original",
    "discount",
    "size",
    "store",
    "brand",
    "days",
    "daysat",
)
CHANGES = ("new", "drop", "lowest", "removed")

STARTER_VIEWS = (
    {
        "id": "decks-range",
        "name": "Decks 8.25-8.5, 35%+ off",
        "query": "type=deck&width=8.25-8.5&discount=35",
    },
    {
        "id": "decks-85",
        "name": "8.5 decks under $50",
        "query": "type=deck&width=8.5&max=50",
    },
    {
        "id": "sw-new",
        "name": "New Skate Warehouse drops",
        "query": "store=skatewarehouse&change=new",
    },
    {
        "id": "watched-lows",
        "name": "Watched items at all-time low",
        "query": "watching=1&low=1",
    },
)


def empty_state():
    return {
        "q": "",
        "store": "all",
        "part": "all",
        "widths": [],
        "brand": "all",
        "min": None,
        "max": None,
        "discount": None,
        "length": "all",
        "wheelbase": "all",
        "sort": "rank",
        "change": "all",
        "watching": False,
        "low": False,
        "added": False,
        "dropped": False,
        "grouped": False,
    }


def _num_text(value):
    number = float(value)
    if abs(number - round(number)) < 1e-9:
        return str(int(round(number)))
    return f"{number:.4f}".rstrip("0").rstrip(".")


def _float(value):
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _store(value):
    key = "".join(ch for ch in str(value or "").lower() if ch.isalnum())
    return STORE_SLUGS.get(key, "")


def _part(value):
    return TYPE_SLUGS.get(str(value or "").strip().lower(), "")


def _flag(value):
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def bucket_contains(bucket, width):
    """True when ``width`` falls in this bucket (low inclusive, high exclusive)."""
    try:
        width = float(width)
    except (TypeError, ValueError):
        return False
    if bucket.min is not None and width < bucket.min - 1e-9:
        return False
    if bucket.max is not None and width >= bucket.max - 1e-9:
        return False
    return True


def bucket_for_width(value):
    """The one bucket that contains ``value``, or None."""
    for bucket in WIDTH_RANGES:
        if bucket_contains(bucket, value):
            return bucket
    return None


def _overlaps_inclusive(bucket, low, high):
    """True when the closed interval overlaps the half-open bucket."""
    left = float("-inf") if low is None else low
    right = float("inf") if high is None else high
    lo = float("-inf") if bucket.min is None else bucket.min
    hi = float("inf") if bucket.max is None else bucket.max
    return left < hi - 1e-12 and right >= lo - 1e-12


def _ordered_widths(ids):
    chosen = set(ids or [])
    return [bucket.id for bucket in WIDTH_RANGES if bucket.id in chosen]


def parse_width_param(value):
    """Bucket ids for a ``width`` query value. Empty means All."""
    text = str(value or "").strip()
    if not text or text.lower() == "all":
        return []
    chosen = []
    for token in text.split(","):
        token = "".join(token.split())
        if not token:
            continue
        alias = _WIDTH_ALIASES.get(token)
        if alias:
            chosen.append(alias)
            continue
        if token in _WIDTH_IDS:
            chosen.append(token)
            continue
        if "-" in token:
            left, right = token.split("-", 1)
            low = _float(left) if left else None
            high = _float(right) if right else None
            if (left and low is None) or (right and high is None):
                continue
            if low is None and high is None:
                continue
            chosen.extend(
                bucket.id for bucket in WIDTH_RANGES if _overlaps_inclusive(bucket, low, high)
            )
            continue
        bucket = bucket_for_width(token)
        if bucket is not None:
            chosen.append(bucket.id)
    return _ordered_widths(chosen)


def decode_query(query):
    """Return a full filter state. Unknown values are ignored."""
    state = empty_state()
    text = str(query or "").strip()
    if text.startswith("?"):
        text = text[1:]
    if not text:
        return state
    for key, value in parse_qsl(text, keep_blank_values=False):
        key = key.strip().lower()
        if key == "q":
            state["q"] = value.strip()
        elif key == "store":
            store = _store(value)
            if store:
                state["store"] = store
        elif key == "type":
            part = _part(value)
            if part:
                state["part"] = part
        elif key == "width":
            state["widths"] = parse_width_param(value)
        elif key == "brand" and value.strip():
            state["brand"] = value.strip()
        elif key == "min":
            state["min"] = _float(value)
        elif key == "max":
            state["max"] = _float(value)
        elif key == "discount":
            state["discount"] = _float(value)
        elif key == "length" and value.strip() and value.strip().lower() != "all":
            state["length"] = value.strip()
        elif key == "wheelbase" and value.strip() and value.strip().lower() != "all":
            state["wheelbase"] = value.strip()
        elif key == "sort" and value.strip() in SORTS:
            state["sort"] = value.strip()
        elif key == "change" and value.strip() in CHANGES:
            state["change"] = value.strip()
        elif key == "watching":
            state["watching"] = _flag(value)
        elif key == "low":
            state["low"] = _flag(value)
        elif key == "added":
            state["added"] = _flag(value)
        elif key == "dropped":
            state["dropped"] = _flag(value)
        elif key == "group":
            state["grouped"] = _flag(value)
    return state


def encode_state(state):
    """Query string without ``?``. Empty when every control is at its default."""
    state = state or {}
    pairs = []

    def add(key, value):
        if value is None:
            return
        text = str(value).strip()
        if not text or text == "all":
            return
        pairs.append((key, text))

    add("q", state.get("q") or "")
    store = state.get("store") or "all"
    if store != "all":
        add("store", STORE_TO_SLUG.get(store, ""))
    part = state.get("part") or "all"
    if part != "all":
        add("type", TYPE_TO_SLUG.get(part, ""))
    widths = _ordered_widths(state.get("widths"))
    if widths:
        add("width", ",".join(widths))
    add("brand", state.get("brand") or "")
    if state.get("min") is not None:
        add("min", _num_text(state["min"]))
    if state.get("max") is not None:
        add("max", _num_text(state["max"]))
    if state.get("discount") is not None:
        add("discount", _num_text(state["discount"]))
    add("length", state.get("length") or "")
    add("wheelbase", state.get("wheelbase") or "")
    sort = state.get("sort") or "rank"
    if sort != "rank" and sort in SORTS:
        add("sort", sort)
    change = state.get("change") or "all"
    if change in CHANGES:
        add("change", change)
    if state.get("watching"):
        add("watching", "1")
    if state.get("low") and state.get("change") != "lowest":
        add("low", "1")
    if state.get("added") and state.get("change") != "new":
        add("added", "1")
    if state.get("dropped") and state.get("change") != "drop":
        add("dropped", "1")
    if state.get("grouped"):
        add("group", "1")
    return urlencode(pairs)
