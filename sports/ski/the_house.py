"""The House (the-house.com, Salesforce Commerce): on-sale ski hardgoods.

Its "on sale now" search pages are allowed by robots.txt and render each
product tile with structured data (``data-gtmdata``: name, id, price, brand,
category, subcategory, stock, percentOff), so no visual markup is scraped.
Pages are read one at a time, a couple of seconds apart, and shared by every
part in a run. Only in-stock ski skis, boots, bindings, poles and helmets are
kept; snowboard gear and clothing are left out.

The store states a percent off rather than a list price, so the "was" price
is worked back from it (price / (1 - percentOff)), rounded to the cent.
"""

import html as html_lib
import json
import logging
import re
import time
import urllib.request

from stores.base import Scraper

logger = logging.getLogger("stores.the_house")

BASE = "https://www.the-house.com"
SEARCH = BASE + "/search?pmid=on-sale-now&start={start}&sz={size}"
PAGE_SIZE = 48
MAX_PAGES = 40
PAGE_DELAY = 2.0
_USER_AGENT = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
               "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
PARTS = ("Skis", "Boots", "Bindings", "Poles", "Helmets")

_TILE = re.compile(r'data-pid="(\d+)"\s+data-gtmdata="([^"]+)"')
_IMAGE = re.compile(r'data-(?:bg|src)="(https://[^"]+?\.(?:jpg|jpeg|png|webp)[^"]*)"', re.I)
_cache = {}


def _fetch(url, timeout=30):
    request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT, "Accept": "text/html"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read().decode("utf-8", "replace")
    except Exception as exc:
        logger.error("The House page fetch failed for %s: %s", url, exc)
        return None


def part_for(data):
    """Skis / Boots / Bindings / Poles / Helmets from the tile's category, or None."""
    text = " ".join(str(data.get(key) or "") for key in ("category", "subcategory", "dimension46")).casefold()
    if "snowboard" in text or "ski" not in text and "helmet" not in text:
        return None
    for words, part in (("boot", "Boots"), ("binding", "Bindings"), ("pole", "Poles"), ("helmet", "Helmets"),
                        ("skis", "Skis"), ("ski", "Skis")):
        if words in text:
            return part
    return None


def tiles(page):
    """[(pid, data, image)] from one search page's product tiles."""
    found = []
    for match in _TILE.finditer(page or ""):
        try:
            data = json.loads(html_lib.unescape(match.group(2)))
        except ValueError:
            continue
        image = _IMAGE.search(page, match.end(), match.end() + 4000)
        found.append((match.group(1), data, html_lib.unescape(image.group(1)) if image else ""))
    return found


def load(fetch=None, sleep=time.sleep):
    """Every on-sale tile, or None when the first page can't be read."""
    own = fetch is None
    if own and "tiles" in _cache:
        return _cache["tiles"]
    fetch = fetch or _fetch
    found, seen = [], set()
    for index in range(MAX_PAGES):
        if index:
            sleep(PAGE_DELAY)
        page = fetch(SEARCH.format(start=index * PAGE_SIZE, size=PAGE_SIZE))
        if page is None:
            if not index:
                return None
            break
        batch = [tile for tile in tiles(page) if tile[0] not in seen]
        if not batch:
            break
        for tile in batch:
            seen.add(tile[0])
        found.extend(batch)
    if own:
        _cache["tiles"] = found
    logger.info("The House on-sale search: %s products", len(found))
    import collections
    tally = collections.Counter(f"{data.get('category')}/{data.get('subcategory')}" for _, data, _ in found)
    logger.info("The House categories: %s", ", ".join(f"{name} ({count})" for name, count in tally.most_common(40)))
    return found


def was_price(price, percent):
    try:
        price, percent = float(price), float(percent)
    except (TypeError, ValueError):
        return None
    if price <= 0 or not 0 < percent < 100:
        return None
    return round(price / (1 - percent / 100), 2)


class TheHouseScraper(Scraper):
    def __init__(self, part):
        super().__init__("The House", SEARCH.format(start=0, size=PAGE_SIZE), part)

    def scrape(self):
        found = load()
        if found is None:
            return None
        return self.items_from(found)

    def parse(self, html):
        return self.items_from(tiles(html))

    def items_from(self, found):
        from sports import brands
        import sports
        from sports.ski import evo, specs

        kept = []
        for pid, data, image in found:
            if part_for(data) != self.part:
                continue
            if str(data.get("dimension20") or "").upper() not in ("IN_STOCK", ""):
                continue
            price = data.get("price")
            old = was_price(price, data.get("percentOff"))
            name = " ".join(str(data.get("name") or "").split())
            if not name or old is None:
                continue
            brand = brands.canonical(data.get("brand") or "", sports.SKI.aliases_file())
            if brand and brand.casefold().split()[0] not in name.casefold():
                name = f"{brand} {name}"
            url = f"{BASE}/{pid}.html"
            if not self._keep(name, url, f"{float(price):.2f}", f"{old:.2f}"):
                continue
            item = {"name": name, "url": url, "price_new": f"{float(price):.2f}", "price_old": f"{old:.2f}",
                    "availability": "In stock", "part": self.part, "store": "The House"}
            if brand:
                item["brand"] = brand
            if image:
                item["image"] = image
            style = str(data.get("dimension46") or "").replace("-", " ")
            fields = evo.fields(self.part, name, style, [], "")
            who = specs.gender(name, [])
            if who:
                item["gender"] = who
                fields["gender"] = [who]
            if fields:
                item["technical_offers"] = [{"variant_id": pid, "price": float(price), "compare": old,
                                             "available": True, "specs": fields}]
                item["technical_specs"] = fields
            kept.append(item)
        logger.info("Parsed %s The House %s", len(kept), self.part)
        return kept


def scrapers():
    return [TheHouseScraper(part) for part in PARTS]
