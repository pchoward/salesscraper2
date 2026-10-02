"""Zumiez sale listings."""

import logging

from bs4 import BeautifulSoup

from filters import extract_deck_size, normalize_product_name, normalize_url
from stores.base import Scraper
from stores.browser import save_debug_file

class ZumiezScraper(Scraper):
    def parse(self, html):
        if not html:
            logging.error("No HTML to parse")
            return []

        soup = BeautifulSoup(html, "html.parser")
        products = []
        seen = set()

        save_debug_file(f"zumiez_debug_{self.part.lower()}.html", html)
        product_grid = soup.select("li.ProductCard")
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
