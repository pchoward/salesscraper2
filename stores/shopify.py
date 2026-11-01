"""Any Shopify store's sale collection, from its public ``products.json`` feed.

A store is a ``ShopifyStore``: its name, domain, sale collection, and which
Shopify ``product_type`` values map to which report part. Everything else
is shared (TGM, Kinetic, SPoT):

* The feed ``/collections/<sale>/products.json?limit=250&page=N`` is read one
  page at a time, with a pause between pages, until a page is empty or
  short. A failed page fails that store for the run.
* A variant is on sale only when ``compare_at_price`` is above ``price``;
  variants the feed marks ``available: false`` are skipped.
* Types not in the store's map are skipped before the filters, except the
  types mapped to ``BY_TITLE``, whose part is read from the title (a store
  that files decks and completes together as "Skateboards").
* The vendor is added to the name when the title leaves the brand out,
  because the shared filters find brands by name.
* The shared filters still decide brands, deck sizes and discounts, the
  tracked sneaker and accessory lists, and cruiser/longboard exclusions.

``preview(store)`` prints what a live run would keep and writes nothing.
"""

import collections
import json
import logging
import re
import time
import urllib.request
from urllib.parse import quote

from filters import extract_deck_dimensions, extract_deck_size, filter_reason, normalize_product_name, normalize_url
from dimensions import set_wheelbase
from part_specs import ordered_shoe_sizes
from protection import classify as classify_protection
from stores.base import Scraper
from stores.ccs import _amount, _money, _plain, _shoe_offers, _stock_known, _variants_of, apply_stock, set_protection_fields

logger = logging.getLogger("stores.shopify")

PAGE_LIMIT = 250
MAX_PAGES = 20
PAGE_DELAY = 1.5  # seconds between page requests
STOCK_DELAY = 0.5  # seconds between product stock reads
MAX_STOCK_READS = 120  # per store and part, per run
# Parts whose sizes come from per-variant stock.
SIZED_PARTS = ("Sneakers", "Protection")
ALL_PARTS = ("Decks", "Wheels", "Trucks", "Bearings", "Completes", "Sneakers", "Accessories", "Protection")
BY_TITLE = "by title"
_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

# Types most skate shops use. A store adds its own on top (``extra_types``).
COMMON_TYPES = {
    "decks": "Decks",
    "deck": "Decks",
    "wheels": "Wheels",
    "trucks": "Trucks",
    "bearings": "Bearings",
    "grip tape": "Accessories",
    "griptape": "Accessories",
    "hardware": "Accessories",
    "risers": "Accessories",
    "tool": "Accessories",
    "completes": "Completes",
    "complete": "Completes",
    # Protective gear. The subtype comes from protection.classify.
    "helmets": "Protection",
    "helmet": "Protection",
    "combo pads": "Protection",
    "pad sets": "Protection",
    "knee pads": "Protection",
    "elbow pads": "Protection",
    "wrist guards": "Protection",
    "hip pads": "Protection",
    "impact shorts": "Protection",
    "pads": "Protection",
    "protective gear": "Protection",
    "protection": "Protection",
}

_TITLE_RULES = (
    ("Completes", re.compile(r"\bcompletes?\b", re.IGNORECASE)),
    ("Decks", re.compile(r"\bdecks?\b", re.IGNORECASE)),
    ("Wheels", re.compile(r"\bwheels?\b", re.IGNORECASE)),
    ("Trucks", re.compile(r"\btrucks?\b", re.IGNORECASE)),
    ("Bearings", re.compile(r"\bbearings?\b", re.IGNORECASE)),
)

# Words in a vendor name that are not the brand: "OJ Wheels", "Ace Trucks MFG".
_VENDOR_FILLER = {"wheels", "wheel", "trucks", "truck", "bearings", "bearing", "skateboards", "skateboard",
                  "skate", "mfg", "co", "company", "inc", "griptape", "grip", "tape", "hardware", "shoes"}


class ShopifyStore:
    def __init__(self, store, display_name, base, collection="sale", extra_types=None, own_vendor="", types=None,
                 brand_of=None, title_part=None, details=None, unknown_by_title=False, more_collections=()):
        self.store = store
        self.display_name = display_name
        self.base = base.rstrip("/")
        self.sale_json = f"{self.base}/collections/{collection}/products.json"
        # Stores that split their sale (parts, wheels, frames...) read every
        # listed collection; a product in two is kept once.
        self.sale_jsons = [self.sale_json] + [f"{self.base}/collections/{name}/products.json" for name in more_collections]
        # ``types`` replaces the skate-shop types (another sport's store).
        self.types = dict(COMMON_TYPES if types is None else types, **(extra_types or {}))
        # The shop's own name as a vendor is not a brand ("TGM Skateboards").
        self.own_vendor = own_vendor.casefold()
        # vendor -> brand name. When set, each listing carries that brand
        # (BMX: Albe's vendors), instead of the page guessing from the title.
        self.brand_of = brand_of
        # title -> part for types mapped to BY_TITLE (default: skate parts).
        self.title_part = title_part
        # (item, product, type_key) -> None: adds sport-specific fields.
        self.details = details
        # A store whose types aren't known yet: unmapped types are read from
        # the title too, instead of skipped.
        self.unknown_by_title = unknown_by_title
        self.cache = {}


def type_key(product_type):
    key = re.sub(r"[^a-z0-9 ]", "", str(product_type or "").casefold())
    return re.sub(r"\s+", " ", key).strip()


def part_for_title(title):
    """The part a title names: protective gear, complete, deck, wheels, trucks, or bearings."""
    if classify_protection(title):
        return "Protection"
    for part, pattern in _TITLE_RULES:
        if pattern.search(title or ""):
            return part
    return None


def part_for(store, product_type, title=""):
    """The report part for a product, or None to skip it."""
    part = store.types.get(type_key(product_type))
    if part is None and getattr(store, "unknown_by_title", False):
        part = BY_TITLE
    if part == BY_TITLE:
        return (getattr(store, "title_part", None) or part_for_title)(title)
    return part


def _fetch_json(url, timeout=30):
    request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8", "replace"))
    except Exception as exc:
        logger.error("Shopify catalog fetch failed for %s: %s", url, exc)
        return None


def load_sale_products(store, fetch=None, sleep=time.sleep):
    """Every product in the store's sale collection, or None when any page fails.

    All parts share one download per run. A caller that passes ``fetch``
    does not read or write that cache.
    """
    own_fetch = fetch is None
    if own_fetch and "products" in store.cache:
        return store.cache["products"]
    fetch = fetch or _fetch_json
    sale_jsons = getattr(store, "sale_jsons", None) or [store.sale_json]
    products = []
    seen = set()
    read = 0
    for index, sale_json in enumerate(sale_jsons):
        if index:
            sleep(PAGE_DELAY)
        batch_products = _read_collection(store, sale_json, fetch, sleep)
        if batch_products is None:
            if len(sale_jsons) == 1:
                return None
            # One of several collections (a seasonal one that ended): the
            # store still counts as read when another collection worked.
            logger.warning("%s: could not read %s; using the other sale collections", store.store, sale_json)
            continue
        read += 1
        for product in batch_products:
            key = (product.get("id") or product.get("handle")) if isinstance(product, dict) else None
            if key is not None and key in seen:
                continue
            if key is not None:
                seen.add(key)
            products.append(product)
    if not read:
        return None
    if own_fetch:
        store.cache["products"] = products
        log_feed_summary(store, products)
    return products


def _read_collection(store, sale_json, fetch, sleep):
    products = []
    for page in range(1, MAX_PAGES + 1):
        if page > 1:
            sleep(PAGE_DELAY)
        payload = fetch(f"{sale_json}?limit={PAGE_LIMIT}&page={page}")
        if not isinstance(payload, dict) or not isinstance(payload.get("products"), list):
            return None
        batch = payload["products"]
        products.extend(batch)
        if len(batch) < PAGE_LIMIT:
            return products
    logger.error("%s sale catalog exceeded %s pages", store.store, MAX_PAGES)
    return None


def feed_summary(store, products):
    """What the sale feed held and why products were left out, before the filters."""
    marked, sold_out = 0, 0
    unmapped = collections.Counter()
    for product in products or []:
        if not isinstance(product, dict):
            continue
        priced = [v for v in _variants_of(product)
                  if (_amount(v.get("price")) or 0) > 0 and (_amount(v.get("compare_at_price")) or 0) > (_amount(v.get("price")) or 0)]
        if not priced:
            continue
        if not sale_variants(product):
            sold_out += 1
            continue
        marked += 1
        title = title_with_brand(product, store.own_vendor, store.brand_of)
        if part_for(store, product.get("product_type"), title) is None:
            unmapped[str(product.get("product_type") or "(none)").strip() or "(none)"] += 1
    return {"products": len(products or []), "marked_down": marked, "sold_out": sold_out,
            "unmapped_types": unmapped.most_common()}


def log_feed_summary(store, products):
    try:
        summary = feed_summary(store, products)
    except Exception as exc:  # logging only; never fails a run
        logger.error("%s feed summary failed: %s", store.store, exc)
        return
    skipped = sum(count for _, count in summary["unmapped_types"])
    logger.info("%s sale feed: %s products, %s marked down and buyable, %s marked down but sold out, "
                "%s in product types with no category", store.store, summary["products"], summary["marked_down"],
                summary["sold_out"], skipped)
    if summary["unmapped_types"]:
        logger.info("%s product types with no category: %s", store.store,
                    ", ".join(f"{kind} ({count})" for kind, count in summary["unmapped_types"][:25]))


def enrich_stock(store, products, part, fetch=None, sleep=time.sleep, limit=MAX_STOCK_READS):
    """Add each variant's ``available`` flag for this part's listings.

    Some sale feeds (Exodus, Kinetic) leave ``available`` out, so no size
    can be called in stock. The product's ``/products/<handle>.js`` has it,
    as CCS already uses. Only products of this part that the shared
    filters would keep are read, with a short pause between reads. An
    unreadable product leaves its sizes unknown.
    """
    fetch = fetch or _fetch_json
    reads = 0
    for product in products or []:
        if not isinstance(product, dict) or _stock_known(_variants_of(product)):
            continue
        title = title_with_brand(product, store.own_vendor, store.brand_of)
        if part_for(store, product.get("product_type"), title) != part:
            continue
        sale = sale_variants(product)
        handle = str(product.get("handle") or "").strip()
        if not sale or not handle:
            continue
        cheapest = min(sale, key=lambda variant: _amount(variant.get("price")))
        if filter_reason(title, part, "", _money(cheapest.get("price")), _money(cheapest.get("compare_at_price")),
                         _plain(product.get("body_html") or ""), str(product.get("product_type") or "")):
            continue
        if reads >= limit:
            logger.warning("%s %s: stock read for only the first %s products", store.store, part, limit)
            break
        if reads:
            sleep(STOCK_DELAY)
        reads += 1
        live = fetch(f"{store.base}/products/{quote(handle, safe='')}.js")
        if isinstance(live, dict) and isinstance(live.get("variants"), list):
            apply_stock(product, live)
    return products


def sale_variants(product):
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


def title_with_brand(product, own_vendor="", brand_of=None):
    """The product title, with the vendor's brand in front when the title leaves it out.

    "Formula Four Classic 54mm" from vendor Spitfire reads "Spitfire Formula
    Four Classic 54mm". A title that already names the brand ("OJ III
    Wheels" from "OJ Wheels") is left alone.
    """
    title = normalize_product_name((product or {}).get("title") or "")
    vendor = normalize_product_name((product or {}).get("vendor") or "")
    if not vendor or (own_vendor and vendor.casefold().startswith(own_vendor)):
        return title
    if brand_of:
        vendor = brand_of(vendor)
        if not vendor:  # not a brand ("Scratch & Dent")
            return title
    brand = [word for word in re.findall(r"[a-z0-9]+", vendor.casefold()) if word not in _VENDOR_FILLER]
    words = set(re.findall(r"[a-z0-9]+", title.casefold()))
    if brand and all(word in words for word in brand):
        return title
    return f"{vendor} {title}".strip()


def variant_label(variant):
    label = normalize_product_name(variant.get("title") or "")
    return "" if label.casefold() in ("", "default title") else label


def width_variants(title, sale):
    """Deck sale variants that each name a different width, when the title names none."""
    if len(sale) < 2 or extract_deck_dimensions(title)[0] is not None:
        return []
    widths = [extract_deck_dimensions(variant_label(variant))[0] for variant in sale]
    if any(width is None for width in widths) or len(set(widths)) != len(widths):
        return []
    return sale


def _images(product):
    return [photo["src"] for photo in (product or {}).get("images") or [] if isinstance(photo, dict) and photo.get("src")]


class ShopifyScraper(Scraper):
    """One part from a Shopify store's shared sale feed."""

    def __init__(self, store, part):
        super().__init__(store.store, store.sale_json, part)
        self.shop = store

    def scrape(self):
        products = load_sale_products(self.shop)
        if products is None:
            return None
        if self.part in SIZED_PARTS:
            enrich_stock(self.shop, products, self.part)
        return self.products_from(products)

    def parse(self, html):
        """Accept a saved products.json body. Shopify stores are never read as HTML."""
        text = str(html or "").lstrip()
        if not text.startswith("{"):
            logger.error("%s parser expected products.json, not HTML", self.shop.store)
            return []
        return self.products_from(json.loads(text).get("products") or [])

    def products_from(self, products):
        kept = []
        seen = set()
        for product in products or []:
            if not isinstance(product, dict):
                continue
            title = title_with_brand(product, self.shop.own_vendor, self.shop.brand_of)
            if part_for(self.shop, product.get("product_type"), title) != self.part:
                continue
            handle = str(product.get("handle") or "").strip()
            sale = sale_variants(product)
            if not handle or not title or not sale:
                continue
            base_url = normalize_url(f"{self.shop.base}/products/{handle}")
            split = width_variants(title, sale) if self.part == "Decks" else []
            offers = [(f"{title} {variant_label(v)}", f"{base_url}?variant={v.get('id')}", [v]) for v in split] or [
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
        logger.info("Parsed %s %s %s", len(kept), self.shop.store, self.part)
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
            "store": self.shop.store,
            "product_type": product_type,
        }
        if self.shop.brand_of:
            vendor = normalize_product_name(product.get("vendor") or "")
            brand = self.shop.brand_of(vendor) if vendor else ""
            if brand and not (self.shop.own_vendor and vendor.casefold().startswith(self.shop.own_vendor)):
                item["brand"] = brand
        if self.shop.details:
            try:
                self.shop.details(item, product, type_key(product_type))
            except Exception as exc:  # a detail never drops a listing
                logger.error("%s details failed for %s: %s", self.shop.store, url, exc)
        images = _images(product)
        if images:
            item["image"] = images[0]
            if len(images) > 1:
                item["images"] = images
        if self.part in ("Decks", "Completes"):
            size = extract_deck_size(name)
            if size:
                item["size"] = size
            set_wheelbase(item, description)
        if self.part == "Protection":
            set_protection_fields(item, name, product_type, variants)
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
        item = self._finish(item, None, self.shop.base)
        from product_specs import enrich
        return enrich(item, description, product, [dict(v, **{key: _amount(v[key]) for key in ('price', 'compare_at_price') if key in v}) for v in variants])


def scrapers_for(store, parts=ALL_PARTS):
    return [ShopifyScraper(store, part) for part in parts]


def preview(store, parts=ALL_PARTS):
    """Print a live run's counts, examples, and drop reasons per part. Writes nothing."""
    logging.basicConfig(level=logging.WARNING)
    products = load_sale_products(store)
    if products is None:
        print(f"{store.display_name} sale feed could not be read.")
        return 1
    types = collections.Counter(str(product.get("product_type") or "(none)") for product in products)
    print(f"{len(products)} products in the sale collection.")
    print("Product types:", ", ".join(f"{kind} {count}" for kind, count in types.most_common()))
    for scraper in scrapers_for(store, parts):
        items = scraper.products_from(products)
        print(f"\n{scraper.part}: {len(items)} kept of {scraper.candidates} candidates")
        for item in items[:5]:
            print(f"  ${item['price_new']} (was ${item['price_old']})  {item['name']}")
        reasons = collections.Counter()
        cruisers = []
        for product in products:
            title = title_with_brand(product, store.own_vendor, store.brand_of)
            if part_for(store, product.get("product_type"), title) != scraper.part or not sale_variants(product):
                continue
            reason = filter_reason(title, scraper.part, "", "1", "2", _plain(product.get("body_html") or ""),
                                   str(product.get("product_type") or ""))
            if reason and not reason.startswith(("known-brand deck", "unknown-brand deck")):
                reasons[re.sub(r"[\d.]+", "N", reason)] += 1
            if reason == "cruiser" and scraper.part in ("Decks", "Completes"):
                cruisers.append(title)
        if reasons:
            print("  Dropped:", ", ".join(f"{reason} {count}" for reason, count in reasons.most_common(5)))
        for title in cruisers:
            print(f"    cruiser: {title}")
    shoes = [title_with_brand(p, store.own_vendor, store.brand_of) for p in products
             if part_for(store, p.get("product_type"), title_with_brand(p, store.own_vendor, store.brand_of)) == "Sneakers"]
    tracked = [t for t in shoes if re.search(r"waffle ?cup|pop ?cush|dunk", t, re.IGNORECASE)]
    print(f"\nShoe titles naming Wafflecup, PopCush, or Dunk: {len(tracked)}")
    for title in tracked[:10]:
        print(f"  {title}")
    return 0
