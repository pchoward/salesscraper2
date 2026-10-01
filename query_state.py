"""Filter state in the report URL.

The page reads and writes this query string with ``history.replaceState``.
Saved views store the same string. Defaults are omitted so an unfiltered
page has no query.

``width=8.25`` is one width. ``width=8.25-8.5`` is an inclusive range.
``type=deck`` is the part. ``discount=40`` is the minimum percent off.
"""

from urllib.parse import parse_qsl, urlencode

STORE_SLUGS = {
    "zumiez": "Zumiez",
    "skatewarehouse": "SkateWarehouse",
    "ccs": "CCS",
    "tactics": "Tactics",
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
        "width": "all",
        "wmin": None,
        "wmax": None,
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


def _parse_width(value):
    text = str(value or "").strip()
    if not text or text.lower() == "all":
        return "all", None, None
    if "-" in text:
        left, right = text.split("-", 1)
        return "all", _float(left), _float(right)
    number = _float(text)
    if number is None:
        return "all", None, None
    return _num_text(number), None, None


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
            width, wmin, wmax = _parse_width(value)
            state["width"] = width
            state["wmin"] = wmin
            state["wmax"] = wmax
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
    width = state.get("width") or "all"
    if width != "all":
        add("width", width)
    else:
        wmin = state.get("wmin")
        wmax = state.get("wmax")
        if wmin is not None or wmax is not None:
            left = _num_text(wmin) if wmin is not None else ""
            right = _num_text(wmax) if wmax is not None else ""
            add("width", f"{left}-{right}")
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
