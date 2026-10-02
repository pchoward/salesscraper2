"""Zumiez sale listings."""

import logging
import re

from bs4 import BeautifulSoup

from filters import extract_deck_size, normalize_product_name, normalize_url
from stores.base import Scraper
from stores.browser import fetch_page, save_debug_file

CARD_SELECTOR = "li.ProductCard, .ProductCard"
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


class ZumiezScraper(Scraper):
    def scrape(self):
        html = fetch_page(self.url, ready_selector=READY_SELECTOR)
        if html and not grid_loaded(html):
            logging.warning("Zumiez %s grid was missing; retrying the page once", self.part)
            html = fetch_page(self.url, ready_selector=READY_SELECTOR)
        if not html:
            return None
        if not grid_loaded(html):
            logging.error(
                "Zumiez %s did not render sale products (empty shell or block). Marking the fetch failed.",
                self.part,
            )
            return None
        return self.parse(html)

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
