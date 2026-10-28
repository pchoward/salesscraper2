"""Skate Warehouse clearance listings."""

import logging
import re

from bs4 import BeautifulSoup

from filters import extract_deck_size, normalize_product_name, normalize_url
from stores.base import Scraper
from stores.browser import fetch_page, save_debug_file
from tracked import sneaker_rule


def _markdown(prices):
    """True when the link prints a sale price and a higher original price."""
    if len(prices) < 2:
        return False
    try:
        return float(prices[1]) > float(prices[0])
    except ValueError:
        return False

class SkateWarehouseScraper(Scraper):
    def __init__(self, name, url, part, require_markdown=False):
        super().__init__(name, url, part)
        self.require_markdown = require_markdown
        self.urls = [url]

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
            text_lower = text.lower()
            if self.part == "Sneakers":
                # The clearance-shoe page also links the rest of the site.
                # Keep a shoe link, or any link whose text is a tracked model.
                if (
                    "shoe" not in href_lower
                    and "shoe" not in text_lower
                    and not sneaker_rule(text)
                ):
                    continue
            elif self.part in ("Accessories", "Protection"):
                # The shared filters decide: tracked accessories, or gear.
                pass
            else:
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

            prices = re.findall(r"\$(\d+\.\d{2})", text)
            if not prices:
                continue
            if self.require_markdown and not _markdown(prices):
                continue

            if href.startswith("/"):
                href = "https://www.skatewarehouse.com" + href
            href = normalize_url(href)
            if href in seen:
                logging.info(f"Duplicate URL skipped: {href}")
                continue

            name = normalize_product_name(text.split(f"${prices[0]}")[0].strip())
            if not name:
                logging.warning(f"No name found for {href}")
                continue

            price_old = prices[1] if len(prices) > 1 else None
            if not self._keep(name, href, prices[0], price_old):
                continue

            seen.add(href)
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


class SkateWarehouseMultiScraper(SkateWarehouseScraper):
    """One part spread across several category pages. A failed page fails the part."""

    def __init__(self, part, urls, require_markdown=False):
        super().__init__("SkateWarehouse", urls[0], part, require_markdown=require_markdown)
        self.urls = list(urls)

    def scrape(self):
        merged = []
        seen = set()
        for url in self.urls:
            self.url = url
            html = fetch_page(url)
            if not html:
                return None
            for item in self.parse(html):
                item_url = item.get("url")
                if not item_url or item_url in seen:
                    continue
                seen.add(item_url)
                merged.append(item)
        return merged


# Protective gear category or clearance pages. Empty until the owner confirms
# the URLs in a browser; a guessed path would fail every night. Like the
# accessory categories, only a two-price markdown is kept.
PROTECTION_URLS = ()


def scrapers():
    # Category pages are allowed. robots.txt only blocks admin and search paths.
    # catpage-SALEBEARINGS.html is a 404, so bearings come from the bearings
    # category and only a two-price markdown is kept. The clearance-accessories
    # page is sunglasses and stickers, not hardware, so accessories use the
    # hardware, grip, wax, tool, riser, and bushing categories the same way.
    return [
        SkateWarehouseScraper("SkateWarehouse", "https://www.skatewarehouse.com/Clearance_Skateboard_Decks/catpage-SALEDECK.html", "Decks"),
        SkateWarehouseScraper("SkateWarehouse", "https://www.skatewarehouse.com/Clearance_Skateboard_Wheels/catpage-SALEWHEELS.html", "Wheels"),
        SkateWarehouseScraper("SkateWarehouse", "https://www.skatewarehouse.com/Clearance_Skateboard_Trucks/catpage-SALETRUCKS.html", "Trucks"),
        SkateWarehouseScraper(
            "SkateWarehouse",
            "https://www.skatewarehouse.com/bearings.html",
            "Bearings",
            require_markdown=True,
        ),
        SkateWarehouseScraper(
            "SkateWarehouse",
            "https://www.skatewarehouse.com/Clearance_Skate_Shoes/catpage-SALESHOE.html",
            "Sneakers",
        ),
        SkateWarehouseMultiScraper(
            "Accessories",
            [
                "https://www.skatewarehouse.com/hardware.html",
                "https://www.skatewarehouse.com/griptape.html",
                "https://www.skatewarehouse.com/wax.html",
                "https://www.skatewarehouse.com/tools.html",
                "https://www.skatewarehouse.com/risers.html",
                "https://www.skatewarehouse.com/bushings.html",
            ],
            require_markdown=True,
        ),
    ] + ([SkateWarehouseMultiScraper("Protection", list(PROTECTION_URLS), require_markdown=True)] if PROTECTION_URLS else [])
