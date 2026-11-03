"""Protection filters shared by BMX, MTB and Ski (owner, 2026-11-03): what a
piece protects (helmets and each body part), the helmet's style, and its
rotational-impact system. Read from the title and store type first, then the
description, so "Knee/Shin/Ankle Combo" counts under all three.

Values are stated in the listing's own words, never guessed from a model name.
"""

import re

# Body part / kind, in sidebar order. Each pattern is matched against the
# title + store product type; several can apply (combo pads, pad sets).
PARTS = (
    ("Helmets", r"\bhelmets?\b|\bfull[- ]?face\b|\bbrain\s*buckets?\b"),
    ("Goggles", r"\bgoggles?\b|\bgoggle\s+lens(?:es)?\b"),
    ("Neck", r"\bneck\s*(?:brace|braces|guard|guards|roll|protector)s?\b"),
    ("Shoulders", r"\bshoulder\s*(?:pads?|guards?|protectors?|armou?r|supports?|braces?)\b"),
    ("Chest & Ribs", r"\bchest\s*(?:protectors?|guards?|plates?|pads?)\b|\broost\s*(?:guards?|deflectors?)\b"
                     r"|\brib\s*(?:protectors?|guards?|pads?)\b|\bbody\s*armou?r\b(?!\s*(?:underwear|shorts|pants))|\bpressure\s*suits?\b"
                     r"|\bpadded\s+(?:shirts?|tops?|jerseys?|jackets?|vests?|tees?)\b|\bprotective\s+(?:shirts?|tops?|jackets?|vests?)\b"
                     r"|\bupper\s*(?:body\s*)?(?:protective|protection|armou?r)\b"
                     r"|\bbody\s*protectors?\b|\bprotection\s+jackets?\b"),
    ("Back & Spine", r"\bback\s*(?:protectors?|guards?|plates?|pads?|armou?r)\b|\bspine\s*(?:protectors?|guards?|pads?)\b"
                     r"|\bprotector\s+vests?\b|\bprotective\s+vests?\b|\bspine\b|\bbody\s*protectors?\b"),
    ("Elbows", r"\belbows?\b|\barm\s*(?:pads?|guards?|protectors?)\b"),
    ("Forearms", r"\bforearms?\b"),
    ("Wrists", r"\bwrists?\s*(?:guards?|braces?|pads?|protectors?|wraps?|supports?)\b|\bwristguards?\b"),
    ("Gloves", r"\bgloves?\b|\bmitts?\b|\bmittens?\b"),
    ("Hips & Tailbone", r"\bhips?\s*(?:pads?|guards?|protectors?)\b|\btailbone\b|\bcrash\s*(?:pants|shorts)\b"
                        r"|\bimpact\s*(?:shorts|pants|liners?|underwear)\b|\barmou?r\s*(?:underwear|shorts|pants)\b"
                        r"|\bprotective\s*(?:shorts|pants|underwear)\b|\bbum\s*pads?\b"),
    ("Knees", r"\bknees?\b"),
    ("Shins", r"\bshins?\b"),
    ("Ankles", r"\bankles?\b"),
)
_PARTS = tuple((label, re.compile(pattern, re.I)) for label, pattern in PARTS)
_PAD_SET = re.compile(r"\bpad\s*-?sets?\b|\bpadsets?\b|\b(?:3|three)[- ]?(?:pc|piece|pack)\b|\bcombo\b", re.I)
# "Helmet Replacement Pads", "Visor", "Lens": parts for a piece, not the piece.
_SPARE = re.compile(r"\breplacement\b|\bspare\b|\bvisors?\b|\bpeaks?\b|\bliners?\b(?!\s*(?:shorts|pants))|\bcheek\s*pads?\b"
                    r"|\blens(?:es)?\b|\bstraps?\b|\bbuckles?\b|\bmount\b|\bparts?\b", re.I)

# Helmet style, from the title + type, then the description.
HELMET_STYLES = (
    ("Full face", r"\bfull[- ]?face\b|\bdownhill\s+helmet\b|\bdh\s+helmet\b|\bconvertible\b|\bchin\s*bar\b"),
    ("Dirt jump / BMX", r"\bdirt\s*jump\b|\bbmx\b|\bskate(?:board)?\b|\bdual[- ]certified\b|\bdj\s+helmet\b|\bbucket\b"),
    ("Trail / half shell", r"\b(?:mtb|mountain|trail|enduro|all[- ]?mountain|half[- ]?shell|open[- ]?face|xc)\b"),
    ("Snow", r"\bski\b|\bsnow(?:board)?\b"),
    ("Road / commuter", r"\broad\b|\bcommuter\b|\burban\b|\bcity\b|\brecreation(?:al)?\b"),
)
_HELMET_STYLES = tuple((label, re.compile(pattern, re.I)) for label, pattern in HELMET_STYLES)

# Rotational-impact systems, as named by their makers.
ROTATIONAL = (
    ("MIPS", r"\bmips\b"),
    ("Spherical", r"\bspherical\b"),
    ("WaveCel", r"\bwavecel\b"),
    ("Kineticore", r"\bkineticore\b"),
    ("SPIN", r"\bspin\b"),
    ("FLAD / 6D ODS", r"\bods\b|\b6d\b"),
)
_ROTATIONAL = tuple((label, re.compile(pattern, re.I)) for label, pattern in ROTATIONAL)

FIELD_KEYS = ("protects", "helmet_style", "rotational")


def _first(table, text):
    for label, pattern in table:
        if pattern.search(text):
            return label
    return None


def protects(title, product_type="", description=""):
    """The body parts / kinds a piece protects, in sidebar order."""
    text = f" {title or ''} ; {product_type or ''} "
    if re.search(r"\b(?:goggle|helmet)\s+parts\b|\bhelmet\s+bags?\b", text, re.I):
        return []  # spares and bags, not the piece
    # The title names the piece; the store's category ("Ankle & Wrist
    # Supports", "Knee & Shin Pads") only fills in when the title doesn't.
    found = [label for label, pattern in _PARTS if pattern.search(f" {title or ''} ")]
    if not found:
        found = [label for label, pattern in _PARTS if pattern.search(text)]
    if "Helmets" in found and _SPARE.search(title or ""):
        # A visor or replacement pads for a helmet is not a helmet.
        found.remove("Helmets")
    # "Goggle Replacement Lenses" / "Goggle Lens - Clear" are spares;
    # "Goggles with Bonus Lens" is a pair of goggles.
    lens_only = re.search(r"\b(?:replacement|spare)\s+lens", title or "", re.I) or (
        re.search(r"\blens(?:es)?\b", title or "", re.I) and not re.search(r"\bgoggles?\b(?!\s+lens)", title or "", re.I))
    if "Goggles" in found and lens_only:
        found.remove("Goggles")
        found.append("Goggle lenses")
    if not found and _PAD_SET.search(text):
        # "Saver Series Pad Set (3-Pack)": knees, elbows and wrists.
        found = ["Pad Sets"]
    elif _PAD_SET.search(title or "") and len(found) <= 1 and "Helmets" not in found:
        found.append("Pad Sets")
    if not found and description:
        # A vague title ("Fuse Omega") whose description says what it is.
        found = [label for label, pattern in _PARTS[:1] + _PARTS[2:] if pattern.search(str(description)[:400])][:2]
    return found


def helmet_style(title, product_type="", description="", sport=""):
    text = f" {title or ''} ; {product_type or ''} "
    if sport == "ski":
        # Snow helmets describe "all-mountain" skiing, not trail riding.
        return "Full face" if _HELMET_STYLES[0][1].search(text) else "Snow"
    style = _first(_HELMET_STYLES, text)
    if style is None and description:
        style = _first(_HELMET_STYLES, str(description)[:600])
    if style is None and sport == "ski":
        style = "Snow"
    return style


def rotational(title, product_type="", description=""):
    text = f" {title or ''} ; {product_type or ''} ; {str(description or '')[:800]} "
    return [label for label, pattern in _ROTATIONAL if pattern.search(text)]


def fields(title, product_type="", description="", sport="", default=None):
    """{filter key: [values]} for one protection listing. ``default`` names
    the kind when the store's category already says it (Ski "Helmets")."""
    found = {}
    # When the store's category already names the kind, its description is
    # not mined for others ("...pairs well with our gloves").
    kinds = (protects(title, product_type) or [default]) if default else protects(title, product_type, description)
    if kinds:
        found["protects"] = kinds
    if "Helmets" in kinds:
        style = helmet_style(title, product_type, description, sport)
        if style:
            found["helmet_style"] = [style]
        systems = rotational(title, product_type, description)
        if systems:
            found["rotational"] = systems
    return found


def facet_fields(prefix, categories):
    """The three sidebar fields for a sport, scoped to its protection categories."""
    return (
        {"key": "protects", "label": "Protects", "param": prefix + "_protects", "categories": tuple(categories)},
        {"key": "helmet_style", "label": "Helmet style", "param": prefix + "_helmet", "categories": tuple(categories)},
        {"key": "rotational", "label": "Rotational protection", "param": prefix + "_rotational",
         "categories": tuple(categories)},
    )
