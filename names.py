"""Tidy product names for the cards (audit 2026-11-12).

* ALL-CAPS names ("SUNDAY NIGHTSHIFT FRAME", 51 listings at Albe's, Powers,
  The House and The Lost Co.) read in title case. Acronyms, model codes and
  sizes keep their capitals ("MIPS", "RHD", "V2", "ZX", "1-1/8").
* Names over 90 characters that list specs after a dash ("Schwalbe
  Shredda Front Tire - 29 x 2.50, Tubeless, Folding, Black, Evolution Line,
  Gravity Pro, Addix Ultra Soft, Radial, E-50") drop specs from the end
  until they fit, keeping at least two. Shorter names keep every word, so
  sizes and drive sides that tell listings apart stay.
* An ALL-CAPS name's long bracketed note ("(INCLUDES 14T UPPER AND 16T
  LOWER ...)") is dropped; other names keep theirs ("with vMotion 10 GW
  Lady System Bindings").

Only the shown name changes; the link, prices and specs are the store's.
"""

import re

# Words that stay in capitals when an ALL-CAPS name is title-cased.
ACRONYMS = {
    "BMX", "MTB", "MIPS", "RHD", "LHD", "OEM", "PC", "DH", "XC", "AXS", "SRAM", "DT", "USA", "UK", "TCS", "GW", "BOA",
    "CA", "HV", "LV", "MV", "TI", "ID", "SL", "XL", "XXL", "XS", "SM", "MD", "LG", "UL", "CTD", "HD", "LED", "ABS",
    "DNA", "GT", "SE", "BSD", "KMC", "FSA", "ZX", "VX", "FX", "CR", "XLT", "PVC", "TPU", "CNC", "OS", "XD", "HG",
    "MS", "RS", "SS", "LT", "ST", "EX", "SX", "NX", "GX", "XO", "XX", "SPD", "DIN", "MX", "CF", "AL", "AM", "BB",
    "FC", "II", "III", "IV", "VI", "WTP", "S&M", "WD", "NOS", "KHE", "YKK", "D3O", "DOT", "CPSC", "EN", "ASTM", "EVOC",
}
SMALL = {"a", "an", "and", "as", "at", "by", "for", "in", "of", "on", "or", "the", "to", "w/", "with", "x"}

_LETTERS = re.compile(r"[A-Za-z]")
_LONG_NOTE = re.compile(r"\s*\((?=[^)]{30,}\))[^)]*\)")


def is_all_caps(name):
    letters = "".join(_LETTERS.findall(str(name or "")))
    return len(letters) > 8 and letters.isupper()


def _word(word, first):
    core = word.strip("()[],.:;\"'")
    if not core or not _LETTERS.search(core):
        return word
    if not first and core.lower() in SMALL:
        return word.replace(core, core.lower())
    if core.upper() in ACRONYMS or re.search(r"\d", core):
        return word
    # Short codes with no vowel stay in capitals: "XP 10", "BFC".
    if len(core) <= 3 and not re.search(r"[AEIOUY]", core.upper()):
        return word
    # Hyphenated and slashed parts each get a capital: "SHIN/ANKLE" ->
    # "Shin/Ankle"; an apostrophe stays inside its word: "WOMEN'S" -> "Women's".
    fixed = re.sub(r"[A-Za-z]+(?:'[A-Za-z]+)?", lambda m: m.group(0).upper() if m.group(0).upper() in ACRONYMS
                   else m.group(0)[0].upper() + m.group(0)[1:].lower(), core)
    return word.replace(core, fixed)


def title_case(name):
    words = str(name or "").split(" ")
    return " ".join(_word(word, index == 0) for index, word in enumerate(words))


LIMIT = 90  # characters; the card shows about three lines


def trim_specs(name, limit=LIMIT):
    """A name over ``limit`` characters that lists specs after its last
    " - " ("Tire - 29 x 2.50, Tubeless, Folding, Black, ...") loses specs
    from the end until it fits, keeping at least two. Shorter names, and
    names without such a list, are left as they are."""
    text = str(name or "").strip()
    if len(text) <= limit:
        return text
    head, dash, tail = text.rpartition(" - ")
    if not dash or not head:
        return text
    specs = [part.strip() for part in tail.split(",") if part.strip()]
    if len(specs) < 3:
        return text
    while len(specs) > 2 and len(f"{head} - {', '.join(specs)}") > limit:
        specs.pop()
    return f"{head} - {', '.join(specs)}"


def tidy(name):
    text = " ".join(str(name or "").split())
    if is_all_caps(text):
        # A shouted name's long bracketed note is shouted packaging text:
        # "(INCLUDES 14T UPPER AND 16T LOWER BLACK METAL SPIDER PULLEY, ...)".
        text = title_case(_LONG_NOTE.sub("", text).strip())
    return trim_specs(text)


def tidy_items(data):
    """Tidy every listing's name in place; returns how many changed."""
    changed = 0
    for items in (data or {}).values():
        for item in items or []:
            if isinstance(item, dict) and item.get("name"):
                tidier = tidy(item["name"])
                if tidier != item["name"]:
                    item["name"] = tidier
                    changed += 1
    return changed
