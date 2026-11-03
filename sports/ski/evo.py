"""evo-style ski filters, read from what the store states (title, product
type, tags and the product description). Owner's model: evo's ski filters
(2026-11-02).

Skis: Type, Waist Width, Turn Radius, Rocker Profile, Ability Level,
Bindings. Boots: Type, Last Width, Flex, Binding Compatibility, Walk Mode,
Ability Level.

Only labelled values ("Radius: 13 m", "100MM LAST", "Ability: Beginner") and
specific phrases ("87mm at the waist", "a park ski", "Bindings Included")
count; a field is left out when the store doesn't state it. The one
convention used is a boot's flex from its model name ("Shadow 120 MV"), and
that is labelled so.
"""

import re

# ---- shared ----------------------------------------------------------------

LEVELS = ("Beginner", "Intermediate", "Advanced", "Expert")
_LEVEL_WORDS = r"(beginner|novice|intermediate|advanced|expert)"
_LABELED_ABILITY = re.compile(r"\b(?:ability(?:\s*level)?|skill\s*level|skier\s*level|level)\s*[:\-–]?\s*((?:[a-z]+(?:\s*(?:to|-|–|/|and|,)\s*)?){1,4})", re.I)
_FOR_ABILITY = re.compile(r"\bfor\s+((?:" + _LEVEL_WORDS + r"(?:\s*(?:to|-|–|/|and|or|,)\s*)?){1,3})\s*(?:-level\s*)?(?:skiers?|riders?|users?)\b", re.I)


def _levels(text):
    found = set()
    for pattern in (_LABELED_ABILITY, _FOR_ABILITY):
        for match in pattern.finditer(text):
            words = re.findall(_LEVEL_WORDS, match.group(1), re.I)
            for word in words:
                word = word.casefold()
                found.add("Beginner" if word == "novice" else word.capitalize())
            span = re.search(r"\b(beginner|intermediate|advanced)\s*(?:to|-|–)\s*(intermediate|advanced|expert)\b", match.group(1), re.I)
            if span:  # "Beginner to Advanced" includes Intermediate
                low, high = (LEVELS.index(word.capitalize()) for word in span.groups())
                found.update(LEVELS[low:high + 1])
    return sorted(found, key=LEVELS.index)


def ability(text):
    return _levels(text)


# ---- skis --------------------------------------------------------------------

SKI_TYPES = (
    ("Park & Freestyle", r"park|freestyle|twin[- ]?tip|jib"),
    ("Powder", r"powder|pow"),
    ("Freeride", r"freeride|big[- ]mountain"),
    ("Backcountry / Touring", r"touring|backcountry|alpine touring|skimo|uphill"),
    ("Carving / Frontside", r"carving|frontside|on[- ]piste|groomer"),
    ("All-Mountain", r"all[- ]mountain|all[- ]terrain"),
    ("Race", r"race|racing|fis|slalom|giant slalom|gs|sl"),
)
# Labelled fields and "a park ski" / "this all-mountain ski" phrases only.
_TYPE_LABEL = re.compile(r"\b(?:category|best\s*use|terrain|ski\s*type|type)\s*[:\-–]\s*([a-z][a-z /&-]{2,40})", re.I)


def ski_types(product_type, tags, text):
    sources = [str(product_type or "")] + [str(tag) for tag in tags or ()]
    sources += [match.group(1) for match in _TYPE_LABEL.finditer(text)]
    found = []
    for label, words in SKI_TYPES:
        pattern = re.compile(r"\b(?:" + words + r")\b", re.I)
        if any(pattern.search(source) for source in sources):
            found.append(label)
    if not found:
        for label, words in SKI_TYPES:
            if label == "Race":
                continue  # "race" in prose is too loose
            if re.search(r"\b(?:a|an|the|this|our|versatile|playful)\s+(?:" + words + r")\s+(?:ski|skis|board)\b", text, re.I):
                found.append(label)
    return found


_WAIST = (
    re.compile(r"\b(\d{2,3})\s*mm\s*(?:at\s+the\s+|in\s+the\s+waist|underfoot|waist)", re.I),
    re.compile(r"\bwaist(?:[- ]width)?\s*(?:of\s*|:\s*|-\s*|=\s*)?(\d{2,3})\s*(?:mm)?\b", re.I),
    re.compile(r"\bunderfoot\s*[:\-]?\s*(\d{2,3})\s*mm", re.I),
)
_DIMENSIONS = re.compile(r"\b(\d{3})\s*[/-]\s*(\d{2,3})\s*[/-]\s*(\d{3})\b")


_WAIST_RANGE = re.compile(r"\bwaist(?:[- ]width)?\s*:\s*(\d{2,3})\s*[-–]\s*(\d{2,3})\s*mm", re.I)


def waist_widths(text):
    found = set()
    # A store's range tag ("Skis-Waist Width: 96-110mm") covers low..high-1.
    for low, high in _WAIST_RANGE.findall(text):
        found.update((int(low), int(high) - 1))
    text = _WAIST_RANGE.sub(" ", text)
    for pattern in _WAIST:
        found.update(int(value) for value in pattern.findall(text))
    for tip, waist, tail in _DIMENSIONS.findall(text):
        if int(tip) > int(waist) < int(tail):
            found.add(int(waist))
    return sorted(width for width in found if 60 <= width <= 140)


def waist_range(mm):
    for top, label in ((84, "Under 85 mm"), (94, "85–94 mm"), (104, "95–104 mm"), (114, "105–114 mm")):
        if mm <= top:
            return label
    return "115 mm and wider"


_RADIUS = (
    re.compile(r"\b(?:turn(?:ing)?\s+)?radius\s*(?:\([^)]{0,20}\))?\s*[:=\-]?\s*(?:of\s*)?(\d{1,2}(?:\.\d)?)\s*m\b", re.I),
    re.compile(r"\bradius\s*\((\d{1,2}(?:\.\d)?)\s*m\)", re.I),
    re.compile(r"\b(\d{1,2}(?:\.\d)?)\s*m\s+(?:turn(?:ing)?\s+)?radius\b", re.I),
)


def turn_radii(text):
    found = set()
    for pattern in _RADIUS:
        found.update(float(value) for value in pattern.findall(text))
    return sorted(radius for radius in found if 5 <= radius <= 40)


def radius_range(metres):
    if metres < 16:
        return "Short (under 16 m)"
    if metres <= 20:
        return "Medium (16–20 m)"
    return "Long (over 20 m)"


ROCKER = (
    ("Full Rocker", r"full[- ]rocker|reverse[- ]camber|fully[- ]rockered"),
    ("Rocker / Camber / Rocker", r"rocker[ /-]+camber[ /-]+rocker|tip(?:\s*(?:&|and)\s*|\s*/\s*)tail\s+rocker|rocker(?:ed)?\s+tip\s+(?:&|and)\s+tail|double\s+rocker|twin\s+rocker|(?:ar|all[- ]?mountain|freestyle|freeride)\s+rocker"),
    ("Tip Rocker / Camber", r"tip\s+rocker|rocker[ /-]+camber\b|early[- ]rise\s+tip"),
    ("Full Camber", r"full[- ]camber|traditional\s+camber|full\s+length\s+camber|camber\s+profile"),
)


def rocker_profile(text):
    for label, words in ROCKER:
        if re.search(r"\b(?:" + words + r")\b", text, re.I):
            return label
    return None


_FLAT = re.compile(r"\bflat\s+ski\b|\bbindings?\s+not\s+included\b|\bno\s+bindings?\b|\bwithout\s+(?:a\s+)?bindings?\b", re.I)
_WITH_BINDING = re.compile(r"\bw/\s*[^,;]{0,40}\bbinding|\bwith\s+[^,;]{0,40}\bbindings?\b|\bbindings?\s+included\b|\bsystem\s+ski\b", re.I)


_BINDING_TAG = re.compile(r"\bwith\s*bindings?\s*:\s*(yes|no)\b", re.I)


def bindings(title, text):
    """"Included" or "Flat (no bindings)", from the title first."""
    tag = _BINDING_TAG.search(text or "")
    if tag:
        return "Included" if tag.group(1).casefold() == "yes" else "Flat (no bindings)"
    for source in (title, text):
        if _FLAT.search(source or ""):
            return "Flat (no bindings)"
        if _WITH_BINDING.search(source or ""):
            return "Included"
    return None


# ---- boots -------------------------------------------------------------------

_LAST = (
    re.compile(r"\b(\d{2,3})\s*mm\s+last\b", re.I),
    re.compile(r"\blast(?:\s*width)?\s*[:=\-]\s*(\d{2,3})\s*(?:mm)?\b", re.I),
)


def last_widths(text):
    found = set()
    for pattern in _LAST:
        found.update(int(value) for value in pattern.findall(text))
    return sorted(width for width in found if 90 <= width <= 110)


def last_range(mm):
    if mm <= 98:
        return "Narrow (98 mm and under)"
    if mm <= 101:
        return "Medium (99–101 mm)"
    return "Wide (102 mm and over)"


_STATED_FLEX = (
    re.compile(r"\bflex(?:\s*index|\s*rating)?\s*[:=\-]\s*(\d{2,3})\b", re.I),
    re.compile(r"\b(\d{2,3})\s+flex\b", re.I),
)
_MODEL_FLEX = re.compile(r"(?<![\d.])(\d{2,3})(?![\d.])")


def flex(title, text):
    """(flex, how) with how "stated" or "model"; (None, None) when unknown."""
    for pattern in _STATED_FLEX:
        values = {int(value) for value in pattern.findall(text) if 40 <= int(value) <= 150}
        if len(values) == 1:
            return values.pop(), "stated"
    numbers = [int(value) for value in _MODEL_FLEX.findall(re.sub(r"\b20\d\d\b", " ", title or ""))]
    numbers = [value for value in numbers if 50 <= value <= 150 and value % 5 == 0]
    if len(numbers) == 1:
        return numbers[0], "model"
    return None, None


def flex_range(value):
    if value < 80:
        return "Soft (under 80)"
    if value <= 100:
        return "Medium (80–100)"
    if value <= 120:
        return "Stiff (105–120)"
    return "Very stiff (over 120)"


SOLES = (
    ("GripWalk", r"grip\s*walk|\bgw\b"),
    ("Alpine (ISO 5355)", r"iso\s*5355|alpine\s+din|din\s+5355"),
    ("Touring (ISO 9523)", r"iso\s*9523|touring\s+sole"),
    ("Tech / Pin inserts", r"tech\s+(?:inserts|fittings|binding\s+compatible)|pin\s+binding|dynafit\s+inserts"),
    ("WTR", r"\bwtr\b|walk\s*to\s*ride"),
    ("MNC", r"\bmnc\b|multi[- ]norm"),
)


def soles(text):
    return [label for label, words in SOLES if re.search(words, text, re.I)]


_WALK = re.compile(r"\b(?:ski\s*/\s*walk|ski\s*/\s*hike|walk\s*mode|hike\s*mode|walk\s*lever|hike\s*lever)\b", re.I)


def walk_mode(text):
    return "Walk mode" if _WALK.search(text) else None


# ---- bindings -----------------------------------------------------------------

_STATED_DIN = re.compile(r"\bdin(?:\s*range|\s*setting)?\s*[:=\-]?\s*(\d{1,2}(?:\.\d)?)\s*(?:-|–|to)\s*(\d{1,2}(?:\.\d)?)\b", re.I)
_MODEL_DIN = re.compile(r"(?<![\d.])(\d{1,2})(?![\d.])")


def din(title, text):
    """(max DIN, how): a stated range's top ("DIN: 4-13"), else the model
    number in a binding's name ("Look Pivot 15", "Strive 12"), by convention."""
    stated = {float(high) for _, high in _STATED_DIN.findall(text) if 3 <= float(high) <= 20}
    if len(stated) == 1:
        return stated.pop(), "stated"
    numbers = [int(value) for value in _MODEL_DIN.findall(re.sub(r"\b20\d\d\b", " ", title or ""))]
    numbers = [value for value in numbers if 3 <= value <= 20]
    if len(numbers) == 1:
        return float(numbers[0]), "model"
    return None, None


def din_range(value):
    if value <= 10:
        return "Up to 10"
    if value <= 13:
        return "11–13"
    return "14 and up"


_BRAKE = re.compile(r"\b(\d{2,3})\s*mm\s+brake(?:\s*width)?\b|\bbrake(?:\s*width)?\s*[:=\-]\s*(\d{2,3})\s*mm", re.I)


def brake_widths(text):
    found = set()
    for first, second in _BRAKE.findall(text):
        value = int(first or second)
        if 70 <= value <= 140:
            found.add(value)
    return sorted(found)


# ---- per listing -------------------------------------------------------------

def fields(part, title, product_type, tags, text):
    """{filter key: [values]} for one listing; empty keys are left out."""
    title = title or ""
    # Tags count as stated specs too ("Skill Level: Advanced", "Skis-Waist Width: 96-110mm").
    tag_text = " ; ".join(str(tag) for tag in tags or ())
    text = " ".join((str(text or "") + " ; " + tag_text).split())
    found = {}

    def put(key, values):
        values = [value for value in (values if isinstance(values, (list, tuple)) else [values]) if value]
        if values:
            found[key] = sorted(set(values), key=values.index)

    if part == "Skis":
        put("ski_type", ski_types(product_type, tags, text))
        put("waist", [waist_range(mm) for mm in waist_widths(text)])
        put("radius", [radius_range(metres) for metres in turn_radii(text)])
        put("rocker", rocker_profile(text))
        put("bindings", bindings(title, text))
    elif part == "Boots":
        put("ski_type", ski_types(product_type, tags, text))
        put("last", [last_range(mm) for mm in last_widths(text)])
        value, how = flex(title, text)
        if value:
            put("flex", flex_range(value))
        put("sole", soles(title + " " + text))
        put("walk", walk_mode(text))
    elif part == "Bindings":
        put("ski_type", ski_types(product_type, tags, text))
        value, how = din(title, text)
        if value:
            put("din", din_range(value))
        put("brake", [f"{mm} mm" for mm in brake_widths(text)])
        put("sole", soles(title + " " + text))
    elif part in ("Helmets", "Protection"):
        from sports import protection
        found.update(protection.fields(title, product_type, text, "ski", default="Helmets" if part == "Helmets" else None))
    put("ability", ability(text))
    return found
