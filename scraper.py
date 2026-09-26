#!/usr/bin/env python3
import os
import re
import json
import time
import logging
import random
import datetime
import shutil
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from fake_useragent import UserAgent
from selenium.common.exceptions import TimeoutException, WebDriverException

from filters import extract_deck_size, filter_reason, normalize_product_name, normalize_url
from report import build_report_html, compare_catalogs

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def safe_write_file(filename, content, mode='w'):
    try:
        with open(filename, mode, encoding='utf-8') as f:
            f.write(content)
        logging.info(f"Successfully wrote to file: {filename}")
        return True
    except (IOError, PermissionError) as e:
        logging.error(f"Permission error writing to {filename}: {e}")
        try:
            tmp_filename = os.path.join('/tmp', os.path.basename(filename))
            with open(tmp_filename, mode, encoding='utf-8') as f:
                f.write(content)
            logging.info(f"Wrote to alternate location: {tmp_filename}")
            try:
                shutil.copy(tmp_filename, filename)
                logging.info(f"Copied from {tmp_filename} to {filename}")
                return True
            except Exception as copy_error:
                logging.error(f"Couldn't copy from temp to original: {copy_error}")
                return False
        except Exception as tmp_error:
            logging.error(f"Could not write to temp location either: {tmp_error}")
            return False


def fetch_page(url, max_retries=3, timeout=30):
    ua = UserAgent()
    
    for attempt in range(max_retries):
        user_agent = ua.random
        logging.info(f"Using user agent: {user_agent}")

        options = Options()
        
        chromium_path = shutil.which("chromium")
        if chromium_path:
            options.binary_location = chromium_path
            logging.info(f"Using system chromium at {chromium_path}")
        
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument(f"--user-agent={user_agent}")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-notifications")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--disable-infobars")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--no-first-run")
        options.add_argument("--no-default-browser-check")
        options.add_argument("--disable-popup-blocking")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        logging.info("Running in headless mode")

        try:
            chromedriver_path = shutil.which("chromedriver")
            if chromedriver_path:
                logging.info(f"Using system chromedriver at {chromedriver_path}")
                service = Service(executable_path=chromedriver_path)
            else:
                chromedriver_path = ChromeDriverManager().install()
                service = Service(executable_path=chromedriver_path)
                logging.info(f"Using chromedriver at {service.path}")
        except Exception as e:
            logging.error(f"Failed to find ChromeDriver: {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
                continue
            else:
                return None

        driver = None
        try:
            logging.info(f"Fetching {url} (Attempt {attempt + 1})")
            
            driver_attempts = 3
            for driver_attempt in range(driver_attempts):
                try:
                    logging.info(f"Initializing WebDriver (Attempt {driver_attempt + 1})")
                    driver = webdriver.Chrome(service=service, options=options)
                    logging.info("WebDriver initialized successfully")
                    break
                except TimeoutException as e:
                    logging.error(f"TimeoutException during WebDriver init: {e}")
                    if driver_attempt < driver_attempts - 1:
                        time.sleep(2)
                        continue
                    else:
                        raise
                except WebDriverException as e:
                    logging.error(f"WebDriverException during WebDriver init: {e}")
                    
                    if "cannot find Chrome binary" in str(e):
                        logging.error("Ensure Chrome is correctly installed and in the system's PATH")
                        
                    if driver_attempt < driver_attempts - 1:
                        time.sleep(2)
                        continue
                    else:
                        raise

            if not driver:
                logging.error("Failed to initialize WebDriver after multiple attempts")
                continue

            driver.set_page_load_timeout(timeout)
            time.sleep(random.uniform(0.5, 1))
            driver.get(url)
            
            WebDriverWait(driver, timeout).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )

            time.sleep(random.uniform(1, 2))
            logging.info("Initial wait for dynamic content")

            current_url = driver.current_url
            if "stash" in current_url.lower():
                logging.error("Redirected to Stash page, retrying")
                driver.quit()
                continue

            try:
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "li.ProductCard, .product-card, .product-item, a[href*='deck'], a[href*='wheels'], a[href*='truck'], a[href*='bearings'], .product-grid__item"))
                )
                logging.info("Product listings detected")
            except Exception as e:
                logging.warning(f"Could not detect product listings: {e}")

            logging.info("Attempting infinite scroll")
            max_scroll_attempts = 3
            scroll_attempts = 0
            previous_item_count = 0

            while scroll_attempts < max_scroll_attempts:
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(random.uniform(1, 2))
                
                current_items = len(driver.find_elements(By.CSS_SELECTOR, "li.ProductCard, .product-card, .product-item, a[href*='deck'], a[href*='wheels'], a[href*='truck'], a[href*='bearings'], .product-grid__item"))
                logging.info(f"Scroll attempt {scroll_attempts + 1}: found {current_items} items")

                current_url = driver.current_url
                if "stash" in current_url.lower():
                    logging.error("Redirected to Stash page during scrolling")
                    driver.quit()
                    return None

                if current_items == previous_item_count and current_items > 0:
                    logging.info("No more items to load")
                    break

                previous_item_count = current_items
                scroll_attempts += 1

            time.sleep(random.uniform(1, 2))
            logging.info("Final wait for AJAX content")

            driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(random.uniform(0.5, 1))

            html = driver.page_source
            logging.info(f"Successfully fetched {url}")
            return html

        except Exception as e:
            logging.error(f"Failed to fetch {url}: {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt + random.uniform(1, 2))
            else:
                logging.error(f"Max retries reached for {url}")
                return None
        finally:
            if driver:
                try:
                    driver.quit()
                    logging.info("WebDriver closed successfully")
                except Exception as e:
                    logging.warning(f"Error quitting driver: {e}")


def save_debug_file(filename, content):
    safe_write_file(filename, content)


def load_price_history():
    """Load price history from JSON file"""
    try:
        with open("price_history.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_price_history(history):
    """Save price history to JSON file"""
    safe_write_file("price_history.json", json.dumps(history, indent=2))


def update_price_history(current_data, history):
    """Update price history with current prices"""
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    
    for site_key, items in current_data.items():
        for item in items:
            url = item.get("url", "")
            if not url:
                continue
            
            price_new = item.get("price_new")
            if not price_new:
                continue
            
            try:
                price = float(price_new)
            except (ValueError, TypeError):
                continue
            
            if url not in history:
                history[url] = {
                    "name": item.get("name", ""),
                    "store": item.get("store", ""),
                    "part": item.get("part", ""),
                    "prices": {}
                }
            
            history[url]["prices"][today] = price
            history[url]["name"] = item.get("name", history[url].get("name", ""))
    
    return history


class Scraper:
    def __init__(self, name, url, part):
        self.name = name
        self.url = url
        self.part = part

    def scrape(self):
        html = fetch_page(self.url)
        if not html:
            return None
        return self.parse(html)

    def _keep(self, name, url, price_new, price_old):
        reason = filter_reason(name, self.part, url, price_new, price_old)
        if reason:
            logging.info(f"Filtered out ({self.part}): {name} ({reason})")
            return False
        return True

    def parse(self, html):
        raise NotImplementedError


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
                products.append(item)
                logging.info(f"Parsed product: {name}")

            except Exception as e:
                logging.error(f"Error parsing product: {e}")
                continue

        logging.info(f"Parsed {len(products)} products")
        return products


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
            products.append(item)
            logging.info(f"Parsed product: {name}")

        logging.info(f"Parsed {len(products)} products")
        return products


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
                products.append(item)
                logging.info(f"Parsed product: {name}")

            except Exception as e:
                logging.error(f"Error parsing CCS product: {e}")
                continue

        logging.info(f"Parsed {len(products)} CCS products")
        return products


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
                products.append(item)
                logging.info(f"Parsed Tactics product: {name}")

            except Exception as e:
                logging.error(f"Error parsing Tactics product: {e}")
                continue

        logging.info(f"Parsed {len(products)} Tactics products")
        return products


class ZumiezDecksScraper(ZumiezScraper):
    def __init__(self):
        super().__init__("Zumiez", "https://www.zumiez.com/skate/skateboard-decks.html?customFilters=promotion_flag:Sale", "Decks")


class TacticsDecksScraper(TacticsScraper):
    def __init__(self):
        super().__init__("Tactics", "https://www.tactics.com/skateboard-decks/sale", "Decks")


class CCSDecksScraper(CCSScraper):
    def __init__(self):
        super().__init__("CCS", "https://shop.ccs.com/collections/clearance/skateboard-deck", "Decks")


def load_previous(path="previous_data.json"):
    try:
        if os.path.exists(path):
            with open(path, 'r') as f:
                return json.load(f)
        return {}
    except Exception as e:
        logging.error(f"Error loading previous data: {e}")
        return {}


def save_current(data, path="previous_data.json"):
    try:
        return safe_write_file(path, json.dumps(data, indent=2))
    except Exception as e:
        logging.error(f"Error saving current data: {e}")
        return False


def main():
    scrapers = [
        ZumiezDecksScraper(),
        ZumiezScraper("Zumiez", "https://www.zumiez.com/skate/components/wheels.html?customFilters=promotion_flag:Sale", "Wheels"),
        ZumiezScraper("Zumiez", "https://www.zumiez.com/skate/components/trucks.html?customFilters=promotion_flag:Sale", "Trucks"),
        ZumiezScraper("Zumiez", "https://www.zumiez.com/skate/components/bearings.html?customFilters=promotion_flag:Sale", "Bearings"),
        
        SkateWarehouseScraper("SkateWarehouse", "https://www.skatewarehouse.com/Clearance_Skateboard_Decks/catpage-SALEDECK.html", "Decks"),
        SkateWarehouseScraper("SkateWarehouse", "https://www.skatewarehouse.com/Clearance_Skateboard_Wheels/catpage-SALEWHEELS.html", "Wheels"),
        SkateWarehouseScraper("SkateWarehouse", "https://www.skatewarehouse.com/Clearance_Skateboard_Trucks/catpage-SALETRUCKS.html", "Trucks"),
        SkateWarehouseScraper("SkateWarehouse", "https://www.skatewarehouse.com/Clearance_Skateboard_Bearings/catpage-SALEBEARINGS.html", "Bearings"),
        
        CCSDecksScraper(),
        CCSScraper("CCS", "https://shop.ccs.com/collections/clearance/skateboard-wheels", "Wheels"),
        CCSScraper("CCS", "https://shop.ccs.com/collections/clearance/skateboard-trucks", "Trucks"),
        CCSScraper("CCS", "https://shop.ccs.com/collections/clearance/bearings", "Bearings"),
        
        TacticsDecksScraper(),
        TacticsScraper("Tactics", "https://www.tactics.com/skateboard-wheels/sale", "Wheels"),
        TacticsScraper("Tactics", "https://www.tactics.com/skateboard-trucks/sale", "Trucks"),
        TacticsScraper("Tactics", "https://www.tactics.com/skateboard-bearings/sale", "Bearings"),
    ]

    prev_data = load_previous()
    curr_data = {}
    failed_keys = set()

    for scraper in scrapers:
        key = f"{scraper.name}_{scraper.part}"
        logging.info(f"Scraping {key}...")
        try:
            items = scraper.scrape()
        except Exception as e:
            logging.error(f"Failed to scrape {key}: {e}")
            items = None
        if items is None:
            failed_keys.add(key)
            retained = prev_data.get(key, [])
            curr_data[key] = retained
            logging.warning(f"Scrape failed for {key}; retaining {len(retained)} previous items")
        else:
            curr_data[key] = items
            logging.info(f"Got {len(items)} items from {key}")

    changes = compare_catalogs(prev_data, curr_data, failed_keys)

    if changes:
        logging.info("Changes detected:")
        for site, site_changes in changes.items():
            logging.info(f"  {site}: {len(site_changes)} changes")
    else:
        logging.info("No changes detected")

    price_history = load_price_history()
    price_history = update_price_history(curr_data, price_history)
    save_price_history(price_history)
    logging.info(f"Updated price history for {len(price_history)} items")

    save_current(curr_data)
    html = build_report_html(curr_data, changes, price_history, failed_keys)
    safe_write_file("sale_items_chart.html", html)

    logging.info("Scraping complete!")


if __name__ == "__main__":
    main()
