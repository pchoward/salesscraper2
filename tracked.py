"""Which sneakers and accessories the sale report keeps.

The lists live in ``tracked.yaml`` so another model is a few lines, not a
code change. A missing or broken file matches nothing and the scrape still
finishes. Clothing, bags, and hats are rejected in ``filters.py``.
"""

import logging
import os
import re

logger = logging.getLogger("tracked")

DEFAULT_PATH = "tracked.yaml"
_PHRASE_CACHE = {}
_LOADED = {}


def _strip_comment(line):
    in_quote = False
    quote = ""
    for index, char in enumerate(line):
        if char in {'"', "'"}:
            if not in_quote:
                in_quote = True
                quote = char
            elif char == quote:
                in_quote = False
        elif char == "#" and not in_quote:
            return line[:index]
    return line


def _clean(value):
    return str(value or "").strip().strip('"').strip("'")


def parse_tracked(text):
    """Parse the tracked-catalog subset. Raises ValueError when it is broken."""
    sneakers = []
    phrases = []
    types = []
    excludes = []
    section = None
    mode = None
    current = None
    for raw_line in str(text or "").splitlines():
        line = _strip_comment(raw_line).rstrip()
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip(" "))
        stripped = line.strip()
        if indent == 0 and stripped.endswith(":"):
            if current:
                sneakers.append(current)
                current = None
            section = stripped[:-1]
            mode = None
            continue
        if section == "sneakers" and stripped.startswith("- id:"):
            if current:
                sneakers.append(current)
            current = {"id": _clean(stripped.split(":", 1)[1]), "all": [], "any": [], "brand": ""}
            mode = None
            continue
        if section == "sneakers" and current is not None and stripped.startswith("brand:"):
            current["brand"] = _clean(stripped.split(":", 1)[1])
            mode = None
            continue
        if section == "sneakers" and current is not None and stripped in ("all:", "any:"):
            mode = stripped[:-1]
            continue
        if section == "sneakers" and current is not None and mode in ("all", "any") and stripped.startswith("- "):
            current[mode].append(_clean(stripped[2:]))
            continue
        if section == "accessories" and stripped in ("phrases:", "types:", "exclude:"):
            mode = stripped[:-1]
            continue
        if section == "accessories" and mode in ("phrases", "types", "exclude") and stripped.startswith("- "):
            value = _clean(stripped[2:])
            if not value:
                continue
            if mode == "phrases":
                phrases.append(value)
            elif mode == "types":
                types.append(value)
            else:
                excludes.append(value)
            continue
        raise ValueError(f"unexpected tracked catalog line: {stripped}")
    if current:
        sneakers.append(current)
    return {"sneakers": sneakers, "phrases": phrases, "types": types, "exclude": excludes}


def load_tracked(path=None):
    """Return the catalog, or empty lists after logging a problem."""
    path = path or os.environ.get("TRACKED_PATH") or DEFAULT_PATH
    empty = {"sneakers": [], "phrases": [], "types": [], "exclude": []}
    try:
        mtime = os.path.getmtime(path)
    except FileNotFoundError:
        logger.error("Tracked catalog not found: %s", path)
        return empty
    except OSError as exc:
        logger.error("Could not read tracked catalog %s: %s", path, exc)
        return empty
    cached = _LOADED.get(path)
    if cached and cached[0] == mtime:
        return cached[1]
    try:
        with open(path, "r", encoding="utf-8") as handle:
            text = handle.read()
        parsed = parse_tracked(text)
    except Exception as exc:
        logger.error("Could not parse tracked catalog %s: %s", path, exc)
        return empty
    _LOADED[path] = (mtime, parsed)
    return parsed


def _phrase(phrase):
    key = str(phrase or "").casefold()
    compiled = _PHRASE_CACHE.get(key)
    if compiled is None:
        parts = [re.escape(part) for part in re.split(r"\s+", key.strip()) if part]
        body = r"\s+".join(parts) if parts else r"$^"
        compiled = re.compile(rf"\b{body}\b", re.IGNORECASE)
        _PHRASE_CACHE[key] = compiled
    return compiled


def _has(text, phrase):
    return bool(_phrase(phrase).search(text or ""))


def sneaker_rule(name, description="", catalog=None):
    """Id of the sneaker rule that matches, or ``""``."""
    catalog = catalog if catalog is not None else load_tracked()
    text = f"{name or ''} {description or ''}"
    for rule in catalog.get("sneakers") or []:
        required = [phrase for phrase in (rule.get("all") or []) if phrase]
        choices = [phrase for phrase in (rule.get("any") or []) if phrase]
        if required and not all(_has(text, phrase) for phrase in required):
            continue
        if choices and not any(_has(text, phrase) for phrase in choices):
            continue
        if not required and not choices:
            continue
        return rule.get("id") or "sneaker"
    return ""


def accessory_rule(name, product_type="", catalog=None):
    """Phrase or type that makes this an accessory, or ``""``.

    Phrases are matched against the name. Types are matched against the
    store's product type, so a hardware listing whose name omits the word
    still counts.
    """
    catalog = catalog if catalog is not None else load_tracked()
    title = name or ""
    kind = str(product_type or "").strip()
    for phrase in catalog.get("exclude") or []:
        if _has(title, phrase):
            return ""
    for phrase in catalog.get("phrases") or []:
        if _has(title, phrase):
            return phrase
    for listed in catalog.get("types") or []:
        if kind.casefold() == str(listed).casefold():
            return listed
    return ""
