"""Skate Warehouse clearance listings."""

import logging
import re
import time

from bs4 import BeautifulSoup

from filters import extract_deck_size, normalize_product_name, normalize_url
from part_specs import ordered_shoe_sizes, shoe_size_token
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


# Product pages read per run for shoe sizes, and the pause between them.
MAX_SIZE_READS = 40
SIZE_READ_DELAY = 1.0


def shoe_offers_from_html(html):
    """``(in-stock sizes → price, rows seen)`` from a product page.

    Each size is a ``tr.subproduct`` row: "Men's Shoe Sizes: 8.5",
    "In Stock: Yes", and its price. The rows are in the page itself.
    """
    soup = BeautifulSoup(html or "", "html.parser")
    offers = {}
    rows = 0
    for row in soup.select("tr.subproduct"):
        size = None
        for entry in row.select(".stylelist li"):
            if entry.select_one('.style[data-styleabbrev="Size"]') is not None:
                value = entry.select_one(".styleitem")
                size = shoe_size_token(value.get_text(strip=True), exact=True) if value is not None else None
        if not size:
            continue
        rows += 1
        available = row.select_one(".available")
        if available is None or available.get_text(strip=True).casefold() != "yes":
            continue
        price = row.select_one(".price")
        try:
            amount = float(price.get_text(strip=True).replace(",", "")) if price is not None else None
        except ValueError:
            amount = None
        if size not in offers or (amount is not None and (offers[size] is None or amount < offers[size])):
            offers[size] = amount
    return offers, rows


def add_shoe_sizes(items, fetch=None, sleep=time.sleep, limit=MAX_SIZE_READS):
    """Set ``shoe_sizes`` (in stock only) from each shoe's product page.

    The clearance listing only has name and price. A page whose sizes are
    all out of stock marks the shoe sold out; an unreadable page changes
    nothing.
    """
    if fetch is None:
        from stores.stock import _fetch_static as fetch
    for index, item in enumerate(items[:limit]):
        if index:
            sleep(SIZE_READ_DELAY)
        html = fetch(item["url"])
        offers, rows = shoe_offers_from_html(html)
        if not rows:
            continue
        sizes = ordered_shoe_sizes(offers)
        item["shoe_sizes"] = sizes
        prices = {size: f"{offers[size]:.2f}" for size in sizes if offers[size] is not None}
        if len(set(prices.values())) > 1:
            item["shoe_prices"] = prices
        if not sizes:
            item["stock"] = "out_of_stock"
            item["availability"] = "Sold out"
    if len(items) > limit:
        logging.warning("Skate Warehouse sizes read for only the first %s of %s shoes", limit, len(items))
    return items


class SkateWarehouseSneakersScraper(SkateWarehouseScraper):
    """Clearance shoes, with in-stock sizes from each product page."""

    def scrape(self):
        items = super().scrape()
        if items is None:
            return None
        return add_shoe_sizes(items)


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


# Protective gear category pages, confirmed by the owner in a browser on
# 2026-10-28. Clearance has no protection section, so like the accessory
# categories these are full category pages and only a two-price markdown
# (a sale price under the regular price) is kept.
PROTECTION_URLS = (
    "https://www.skatewarehouse.com/helmets.html",
    "https://www.skatewarehouse.com/kneepads.html",
    "https://www.skatewarehouse.com/elbowpad.html",
    "https://www.skatewarehouse.com/wristguards.html",
)


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
        SkateWarehouseSneakersScraper(
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
