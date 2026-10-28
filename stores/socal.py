"""SoCal Skateshop clearance (socalskateshop.com, a Miva Merchant store).

The clearance category ``/Clearance-Skateboard-Products.html`` mixes every
kind of product. It is read 72 items a page (the largest page size the
store offers) with ``?CatListingOffset=N&Offset=N&Per_Page=72``, and robots.txt's
``Crawl-delay: 5`` is honored between pages. It disallows nothing else.

Each card (``.x-product-list__item``) has the link and name, the regular
price struck through (``<s>$49.95</s>``), and the sale price in red. The
part comes from the name (deck, complete, wheels, trucks, bearings,
grip/hardware, protective gear), like Deathgear; anything else is skipped.
The shared filters still decide brands, deck sizes, and discounts.

``python -m stores.socal`` previews what a run would keep.
"""

import logging
import re
import time
import urllib.request
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from filters import extract_deck_size, normalize_product_name, normalize_url
from stores.base import Scraper
from stores.ccs import set_protection_fields
from stores.deathgear import part_for_title

logger = logging.getLogger("stores.socal")

STORE = "SoCal"
DISPLAY_NAME = "SoCal Skateshop"
BASE = "https://socalskateshop.com/"
CATEGORY = "https://socalskateshop.com/Clearance-Skateboard-Products.html"
PER_PAGE = 72
MAX_PAGES = 10
CRAWL_DELAY = 5  # robots.txt: Crawl-delay: 5
PARTS = ("Decks", "Wheels", "Trucks", "Bearings", "Completes", "Accessories", "Protection")
_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
_PRICE = re.compile(r"\$\s?(\d[\d,]*\.\d{2})")
_CACHE = {}


def page_url(offset):
    return f"{CATEGORY}?CatListingOffset={offset}&Offset={offset}&Per_Page={PER_PAGE}&Sort_By=newest"


def _fetch(url, timeout=30):
    request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT, "Accept": "text/html"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read().decode("utf-8", "replace")
    except Exception as exc:
        logger.error("SoCal page fetch failed for %s: %s", url, exc)
        return None


def _price(node):
    match = _PRICE.search(node.get_text(" ", strip=True)) if node is not None else None
    return f"{float(match.group(1).replace(',', '')):.2f}" if match else None


def cards_from_html(html):
    """``[{name, url, price_new, price_old, image}]`` from one category page."""
    soup = BeautifulSoup(html or "", "html.parser")
    cards = []
    for card in soup.select(".x-product-list__item"):
        link = card.select_one("a.x-product-list__link[href]")
        name_node = card.select_one(".x-product-list__name")
        if link is None or name_node is None:
            continue
        name = normalize_product_name(name_node.get_text(" ", strip=True))
        url = normalize_url(urljoin(BASE, link["href"]))
        was = None
        now = None
        for price in card.select(".x-product-list__price"):
            if price.find("s") is not None:
                was = _price(price.find("s"))
            elif now is None:
                now = _price(price)
        image = card.select_one("img.x-product-list__image[src]")
        if name and url.startswith(BASE) and now:
            cards.append({
                "name": name,
                "url": url,
                "price_new": now,
                "price_old": was,
                "image": urljoin(BASE, image["src"]) if image is not None else "",
            })
    return cards


def load_clearance(fetch=None, sleep=time.sleep):
    """Every clearance card, or None when a page cannot be read. One shared crawl."""
    own_fetch = fetch is None
    if own_fetch and "cards" in _CACHE:
        return _CACHE["cards"]
    fetch = fetch or _fetch
    cards = []
    seen = set()
    for page in range(MAX_PAGES):
        if page:
            sleep(CRAWL_DELAY)
        html = fetch(page_url(page * PER_PAGE))
        if html is None:
            return None
        batch = [card for card in cards_from_html(html) if card["url"] not in seen]
        seen.update(card["url"] for card in batch)
        cards.extend(batch)
        if len(batch) < PER_PAGE:
            break
    else:
        logger.warning("SoCal clearance has more than %s pages; the rest was not read", MAX_PAGES)
    if own_fetch:
        _CACHE["cards"] = cards
    return cards


class SoCalScraper(Scraper):
    """One part from the shared SoCal clearance crawl."""

    def __init__(self, part):
        super().__init__(STORE, CATEGORY, part)

    def scrape(self):
        cards = load_clearance()
        if cards is None:
            return None
        return self.products_from(cards)

    def parse(self, html):
        return self.products_from(cards_from_html(html))

    def products_from(self, cards):
        kept = []
        for card in cards or []:
            if part_for_title(card["name"]) != self.part:
                continue
            if not card.get("price_old") or float(card["price_old"]) <= float(card["price_new"]):
                continue  # clearance without a higher regular price is not a markdown
            if not self._keep(card["name"], card["url"], card["price_new"], card["price_old"]):
                continue
            item = {
                "name": card["name"],
                "url": card["url"],
                "price_new": card["price_new"],
                "price_old": card["price_old"],
                "availability": "Check store",
                "part": self.part,
                "store": STORE,
                "currency": "USD",
            }
            if card.get("image"):
                item["image"] = card["image"]
            if self.part in ("Decks", "Completes"):
                size = extract_deck_size(card["name"])
                if size:
                    item["size"] = size
            if self.part == "Protection":
                set_protection_fields(item, card["name"], "", [])
            kept.append(self._finish(item, None, BASE))
        logger.info("Parsed %s SoCal %s", len(kept), self.part)
        return kept


def scrapers():
    return [SoCalScraper(part) for part in PARTS]


def main():
    """Preview a live run: counts and examples per part. Writes nothing."""
    logging.basicConfig(level=logging.WARNING)
    cards = load_clearance()
    if cards is None:
        print("SoCal clearance could not be read.")
        return 1
    print(f"{len(cards)} clearance products.")
    for scraper in scrapers():
        kept = scraper.products_from(cards)
        print(f"\n{scraper.part}: {len(kept)} kept of {scraper.candidates} candidates")
        for item in kept[:5]:
            print(f"  ${item['price_new']} (was ${item['price_old']})  {item['name']}")
    skipped = [card["name"] for card in cards if not part_for_title(card["name"])]
    print(f"\nNot a tracked part ({len(skipped)}), first 15:")
    for name in skipped[:15]:
        print(f"  {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
