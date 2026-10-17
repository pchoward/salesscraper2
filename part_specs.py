"""Specs that are printed in a product name.

Wheel diameter, durometer, and shape, truck size and height, and bearing
ABEC ratings come only from tokens in the name. A missing token stays blank.
Nothing here invents a size, a hardness, or a rating the name does not show.

A filter section should stay off the page when fewer than ``MIN_SPEC_COUNT``
listings in that part have a parsed value.
"""

import re

MIN_SPEC_COUNT = 5

# Half-open millimeter bands. 55.5 is 54-55. 56 and wider, including 63, is 56+.
# Nothing below 50mm gets a band.
DIAMETER_BANDS = (
    ("50-51", 50.0, 52.0),
    ("52-53", 52.0, 54.0),
    ("54-55", 54.0, 56.0),
    ("56+", 56.0, None),
)
DIAMETER_ORDER = tuple(band[0] for band in DIAMETER_BANDS)

SHAPES = ("conical", "radial", "sidecut")
SHAPE_LABELS = {"conical": "Conical", "radial": "Radial", "sidecut": "Sidecut"}

# Independent / Thunder hanger sizes printed as whole millimeters.
MM_SIZES = frozenset(
    {"109", "129", "136", "139", "144", "145", "147", "148", "149", "151", "159", "169", "215"}
)
# Ace size codes. They are not millimeter hangers. 60 is an Ace code and is
# not in the millimeter list. Accepted only when the name also says Ace.
ACE_SIZES = frozenset({"22", "33", "44", "55", "60", "66", "77"})
# Venture axle widths that show up as a bare decimal, such as 5.6.
AXLE_SIZES = frozenset({"5.0", "5.2", "5.6", "5.8", "6.1"})

HEIGHTS = ("low", "mid", "high")
HEIGHT_LABELS = {"low": "Low", "mid": "Mid", "high": "High"}
# Only words the name prints. Hollow and Standard are construction. Lights,
# titanium, and forged are product lines or too rare to treat as one.
CONSTRUCTIONS = ("hollow", "standard")
CONSTRUCTION_LABELS = {"hollow": "Hollow", "standard": "Standard"}

_MM_RE = re.compile(r"\b(\d{2}(?:\.\d)?)\s*mm\b", re.IGNORECASE)
# "51 (99d)" prints the diameter beside the durometer, without "mm".
_BARE_MM_RE = re.compile(r"\b(\d{2}(?:\.\d)?)\s*\(\s*\d{2,3}\s*[aAbBdD]\s*\)")
_DURO_RE = re.compile(r"\b(\d{2,3})\s*([aAbBdD])\b")
_DURO_TOKEN = re.compile(r"^\d{2,3}[abd]$")
# "Classic" is a Spitfire model name, not a wheel shape.
_SHAPE_RE = re.compile(r"\b(conical|radial|sidecut|side[\s\-]?cut)\b", re.IGNORECASE)
_MM_SIZE_RE = re.compile(
    r"\b(109|129|136|139|144|145|147|148|149|151|159|169|215)\b"
)
_ACE_NAME_RE = re.compile(r"\bace\b", re.IGNORECASE)
_ACE_SIZE_RE = re.compile(r"\b(22|33|44|55|60|66|77)\b")
_INCH_RE = re.compile(
    r"\b(\d{1,2}\.\d+)\s*(?:\"|\u201d|\u2033|in(?:ch(?:es)?)?)(?!\w)",
    re.IGNORECASE,
)
_AXLE_RE = re.compile(r"\b(5\.0|5\.2|5\.6|5\.8|6\.1)\b")
_HEIGHT_RE = re.compile(r"\b(low|mid|high)\b", re.IGNORECASE)
_CONSTRUCTION_RE = re.compile(r"\b(hollows?|standard)\b", re.IGNORECASE)
_ABEC_RE = re.compile(r"\babec[\s\-]?(\d{1,2})\b", re.IGNORECASE)
_SIZE_TOKEN = re.compile(r"^(?:\d{2,3}|\d{1,2}\.\d+)$")
_ABEC_TOKEN = re.compile(r"^\d{1,2}$")


def section_ready(count):
    """True when a spec section has enough parsed listings to show."""
    try:
        return int(count) >= MIN_SPEC_COUNT
    except (TypeError, ValueError):
        return False


def _unique(values):
    found = []
    for value in values:
        if value not in found:
            found.append(value)
    return found


def format_decimal_size(value):
    """Keep a printed decimal. 11.0 stays ``11.0`` and 10.50 becomes ``10.5``."""
    number = float(value)
    if abs(number - round(number)) < 1e-9:
        return f"{number:.1f}"
    return f"{number:.4f}".rstrip("0").rstrip(".")


def diameter_band(millimeters):
    """Band id for a parsed diameter, or ``""`` when it is missing or under 50."""
    if millimeters is None:
        return ""
    try:
        value = float(millimeters)
    except (TypeError, ValueError):
        return ""
    for band_id, low, high in DIAMETER_BANDS:
        if value >= low and (high is None or value < high):
            return band_id
    return ""


def diameter_tip(band_id):
    """Tooltip for a diameter band. Empty when the band is unknown."""
    for known, low, high in DIAMETER_BANDS:
        if known != band_id:
            continue
        if high is None:
            return f"{low:.0f}mm and wider, printed in the name"
        return f"{low:.0f}mm up to but not including {high:.0f}mm, printed in the name"
    return ""


def size_tip(token):
    """Tooltip for a truck size token taken from a name."""
    if token in MM_SIZES:
        return f"Hanger size {token} printed in the name"
    if token in ACE_SIZES:
        return f"Ace size {token} printed in the name"
    if token in AXLE_SIZES:
        return f"Axle width {token} printed in the name"
    return f'Hanger width {token}" printed in the name'


def wheel_specs(name):
    """Diameter in mm, durometer tokens, and an unambiguous shape word.

    ``classic`` is ignored. Two hardness tokens, ``101a/95a`` or ``99a & 95a``,
    are both returned, in the order they appear.
    """
    text = str(name or "")
    diameter = None
    explicit = _unique(_MM_RE.findall(text))
    if len(explicit) == 1:
        diameter = float(explicit[0])
    elif not explicit:
        bare = _unique(_BARE_MM_RE.findall(text))
        if len(bare) == 1:
            diameter = float(bare[0])
    duros = []
    seen = set()
    for number, letter in _DURO_RE.findall(text):
        token = f"{int(number)}{letter.lower()}"
        if token in seen:
            continue
        seen.add(token)
        duros.append(token)
    shape = ""
    match = _SHAPE_RE.search(text)
    if match:
        raw = match.group(1).lower().replace(" ", "").replace("-", "")
        shape = "sidecut" if raw.startswith("side") else raw
        if shape not in SHAPES:
            shape = ""
    return {"diameter_mm": diameter, "durometers": duros, "shape": shape}


def truck_specs(name):
    """One size token and a low/mid/high word, when the name prints them.

    Inch-marked hanger widths win, then a known millimeter hanger, then an
    Ace size code when the name says Ace, then a known axle decimal such as
    5.6. Stage 11, a percent, and the word Hollow are not sizes or heights.
    Two different sizes of the same kind leave the size blank.

    Construction is Hollow or Standard only when that word is printed. A name
    that says both stays blank. Lights, titanium, and forged are not construction.
    """
    text = str(name or "")
    size = ""
    inches = _unique(_INCH_RE.findall(text))
    millimeters = _unique(_MM_SIZE_RE.findall(text))
    if len(inches) == 1:
        size = format_decimal_size(inches[0])
    elif len(inches) > 1:
        size = ""
    elif len(millimeters) == 1:
        size = millimeters[0]
    elif len(millimeters) > 1:
        size = ""
    else:
        aces = _unique(_ACE_SIZE_RE.findall(text)) if _ACE_NAME_RE.search(text) else []
        if len(aces) == 1:
            size = aces[0]
        elif not aces:
            axles = _unique(_AXLE_RE.findall(text))
            if len(axles) == 1:
                size = format_decimal_size(axles[0])
    found = _HEIGHT_RE.search(text)
    height = found.group(1).lower() if found else ""
    kinds = []
    for match in _CONSTRUCTION_RE.finditer(text):
        word = match.group(1).lower()
        token = "hollow" if word.startswith("hollow") else "standard"
        if token not in kinds:
            kinds.append(token)
    construction = kinds[0] if len(kinds) == 1 else ""
    return {"size": size, "height": height, "construction": construction}


def bearing_specs(name):
    """ABEC rating digits from ``ABEC-7``, ``ABEC 7``, or ``ABEC7``."""
    match = _ABEC_RE.search(str(name or ""))
    return {"abec": match.group(1) if match else ""}


def normalize_duro(value):
    token = str(value or "").strip().lower()
    if not _DURO_TOKEN.fullmatch(token):
        return ""
    return f"{int(token[:-1])}{token[-1]}"


def normalize_size_token(value):
    """A size token the parser can emit. Bare ``11`` is not a truck size."""
    text = str(value or "").strip()
    if not _SIZE_TOKEN.fullmatch(text):
        return ""
    if "." in text:
        token = format_decimal_size(text)
        if token in AXLE_SIZES:
            return token
        number = float(token)
        if 7.0 <= number <= 12.0:
            return token
        return ""
    token = str(int(text))
    if token in MM_SIZES or token in ACE_SIZES:
        return token
    return ""


def normalize_abec(value):
    token = str(value or "").strip()
    if not _ABEC_TOKEN.fullmatch(token):
        return ""
    return str(int(token))


def ordered_diameters(values):
    chosen = {str(value or "").strip() for value in (values or [])}
    return [band for band in DIAMETER_ORDER if band in chosen]


def ordered_shapes(values):
    chosen = {str(value or "").strip().lower() for value in (values or [])}
    return [shape for shape in SHAPES if shape in chosen]


def ordered_heights(values):
    chosen = {str(value or "").strip().lower() for value in (values or [])}
    return [height for height in HEIGHTS if height in chosen]


def ordered_constructions(values):
    chosen = {str(value or "").strip().lower() for value in (values or [])}
    return [kind for kind in CONSTRUCTIONS if kind in chosen]


def ordered_duros(values):
    chosen = []
    seen = set()
    for raw in values or []:
        token = normalize_duro(raw)
        if token and token not in seen:
            seen.add(token)
            chosen.append(token)
    return sorted(chosen, key=lambda token: (int(token[:-1]), token[-1]))


def ordered_sizes(values):
    chosen = []
    seen = set()
    for raw in values or []:
        token = normalize_size_token(raw)
        if token and token not in seen:
            seen.add(token)
            chosen.append(token)
    return sorted(chosen, key=float)


def ordered_abecs(values):
    chosen = []
    seen = set()
    for raw in values or []:
        token = normalize_abec(raw)
        if token and token not in seen:
            seen.add(token)
            chosen.append(token)
    return sorted(chosen, key=int)


# US men's skate-shoe sizes. A bare number is not a size: model numbers
# (Force 58, 933) and deck widths must not land here. The token has to be
# the whole value, or sit next to "size", "US", or "men's".
_SHOE_SIZE_MARKED = re.compile(
    r"\b(?:men(?:'s|\u2019s)?|mens|us)\s*(?:size\s*)?(\d{1,2}(?:\.5)?)\b"
    r"|\bsize\s*(\d{1,2}(?:\.5)?)\b",
    re.IGNORECASE,
)
_SHOE_SIZE_EXACT = re.compile(r"^\s*(\d{1,2}(?:\.\d+)?)\s*(?:us)?\s*$", re.IGNORECASE)


def format_shoe_size(value):
    """``10`` or ``10.5``. Empty when the number is not a men's US size."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return ""
    if number < 4 or number > 15:
        return ""
    doubled = number * 2
    if abs(doubled - round(doubled)) > 1e-6:
        return ""
    if abs(number - round(number)) < 1e-6:
        return str(int(round(number)))
    return f"{number:.1f}"


def shoe_size_token(text, exact=False):
    """One US men's size from a marked phrase, or from a variant title when ``exact``."""
    raw = str(text or "").strip()
    if not raw:
        return ""
    if exact:
        match = _SHOE_SIZE_EXACT.match(raw)
        return format_shoe_size(match.group(1)) if match else ""
    match = _SHOE_SIZE_MARKED.search(raw)
    if not match:
        return ""
    return format_shoe_size(match.group(1) or match.group(2))


def shoe_sizes_in(text):
    """Every marked US men's size in a name or description, in order."""
    found = []
    for match in _SHOE_SIZE_MARKED.finditer(str(text or "")):
        token = format_shoe_size(match.group(1) or match.group(2))
        if token and token not in found:
            found.append(token)
    return found


def ordered_shoe_sizes(values):
    chosen = []
    seen = set()
    for raw in values or []:
        token = format_shoe_size(raw) or shoe_size_token(raw, exact=True)
        if token and token not in seen:
            seen.add(token)
            chosen.append(token)
    return sorted(chosen, key=float)
