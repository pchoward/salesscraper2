"""Christy Sports (christysports.com, Salesforce Commerce): clearance ski gear.

Its clearance ski pages (/sale/clearance/ski/, allowed by robots.txt) render
product tiles with machine-readable prices: the list price in
``<span class="strike-through list"><span class="value" content="529.99">``
and the sale price in ``<span class="sales"><span class="value" content=...>``.
Pages are read a couple of seconds apart and shared by every part in a run.
The section is ski equipment; the name says which part (boots, poles, skis,
bindings, helmets).
"""

import html as html_lib
import logging
import re
import time
import urllib.request

from stores.base import Scraper

logger = logging.getLogger("stores.christy")

BASE = "https://www.christysports.com"
LISTING = BASE + "/sale/clearance/ski/?sz={size}&start={start}"
PAGE_SIZE = 24
MAX_PAGES = 40
PAGE_DELAY = 2.0
_USER_AGENT = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
               "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
PARTS = ("Skis", "Boots", "Bindings", "Poles", "Helmets", "Protection", "Packs")  # = sports.SKI.parts

_TILE_START = re.compile(r'<div class="product-tile[^"]*" data-pid="([^"]+)"')
_LINK = re.compile(r'href="(/product/[^"?]+\.html)')
_NAME = re.compile(r'<img[^>]+class="product-tile-image[^"]*"[^>]*\btitle="([^"]+)"|\btitle="([^"]+)"[^>]*class="product-tile-image', re.I)
_IMAGE = re.compile(r'<img[^>]+class="product-tile-image[^"]*"[^>]*\bsrc="([^"]+)"|\bsrc="([^"]+)"[^>]*class="product-tile-image', re.I)
_LIST = re.compile(r'class="strike-through list"\s*>\s*<span class="value" content="([\d.]+)"')
_SALE = re.compile(r'class="sales"\s*>\s*<span class="value" content="([\d.]+)"')
_cache = {}


def _fetch(url, timeout=30):
    request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT, "Accept": "text/html"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read().decode("utf-8", "replace")
    except Exception as exc:
        logger.error("Christy Sports page fetch failed for %s: %s", url, exc)
        return None


def part_for(name):
    """The part a clearance ski product's name states, or None."""
    words = " " + re.sub(r"[^a-z0-9]+", " ", str(name or "").casefold()) + " "
    # Backpacks and avalanche packs in the ski clearance (sports/packs.py).
    from sports import packs
    if packs.is_pack(name):
        return packs.PART
    if re.search(r" helmets? ", words):
        return "Helmets"
    if re.search(r" goggles? ", words) and not re.search(r" lens(?:es)? ", words):
        return "Protection"
    from sports.protection import protects
    if protects(str(name or "")):
        return "Protection"  # back protectors, wrist guards, impact shorts
    if re.search(r" boots? ", words):
        return "Boots"
    if re.search(r" poles? ", words):
        return "Poles"
    if " skis " in words or " ski w " in words or words.rstrip().endswith(" ski"):
        return "Skis"
    if re.search(r" bindings? ", words):
        return "Bindings"
    return None


def tiles(page):
    """[{pid, url, name, image, list, sale}] from one listing page."""
    page = page or ""
    starts = [match for match in _TILE_START.finditer(page)]
    found = []
    for index, match in enumerate(starts):
        end = starts[index + 1].start() if index + 1 < len(starts) else len(page)
        block = page[match.start():end]
        link, name, image = _LINK.search(block), _NAME.search(block), _IMAGE.search(block)
        listed, sale = _LIST.search(block), _SALE.search(block)
        if not (link and name and sale):
            continue
        found.append({
            "pid": match.group(1),
            "url": BASE + html_lib.unescape(link.group(1)),
            "name": " ".join(html_lib.unescape(name.group(1) or name.group(2)).split()),
            "image": html_lib.unescape((image.group(1) or image.group(2))) if image else "",
            "list": listed.group(1) if listed else None,
            "sale": sale.group(1),
        })
    return found


def load(fetch=None, sleep=time.sleep):
    """Every clearance ski tile, or None when the first page can't be read."""
    own = fetch is None
    if own and "tiles" in _cache:
        return _cache["tiles"]
    fetch = fetch or _fetch
    found, seen = [], set()
    for index in range(MAX_PAGES):
        if index:
            sleep(PAGE_DELAY)
        page = fetch(LISTING.format(size=PAGE_SIZE, start=index * PAGE_SIZE))
        if page is None:
            if not index:
                return None
            break
        batch = [tile for tile in tiles(page) if tile["pid"] not in seen]
        if not batch:
            break
        for tile in batch:
            seen.add(tile["pid"])
        found.extend(batch)
    if own:
        _cache["tiles"] = found
    logger.info("Christy Sports clearance ski: %s products", len(found))
    return found


class ChristyScraper(Scraper):
    def __init__(self, part):
        super().__init__("Christy Sports", LISTING.format(size=PAGE_SIZE, start=0), part)

    def scrape(self):
        found = load()
        if found is None:
            return None
        return self.items_from(found)

    def parse(self, html):
        return self.items_from(tiles(html))

    def items_from(self, found):
        import sports
        from sports import brands
        from sports.ski import evo, specs

        kept = []
        for tile in found:
            if part_for(tile["name"]) != self.part:
                continue
            try:
                price, old = float(tile["sale"]), float(tile["list"] or 0)
            except ValueError:
                continue
            if not (0 < price < old):
                continue
            name = tile["name"]
            if not self._keep(name, tile["url"], f"{price:.2f}", f"{old:.2f}"):
                continue
            item = {"name": name, "url": tile["url"], "price_new": f"{price:.2f}", "price_old": f"{old:.2f}",
                    "availability": "Check store", "part": self.part, "store": "Christy Sports"}
            first = name.split()[0] if name.split() else ""
            brand = brands.canonical(first, sports.SKI.aliases_file())
            if brand and brand != first:
                item["brand"] = brand
            if tile["image"]:
                item["image"] = tile["image"]
            fields = evo.fields(self.part, name, "", [], "")
            who = specs.gender(name, [])
            if who:
                item["gender"] = who
                fields["gender"] = [who]
            if fields:
                item["technical_offers"] = [{"variant_id": tile["pid"], "price": price, "compare": old,
                                             "available": None, "specs": fields}]
                item["technical_specs"] = fields
            kept.append(item)
        logger.info("Parsed %s Christy Sports %s", len(kept), self.part)
        return kept


def scrapers():
    return [ChristyScraper(part) for part in PARTS]
