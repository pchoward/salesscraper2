"""Deathgear sale listings (deathgearproducts.com, a Squarespace shop).

The sale page ``/shop/sale-clearance-blemished`` returns its whole listing as
data with ``?format=json``: one request, no browser. robots.txt disallows
only ``/config``, ``/search``, ``/account`` and digital downloads.

Squarespace products have no store part type, so the part comes from the
title (deck, wheels, trucks, bearings, grip/hardware, complete, or
protective gear). A variant is a deal only when the shop marks it
``onSale`` with a sale price under the regular price. Sold-out variants
(no stock, not unlimited) are kept but marked sold out, like Zumiez gear.
The shared filters still decide brands, deck sizes, and discounts.
"""

import json
import logging
import re
import urllib.request

from filters import extract_deck_dimensions, extract_deck_size, normalize_product_name, normalize_url
from protection import classify as classify_protection
from stores.base import Scraper
from stores.ccs import set_protection_fields

logger = logging.getLogger("stores.deathgear")

STORE = "Deathgear"
DISPLAY_NAME = "Deathgear Products"
BASE = "https://www.deathgearproducts.com"
SALE_JSON = f"{BASE}/shop/sale-clearance-blemished?format=json"
PARTS = ("Decks", "Wheels", "Trucks", "Bearings", "Completes", "Accessories", "Protection")
_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
_CACHE = {}

_RE = lambda pattern: re.compile(pattern, re.IGNORECASE)  # noqa: E731
# Checked in this order: a "complete skateboard" is not a deck, and
# "bearings" in a wheel bundle's name does not make it bearings.
_PART_RULES = (
    ("Completes", _RE(r"\bcompletes?\b")),
    ("Decks", _RE(r"\bdecks?\b")),
    ("Wheels", _RE(r"\bwheels?\b")),
    ("Trucks", _RE(r"\btrucks?\b")),
    ("Bearings", _RE(r"\bbearings?\b")),
    ("Accessories", _RE(r"\bgrip\s*tape\b|\bgriptape\b|\bhardware\b|\bbolts?\b|\brisers?\b|\bskate\s*tool\b|\bwax\b|\bbushings?\b")),
)


def part_for_title(title):
    """The report part a Deathgear title names, or None to skip it."""
    if classify_protection(title):
        return "Protection"
    for part, pattern in _PART_RULES:
        if pattern.search(title or ""):
            return part
    return None


def clean_title(title):
    """``"HEROIN~ QUESTIONS DECK"`` reads ``"Heroin Questions Deck"``; mixed case is kept."""
    text = normalize_product_name(str(title or "").replace("~", " "))
    if text.isupper():
        text = " ".join(word if re.search(r"\d", word) else word.capitalize() for word in text.split())
    return text


def _fetch_json(url, timeout=30):
    request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8", "replace"))
    except Exception as exc:
        logger.error("Deathgear sale page fetch failed: %s", exc)
        return None


def load_sale_items(fetch=None):
    """The sale page's items, or None when it cannot be read. One shared download."""
    own_fetch = fetch is None
    if own_fetch and "items" in _CACHE:
        return _CACHE["items"]
    payload = (fetch or _fetch_json)(SALE_JSON)
    if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
        return None
    if (payload.get("pagination") or {}).get("nextPageUrl"):
        # 44 items fit on one page today. A second page would need paging here.
        logger.warning("Deathgear sale page has more pages; only the first is read")
    if own_fetch:
        _CACHE["items"] = payload["items"]
    return payload["items"]


def _money(value):
    """A Squarespace money object (``{"value": "72.00"}``) as ``"72.00"``, or None."""
    try:
        amount = float((value or {}).get("value"))
    except (AttributeError, TypeError, ValueError):
        return None
    return f"{amount:.2f}" if amount > 0 else None


def _deal(variant):
    """``(sale, regular)`` when the shop marks this variant on sale below its price."""
    if not isinstance(variant, dict) or variant.get("onSale") is not True:
        return None
    sale = _money(variant.get("salePriceMoney"))
    regular = _money(variant.get("priceMoney"))
    if not sale or not regular or float(sale) >= float(regular):
        return None
    return sale, regular


def _in_stock(variant):
    return variant.get("unlimited") is True or (variant.get("qtyInStock") or 0) > 0


def _variant_label(variant):
    """The option values (``"8.5"``, ``"Large"``), joined, for names and sizes."""
    values = [str(value) for value in (variant.get("attributes") or {}).values() if value not in (None, "")]
    return " ".join(values).strip()


class DeathgearScraper(Scraper):
    """One part from the shared Deathgear sale page."""

    def __init__(self, part):
        super().__init__(STORE, SALE_JSON, part)

    def scrape(self):
        items = load_sale_items()
        if items is None:
            return None
        return self.products_from(items)

    def parse(self, html):
        """Accept a saved ``?format=json`` body."""
        text = str(html or "").lstrip()
        if not text.startswith("{"):
            logger.error("Deathgear parser expected the page as JSON, not HTML")
            return []
        return self.products_from(json.loads(text).get("items") or [])

    def products_from(self, items):
        kept = []
        seen = set()
        for product in items or []:
            if not isinstance(product, dict):
                continue
            title = clean_title(product.get("title"))
            path = str(product.get("fullUrl") or "").strip()
            if not title or not path.startswith("/") or part_for_title(title) != self.part:
                continue
            variants = [v for v in (product.get("structuredContent") or {}).get("variants") or [] if isinstance(v, dict)]
            deals = [(v, _deal(v)) for v in variants]
            deals = [(v, deal) for v, deal in deals if deal]
            if not deals:
                continue
            url = normalize_url(BASE + path)
            # Decks whose title has no width but whose variants are widths:
            # one listing per width, like the other stores.
            labels = [_variant_label(v) for v, _deal_ in deals]
            per_width = (
                self.part == "Decks"
                and len(deals) > 1
                and extract_deck_dimensions(title)[0] is None
                and all(extract_deck_dimensions(label)[0] is not None for label in labels)
            )
            offers = (
                [(f'{title} {label}"' if label.replace(".", "", 1).isdigit() else f"{title} {label}",
                  f"{url}?variant={v.get('id')}", [(v, deal)]) for (v, deal), label in zip(deals, labels)]
                if per_width else [(title, url, deals)]
            )
            for name, href, chosen in offers:
                if href in seen:
                    continue
                item = self._item(product, name, href, chosen)
                if item:
                    seen.add(href)
                    kept.append(item)
        logger.info("Parsed %s Deathgear %s", len(kept), self.part)
        return kept

    def _item(self, product, name, url, deals):
        buyable = [(v, deal) for v, deal in deals if _in_stock(v)]
        pick = min(buyable or deals, key=lambda pair: float(pair[1][0]))
        price_new, price_old = pick[1]
        if not self._keep(name, url, price_new, price_old):
            return None
        item = {
            "name": name,
            "url": url,
            "price_new": price_new,
            "price_old": price_old,
            "availability": "Check store",
            "part": self.part,
            "store": STORE,
            "currency": "USD",
        }
        if not buyable:
            item["stock"] = "out_of_stock"
            item["availability"] = "Sold out"
        else:
            item["stock"] = "in_stock"
        image = product.get("assetUrl")
        if isinstance(image, str) and image.startswith("https://"):
            item["image"] = image
        if self.part in ("Decks", "Completes"):
            size = extract_deck_size(name)
            if size:
                item["size"] = size
        if self.part == "Protection":
            variants = [{"option1": _variant_label(v)} for v, _deal_ in (buyable or deals)]
            set_protection_fields(item, name, "", variants)
        item = self._finish(item, None, BASE)
        from product_specs import enrich
        description = product.get('body') or product.get('excerpt') or (product.get('structuredContent') or {}).get('description') or ''
        variants = [dict(v, price=deal[0], compare_at_price=deal[1], available=_in_stock(v)) for v, deal in deals]
        return enrich(item, description, product, variants)


def scrapers():
    return [DeathgearScraper(part) for part in PARTS]


def main():
    """Preview a live run: counts and examples per part. Writes nothing."""
    logging.basicConfig(level=logging.WARNING)
    items = load_sale_items()
    if items is None:
        print("Deathgear sale page could not be read.")
        return 1
    print(f"{len(items)} items on the sale page.")
    unmatched = [clean_title(i.get("title")) for i in items if not part_for_title(clean_title(i.get("title")))]
    for scraper in scrapers():
        kept = scraper.products_from(items)
        print(f"\n{scraper.part}: {len(kept)} kept of {scraper.candidates} candidates")
        for item in kept[:5]:
            sold = "  (sold out)" if item.get("stock") == "out_of_stock" else ""
            print(f"  ${item['price_new']} (was ${item['price_old']})  {item['name']}{sold}")
    print(f"\nNot a tracked part ({len(unmatched)}):")
    for title in unmatched[:15]:
        print(f"  {title}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
