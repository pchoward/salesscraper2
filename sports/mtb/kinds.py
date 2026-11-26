"""MTB product types inside each heading, and Tools & Care (owner, 2026-11-26).

Bike shops keep spares inside their category as their own type (Powers'
Braking: Brake Kits, Brake Parts, Pads, Levers; Source's Wheel Parts: Hubs,
Hub Spares; Circuit's Hubs, Hub Parts, Drivers). So every MTB heading keeps
its parts, and a Type filter separates the thing itself (Forks, Hubs,
Cranks) from its parts (Fork parts, Hub parts, Drivetrain parts). Tools,
pumps, lubes and cleaners from any heading are shown under Tools & Care.

``kind(part, title, product_type)`` gives the type, or None for headings
that have no types (Bikes, Frames, gear). The store's own product type is
read first ("Fork Parts", "Seal Kit", "Disc Brake Rotors"); the title
decides when it is vague ("Parts", "Fanatik Outlet"). A listing is a whole
fork, shock, wheel or crank only when its name reads like one, so kits and
adapters don't slip in.
"""

import re

TOOLS_AND_CARE = "Tools & Care"

# Tools, pumps, lubes and cleaners, from any heading. A rebuild, service or
# tune kit that mentions oil or a tool is still a part.
_CARE_TYPE = re.compile(r"\b(?:tools?|pumps?|lubes?|lubricants?|greases?|cleaners?|degreasers?|polish|wax|oil|bleed\s*kits?"
                        r"|fluids?|work\s*stands?|workstands?|repair\s*stands?|tire\s*levers?|maintenance)\b", re.I)
_CARE_NAME = re.compile(r"\b(?:tools?|tool\s*kit|multi-?tools?|pumps?|floor\s*pump|shock\s*pump|inflators?|co2"
                        r"|lubes?|lubricants?|greases?|degreasers?|cleaners?|wash|chain\s*(?:checker|wear|breaker|brute)"
                        r"|bleed\s*kit|brake\s*fluid|dot\s*[345](?:\.1)?\b|torque\s*(?:wrench|driver|key)"
                        r"|work\s*stand|repair\s*stand|bead\s*(?:breaker|seater)|tire\s*(?:seater|levers?)"
                        r"|wrench|spoke\s*key|cassette\s*(?:lockring\s*)?tool|chain\s*whip|truing\s*stand)\b", re.I)
_STILL_A_PART = re.compile(r"\b(?:rebuild|service|tune|upgrade|damper|replacement|internals)\b", re.I)


def is_tools_and_care(title, product_type=""):
    kind = str(product_type or "")
    name = str(title or "")
    if _CARE_TYPE.search(kind) and not re.search(r"\b(?:parts?|hangers?)\b", kind, re.I):
        return True
    return bool(_CARE_NAME.search(name)) and not _STILL_A_PART.search(name)


# Words that make a listing a part or spare rather than the thing itself.
_PARTISH = re.compile(
    r"\b(?:kits?|adapters?|adaptors?|conversion|tune|shims?|seals?|wipers?|foam\s*rings?|o-?rings?|service|rebuild"
    r"|bushings?|spacers?|tokens?|volume|bolts?|screws?|nuts?|washers?|hardware|decals?|stickers?|remotes?|lockout"
    r"|cartridge|ifp|air\s*(?:spring|shaft|piston|can)|lowers?|lower\s*legs?|csu|crown|top\s*caps?|caps?|knobs?|dials?"
    r"|internals|reducers?|eyelet|fenders?|guards?|axles?|replacement|spare|spares|upgrade|mounting|mounts?|clamps?"
    r"|bearings?|pawls?|drivers?|freehub|end\s*caps?|springs?|cables?|housing|hoses?|barbs?|olives?|ferrules?"
    r"|lever\s*blades?|blades?|pistons?|pulleys?|jockey|cages?|hangers?|boots?|covers?|plugs?|inserts?|shields?"
    r"|bands?|straps?|pins?|parts?)\b", re.I)


def _partish(title, product_type):
    kind = str(product_type or "").lower()
    if re.search(r"\b(?:parts?|service|seal|hardware|bolts?|decals?|remote|small\s*parts?|spares?|accessor(?:y|ies))\b", kind):
        return True
    return bool(_PARTISH.search(str(title or "")))


def _has(pattern, text):
    return bool(re.search(pattern, text or "", re.I))


# ---- Suspension ----------------------------------------------------------

_FORKY = r"\bforks?\b|\b(?:pike|lyrik|zeb|domain|judy|bomber|sid|recon|boxxer|yari|revelation|onyx|ribbon|psylo)\b|\bfox\s*(?:3[2-8]|40)\b"
_SHOCKY = r"\bshocks?\b|\b(?:vivid|deluxe|monarch|float\s*x2?|dhx2?|kage|jade|db\s*(?:air|coil|inline)|super\s*deluxe)\b"
_WHOLE_FORK = re.compile(r"\bfork\b\s*(?:-|\(oem\)|$)|\b(?:26|27\.5|29)\s*(?:\"|in|er|`)?.*\b\d{2,3}\s*mm\b|\bsuspension\s+forks?\b"
                         r"|\b(?:26|27\.5|29)\s*(?:\"|in|er)?\s*$", re.I)
_WHOLE_SHOCK = re.compile(r"\b\d{3}\s*x\s*\d{2}(?:\.\d)?\b|\brear\s+shock\s*(?:-|$)", re.I)


def _suspension(title, product_type):
    kind, name = str(product_type or "").lower(), str(title or "")
    forky = _has(_FORKY, name) or "fork" in kind
    shocky = _has(_SHOCKY, name) or "shock" in kind
    if (_has(r"\bsprings?\b", name) or "spring" in kind) and not _has(r"\b(?:conversion|air\s*spring|debonair|upgrade)\b", name):
        return "Coil Springs"
    named_part = bool(_PARTISH.search(re.sub(r"(?i)\bsprings?\b", "", name)))
    if forky and not "shock" in kind and _WHOLE_FORK.search(name) and not named_part:
        return "Forks"
    if shocky and _WHOLE_SHOCK.search(name) and not named_part:
        return "Rear Shocks"
    if _partish(name, kind):
        return "Shock Parts" if ("shock" in kind or (shocky and not forky)) else "Fork Parts"
    if "shock" in kind or (shocky and not forky):
        return "Rear Shocks"
    return "Forks" if forky else "Fork Parts"


# ---- Wheels --------------------------------------------------------------

def _wheels(title, product_type):
    kind, name = str(product_type or "").lower(), str(title or "")
    text = kind + " " + name
    if _has(r"\btubeless\s*(?:tape|valves?)|\brim\s*(?:tape|strips?)\b|\bvalves?\b|\bvalve\s*cores?\b", text):
        return "Rim Tape & Valves"
    if _has(r"\bspokes?\b|\bnipples?\b", text) and not _has(r"\bwheels?\b|\bwheelsets?\b", name):
        return "Spokes"
    if _has(r"\bdrivers?\b|\bfreehub\b|\bcassette\s*bod(?:y|ies)\b|\bhub\s*parts?\b|\baxles?\b|\bend\s*caps?\b|\bpawls?\b|\bbearings?\b|\bratchet\b"
            r"|\bskewers?\b|\bthru[-\s]?axles?\b|\bdecals?\b|\bconversion\b|\bhub\s*(?:spares?|kit)\b", text) \
            and not _has(r"\bwheelsets?\b|\bwheels?\b(?!\s*(?:bearing|axle))", name):
        return "Hub Parts"
    if _has(r"\bwheelsets?\b|\bwheels?\b", text) and not _has(r"\bpulley\s*wheel", name):
        return "Wheels"
    if _has(r"\bhubs?\b|\bhubset\b", text):
        return "Hubs"
    if _has(r"\brims?\b", text):
        return "Rims"
    return "Hub Parts" if _partish(name, kind) else "Wheels"


# ---- Tires ---------------------------------------------------------------

def _tires(title, product_type):
    kind, name = str(product_type or "").lower(), str(title or "")
    text = kind + " " + name
    if _has(r"\btubes?\b", text) and not _has(r"\btubeless\b", text):
        return "Tubes"
    if _has(r"\bsealant\b|\bplugs?\b|\bliners?\b|\binserts?\b|\bpatch(?:es)?\b|\brepair\b|\btubeless\s*accessor|\bvalves?\b", text):
        return "Tubeless & Repair"
    return "Tires"


# ---- Drivetrain ----------------------------------------------------------

_DRIVE = (
    ("Groupsets", r"\bgroup\s*sets?\b|\bgroupsets?\b|\bgroup\b|\bbuild\s*kit\b|\bupgrade\s*kit\b(?=.*\b(?:eagle|transmission|axs)\b)"),
    ("Derailleurs", r"\bderailleurs?\b|\bmech\b"),
    ("Shifters", r"\bshifters?\b|\bshift\s*levers?\b|\btrigger\b|\bcontrollers?\b|\bpods?\b"),
    ("Cassettes", r"\bcassettes?\b|\bcogs?\b|\bxg-?\d{3,4}\b|\bcs-[a-z]*\d"),
    ("Chains", r"\bchains?\b(?!\s*(?:guides?|rings?|device|checker|keeper|stay|tensioner))"),
    ("Chainrings", r"\bchain\s*rings?\b|\bchainrings?\b|\brings?\b|\b\d{2}\s*t\b(?!.*\bcassette)"),
    ("Cranks", r"\bcranks?(?:sets?|\s*arms?)?\b|\bcrankset\b"),
    ("Bottom Brackets", r"\bbottom\s*brackets?\b|\bbb\b|\bdub\s*(?:bb|bottom)|\bpressfit\b|\bbsa\b|\bt47\b"),
    ("Chain Guides", r"\bchain\s*guides?\b|\bchain\s*devices?\b|\bbash\s*guards?\b|\bbashguards?\b|\btaco\b"),
)
# Store types that name a part bin ("Derailleur Parts", "Crank Parts",
# "Derailleur Hangers"). A bare "Parts" (Bikes Online files everything
# there) says nothing, so the name decides.
_DRIVE_PART_TYPE = r"\b(?:derailleur|crank|shifter|chain|cassette|bottom\s*bracket|bb|drivetrain)\s*(?:parts?|spares?|small\s*parts?)\b|\bhangers?\b|\blinks\b|\bcables?\b|\bhousing\b"
# Words that always make a drivetrain listing a part: kits, pulleys, chain
# links and pins, hangers, boots. Soft words (clamp, spindle, a bolt count,
# I-Spec, cage) describe a whole crank, shifter or derailleur when the name
# also names one ("8-bolt Chainring", "High Clamp Front Derailleur").
_DRIVE_STRONG = (r"\bkits?\b|(?<!\d-)(?<!\d\s)(?<!\d)\bbolts?\b|\bscrews?\b|\bboots?\b|\bpulleys?\b|\bjockey\b"
                 r"|\binner\s*cage\b|\bcage\s*(?:kit|assembly|plate)\b|\bhangers?\b|\bcovers?\b|\bspacers?\b|\blockrings?\b"
                 r"|\bquick-?\s*links?\b|\bmissing\s*links?\b|\bchain\s*links?\b|\bpower\s*lock\s*link\b|\blink\b(?!s)"
                 r"|\b(?:chain|connecting|joining)\s*pins?\b|\badapters?\b|\bconnectors?\b|\bbatter(?:y|ies)\b|\bchargers?\b"
                 r"|\bferrules?\b|\bcables?\b|\bhousing\b|\bpreload\b|\bguards?\b(?=.*\bcrank)|\breplacement\b|\bparts?\b"
                 r"|\bbearings?\b(?!.*\bbottom\s*bracket)|\bdecals?\b|\bmatchmaker\b")
_DRIVE_SOFT = r"\bclamps?\b|\bbands?\b|\bspindles?\b|\bi-?spec\b|\bcage\b|\bmounts?\b"
_DRIVE_WHOLE = r"\bcranks?(?:sets?|\s*arm\s*sets?)?\b|\bderailleurs?\b|\bshifters?\b|\bchainrings?\b|\bchains?\b|\bcassettes?\b|\bbottom\s*brackets?\b|\bgroupsets?\b"


def _drivetrain(title, product_type):
    kind, name = str(product_type or "").lower(), str(title or "")
    # "Chain w/ Quick Link", "126 Links", "Hollow Pin Chain": a whole chain.
    if _has(r"\bchain\b.*\bw/|\b\d+\s*links\b|\bhollow\s*pin\b|\bhollowpin\b", name) and _has(r"\bchains?\b", name) \
            and not _has(r"^(?:(?!\bchain\b).)*\blink\b.*\bchain\b", name):
        return "Chains"
    if _has(_DRIVE_STRONG, name):
        return "Drivetrain Parts"
    # A part bin type ("Crank Parts") with a name that names a whole item
    # ("X1 1400 Crankset") is the store's filing slip; the name wins.
    if _has(_DRIVE_PART_TYPE, kind) and not _has(_DRIVE_WHOLE, name):
        return "Drivetrain Parts"
    if _has(_DRIVE_SOFT, name) and not _has(_DRIVE_WHOLE, name):
        return "Drivetrain Parts"
    vague = not kind.strip() or _has(r"^\s*(?:parts?|sale|fanatik outlet|bundles?)\s*$", kind)
    if not vague:
        for label, words in _DRIVE:
            if _has(words, kind):
                return label
    for label, words in _DRIVE:
        if _has(words, name):
            return label
    return "Drivetrain Parts"


# ---- Brakes --------------------------------------------------------------

def _brakes(title, product_type):
    kind, name = str(product_type or "").lower(), str(title or "")
    text = kind + " " + name
    whole_brake = _has(r"\bdisc\s*brakes?\b(?!\s*(?:pads?|rotors?|adapt|levers?\s*(?:blade|clamp|parts?)|parts?|hose))"
                       r"|\bbrake\s*(?:set|kit)\b|\bv-?brakes?\b|\bcalipers?\b(?!\s*(?:pistons?|bolts?|parts?))", name)
    if _has(r"\bpads?\b|\bbrake\s*shoes?\b", name) and not _has(r"\bwith\b.*\bpads?\b|\bpad\s*(?:spring|pins?|retainer|bolts?)\b", name):
        return "Pads"
    if _has(r"\bpads?\b", kind) and not whole_brake:
        return "Pads"
    if (_has(r"\brotors?\b|\bdiscs?\b(?!\s*brake)", name) or _has(r"\brotors?\b", kind)) \
            and not _has(r"(?<!\d-)(?<!\d)\bbolts?\b|\blockrings?\b|\badapt(?:er|or)s?\b", name):
        return "Rotors"
    part_words = (r"\badapt(?:er|or)s?\b|\bhoses?\b|\bbarbs?\b|\bolives?\b|(?<!\d-)(?<!\d)\bbolts?\b|\blockrings?\b|\bblades?\b"
                  r"|\binternals\b|(?<!brake\s)\bkits?\b|\bpistons?\b|\breservoir\b|\bbladder\b|\bclamps?\b|\bcables?\b|\bhousing\b"
                  r"|\bspacers?\b|\bpins?\b|\bsprings?\b|\breplacement\b|\bparts?\b|\bcovers?\b|\bmounts?\b(?!\s*disc)|\bassembly\b|\bferrules?\b|\bmagnets?\b|\bsensors?\b")
    if _has(part_words, name) and not (whole_brake and not _has(r"\bparts?\b|\breplacement\b|\binternals\b|\bblades?\b|\bassembly\b|\bhoses?\b", name)):
        return "Brake Parts"
    if _has(r"\bparts?\b|\badapt|\bhoses?\b|\bcables?\b|\bhousing\b|\bsmall\b", kind) and not whole_brake:
        return "Brake Parts"
    if _has(r"\blevers?\b", text) and not whole_brake:
        return "Levers"
    return "Brakes"


# ---- Cockpit -------------------------------------------------------------

def _cockpit(title, product_type):
    kind, name = str(product_type or "").lower(), str(title or "")
    text = kind + " " + name
    parts = (r"\bparts?\b|\bsmall\b|\baccessor(?:y|ies)\b|\btop\s*caps?\b|\bstem\s*caps?\b|\bspacers?\b|\bstar\s*nut\b|\bcompression\s*plug\b"
             r"|\bcups?\b|\bcrown\s*races?\b|\bbearings?\b|\bremotes?\b|\blevers?\b|\bhoses?\b|\bbarbs?\b|\bcartridge\b|\bservice\b"
             r"|\bkits?\b|\bclamps?\b|\bcollars?\b|\bbolts?\b|\bplugs?\b|\bend\s*caps?\b|\bbar\s*ends?\b|\bshims?\b|\bheads?\b(?=.*\bseatpost)"
             r"|\blights?\b|\bmounts?\b(?!.*\bstem\b)|\bcovers?\b|\bbags?\b|\bbells?\b|\block\s*nuts?\b|\bnuts?\b|\bbinder\b|\bstorage\b")
    if _has(r"\bgrips?\b", text) and not _has(r"\bparts?\b|\bclamps?\b|\bcollars?\b|\bend\s*caps?\b", name):
        return "Grips"
    if _has(r"\bsaddles?\b|\bseats?\b(?!\s*(?:post|clamp|collar|binder))", text) \
            and not _has(r"\bparts?\b|\brails?\s*kit\b|\bcovers?\b|\bclamps?\b|\bbinder\b|\bbolts?\b|\bbags?\b", name):
        return "Saddles"
    # A bare "Parts" type (Bikes Online files everything there) says
    # nothing; a bolt count ("2-Bolt Stem") describes the whole item.
    vague = _has(r"^\s*(?:parts?|sale|bundles?)\s*$", kind)
    named = re.sub(r"(?i)\b\d\s*-?\s*bolt\b|\b\d{2}(?:\.\d)?\s*mm\s*clamp\b|\b(?:no|without|w/o)\s+remote\b", "", name)
    if (not vague and _has(parts, kind)) or _has(parts, named):
        whole = (("Dropper Posts", r"\bdropper\b.*\bposts?\b|\bdropper\s*seat\s*posts?\b|\bdropper\b\s*(?:-|$)",
                  r"\bremotes?\b(?!.*\bdropper\s*(?:seat\s*)?post\b)|\bparts?\b|\bkits?\b|\bservice\b|\bcartridge\b|\blevers?\b"),
                 ("Handlebars", r"\bhandlebars?\b|\briser\s*bars?\b", r"\bend\s*caps?\b|\bplugs?\b|\bbar\s*ends?\b|\bparts?\b|\bkits?\b|\bmounts?\b|\blights?\b|\bcovers?\b|\bbags?\b"),
                 ("Seatposts", r"\bseat\s*posts?\b|\bseatposts?\b", r"\bclamps?\b|\bbinder\b|\bcollars?\b|\bheads?\b|\bparts?\b|\bkits?\b|\bbolts?\b|\bremotes?\b|\bservice\b"),
                 ("Stems", r"\bstems?\b", r"\bcaps?\b|\bspacers?\b|\bparts?\b|\bkits?\b|\bbolts?\b|\bfaceplates?\b"),
                 ("Headsets", r"\bheadsets?\b", r"\bparts?\b|\bcups?\b|\bspacers?\b|\btop\s*caps?\b|\bcrown\s*races?\b|\bbearings?\b|\bstar\s*nut\b|\bcompression\b|\bangleset\s*cup\b"))
        for label, words, partwords in whole:
            if _has(words, named) and not _has(partwords, named) and (vague or not _has(r"\bparts?\b|\bsmall\b|\baccessor", kind)):
                return label
        return "Cockpit Parts"
    if _has(r"\bdropper\b", text):
        return "Dropper Posts"
    if _has(r"\bseat\s*posts?\b|\bseatposts?\b|\bposts?\b", text):
        return "Seatposts"
    if _has(r"\bstems?\b", text):
        return "Stems"
    if _has(r"\bheadsets?\b|\bangleset\b", text):
        return "Headsets"
    if _has(r"\bhandlebars?\b|\bbars?\b|\briser\b", text):
        return "Handlebars"
    return "Cockpit Parts"


_BY_PART = {
    "Forks & Shocks": _suspension,
    "Wheels": _wheels,
    "Tires": _tires,
    "Drivetrain": _drivetrain,
    "Brakes": _brakes,
    "Cockpit": _cockpit,
    # Pedals has no Type: its Pedal type filter already splits flats,
    # clipless, cleats and parts (sports/mtb/specs.py).
}

# Type values per store category, in the order the filter lists them.
ORDER = {
    "Forks & Shocks": ("Forks", "Rear Shocks", "Coil Springs", "Fork Parts", "Shock Parts"),
    "Wheels": ("Wheels", "Hubs", "Rims", "Spokes", "Hub Parts", "Rim Tape & Valves"),
    "Tires": ("Tires", "Tubes", "Tubeless & Repair"),
    "Drivetrain": ("Groupsets", "Cranks", "Chainrings", "Chains", "Cassettes", "Derailleurs", "Shifters",
                   "Bottom Brackets", "Chain Guides", "Drivetrain Parts"),
    "Brakes": ("Brakes", "Levers", "Pads", "Rotors", "Brake Parts"),
    "Cockpit": ("Handlebars", "Stems", "Grips", "Saddles", "Seatposts", "Dropper Posts", "Headsets", "Cockpit Parts"),
}
VALUES = tuple(dict.fromkeys(value for values in ORDER.values() for value in values))


# Brake pads and calipers some stores file under Wheels ("Rim Brake Parts",
# "COMPONENTS/BRAKES/RIM CALIPER") belong with Brakes.
_BRAKE_ITEM = re.compile(r"\bbrakes?\b|\bcalipers?\b|\bv-?brake\b|\bbrake\s*pads?\b", re.I)


def heading_part(part, title, product_type=""):
    """The store category a listing is shown under: its own, or Brakes for
    a brake item filed elsewhere."""
    if part in ("Wheels", "Cockpit", "Drivetrain") and (_BRAKE_ITEM.search(str(product_type or ""))
                                                       or _BRAKE_ITEM.search(str(title or ""))):
        if not re.search(r"\bwheels?\b|\bwheelsets?\b|\bhubs?\b|\brotors?\b(?=.*\bwheel)", str(title or ""), re.I):
            return "Brakes"
    if part == "Wheels" and re.search(r"\bpulley\b|\bderailleur\b|\bcage\s*assembly\b", f"{title} {product_type}", re.I):
        return "Drivetrain"
    return part


def kind(part, title, product_type=""):
    """The listing's type within its store category, or None."""
    part = heading_part(part, title, product_type)
    sort = _BY_PART.get(part)
    if sort is None:
        return None
    try:
        return sort(title, product_type)
    except (TypeError, re.error):
        return None
