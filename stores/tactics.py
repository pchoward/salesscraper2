"""Tactics sale listings."""

import logging
import re

from bs4 import BeautifulSoup

from filters import extract_deck_size, normalize_product_name, normalize_url
from stores.base import Scraper
from stores.browser import save_debug_file

class TacticsScraper(Scraper):
    def parse(self, html):
        if not html:
            logging.error("No HTML to parse")
            return []

        soup = BeautifulSoup(html, "html.parser")
        products = []
        seen = set()

        save_debug_file(f"tactics_debug_{self.part.lower()}.html", html)

        product_containers = soup.select(".browse-grid-item, .product-thumb, .product-card, article.product, [data-product]")
        logging.info(f"Found {len(product_containers)} Tactics product containers")

        for container in product_containers:
            try:
                link_el = container.select_one("a[href]")
                if not link_el:
                    link_el = container if container.name == 'a' else None
                
                if not link_el:
                    continue
                    
                href = normalize_url(link_el.get("href", ""))
                if href.startswith("/"):
                    href = "https://www.tactics.com" + href
                if href in seen or not href:
                    continue
                    
                seen.add(href)

                img = container.select_one("img[alt]")
                name = str(img.get("alt", "")).strip() if img else ""
                
                if not name:
                    brand_el = container.select_one(".browse-grid-item-brand, .product-thumb__title, [class*='brand']")
                    if brand_el:
                        name = brand_el.get_text(strip=True)
                
                name = normalize_product_name(name)
                if not name:
                    continue

                price_new = None
                price_old = None
                
                price_el = container.select_one(".browse-grid-item-sale-price, .browse-grid-item-price, .sale-price, [class*='price']")
                if price_el:
                    price_text = price_el.get_text(strip=True)
                    price_match = re.search(r"\$(\d+\.?\d*)", price_text)
                    if price_match:
                        price_new = price_match.group(1)
                
                promo_el = container.select_one(".browse-grid-item-discount, .browse-grid-item-promo-bug, .discount, [class*='promo']")
                if promo_el:
                    promo_text = promo_el.get_text(strip=True)
                    discount_match = re.search(r"(\d+)%", promo_text)
                    if discount_match and price_new:
                        percent_off_value = int(discount_match.group(1))
                        try:
                            price_old = str(round(float(price_new) / (1 - percent_off_value / 100), 2))
                        except (ValueError, ZeroDivisionError, TypeError):
                            pass
                
                if not price_new:
                    all_text = container.get_text(" ", strip=True)
                    all_prices = re.findall(r"\$(\d+\.?\d*)", all_text)
                    if all_prices:
                        price_new = all_prices[0]
                        if len(all_prices) > 1:
                            price_old = all_prices[1]

                if not price_new:
                    continue

                if not self._keep(name, href, price_new, price_old):
                    continue

                item = {
                    "name": name,
                    "url": href,
                    "price_new": price_new,
                    "price_old": price_old,
                    "availability": "Check store",
                    "part": self.part,
                    "store": "Tactics"
                }
                if self.part == "Decks":
                    item["size"] = extract_deck_size(name)
                self._finish(item, container, "https://www.tactics.com")
                products.append(item)
                logging.info(f"Parsed Tactics product: {name}")

            except Exception as e:
                logging.error(f"Error parsing Tactics product: {e}")
                continue

        logging.info(f"Parsed {len(products)} Tactics products")
        return products


class TacticsDecksScraper(TacticsScraper):
    def __init__(self):
        super().__init__("Tactics", "https://www.tactics.com/skateboard-decks/sale", "Decks")


def scrapers():
    return [
        TacticsDecksScraper(),
        TacticsScraper("Tactics", "https://www.tactics.com/skateboard-wheels/sale", "Wheels"),
        TacticsScraper("Tactics", "https://www.tactics.com/skateboard-trucks/sale", "Trucks"),
        TacticsScraper("Tactics", "https://www.tactics.com/skateboard-bearings/sale", "Bearings"),
    ]
