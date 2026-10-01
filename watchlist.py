"""Match sale listings against ``watchlist.yaml``.

The file is a small YAML subset: a ``rules:`` list of maps with string,
number, and true/false values. There is no extra dependency. A missing or
broken file logs an error and matches nothing, so the scrape still finishes.

See ``watchlist.yaml`` for the fields and the seeded preferences.
"""

import logging
import os
import re

from dimensions import dimension_key, dimensions_match, extract_specs, parse_dimension
from filters import normalize_product_name, normalize_url

logger = logging.getLogger("watchlist")

DEFAULT_PATH = "watchlist.yaml"
_TRIGGER_FIELDS = ("max_price", "alert_on_drop", "back_in_stock_width")


def _words(text):
    cleaned = normalize_product_name(text).replace("'", "").replace("\u2019", "")
    cleaned = cleaned.replace("-", " ")
    return [word.casefold() for word in re.findall(r"[A-Za-z0-9]+", cleaned)]


def _token_in(token, words):
    token = token.casefold().replace("-", "")
    compact = [word.replace("-", "") for word in words]
    if token in compact:
        return True
    for index in range(len(compact) - 1):
        if compact[index] + compact[index + 1] == token:
            return True
    return False


def phrase_in_name(phrase, name):
    """True when every word in ``phrase`` appears in ``name``.

    ``Antihero`` matches ``Anti-Hero`` and ``Anti Hero``.
    """
    wanted = _words(phrase)
    have = _words(name)
    return bool(wanted) and all(_token_in(token, have) for token in wanted)


def _parse_scalar(raw):
    text = raw.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {'"', "'"}:
        return text[1:-1]
    lower = text.lower()
    if lower in {"true", "yes"}:
        return True
    if lower in {"false", "no"}:
        return False
    if lower in {"null", "~"}:
        return None
    try:
        if "." in text:
            return float(text)
        return int(text)
    except ValueError:
        return text


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


def parse_watchlist(text):
    """Parse the watchlist subset. Raises ValueError on a broken structure."""
    rules = []
    seen_rules = False
    current = None
    for raw_line in str(text or "").splitlines():
        line = _strip_comment(raw_line).rstrip()
        if not line.strip():
            continue
        stripped = line.strip()
        if stripped == "rules:":
            seen_rules = True
            continue
        if not seen_rules:
            continue
        if stripped.startswith("- "):
            if current:
                rules.append(current)
            current = {}
            body = stripped[2:].strip()
            if not body:
                continue
            if ":" not in body:
                raise ValueError(f"expected key on rule line: {stripped}")
            key, value = body.split(":", 1)
            current[key.strip()] = _parse_scalar(value)
            continue
        if current is None or ":" not in stripped:
            raise ValueError(f"expected a rule field: {stripped}")
        key, value = stripped.split(":", 1)
        current[key.strip()] = _parse_scalar(value)
    if current:
        rules.append(current)
    return [rule for rule in rules if isinstance(rule, dict) and rule]


def load_watchlist(path=None):
    """Return rules, or an empty list after logging a problem."""
    path = path or os.environ.get("WATCHLIST_PATH") or DEFAULT_PATH
    try:
        with open(path, "r", encoding="utf-8") as handle:
            text = handle.read()
    except FileNotFoundError:
        logger.error("Watchlist file not found: %s", path)
        return []
    except OSError as exc:
        logger.error("Could not read watchlist %s: %s", path, exc)
        return []
    try:
        return parse_watchlist(text)
    except Exception as exc:
        logger.error("Could not parse watchlist %s: %s", path, exc)
        return []


def _price(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _width_of(item):
    if not isinstance(item, dict):
        return None
    parsed = parse_dimension(item.get("width"))
    if parsed is not None:
        return parsed
    specs = extract_specs(item.get("name") or "")
    return specs.get("width")


def _has_trigger(rule):
    if rule.get("alert_on_drop") is True:
        return True
    if rule.get("max_price") not in (None, ""):
        return True
    if rule.get("back_in_stock_width") not in (None, ""):
        return True
    return False


def rule_matches(rule, item):
    """True when brand/name, part, and min_width match. Ignores alert triggers."""
    if not isinstance(rule, dict) or not isinstance(item, dict):
        return False
    part = str(rule.get("part") or "Decks").strip().casefold()
    if str(item.get("part") or "").strip().casefold() != part:
        return False
    name = item.get("name") or ""
    if rule.get("name") and not phrase_in_name(rule.get("name"), name):
        return False
    if rule.get("brand") and not phrase_in_name(rule.get("brand"), name):
        return False
    if not rule.get("name") and not rule.get("brand"):
        return False
    if rule.get("min_width") not in (None, ""):
        width = _width_of(item)
        minimum = parse_dimension(rule.get("min_width"))
        if width is None or minimum is None or width < minimum - 1e-9:
            return False
    return True


def _index_items(catalog):
    indexed = {}
    if isinstance(catalog, dict):
        groups = catalog.values()
    else:
        groups = [catalog or []]
    for items in groups:
        for item in items or []:
            if not isinstance(item, dict):
                continue
            url = normalize_url(item.get("url"))
            if url:
                indexed[url] = item
    return indexed


def _reasons(rule, item, previous, history, today):
    url = normalize_url(item.get("url"))
    prev = previous.get(url) if url else None
    entry = history.get(url) if isinstance(history, dict) and url else None
    first_seen = str((entry or {}).get("first_seen") or "")[:10]
    today_text = str(today or "")[:10]
    seen_before = bool(first_seen and today_text and first_seen < today_text)
    in_previous = prev is not None
    is_back = (not in_previous) and seen_before
    is_new = not in_previous and not is_back
    current = _price(item.get("price_new"))
    prior = _price((prev or {}).get("price_new")) if prev else None
    dropped = current is not None and prior is not None and current < prior - 0.001
    delta = (prior - current) if dropped else None
    width = _width_of(item)
    reasons = []

    if _has_trigger(rule):
        if rule.get("max_price") not in (None, ""):
            ceiling = _price(rule.get("max_price"))
            under = current is not None and ceiling is not None and current < ceiling - 1e-9
            was_under = prior is not None and ceiling is not None and prior < ceiling - 1e-9
            if under and not was_under:
                reasons.append(f"Under ${ceiling:.2f}")
        if rule.get("alert_on_drop") is True and dropped:
            reasons.append(f"Price dropped ${delta:.2f}")
        target = rule.get("back_in_stock_width")
        if target not in (None, "") and is_back and dimensions_match(width, target):
            label = dimension_key(width) or dimension_key(target)
            reasons.append(f'{label}" back in stock')
        return reasons

    if is_new:
        reasons.append("New")
    elif is_back:
        reasons.append("Back in stock")
    if dropped:
        reasons.append(f"Price dropped ${delta:.2f}")
    return reasons


def match_watchlist(items, rules=None, previous=None, history=None, today=None, path=None):
    """Return ``(hits, alerts)``.

    Hits are current matches (page highlight). Alerts are hits with a reason
    to email. Never raises.
    """
    try:
        if rules is None:
            rules = load_watchlist(path)
        previous_index = _index_items(previous)
        history = history or {}
        hits = []
        for item in items or []:
            if not isinstance(item, dict):
                continue
            for rule in rules or []:
                try:
                    if not rule_matches(rule, item):
                        continue
                    reasons = _reasons(rule, item, previous_index, history, today)
                except Exception as exc:
                    logger.error("Watchlist rule %s failed: %s", rule.get("id"), exc)
                    continue
                hits.append(
                    {
                        "rule_id": str(rule.get("id") or ""),
                        "note": str(rule.get("note") or ""),
                        "reasons": reasons,
                        "item": item,
                    }
                )
        alerts = [hit for hit in hits if hit["reasons"]]
        return hits, alerts
    except Exception as exc:
        logger.error("Watchlist matching failed: %s", exc)
        return [], []
