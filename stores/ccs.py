"""CCS clearance listings."""

import logging
import re

from bs4 import BeautifulSoup

from filters import extract_deck_size, normalize_product_name, normalize_url
from stores.base import Scraper
from stores.browser import save_debug_file

class CCSScraper(Scraper):
    def parse(self, html):
        if not html:
            logging.error("No HTML to parse")
            return []

        soup = BeautifulSoup(html, "html.parser")
        products = []
        seen = set()

        save_debug_file(f"ccs_debug_{self.part.lower()}.html", html)

        product_containers = soup.select(".product-item, [class*='product-item']")
        logging.info(f"Found {len(product_containers)} CCS product containers")

        if len(product_containers) == 0:
            product_containers = soup.select("a[href*='/products/']")
            logging.info(f"Fallback: found {len(product_containers)} product links")

        for container in product_containers:
            try:
                if container.name == 'a':
                    link_el = container
                else:
                    link_el = container.select_one("a[href*='/products/']")
                
                if not link_el:
                    continue
                    
                href = normalize_url(link_el.get("href", ""))
                if href.startswith("/"):
                    href = "https://shop.ccs.com" + href
                if href in seen or not href:
                    continue
                seen.add(href)

                name_el = container.select_one(".product-item__title")
                if name_el:
                    name = name_el.get_text(strip=True)
                else:
                    img = container.select_one("img[alt]")
                    name = str(img.get("alt", "")).strip() if img else ""
                
                if not name:
                    title_attr = str(link_el.get("title", ""))
                    aria_label = str(link_el.get("aria-label", ""))
                    name = title_attr or aria_label
                    
                name = normalize_product_name(name)
                if not name:
                    continue

                name_lower = name.lower()
                href_lower = href.lower()

                if self.part == "Decks":
                    if "deck" not in name_lower and "deck" not in href_lower:
                        continue
                elif self.part == "Wheels":
                    if "wheel" not in name_lower and "wheel" not in href_lower:
                        continue
                elif self.part == "Trucks":
                    if ("truck" not in name_lower or "trucker" in name_lower) and "truck" not in href_lower:
                        continue
                elif self.part == "Bearings":
                    if "bearing" not in name_lower and "bearing" not in href_lower:
                        continue

                price_current_el = container.select_one(".product-item__price-current")
                price_compare_el = container.select_one(".product-item__price-compare")
                
                price_new = None
                price_old = None
                
                if price_current_el:
                    price_text = price_current_el.get_text(strip=True)
                    price_matches = re.findall(r"\$?(\d+\.?\d*)", price_text)
                    if price_matches:
                        price_new = price_matches[0]
                
                if price_compare_el:
                    compare_text = price_compare_el.get_text(strip=True)
                    compare_matches = re.findall(r"\$?(\d+\.?\d*)", compare_text)
                    if compare_matches:
                        price_old = compare_matches[0]
                
                if not price_new:
                    price_el = container.select_one(".product-item__price")
                    if price_el:
                        all_text = price_el.get_text(strip=True)
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
                    "store": "CCS"
                }
                if self.part == "Decks":
                    item["size"] = extract_deck_size(name)
                self._finish(item, container, "https://shop.ccs.com")
                products.append(item)
                logging.info(f"Parsed product: {name}")

            except Exception as e:
                logging.error(f"Error parsing CCS product: {e}")
                continue

        logging.info(f"Parsed {len(products)} CCS products")
        return products


class CCSDecksScraper(CCSScraper):
    def __init__(self):
        super().__init__("CCS", "https://shop.ccs.com/collections/clearance/skateboard-deck", "Decks")


def scrapers():
    return [
        CCSDecksScraper(),
        CCSScraper("CCS", "https://shop.ccs.com/collections/clearance/skateboard-wheels", "Wheels"),
        CCSScraper("CCS", "https://shop.ccs.com/collections/clearance/skateboard-trucks", "Trucks"),
        CCSScraper("CCS", "https://shop.ccs.com/collections/clearance/bearings", "Bearings"),
    ]
