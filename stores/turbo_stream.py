"""Decode React Router "turbo-stream" data (``<page>.data`` responses).

Headless Shopify (Hydrogen) storefronts serve each page's loader data at
``<path>.data`` in this format: the first line is a JSON array whose objects
refer to other entries by index ({"_12": 34} means key arr[12], value
arr[34]); negative indexes are undefined/null/special values. Later lines
resolve deferred promises and are not needed for collection pages.
"""

import json


def decode(text):
    line = str(text or "").split("\n", 1)[0]
    table = json.loads(line)
    memo = {}

    def value(index):
        if not isinstance(index, int):
            return index
        if index < 0:
            return None
        if index in memo:
            return memo[index]
        raw = table[index]
        if isinstance(raw, dict):
            out = {}
            memo[index] = out
            for key, ref in raw.items():
                name = table[int(key[1:])] if key.startswith("_") else key
                out[name] = value(ref)
            return out
        if isinstance(raw, list):
            # Typed entries ("D" date, "P" promise, ...) are kept as they are.
            if raw and isinstance(raw[0], str) and raw[0] in ("D", "P", "Z", "R", "E", "Y", "S", "M"):
                memo[index] = raw
                return raw
            out = []
            memo[index] = out
            out.extend(value(item) for item in raw)
            return out
        memo[index] = raw
        return raw

    return value(0)


def find(node, key, depth=0, out=None):
    """Every dict under ``node`` that has ``key``."""
    out = [] if out is None else out
    if depth > 60:
        return out
    if isinstance(node, dict):
        if key in node:
            out.append(node)
        for item in node.values():
            find(item, key, depth + 1, out)
    elif isinstance(node, list):
        for item in node:
            find(item, key, depth + 1, out)
    return out
