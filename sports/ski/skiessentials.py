"""Ski Essentials (skiessentials.com): a headless Shopify (Hydrogen) store.

Store probe 2026-11-11, owner approved. Hydrogen turns off ``products.json``,
so collections are read from React Router's ``<collection>.data`` responses
(robots.txt allows them): the first 48 products of each sale category.
Each product node there carries what products.json would (type, vendor, tags,
variants with price, compare-at price and stock), so it is converted to that
shape and goes through the shared Shopify code (stores/shopify.py).

Types are paths ("Alpine Ski > Boot > Alpine", "Nordic > Ski > Classic");
only alpine hard goods count. Sale prices are not the variant price: they
are in the custom.online_variant_prices metafield, keyed by SKU, and the
variant price is the regular price the page shows struck through.
"""

import json
import logging
import re
import time
import urllib.request

import sports
from sports import brands
from stores import shopify, turbo_stream

logger = logging.getLogger("sports.ski.skiessentials")

BASE = "https://www.skiessentials.com"
# Sale categories (2026-11-11 sizes): skis 471, binding combos 143, boots 80,
# packages 66, bindings 24, helmets 33, goggles 8; then the outlet. Each is
# read to its first 48, so big ones (skis) are only partly covered.
COLLECTIONS = ("sale-alpine-skis", "sale-alpine-ski-boots", "sale-alpine-ski-bindings",
               "sale-alpine-ski-binding-combos", "sale-alpine-ski-packages", "sale-helmets", "sale-goggles", "outlet")
PAGE_DELAY = 2.0

_PATH_PARTS = ((r">\s*ski\b", "Skis"), (r">\s*boot\b", "Boots"), (r">\s*binding", "Bindings"),
               (r">\s*pole", "Poles"), (r">\s*helmet", "Helmets"), (r">\s*goggle", "Protection"))


def path_part(product_type):
    path = str(product_type or "")
    if not re.match(r"\s*alpine\s*ski\b", path, re.I):
        return None
    for pattern, part in _PATH_PARTS:
        if re.search(pattern, path, re.I):
            return part
    return None


def _fetch_text(url, timeout=60):
    request = urllib.request.Request(url, headers={"User-Agent": shopify._USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read().decode("utf-8", "replace")
    except Exception as exc:
        logger.error("Ski Essentials fetch failed for %s: %s", url, exc)
        return None


def _amount(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def online_prices(node):
    """{sku: online sale price} from the product's custom.online_variant_prices
    metafield: Ski Essentials' sale prices live there, not in the variant price."""
    for field in node.get("metafields") or []:
        if isinstance(field, dict) and field.get("key") == "online_variant_prices":
            try:
                table = json.loads(field.get("value") or "{}")
            except ValueError:
                return {}
            return {str(sku).strip(): _amount(price) for sku, price in table.items() if _amount(price) > 0}
    return {}


def to_product(node):
    """A .data product node in products.json's shape."""
    names = []
    for variant in node.get("variants") or []:
        for option in variant.get("selectedOptions") or []:
            name = str(option.get("name") or "").replace("_", " ")
            if name and name not in names:
                names.append(name)
    online = online_prices(node)
    variants = []
    for variant in node.get("variants") or []:
        values = {str(o.get("name") or "").replace("_", " "): o.get("value") for o in variant.get("selectedOptions") or []}
        price = _amount((variant.get("priceV2") or {}).get("amount"))
        compare = max(_amount(variant.get("compareAtPrice")), price)
        # The page's sale price is the online price for this SKU; the variant
        # price is the regular price the card shows struck through.
        sale = online.get(str(variant.get("sku") or "").strip())
        if sale and 0 < sale < compare:
            price = sale
        item = {"id": variant.get("id"), "title": variant.get("title") or "",
                "price": f"{price:.2f}" if price else None,
                "compare_at_price": f"{compare:.2f}" if compare > price else None,
                "available": bool(variant.get("available"))}
        for index, name in enumerate(names[:3], start=1):
            item[f"option{index}"] = values.get(name)
        variants.append(item)
    images = []
    for image in [node.get("featuredImage")] + list(node.get("images") or []):
        url = (image or {}).get("url") if isinstance(image, dict) else None
        if url and url not in [photo["src"] for photo in images]:
            images.append({"src": url})
    return {"id": node.get("id"), "handle": node.get("handle"), "title": node.get("title") or "",
            "vendor": node.get("vendor") or "", "product_type": node.get("productType") or "",
            "tags": list(node.get("tags") or []), "body_html": node.get("description") or "",
            "options": [{"name": name} for name in names[:3]], "variants": variants, "images": images}


def read_collection(handle, fetch=_fetch_text):
    """A collection's first page (48 products), or None when it fails.

    Only the first page carries full product data. "Show more" loads 8
    light items at a time (title and regular price, no sale price), so each
    sale category is read from its own collection instead."""
    text = fetch(f"{BASE}/collections/{handle}.data")
    if not text:
        return None
    try:
        tree = turbo_stream.decode(text)
    except (ValueError, IndexError, KeyError) as exc:
        logger.error("Ski Essentials %s unreadable: %s", handle, exc)
        return None
    return [to_product(node) for node in turbo_stream.find(tree, "productType") if "variants" in node]


def load_products(fetch=_fetch_text, sleep=time.sleep):
    """Both collections, each product once; None when the main one fails."""
    merged, seen = [], set()
    for index, handle in enumerate(COLLECTIONS):
        if index:
            sleep(PAGE_DELAY)
        products = read_collection(handle, fetch)
        if products is None:
            if index == 0:
                return None
            logger.warning("Ski Essentials: could not read %s; using %s", handle, COLLECTIONS[0])
            continue
        for product in products:
            if product.get("id") not in seen:
                seen.add(product.get("id"))
                merged.append(product)
    return merged


def store(details):
    shop = shopify.ShopifyStore("Ski Essentials", "Ski Essentials", BASE, collection=COLLECTIONS[0],
                                more_collections=COLLECTIONS[1:], types={}, type_part=path_part, raw_type_part=True,
                                brand_of=brands.for_sport(sports.SKI), own_vendor="ski essentials",
                                details=details, track_exclusions=True)
    shop.load_products = load_products
    return shop
