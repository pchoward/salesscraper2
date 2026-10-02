"""Muir Skate sale listings.

Disabled. On 2026-10-02 the storefront at muirskate.com (and www, which
redirects there) returned Shopify's "This store is unavailable" page in
both a normal HTTP client and headless Chrome. ``/collections/gear-on-sale``
is a real collection (Shopify sends a canonical redirect with
``pageType=collection``) but ``products.json``, ``.js``, and ``.atom`` all
404. Shipping a live scraper against that would record empty or failed
runs every morning.

The parser below speaks Shopify's public collection ``products.json``
shape so it can be turned on by setting ``ENABLED`` once the shop answers
again. It still runs every product through the shared filters, which drop
longboards and cruisers. Muir's catalog is mostly longboards; street
decks, wheels, trucks, and bearings are kept only when they match the
same brand, width, and discount rules as the other stores.
"""

import json
import logging
import re

from filters import extract_deck_size, normalize_product_name, normalize_url
from stores.base import Scraper

logger = logging.getLogger("stores.muirskate")

STORE = "Muir Skate"
BASE = "https://muirskate.com"
ENABLED = False
DISABLED_REASON = (
    "muirskate.com returns Shopify's 'This store is unavailable' page, and "
    "collection products.json endpoints 404. Left disabled until the "
    "storefront can be scraped reliably."
)

# Tried in order when ENABLED is true. gear-on-sale is the nav label
# "Gear on Sale" from the shop's collection index.
COLLECTION_HANDLES = (
    "gear-on-sale",
    "sale",
    "clearance",
    "on-sale",
)

_PART_RULES = (
    ("Bearings", re.compile(r"\bbearings?\b", re.IGNORECASE)),
    ("Wheels", re.compile(r"\bwheels?\b", re.IGNORECASE)),
    ("Trucks", re.compile(r"\btrucks?\b", re.IGNORECASE)),
    ("Decks", re.compile(r"\bdecks?\b", re.IGNORECASE)),
)


def classify_part(name, product_type="", url=""):
    text = f"{name or ''} {product_type or ''} {url or ''}"
    for part, pattern in _PART_RULES:
        if pattern.search(text):
            return part
    return None


def _amount(value):
    if value is None or value == "":
        return None
    try:
        amount = float(value)
    except (TypeError, ValueError):
        return None
    if amount <= 0:
        return None
    return f"{amount:.2f}"


def _on_sale(variant):
    price = _amount((variant or {}).get("price"))
    compare = _amount((variant or {}).get("compare_at_price"))
    if not price or not compare:
        return None
    if float(compare) <= float(price):
        return None
    return price, compare


def _product_name(product, variant):
    title = str((product or {}).get("title") or "").strip()
    vendor = str((product or {}).get("vendor") or "").strip()
    variant_title = str((variant or {}).get("title") or "").strip()
    name = title
    if vendor and vendor.casefold() not in title.casefold():
        name = f"{vendor} {title}".strip()
    if variant_title and variant_title.casefold() not in ("default title",) and variant_title.casefold() not in name.casefold():
        name = f"{name} {variant_title}".strip()
    return normalize_product_name(name)


def _image(product):
    images = (product or {}).get("images") or []
    if not images:
        image = (product or {}).get("image")
        if isinstance(image, dict):
            return str(image.get("src") or "")
        return ""
    first = images[0]
    if isinstance(first, dict):
        return str(first.get("src") or "")
    return ""


def products_from_payload(payload, part):
    """Kept listings for ``part`` from one Shopify ``products.json`` body.

    ``payload`` may be a dict or a JSON string. Full-price variants (no
    higher compare-at price) are not candidates. The shared filters still
    decide brand, discount, width, and longboard/cruiser exclusions.
    """
    if isinstance(payload, str):
        payload = json.loads(payload)
    if not isinstance(payload, dict):
        return []
    products = []
    seen = set()
    for product in payload.get("products") or []:
        if not isinstance(product, dict):
            continue
        handle = str(product.get("handle") or "").strip()
        product_type = str(product.get("product_type") or "")
        image = _image(product)
        variants = product.get("variants") or [{}]
        if not isinstance(variants, list):
            continue
        for variant in variants:
            if not isinstance(variant, dict):
                continue
            sale = _on_sale(variant)
            if not sale:
                continue
            price_new, price_old = sale
            name = _product_name(product, variant)
            guessed = classify_part(name, product_type, handle)
            if guessed != part or not name:
                continue
            href = f"{BASE}/products/{handle}" if handle else ""
            variant_id = variant.get("id")
            if variant_id and len(variants) > 1:
                href = f"{href}?variant={variant_id}"
            href = normalize_url(href)
            if not href or href in seen:
                continue
            seen.add(href)
            available = variant.get("available")
            products.append(
                {
                    "name": name,
                    "url": href,
                    "price_new": price_new,
                    "price_old": price_old,
                    "availability": "Check store" if available is not False else "Sold out",
                    "part": part,
                    "store": STORE,
                    "currency": "USD",
                    "image": image,
                    "_node": None,
                }
            )
    return products


class MuirSkateScraper(Scraper):
    def __init__(self, part, catalog):
        super().__init__(STORE, f"{BASE}/collections/gear-on-sale", part)
        self.catalog = catalog

    def scrape(self):
        if not ENABLED:
            logger.error("Muir Skate is disabled: %s", DISABLED_REASON)
            return None
        payload = self.catalog.payload()
        return self.parse_payload(payload)

    def parse(self, html):
        """Accept a JSON string saved from products.json. HTML is not used."""
        text = html if isinstance(html, str) else ""
        stripped = text.lstrip()
        if not stripped.startswith("{"):
            logger.error("Muir Skate parser expected products.json, not HTML")
            return []
        return self.parse_payload(json.loads(stripped))

    def parse_payload(self, payload):
        products = []
        for raw in products_from_payload(payload, self.part):
            if not self._keep(raw["name"], raw["url"], raw["price_new"], raw["price_old"]):
                continue
            item = {key: value for key, value in raw.items() if key != "_node"}
            if self.part == "Decks":
                item["size"] = extract_deck_size(item["name"])
            if item.get("image"):
                pass
            self._finish(item, None, BASE)
            if raw.get("image") and not item.get("image"):
                item["image"] = raw["image"]
            products.append(item)
        logger.info("Parsed %s Muir Skate %s", len(products), self.part)
        return products


class MuirCatalog:
    def __init__(self, fetch=None):
        self._fetch = fetch
        self._payload = None

    def payload(self):
        if self._payload is None:
            self._payload = self._fetch() if self._fetch else fetch_products_json()
        return self._payload


def fetch_products_json():
    """Page through the first Shopify sale collection that returns products."""
    import urllib.request

    opener = urllib.request.build_opener()
    last_error = None
    for handle in COLLECTION_HANDLES:
        products = []
        for page in range(1, 11):
            url = f"{BASE}/collections/{handle}/products.json?limit=250&page={page}"
            request = urllib.request.Request(
                url,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
                    ),
                    "Accept": "application/json",
                },
            )
            try:
                with opener.open(request, timeout=30) as response:
                    body = response.read().decode("utf-8", "replace")
            except Exception as exc:
                last_error = exc
                logger.warning("Muir Skate %s failed: %s", url, exc)
                products = []
                break
            try:
                payload = json.loads(body)
            except json.JSONDecodeError as exc:
                last_error = exc
                products = []
                break
            batch = payload.get("products") if isinstance(payload, dict) else None
            if not isinstance(batch, list) or not batch:
                break
            products.extend(batch)
            if len(batch) < 250:
                break
        if products:
            logger.info("Muir Skate collection %s returned %s products", handle, len(products))
            return {"products": products}
    raise RuntimeError(f"Muir Skate products.json was not available ({last_error})")


def scrapers(catalog=None):
    shared = catalog or MuirCatalog()
    return [MuirSkateScraper(part, shared) for part in ("Decks", "Wheels", "Trucks", "Bearings")]
