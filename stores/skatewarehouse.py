"""Skate Warehouse clearance listings."""

import logging
import re

from bs4 import BeautifulSoup

from filters import extract_deck_size, normalize_product_name, normalize_url
from stores.base import Scraper
from stores.browser import save_debug_file

class SkateWarehouseScraper(Scraper):
    def parse(self, html):
        if not html:
            logging.error("No HTML to parse")
            return []

        soup = BeautifulSoup(html, "html.parser")
        products = []
        seen = set()

        save_debug_file(f"skatewarehouse_debug_{self.part.lower()}.html", html)

        for a in soup.find_all("a", href=True):
            text = a.get_text(strip=True)
            href = str(a.get("href", ""))

            href_lower = href.lower()
            if not any(part in href_lower for part in ["wheels", "truck", "bearings", "deck"]) and not any(brand.lower() in href_lower for brand in ["bones", "spitfire", "independent", "bronson"]):
                continue

            if self.part == "Wheels" and "Wheels" not in text:
                continue
            if self.part == "Trucks" and "Truck" not in text:
                continue
            if self.part == "Bearings" and "Bearings" not in text:
                continue
            if self.part == "Decks" and "Deck" not in text:
                continue

            if href.startswith("/"):
                href = "https://www.skatewarehouse.com" + href
            href = normalize_url(href)
            if href in seen:
                logging.info(f"Duplicate URL skipped: {href}")
                continue

            prices = re.findall(r"\$(\d+\.\d{2})", text)
            if not prices:
                continue

            name = normalize_product_name(text.split(f"${prices[0]}")[0].strip())
            if not name:
                logging.warning(f"No name found for {href}")
                continue

            price_old = prices[1] if len(prices) > 1 else None
            if not self._keep(name, href, prices[0], price_old):
                continue

            seen.add(href)
            price_old = prices[1] if len(prices) > 1 else None
            item = {
                "name": name,
                "url": href,
                "price_new": prices[0],
                "price_old": price_old,
                "availability": "Check store",
                "part": self.part,
                "store": "SkateWarehouse"
            }
            if self.part == "Decks":
                item["size"] = extract_deck_size(name)
            self._finish(item, a, "https://www.skatewarehouse.com")
            products.append(item)
            logging.info(f"Parsed product: {name}")

        logging.info(f"Parsed {len(products)} products")
        return products


def scrapers():
    return [
        SkateWarehouseScraper("SkateWarehouse", "https://www.skatewarehouse.com/Clearance_Skateboard_Decks/catpage-SALEDECK.html", "Decks"),
        SkateWarehouseScraper("SkateWarehouse", "https://www.skatewarehouse.com/Clearance_Skateboard_Wheels/catpage-SALEWHEELS.html", "Wheels"),
        SkateWarehouseScraper("SkateWarehouse", "https://www.skatewarehouse.com/Clearance_Skateboard_Trucks/catpage-SALETRUCKS.html", "Trucks"),
        SkateWarehouseScraper("SkateWarehouse", "https://www.skatewarehouse.com/Clearance_Skateboard_Bearings/catpage-SALEBEARINGS.html", "Bearings"),
    ]
