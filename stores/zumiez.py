"""Zumiez sale listings."""

import logging
import re

from bs4 import BeautifulSoup

from filters import extract_deck_size, normalize_product_name, normalize_url
from stores.base import Scraper
from stores.browser import fetch_page, save_debug_file

CARD_SELECTOR = "li.ProductCard, .ProductCard"
# The category query uses pageSize 60. The grid only paints cards as they
# scroll into view, and the pager is ``&page=N`` (page 1 has no page param).
PAGE_SIZE = 60
MAX_SALE_PAGES = 30
# Header links contain "deck" / "wheels" and used to satisfy the generic
# listing wait before the sale grid hydrated, so a slow or blocked page was
# saved as a real empty catalog.
READY_SELECTOR = "li.ProductCard, .ProductCard"


def grid_loaded(html):
    """True when the sale grid rendered, or the page itself says there are 0 items.

    A shell page (navigation only, no product cards and no item count) is not
    a real empty sale. Callers treat that as a failed fetch.
    """
    if not html:
        return False
    soup = BeautifulSoup(html, "html.parser")
    if soup.select(CARD_SELECTOR):
        return True
    count = soup.select_one(".CategoryPage-ItemsCount")
    text = count.get_text(" ", strip=True) if count else ""
    return bool(re.match(r"^0\b", text))


def page_url(url, page):
    """Sale category URL for a 1-based page. Page 1 keeps the original query."""
    if page <= 1:
        return url
    joiner = "&" if "?" in (url or "") else "?"
    return f"{url}{joiner}page={page}"


def has_page_link(html, page):
    """True when the pager links to this 1-based page number."""
    if not html or page <= 1:
        return False
    soup = BeautifulSoup(html, "html.parser")
    needle = f"page={page}"
    for link in soup.select("a.PaginationLink, a[href*='page=']"):
        href = link.get("href") or ""
        if needle in href:
            return True
    return False


def _product_cards(html):
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select(CARD_SELECTOR)
    return [node for node in cards if node.name == "li" or not node.find_parent("li", class_="ProductCard")]


def listing_urls(html):
    """Product URLs on one rendered Zumiez grid, before the shared filters."""
    urls = []
    seen = set()
    for product in _product_cards(html):
        link = product.select_one("a.ProductCard-Link")
        if not link:
            continue
        href = normalize_url(link.get("href") or "")
        if href.startswith("/"):
            href = "https://www.zumiez.com" + href
        if not href or href in seen:
            continue
        seen.add(href)
        urls.append(href)
    return urls


class ZumiezScraper(Scraper):
    def _fetch_grid(self, url):
        html = fetch_page(
            url,
            ready_selector=READY_SELECTOR,
            item_selector="li.ProductCard",
            max_scroll_attempts=40,
            incremental_scroll=True,
        )
        if html and not grid_loaded(html):
            logging.warning("Zumiez %s grid was missing; retrying the page once", self.part)
            html = fetch_page(
                url,
                ready_selector=READY_SELECTOR,
                item_selector="li.ProductCard",
                max_scroll_attempts=40,
                incremental_scroll=True,
            )
        return html

    def scrape(self):
        products = []
        seen_raw = set()
        seen_kept = set()
        for page in range(1, MAX_SALE_PAGES + 1):
            url = page_url(self.url, page)
            html = self._fetch_grid(url)
            if not html or not grid_loaded(html):
                logging.error(
                    "Zumiez %s did not render sale products on page %s. Marking the fetch failed.",
                    self.part,
                    page,
                )
                return None
            raw = listing_urls(html)
            new_raw = [item_url for item_url in raw if item_url not in seen_raw]
            seen_raw.update(raw)
            logging.info(
                "Zumiez %s page %s: %s new cards (%s on the page)",
                self.part,
                page,
                len(new_raw),
                len(raw),
            )
            if page > 1 and not new_raw:
                break
            for item in self.parse(html):
                item_url = item.get("url")
                if not item_url or item_url in seen_kept:
                    continue
                seen_kept.add(item_url)
                products.append(item)
            if len(raw) < PAGE_SIZE and not has_page_link(html, page + 1):
                break
        logging.info("Zumiez %s: %s items across the sale pages", self.part, len(products))
        return products

    def parse(self, html):
        if not html:
            logging.error("No HTML to parse")
            return []

        soup = BeautifulSoup(html, "html.parser")
        products = []
        seen = set()

        save_debug_file(f"zumiez_debug_{self.part.lower()}.html", html)
        product_grid = soup.select(CARD_SELECTOR)
        # A card can match both ``li.ProductCard`` and ``.ProductCard``.
        product_grid = [node for node in product_grid if node.name == "li" or not node.find_parent("li", class_="ProductCard")]
        logging.info(f"Found {len(product_grid)} product containers")

        for product in product_grid:
            try:
                link = product.select_one("a.ProductCard-Link")
                if not link:
                    logging.warning("No link found for product")
                    continue
                href = normalize_url(link.get("href", ""))
                if href.startswith("/"):
                    href = "https://www.zumiez.com" + href
                if href in seen:
                    logging.info(f"Duplicate URL skipped: {href}")
                    continue
                seen.add(href)

                name_el = product.select_one(".ProductCard-Name")
                if name_el:
                    name = name_el.get_text(strip=True)
                else:
                    img = link.find("img", alt=True)
                    name = str(img.get("alt", "")).strip() if img else ""
                name = normalize_product_name(name)
                if not name:
                    logging.warning(f"No name found for {href}")
                    continue

                sale_price_el = product.select_one(".ProductPrice-PriceValue")
                original_price_el = product.select_one(".ProductCardPrice-HighPrice")
                sale_price = sale_price_el.get_text(strip=True).replace("$", "") if sale_price_el else None
                original_price = original_price_el.get_text(strip=True).replace("$", "") if original_price_el else None

                if not sale_price:
                    logging.warning(f"No sale price found for {href}")
                    continue

                if not self._keep(name, href, sale_price, original_price):
                    continue

                availability = "Check store"
                item = {
                    "name": name,
                    "url": href,
                    "price_new": sale_price,
                    "price_old": original_price,
                    "availability": availability,
                    "part": self.part,
                    "store": "Zumiez"
                }
                if self.part == "Decks":
                    item["size"] = extract_deck_size(name)
                self._finish(item, product, "https://www.zumiez.com")
                products.append(item)
                logging.info(f"Parsed product: {name}")

            except Exception as e:
                logging.error(f"Error parsing product: {e}")
                continue

        logging.info(f"Parsed {len(products)} products")
        return products


class ZumiezDecksScraper(ZumiezScraper):
    def __init__(self):
        super().__init__("Zumiez", "https://www.zumiez.com/skate/skateboard-decks.html?customFilters=promotion_flag:Sale", "Decks")


def scrapers():
    return [
        ZumiezDecksScraper(),
        ZumiezScraper("Zumiez", "https://www.zumiez.com/skate/components/wheels.html?customFilters=promotion_flag:Sale", "Wheels"),
        ZumiezScraper("Zumiez", "https://www.zumiez.com/skate/components/trucks.html?customFilters=promotion_flag:Sale", "Trucks"),
        ZumiezScraper("Zumiez", "https://www.zumiez.com/skate/components/bearings.html?customFilters=promotion_flag:Sale", "Bearings"),
    ]
