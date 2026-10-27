"""TGM Skateboards sale listings (tgmskateboards.com, a US Shopify store).

One download serves every part: the public collection feed
``/collections/sale/products.json?limit=250&page=N``, read page by page
until a page comes back empty or short. robots.txt allows collections but
disallows ``sort_by`` and multi-filter URLs, so the storefront's filtered
pages are never requested; this module sorts products by their Shopify
``product_type`` instead.

* Kept types: Decks, Wheels, Trucks, Bearings, Grip Tape and Hardware (as
  Accessories), Completes, and Mens Shoes (as Sneakers). Everything else
  (clothing, Disc, Roller Hockey, ...) is skipped before the filters.
* A variant is on sale only when ``compare_at_price`` is above ``price``.
  The sale price is the variant price and the was price is its compare-at.
* The shared filters still decide brands, deck width and discount,
  the tracked sneaker and accessory lists, and cruiser/longboard exclusions.

Polite crawling: a browser User-Agent, one request at a time, and a pause
between pages. ``python -m stores.tgm`` previews what a run would keep
without writing anything.
"""

import collections
import json
import logging
import re
import time
import urllib.request

from filters import extract_deck_dimensions, extract_deck_size, filter_reason, normalize_product_name, normalize_url
from part_specs import ordered_shoe_sizes
from stores.base import Scraper
from stores.ccs import _amount, _money, _plain, _shoe_offers, _stock_known, _variants_of

logger = logging.getLogger("stores.tgm")

STORE = "TGM"
DISPLAY_NAME = "TGM Skateboards"
BASE = "https://tgmskateboards.com"
SALE_JSON = f"{BASE}/collections/sale/products.json"
PAGE_LIMIT = 250
MAX_PAGES = 20
PAGE_DELAY = 1.5  # seconds between page requests
PARTS = ("Decks", "Wheels", "Trucks", "Bearings", "Completes", "Sneakers", "Accessories")
_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

# Shopify product_type (lowercase, punctuation and repeated spaces removed)
# to the report's part. Types not listed here are never candidates.
PART_BY_TYPE = {
    "decks": "Decks",
    "deck": "Decks",
    "wheels": "Wheels",
    "trucks": "Trucks",
    "bearings": "Bearings",
    "grip tape": "Accessories",
    "griptape": "Accessories",
    "hardware": "Accessories",
    "completes": "Completes",
    "complete": "Completes",
    "mens shoes": "Sneakers",
}
_CACHE = {}


def part_for_type(product_type):
    """The report part for a Shopify product type, or None to skip it."""
    key = re.sub(r"[^a-z0-9 ]", "", str(product_type or "").casefold())
    return PART_BY_TYPE.get(re.sub(r"\s+", " ", key).strip())


def _fetch_json(url, timeout=30):
    request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8", "replace"))
    except Exception as exc:
        logger.error("TGM catalog fetch failed for %s: %s", url, exc)
        return None


def load_sale_products(fetch=None, sleep=time.sleep):
    """Every product in the sale collection, or None when any page fails.

    All parts share one download. A caller that passes ``fetch`` does not
    read or write that cache.
    """
    own_fetch = fetch is None
    if own_fetch and "products" in _CACHE:
        return _CACHE["products"]
    fetch = fetch or _fetch_json
    products = []
    for page in range(1, MAX_PAGES + 1):
        if page > 1:
            sleep(PAGE_DELAY)
        payload = fetch(f"{SALE_JSON}?limit={PAGE_LIMIT}&page={page}")
        if not isinstance(payload, dict) or not isinstance(payload.get("products"), list):
            return None
        batch = payload["products"]
        products.extend(batch)
        if len(batch) < PAGE_LIMIT:
            break
    else:
        logger.error("TGM sale catalog exceeded %s pages", MAX_PAGES)
        return None
    if own_fetch:
        _CACHE["products"] = products
    return products


def _sale_variants(product):
    """Variants with a compare-at price above the price that can be bought.

    A variant is dropped only when the feed says ``available: false``; a
    feed without that flag keeps every on-sale variant.
    """
    sale = []
    for variant in _variants_of(product):
        price = _amount(variant.get("price"))
        compare = _amount(variant.get("compare_at_price"))
        if price is None or compare is None or compare <= price or price <= 0:
            continue
        if variant.get("available") is False:
            continue
        sale.append(variant)
    return sale


# Words in a vendor name that are not the brand: "OJ Wheels", "Ace Trucks MFG".
_VENDOR_FILLER = {"wheels", "wheel", "trucks", "truck", "bearings", "bearing", "skateboards", "skateboard",
                  "skate", "mfg", "co", "company", "inc", "griptape", "grip", "tape", "hardware", "shoes"}


def _title(product):
    """The product title, with the vendor's brand in front when the title leaves it out.

    The shared filters find brands by name, so "Formula Four Classic 54mm"
    from vendor Spitfire must read "Spitfire Formula Four Classic 54mm". A
    title that already names the brand ("OJ III Wheels" from "OJ Wheels")
    is left alone.
    """
    title = normalize_product_name((product or {}).get("title") or "")
    vendor = normalize_product_name((product or {}).get("vendor") or "")
    if not vendor or vendor.casefold().startswith("tgm"):
        return title
    brand = [word for word in re.findall(r"[a-z0-9]+", vendor.casefold()) if word not in _VENDOR_FILLER]
    words = set(re.findall(r"[a-z0-9]+", title.casefold()))
    if brand and all(word in words for word in brand):
        return title
    return f"{vendor} {title}".strip()


def _variant_label(variant):
    label = normalize_product_name(variant.get("title") or "")
    return "" if label.casefold() in ("", "default title") else label


def _width_variants(title, sale):
    """Deck sale variants that each name a different width, when the title names none."""
    if len(sale) < 2 or extract_deck_dimensions(title)[0] is not None:
        return []
    widths = [extract_deck_dimensions(_variant_label(variant))[0] for variant in sale]
    if any(width is None for width in widths) or len(set(widths)) != len(widths):
        return []
    return sale


def _images(product):
    return [photo["src"] for photo in (product or {}).get("images") or [] if isinstance(photo, dict) and photo.get("src")]


class TGMScraper(Scraper):
    """One part from the shared TGM sale feed."""

    def __init__(self, part):
        super().__init__(STORE, SALE_JSON, part)

    def scrape(self):
        products = load_sale_products()
        if products is None:
            return None
        return self.products_from(products)

    def parse(self, html):
        """Accept a saved products.json body. TGM is never read as HTML."""
        text = str(html or "").lstrip()
        if not text.startswith("{"):
            logger.error("TGM parser expected products.json, not HTML")
            return []
        return self.products_from(json.loads(text).get("products") or [])

    def products_from(self, products):
        kept = []
        seen = set()
        for product in products or []:
            if not isinstance(product, dict) or part_for_type(product.get("product_type")) != self.part:
                continue
            handle = str(product.get("handle") or "").strip()
            title = _title(product)
            sale = _sale_variants(product)
            if not handle or not title or not sale:
                continue
            base_url = normalize_url(f"{BASE}/products/{handle}")
            split = _width_variants(title, sale) if self.part == "Decks" else []
            offers = [(f"{title} {_variant_label(v)}", f"{base_url}?variant={v.get('id')}", [v]) for v in split] or [
                (title, base_url, sale)
            ]
            for name, url, variants in offers:
                if url in seen:
                    continue
                item = self._item(product, name, url, variants)
                if item is None:
                    continue
                seen.add(url)
                kept.append(item)
        logger.info("Parsed %s TGM %s", len(kept), self.part)
        return kept

    def _item(self, product, name, url, variants):
        cheapest = min(variants, key=lambda variant: _amount(variant.get("price")))
        price_new = _money(cheapest.get("price"))
        price_old = _money(cheapest.get("compare_at_price"))
        product_type = str(product.get("product_type") or "").strip()
        description = _plain(product.get("body_html") or "")
        if not self._keep(name, url, price_new, price_old, description, product_type):
            return None
        item = {
            "name": name,
            "url": url,
            "price_new": price_new,
            "price_old": price_old,
            "availability": "Check store",
            "part": self.part,
            "store": STORE,
            "product_type": product_type,
        }
        images = _images(product)
        if images:
            item["image"] = images[0]
            if len(images) > 1:
                item["images"] = images
        if self.part in ("Decks", "Completes"):
            size = extract_deck_size(name)
            if size:
                item["size"] = size
        if self.part == "Sneakers":
            item["description"] = description
            if _stock_known(_variants_of(product)):
                offers = _shoe_offers(variants)
                sizes = ordered_shoe_sizes(offers)
                item["shoe_sizes"] = sizes
                prices = {size: offers[size]["price"] for size in sizes}
                compares = {size: offers[size]["compare"] for size in sizes}
                if len(set(prices.values())) > 1:
                    item["shoe_prices"] = prices
                if len(set(compares.values())) > 1:
                    item["shoe_compares"] = compares
        # Width, length, and wheelbase from the name, like the other stores.
        return self._finish(item, None, BASE)


def scrapers():
    return [TGMScraper(part) for part in PARTS]


def main():
    """Preview a live run: counts and a few examples per part. Writes nothing."""
    logging.basicConfig(level=logging.WARNING)
    products = load_sale_products()
    if products is None:
        print("TGM sale feed could not be read.")
        return 1
    types = {}
    for product in products:
        kind = str(product.get("product_type") or "(none)")
        types[kind] = types.get(kind, 0) + 1
    print(f"{len(products)} products in the sale collection.")
    print("Product types:", ", ".join(f"{kind} {count}" for kind, count in sorted(types.items(), key=lambda pair: -pair[1])))
    for scraper in scrapers():
        items = scraper.products_from(products)
        print(f"\n{scraper.part}: {len(items)} kept of {scraper.candidates} candidates")
        for item in items[:5]:
            print(f"  ${item['price_new']} (was ${item['price_old']})  {item['name']}")
        reasons = collections.Counter()
        for product in products:
            if part_for_type(product.get("product_type")) != scraper.part or not _sale_variants(product):
                continue
            reason = filter_reason(_title(product), scraper.part, "", "1", "2", _plain(product.get("body_html") or ""),
                                   str(product.get("product_type") or ""))
            if reason and not reason.startswith(("known-brand deck", "unknown-brand deck")):
                reasons[re.sub(r"[\d.]+", "N", reason)] += 1
        if reasons:
            print("  Dropped:", ", ".join(f"{reason} {count}" for reason, count in reasons.most_common(5)))
    shoes = [_title(p) for p in products if part_for_type(p.get("product_type")) == "Sneakers"]
    tracked = [t for t in shoes if re.search(r"waffle ?cup|pop ?cush|dunk", t, re.IGNORECASE)]
    print(f"\nShoe titles naming Wafflecup, PopCush, or Dunk: {len(tracked)}")
    for title in tracked[:10]:
        print(f"  {title}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
