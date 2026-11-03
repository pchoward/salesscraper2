"""SkatePro (skatepro.com/en-us, US prices): protection for Skate, BMX and Ski.

The owner asked for more Triple 8, Shadow and other helmets and pads "from
places like SkatePro" (2026-11-03). SkatePro is not Shopify; its category
pages list products as cards with the brand, name, selling price and, on a
sale, the normal price (``product_card__list_price``). robots.txt allows the
category pages (only its catalog/wishlist/admin paths are disallowed).

Pages are read one at a time, a couple of seconds apart, and shared by every
sport and part in a run. A card is a deal only when its normal price is above
its selling price. Each sport reads its own categories (skate, BMX or snow
protection), so a piece is listed under the sport SkatePro files it for.
"""

import html as html_lib
import logging
import re
import time
import urllib.request

from stores.base import Scraper

logger = logging.getLogger("stores.skatepro")

STORE = "SkatePro"
BASE = "https://www.skatepro.com/en-us"
PAGE_DELAY = 2.0
MAX_PAGES = 8
_USER_AGENT = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
               "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

# Category ids per sport and part (store probe, 2026-11-03).
CATEGORIES = {
    "skate": {"Protection": (486, 488, 497, 475, 496, 51)},   # helmets, kids helmets, knee, elbow, impact shorts x2
    "bmx": {"Protection": (482, 490, 498, 473, 595)},         # helmets, kids helmets, knee, elbow, padded shorts
    "ski": {"Helmets": (316, 485),                             # ski and snowboard helmets
            "Protection": (323, 504, 492, 493)},               # back protectors, impact shorts
}

_CARD = re.compile(r'<a class="product_card" href="([^"]+)">(.*?)</a>', re.S)
_BRAND = re.compile(r'class="product_card__brand">\s*(.*?)\s*<', re.S)
_NAME = re.compile(r'class="product_card__name">\s*(.*?)\s*<', re.S)
_SALE = re.compile(r'product_card__selling_price[^"]*">\s*<span class="product_card__price_value">\s*\$([\d,]+\.\d{2})', re.S)
_LIST = re.compile(r'class="product_card__list_price">\s*\$([\d,]+\.\d{2})', re.S)
_IMAGE = re.compile(r'<img src="(https://[^"]+)"')
_cache = {}
_read_any = []  # a page was read this run: wait before the next one


def _fetch(url, timeout=30):
    request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT, "Accept": "text/html"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read().decode("utf-8", "replace")
    except Exception as exc:
        logger.error("SkatePro page fetch failed for %s: %s", url, exc)
        return None


def _text(value):
    return " ".join(html_lib.unescape(re.sub(r"<[^>]+>", " ", value or "")).split())


def cards(page):
    """[{url, brand, name, price, list_price, image}] from one category page."""
    found = []
    for match in _CARD.finditer(page or ""):
        href, block = match.group(1), match.group(2)
        sale, listed = _SALE.search(block), _LIST.search(block)
        brand, name, image = _BRAND.search(block), _NAME.search(block), _IMAGE.search(block)
        if not name or not sale:
            continue
        found.append({
            "url": html_lib.unescape(href).split("?", 1)[0],
            "brand": _text(brand.group(1)) if brand else "",
            "name": _text(name.group(1)),
            "price": float(sale.group(1).replace(",", "")),
            "list_price": float(listed.group(1).replace(",", "")) if listed else None,
            "image": html_lib.unescape(image.group(1)) if image else "",
        })
    return found


def load(category, fetch=None, sleep=time.sleep):
    """Every card in one category (all its pages), or None when page 1 can't be read."""
    own = fetch is None
    if own and category in _cache:
        return _cache[category]
    fetch = fetch or _fetch
    found, seen = [], set()
    for page in range(1, MAX_PAGES + 1):
        if page > 1 or _read_any:
            sleep(PAGE_DELAY)
        _read_any.append(True)
        body = fetch(f"{BASE}/c{category}.htm" + (f"?page={page}" if page > 1 else ""))
        if body is None:
            if page == 1:
                return None
            break
        batch = [card for card in cards(body) if card["url"] not in seen]
        if not batch:
            break
        seen.update(card["url"] for card in batch)
        found.extend(batch)
    if own:
        _cache[category] = found
    logger.info("SkatePro c%s: %s products, %s on sale", category, len(found),
                sum(1 for card in found if card["list_price"] and card["list_price"] > card["price"]))
    return found


class SkateProScraper(Scraper):
    """One sport's part from SkatePro's protection categories.

    ``extra(item)`` adds the sport's own fields (protection filters, kind).
    """

    def __init__(self, sport_id, part, extra=None, fetch=None, sleep=time.sleep):
        self.sport_id = sport_id
        self.categories = CATEGORIES[sport_id][part]
        super().__init__(STORE, f"{BASE}/c{self.categories[0]}.htm", part)
        self.extra = extra
        self._fetch, self._sleep = fetch, sleep

    def scrape(self):
        found, read = [], 0
        for category in self.categories:
            batch = load(category, self._fetch, self._sleep)
            if batch is None:
                continue
            read += 1
            found.extend(batch)
        if not read:
            return None
        return self.items_from(found)

    def parse(self, html):
        return self.items_from(cards(html))

    def items_from(self, found):
        from sports import protection

        kept, seen = [], set()
        for card in found:
            old, price = card["list_price"], card["price"]
            if not old or old <= price or card["url"] in seen:
                continue
            name = card["name"]
            if card["brand"] and card["brand"].casefold().split()[0] not in name.casefold():
                name = f"{card['brand']} {name}"
            # BMX: the brand stores' rule (no snow or other sports' gear). Ski's
            # and Skate's categories are already theirs; Skate's own
            # protective-gear rules apply in ``_keep``.
            if self.sport_id == "bmx" and not protection.suits("bmx", name):
                continue
            if not self._keep(name, card["url"], f"{price:.2f}", f"{old:.2f}"):
                continue
            seen.add(card["url"])
            item = {"name": name, "url": card["url"], "price_new": f"{price:.2f}", "price_old": f"{old:.2f}",
                    "availability": "In stock", "part": self.part, "store": STORE}
            if card["brand"]:
                import sports
                from sports import brands
                item["brand"] = brands.canonical(card["brand"], sports.get(self.sport_id).aliases_file()) or card["brand"]
            if card["image"]:
                item["image"] = card["image"]
            if self.extra:
                self.extra(item)
            kept.append(item)
        logger.info("Parsed %s SkatePro %s (%s)", len(kept), self.part, self.sport_id)
        return kept


def technical(item, fields):
    """One offer with the listing's filter fields (BMX, Ski sidebars)."""
    if not fields:
        return
    price, old = float(item["price_new"]), float(item["price_old"])
    item["technical_offers"] = [{"variant_id": item["url"], "price": price, "compare": old, "available": True,
                                 "specs": fields}]
    item["technical_specs"] = fields


def bmx_extra(item):
    from sports import protection
    from sports.bmx import specs
    fields = protection.fields(item["name"], sport="bmx")
    kind = specs.kind_for("", item["name"], item["part"])
    if kind:
        item["kind"] = kind
        fields["kind"] = [kind]
    technical(item, fields)


def ski_extra(item):
    from sports.ski import evo
    technical(item, evo.fields(item["part"], item["name"], "", [], ""))


def scrapers(sport_id, extra=None):
    return [SkateProScraper(sport_id, part, extra) for part in CATEGORIES[sport_id]]
