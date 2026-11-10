"""One listing per product per store (audit 2026-11-10).

Stores sell sizes, colours and model years as separate products under one
name ("Owliad Skateboard Deck" at 8.25 and 8.5, Alpinestars gloves in four
colours, The House's Scott goggles seven times), and some list the very same
product twice. Each showed as its own card, so the grid read as duplicates.

``merge`` keeps the cheapest listing of each name within a store's category,
adds the others' sizes and spec offers so the filters still find it, and
lists the others under ``versions``. The merged-away links are returned as
intentional catalog changes, so history and the report don't call them
"Disappeared".
"""

import json

from filters import item_passes_filters, normalize_product_name, normalize_url

# Fields whose values describe what can be bought (sizes, spec offers): the
# merged listing offers every version's.
_LIST_FIELDS = ("widths", "sizes", "lengths", "shoe_sizes", "protection_sizes", "wheelbases",
                "durometers", "diameters_mm", "truck_sizes", "spec_offers", "technical_offers")


def _price(value):
    try:
        return float(str(value).replace("$", "").replace(",", ""))
    except (TypeError, ValueError):
        return None


def _name_key(item):
    return normalize_product_name(item.get("name") or "").casefold().strip()


def _union(first, second):
    if not isinstance(first, list) or not isinstance(second, list):
        return first if first is not None else second
    seen = {json.dumps(value, sort_keys=True, default=str) for value in first}
    merged = list(first)
    for value in second:
        key = json.dumps(value, sort_keys=True, default=str)
        if key not in seen:
            seen.add(key)
            merged.append(value)
    return merged


# A single value per listing (a deck's width) that differs between versions
# becomes the plural list the filters read ("widths").
_SCALAR_TO_LIST = (("width", "widths"), ("wheelbase", "wheelbases"))


def _merge_scalars(kept, group):
    for single, plural in _SCALAR_TO_LIST:
        values = []
        for item in group:
            for value in ([item.get(single)] + list(item.get(plural) or [])):
                if value not in (None, "") and value not in values:
                    values.append(value)
        if len(values) > 1:
            try:
                kept[plural] = sorted(values, key=float)
            except (TypeError, ValueError):
                kept[plural] = values


def _merge_specs(kept, other):
    for field in _LIST_FIELDS:
        if field in other:
            kept[field] = _union(kept.get(field), other[field])
    specs, more = kept.get("technical_specs"), other.get("technical_specs")
    if isinstance(specs, dict) and isinstance(more, dict):
        for key, values in more.items():
            specs[key] = _union(specs.get(key), values)


def merge_items(items):
    """(items with one listing per name, {merged-away url: reason})."""
    groups = {}
    order = []
    for item in items or []:
        # Only listings that will show are merged: a cheapest version under
        # the 10% minimum must not hide a better-marked-down one.
        key = _name_key(item) if isinstance(item, dict) and item_passes_filters(item) else ""
        if not key:
            order.append([item])
            continue
        if key not in groups:
            groups[key] = []
            order.append(groups[key])
        groups[key].append(item)
    kept_items, merged_away = [], {}
    for group in order:
        if len(group) == 1:
            kept_items.append(group[0])
            continue
        ranked = sorted(group, key=lambda item: (_price(item.get("price_new")) is None,
                                                 _price(item.get("price_new")) or 0.0, str(item.get("url") or "")))
        kept = dict(ranked[0])
        for field in ("technical_specs",):
            if isinstance(kept.get(field), dict):
                kept[field] = {key: list(values) if isinstance(values, list) else values
                               for key, values in kept[field].items()}
        versions = []
        for other in ranked[1:]:
            if normalize_url(other.get("url")) == normalize_url(kept.get("url")):
                continue
            _merge_specs(kept, other)
            versions.append({field: other.get(field) for field in ("url", "price_new", "price_old", "image")
                             if other.get(field)})
            merged_away[normalize_url(other.get("url"))] = "catalog scope: another version of " + str(kept.get("url"))
        if versions:
            _merge_scalars(kept, ranked)
            kept["versions"] = versions
        kept_items.append(kept)
    return kept_items, merged_away


def merge(data, into=None):
    """Merge each ``store_part`` list; returns {merged-away url: reason}.

    The merged lists replace ``data``'s, or ``into``'s when given (merging a
    subset of a catalog's keys)."""
    target = data if into is None else into
    merged_away = {}
    for key, items in list((data or {}).items()):
        if isinstance(items, list):
            target[key], away = merge_items(items)
            merged_away.update(away)
    return merged_away
