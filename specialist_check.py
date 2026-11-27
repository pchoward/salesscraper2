"""Specialist shop check for MTB (owner, 2026-11-26).

The front derailleurs were the lesson. Fanatik, an MTB-only shop, carries
none, while general bike shops still clear out old 2x/3x and road stock that
lands under MTB headings. This check makes that test regular. It is a monthly
audit, not a filter: it only lists candidates, and the store monitor decides
which are real before anything changes.

How it works:
1. Read the whole catalogs of the MTB-only shops we already scrape (Fanatik,
   Worldwide Cyclery, The Lost Co.) from their public Shopify
   ``products.json``. robots.txt is checked before every request.
2. Group our MTB listings from every other store by (store, product type).
3. Flag a group when no specialist product names all of its type's key
   words, in any order: "MTB Front Derailleurs" needs a product with both
   "front" and "derailleur"; "MTB Tires Folding" is found in "Folding Tire".

The report, ``catalogs/mtb/specialist_report.json``, marks the groups that are
new since the last run. The monitor posts only the real ones on the "Store
monitor" issue, as questions. Nothing here changes a listing.

    python specialist_check.py
"""
import datetime
import json
import logging
import os
import re
import sys
import time

from stores import shopify

logger = logging.getLogger("specialist_check")

FOLDER = os.path.join("catalogs", "mtb")
DATA = "previous_data.json"
REPORT = "specialist_report.json"
MIN_LISTINGS = 3  # a store's type with fewer listings isn't worth a question
SAMPLES = 3  # listing names shown per flagged group

# Words that say nothing about what the part is.
GENERIC = frozenset("""
    mtb mountain bike bicycle cycling component accessory part and or flat bar misc all road small sale other
    men women mens womens unisex the of for with gear equipment new used outlet clearance closeout item product
    general shop store deal hot default type
""".split())


def specialists():
    """The MTB-only shops, as their scrapers define them."""
    from sports.mtb import stores
    return (stores.FANATIK, stores.WORLDWIDE, stores.LOST_CO)


def _singular(word):
    if len(word) > 3 and word.endswith("ies"):
        return word[:-3] + "y"
    if len(word) > 3 and word.endswith("s") and not word.endswith(("ss", "us")):
        return word[:-1]
    return word


def tokens(text):
    """Lowercase, singular words of ``text``; numbers and punctuation dropped."""
    return [_singular(word) for word in re.findall(r"[a-z]+", str(text or "").lower())]


def key_words(product_type):
    """What a store's product type names, without its filing path or generic
    words: "COMPONENTS/DERAILLEURS/FRONT DERAILLEURS MTB" -> [front, derailleur]."""
    last = re.split(r"[/>|]", str(product_type or ""))[-1]
    return [word for word in tokens(last) if word not in GENERIC and len(word) > 1]


def word_bags(products):
    """Each specialist product's words (title, type and vendor), as sets."""
    return [frozenset(tokens(" ".join(str(product.get(field) or "") for field in ("title", "product_type", "vendor"))))
            for product in products]


def sold_by_specialists(product_type, bags):
    """False when no specialist product names everything this type names.
    None when the type names nothing (all generic words)."""
    key = set(key_words(product_type))
    if not key:
        return None
    return any(key <= bag for bag in bags)


def groups(current_data, skip_stores):
    """Our listings by (store, product type), other than the specialists'."""
    found = {}
    for items in current_data.values():
        for item in items or ():
            store, kind = item.get("store"), item.get("product_type")
            if not store or not kind or store in skip_stores:
                continue
            found.setdefault((store, kind), []).append(item)
    return found


def compare(current_data, catalogs, previous=None, skip_stores=()):
    """The report: every group the specialists don't sell, biggest first.
    ``skip_stores`` are the specialists that couldn't be read this time."""
    bags = word_bags(product for products in catalogs.values() for product in products)
    seen_before = {(entry["store"], entry["product_type"]) for entry in (previous or {}).get("flagged", ())}
    flagged = []
    for (store, kind), items in groups(current_data, set(catalogs) | set(skip_stores)).items():
        if len(items) < MIN_LISTINGS or sold_by_specialists(kind, bags) is not False:
            continue
        flagged.append({
            "store": store,
            "product_type": kind,
            "listings": len(items),
            "parts": sorted({item.get("part") or "" for item in items}),
            "key_words": key_words(kind),
            "samples": [item.get("name") for item in items[:SAMPLES]],
            "new": (store, kind) not in seen_before,
        })
    flagged.sort(key=lambda entry: (-entry["listings"], entry["store"], entry["product_type"]))
    return flagged


def read_catalog(store, fetch=None, sleep=time.sleep):
    """Every product in ``store``'s catalog as {title, product_type, vendor},
    or None when robots.txt forbids it or a page fails."""
    guarded = shopify.polite_fetch(store, fetch)
    wait = shopify._polite_sleep(store, sleep)
    products = []
    for page in range(1, shopify.WHOLE_SITE_MAX_PAGES + 1):
        if page > 1:
            wait(shopify.PAGE_DELAY)
        payload = guarded(f"{store.base}/products.json?limit={shopify.PAGE_LIMIT}&page={page}")
        if not isinstance(payload, dict) or not isinstance(payload.get("products"), list):
            logger.error("%s: catalog page %s could not be read", store.store, page)
            return None
        batch = payload["products"]
        products.extend({"title": p.get("title"), "product_type": p.get("product_type"), "vendor": p.get("vendor")}
                        for p in batch if isinstance(p, dict))
        if len(batch) < shopify.LAST_PAGE_UNDER:
            break
    return products


def _read(path, default):
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return default


def run(folder=FOLDER, today=None, read=read_catalog):
    today = today or datetime.date.today().isoformat()
    catalogs, unread = {}, []
    for store in specialists():
        products = read(store)
        if products:
            catalogs[store.store] = products
        else:
            unread.append(store.store)
    if not catalogs:
        logger.error("No specialist catalog could be read; report not written")
        return None
    path = os.path.join(folder, REPORT)
    report = {
        "date": today,
        "specialists": {name: len(products) for name, products in catalogs.items()},
        "unread": unread,
        "flagged": compare(_read(os.path.join(folder, DATA), {}), catalogs, _read(path, {}), unread),
    }
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=1, sort_keys=True)
        handle.write("\n")
    return report


def markdown(report):
    lines = [f"Specialist check {report['date']}: "
             + ", ".join(f"{name} {count}" for name, count in report["specialists"].items())
             + (f"; not read: {', '.join(report['unread'])}" if report["unread"] else "")]
    for entry in report["flagged"]:
        mark = "NEW " if entry["new"] else ""
        lines.append(f"- {mark}{entry['store']} / {entry['product_type']} ({entry['listings']}): "
                     + "; ".join(str(name) for name in entry["samples"]))
    return "\n".join(lines)


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    report = run()
    if report is None:
        return 1
    print(markdown(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
