#!/usr/bin/env python3
import os
import re
import json
import time
import logging
import random
import requests
import datetime
import string
import uuid
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


def create_chrome_temp_dir():
    system_tmpdir = os.environ.get('TMPDIR', '/tmp')
    unique_id = str(uuid.uuid4())
    temp_dir = os.path.join(system_tmpdir, f'chrome_data_{unique_id}')
    
    try:
        os.makedirs(temp_dir, mode=0o777, exist_ok=True)
        os.chmod(temp_dir, 0o777)
        logging.info(f"Created Chrome temp dir: {temp_dir}")
        return temp_dir
    except Exception as e:
        logging.error(f"Failed to create Chrome temp dir: {e}")
        try:
            import tempfile
            alt_temp_dir = tempfile.mkdtemp(prefix='chrome_data_')
            os.chmod(alt_temp_dir, 0o777)
            logging.info(f"Created alternate temp dir: {alt_temp_dir}")
            return alt_temp_dir
        except Exception as alt_e:
            logging.error(f"Failed to create alternate temp dir: {alt_e}")
            return None


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
        options.add_argument("--disable-web-security")
        options.add_argument("--allow-running-insecure-content")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--disable-infobars")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--no-first-run")
        options.add_argument("--no-default-browser-check")
        options.add_argument("--disable-popup-blocking")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        logging.info("Running in headless mode with CI-friendly options")

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


def calculate_percent_off(price_new, price_old):
    try:
        new = float(price_new)
        old = float(price_old)
        if old <= 0:
            return "N/A"
        percent_off = ((old - new) / old) * 100
        return f"{percent_off:.0f}%"
    except (ValueError, TypeError):
        return "N/A"


class Scraper:
    def __init__(self, name, url, part):
        self.name = name
        self.url = url
        self.part = part

    def scrape(self):
        html = fetch_page(self.url)
        return self.parse(html)

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
                href = str(link.get("href", ""))
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
                if not name:
                    logging.warning(f"No name found for {href}")
                    continue

                if self.part == "Wheels":
                    if not any(brand in name for brand in ["Bones", "Powell", "Spitfire", "OJ"]):
                        logging.info(f"Skipping product not from Bones, Powell, Spitfire, or OJ: {name}")
                        continue

                sale_price_el = product.select_one(".ProductPrice-PriceValue")
                original_price_el = product.select_one(".ProductCardPrice-HighPrice")
                sale_price = sale_price_el.get_text(strip=True).replace("$", "") if sale_price_el else None
                original_price = original_price_el.get_text(strip=True).replace("$", "") if original_price_el else None

                if not sale_price:
                    logging.warning(f"No sale price found for {href}")
                    continue

                if self.part == "Decks":
                    percent_off = calculate_percent_off(sale_price, original_price)
                    logging.info(f"Deck {name}: {percent_off} off")
                    try:
                        percent_off_value = float(percent_off.strip("%"))
                        if percent_off_value < 10:
                            logging.info(f"Skipping deck with less than 10% off: {name} ({percent_off})")
                            continue
                    except (ValueError, TypeError):
                        logging.info(f"Skipping deck with invalid % off: {name} ({percent_off})")
                        continue

                availability = "Check store"
                products.append({
                    "name": name,
                    "url": href,
                    "price_new": sale_price,
                    "price_old": original_price,
                    "availability": availability,
                    "part": self.part,
                    "store": "Zumiez"
                })
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
            if href in seen:
                logging.info(f"Duplicate URL skipped: {href}")
                continue

            prices = re.findall(r"\$(\d+\.\d{2})", text)
            if not prices:
                continue

            name = text.split(f"${prices[0]}")[0].strip()
            if not name:
                logging.warning(f"No name found for {href}")
                continue

            if self.part == "Wheels":
                if not any(brand in name for brand in ["Bones", "Powell", "Spitfire", "OJ"]):
                    logging.info(f"Skipping product not from Bones, Powell, Spitfire, or OJ: {name}")
                    continue
            elif self.part == "Trucks":
                if not any(brand in name for brand in ["Independent", "Indy", "Ace"]):
                    logging.info(f"Skipping product not from Independent or Ace Trucks: {name}")
                    continue
            elif self.part == "Decks":
                price_new = prices[0]
                price_old = prices[1] if len(prices) > 1 else None
                percent_off = calculate_percent_off(price_new, price_old)
                logging.info(f"Deck {name}: {percent_off} off")
                try:
                    percent_off_value = float(percent_off.strip("%"))
                    if percent_off_value < 10:
                        logging.info(f"Skipping deck with less than 10% off: {name} ({percent_off})")
                        continue
                except (ValueError, TypeError):
                    logging.info(f"Skipping deck with invalid % off: {name} ({percent_off})")
                    continue

            seen.add(href)
            price_old = prices[1] if len(prices) > 1 else None
            products.append({
                "name": name,
                "url": href,
                "price_new": prices[0],
                "price_old": price_old,
                "availability": "Check store",
                "part": self.part,
                "store": "SkateWarehouse"
            })
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
                    
                href = str(link_el.get("href", ""))
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
                    
                if not name:
                    continue

                name_lower = name.lower()
                href_lower = href.lower()
                
                non_skate_keywords = ["hat", "cap", "shirt", "tee", "hoodie", "jacket", "pant", "short", "shoe", "sneaker", "sock", "backpack", "bag", "beanie", "glove"]
                if any(keyword in name_lower for keyword in non_skate_keywords):
                    logging.info(f"Skipping non-skate product: {name}")
                    continue
                
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
                price_discount_el = container.select_one(".product-item__price-discount")
                
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

                if self.part == "Decks":
                    percent_off = calculate_percent_off(price_new, price_old)
                    try:
                        percent_off_value = float(percent_off.strip("%"))
                        if percent_off_value < 10:
                            logging.info(f"Skipping deck with less than 10% off: {name} ({percent_off})")
                            continue
                    except (ValueError, TypeError):
                        continue

                if self.part == "Wheels":
                    if not any(brand in name for brand in ["Bones", "Powell", "Spitfire", "OJ"]):
                        continue

                products.append({
                    "name": name,
                    "url": href,
                    "price_new": price_new,
                    "price_old": price_old,
                    "availability": "Check store",
                    "part": self.part,
                    "store": "CCS"
                })
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
                    
                href = str(link_el.get("href", ""))
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
                
                if not name:
                    continue

                price_new = None
                price_old = None
                
                price_el = container.select_one(".browse-grid-item-price, .sale-price, [class*='price']")
                if price_el:
                    price_text = price_el.get_text(strip=True)
                    price_match = re.search(r"\$(\d+\.?\d*)", price_text)
                    if price_match:
                        price_new = price_match.group(1)
                
                promo_el = container.select_one(".browse-grid-item-promo-bug, .discount, [class*='promo']")
                if promo_el:
                    promo_text = promo_el.get_text(strip=True)
                    discount_match = re.search(r"(\d+)%", promo_text)
                    if discount_match and price_new:
                        percent_off_value = int(discount_match.group(1))
                        try:
                            price_old = str(round(float(price_new) / (1 - percent_off_value / 100), 2))
                        except:
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

                if self.part == "Decks":
                    percent_off = calculate_percent_off(price_new, price_old)
                    try:
                        percent_off_value = float(percent_off.strip("%"))
                        if percent_off_value < 10:
                            logging.info(f"Skipping deck with less than 10% off: {name} ({percent_off})")
                            continue
                    except (ValueError, TypeError):
                        continue

                if self.part == "Wheels":
                    if not any(brand in name for brand in ["Bones", "Powell", "Spitfire", "OJ"]):
                        continue

                products.append({
                    "name": name,
                    "url": href,
                    "price_new": price_new,
                    "price_old": price_old,
                    "availability": "Check store",
                    "part": self.part,
                    "store": "Tactics"
                })
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


def compare(prev, curr):
    valid_parts = {"Decks", "Wheels", "Trucks", "Bearings"}
    changes = {}
    for site, items in curr.items():
        prev_map = {i["url"]: i for i in prev.get(site, [])}
        diffs = []
        for it in items:
            pi = prev_map.get(it["url"])
            if not pi:
                diffs.append({"type": "new", "item": it})
            elif it["price_new"] != pi.get("price_new"):
                diffs.append({
                    "type": "price_change",
                    "url": it["url"],
                    "old": pi.get("price_new"),
                    "new": it["price_new"],
                    "name": it["name"]
                })
        curr_urls = {i["url"] for i in items}
        for url, pi in prev_map.items():
            if url not in curr_urls:
                item_part = pi.get("part", "")
                if item_part in valid_parts:
                    diffs.append({"type": "removed", "item": pi})
                else:
                    logging.info(f"Skipping out-of-scope removed item: {pi.get('name', 'Unknown')} (part: {item_part})")
        if diffs:
            changes[site] = diffs
    return changes


def generate_html_chart(data, changes, output_file="sale_items_chart.html"):
    current_date = datetime.datetime.now().strftime("%Y-%m-%d")
    current_datetime = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    all_products = []
    for site_key, items in data.items():
        all_products.extend(items)

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Skateboard Sale Tracker | {current_date}</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {{
            --primary: #2563eb;
            --primary-dark: #1d4ed8;
            --secondary: #64748b;
            --success: #22c55e;
            --warning: #f59e0b;
            --danger: #ef4444;
            --bg-primary: #f8fafc;
            --bg-card: #ffffff;
            --text-primary: #1e293b;
            --text-secondary: #64748b;
            --border: #e2e8f0;
            --shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1);
            --shadow-lg: 0 10px 15px -3px rgb(0 0 0 / 0.1), 0 4px 6px -4px rgb(0 0 0 / 0.1);
        }}

        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}

        body {{
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            line-height: 1.6;
            min-height: 100vh;
        }}

        .container {{
            max-width: 1400px;
            margin: 0 auto;
            padding: 2rem;
        }}

        header {{
            text-align: center;
            margin-bottom: 2rem;
            padding: 2rem;
            background: linear-gradient(135deg, var(--primary) 0%, var(--primary-dark) 100%);
            border-radius: 16px;
            color: white;
            box-shadow: var(--shadow-lg);
        }}

        header h1 {{
            font-size: 2.25rem;
            font-weight: 700;
            margin-bottom: 0.5rem;
        }}

        header p {{
            opacity: 0.9;
            font-size: 1rem;
        }}

        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1rem;
            margin-bottom: 2rem;
        }}

        .stat-card {{
            background: var(--bg-card);
            padding: 1.5rem;
            border-radius: 12px;
            box-shadow: var(--shadow);
            text-align: center;
            transition: transform 0.2s, box-shadow 0.2s;
        }}

        .stat-card:hover {{
            transform: translateY(-2px);
            box-shadow: var(--shadow-lg);
        }}

        .stat-card .number {{
            font-size: 2rem;
            font-weight: 700;
            color: var(--primary);
        }}

        .stat-card .label {{
            color: var(--text-secondary);
            font-size: 0.875rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}

        .controls {{
            display: flex;
            flex-wrap: wrap;
            gap: 1rem;
            margin-bottom: 1.5rem;
            padding: 1.5rem;
            background: var(--bg-card);
            border-radius: 12px;
            box-shadow: var(--shadow);
        }}

        .search-box {{
            flex: 1;
            min-width: 250px;
            position: relative;
        }}

        .search-box input {{
            width: 100%;
            padding: 0.75rem 1rem 0.75rem 2.75rem;
            border: 2px solid var(--border);
            border-radius: 8px;
            font-size: 1rem;
            transition: border-color 0.2s, box-shadow 0.2s;
        }}

        .search-box input:focus {{
            outline: none;
            border-color: var(--primary);
            box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1);
        }}

        .search-box::before {{
            content: "🔍";
            position: absolute;
            left: 1rem;
            top: 50%;
            transform: translateY(-50%);
            font-size: 1rem;
        }}

        .filter-group {{
            display: flex;
            gap: 0.5rem;
            flex-wrap: wrap;
        }}

        .filter-btn {{
            padding: 0.5rem 1rem;
            border: 2px solid var(--border);
            background: var(--bg-card);
            border-radius: 8px;
            cursor: pointer;
            font-size: 0.875rem;
            font-weight: 500;
            transition: all 0.2s;
        }}

        .filter-btn:hover {{
            border-color: var(--primary);
            color: var(--primary);
        }}

        .filter-btn.active {{
            background: var(--primary);
            border-color: var(--primary);
            color: white;
        }}

        .section {{
            margin-bottom: 2rem;
        }}

        .section-header {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 1rem 1.5rem;
            background: var(--bg-card);
            border-radius: 12px 12px 0 0;
            border-bottom: 2px solid var(--border);
            cursor: pointer;
            user-select: none;
            transition: background 0.2s;
        }}

        .section-header:hover {{
            background: #f1f5f9;
        }}

        .section-header h2 {{
            font-size: 1.25rem;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }}

        .section-header .badge {{
            background: var(--primary);
            color: white;
            padding: 0.25rem 0.75rem;
            border-radius: 999px;
            font-size: 0.875rem;
            font-weight: 500;
        }}

        .section-header .toggle-icon {{
            font-size: 1.5rem;
            color: var(--secondary);
            transition: transform 0.3s;
        }}

        .section-header.collapsed .toggle-icon {{
            transform: rotate(-90deg);
        }}

        .section-content {{
            background: var(--bg-card);
            border-radius: 0 0 12px 12px;
            overflow: hidden;
            box-shadow: var(--shadow);
        }}

        .section-content.collapsed {{
            display: none;
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
        }}

        th {{
            background: linear-gradient(135deg, #334155 0%, #1e293b 100%);
            color: white;
            padding: 1rem;
            text-align: left;
            font-weight: 600;
            font-size: 0.875rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            cursor: pointer;
            position: sticky;
            top: 0;
            z-index: 10;
            white-space: nowrap;
        }}

        th:hover {{
            background: linear-gradient(135deg, #475569 0%, #334155 100%);
        }}

        th .sort-icon {{
            margin-left: 0.5rem;
            opacity: 0.5;
        }}

        th.sorted .sort-icon {{
            opacity: 1;
        }}

        td {{
            padding: 1rem;
            border-bottom: 1px solid var(--border);
            vertical-align: middle;
        }}

        tr:hover td {{
            background: #f8fafc;
        }}

        tr:last-child td {{
            border-bottom: none;
        }}

        .product-name {{
            font-weight: 500;
            max-width: 400px;
        }}

        .product-name a {{
            color: var(--text-primary);
            text-decoration: none;
            transition: color 0.2s;
        }}

        .product-name a:hover {{
            color: var(--primary);
        }}

        .price {{
            font-weight: 600;
            font-family: 'SF Mono', 'Consolas', monospace;
        }}

        .price-new {{
            color: var(--success);
            font-size: 1.1rem;
        }}

        .price-old {{
            color: var(--text-secondary);
            text-decoration: line-through;
            font-size: 0.9rem;
        }}

        .discount {{
            display: inline-block;
            padding: 0.25rem 0.75rem;
            border-radius: 999px;
            font-weight: 600;
            font-size: 0.875rem;
        }}

        .discount.high {{
            background: #dcfce7;
            color: #166534;
        }}

        .discount.medium {{
            background: #fef3c7;
            color: #92400e;
        }}

        .discount.low {{
            background: #fee2e2;
            color: #991b1b;
        }}

        .store-badge {{
            display: inline-block;
            padding: 0.25rem 0.75rem;
            border-radius: 6px;
            font-size: 0.75rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}

        .store-zumiez {{ background: #fce7f3; color: #be185d; }}
        .store-skatewarehouse {{ background: #dbeafe; color: #1d4ed8; }}
        .store-ccs {{ background: #d1fae5; color: #059669; }}
        .store-tactics {{ background: #fef3c7; color: #d97706; }}

        .part-badge {{
            display: inline-block;
            padding: 0.25rem 0.5rem;
            border-radius: 4px;
            font-size: 0.75rem;
            font-weight: 500;
            background: #f1f5f9;
            color: var(--text-secondary);
        }}

        .changes-section {{
            margin-top: 2rem;
        }}

        .change-row.new td {{
            background: #f0fdf4;
        }}

        .change-row.price-change td {{
            background: #fffbeb;
        }}

        .change-row.removed td {{
            background: #fef2f2;
            text-decoration: line-through;
            opacity: 0.7;
        }}

        .no-results {{
            text-align: center;
            padding: 3rem;
            color: var(--text-secondary);
        }}

        .no-results-icon {{
            font-size: 3rem;
            margin-bottom: 1rem;
        }}

        footer {{
            text-align: center;
            padding: 2rem;
            color: var(--text-secondary);
            font-size: 0.875rem;
        }}

        @media (max-width: 768px) {{
            .container {{
                padding: 1rem;
            }}

            header h1 {{
                font-size: 1.5rem;
            }}

            .controls {{
                flex-direction: column;
            }}

            .search-box {{
                min-width: 100%;
            }}

            table {{
                display: block;
                overflow-x: auto;
            }}

            th, td {{
                padding: 0.75rem;
                font-size: 0.875rem;
            }}

            .product-name {{
                max-width: 200px;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>Skateboard Sale Tracker</h1>
            <p>Last updated: {current_datetime}</p>
        </header>
"""

    store_counts = {}
    part_counts = {}
    total_products = len(all_products)
    
    for item in all_products:
        store = item.get("store", "Unknown")
        part = item.get("part", "Unknown")
        store_counts[store] = store_counts.get(store, 0) + 1
        part_counts[part] = part_counts.get(part, 0) + 1

    html_content += """
        <div class="stats-grid">
"""
    html_content += f"""
            <div class="stat-card">
                <div class="number">{total_products}</div>
                <div class="label">Total Deals</div>
            </div>
"""
    
    for store, count in sorted(store_counts.items()):
        html_content += f"""
            <div class="stat-card">
                <div class="number">{count}</div>
                <div class="label">{store}</div>
            </div>
"""
    
    html_content += """
        </div>

        <div class="controls">
            <div class="search-box">
                <input type="text" id="searchInput" placeholder="Search products..." onkeyup="filterProducts()">
            </div>
            <div class="filter-group" id="storeFilters">
                <button class="filter-btn active" data-store="all" onclick="filterByStore('all')">All Stores</button>
"""
    
    for store in sorted(store_counts.keys()):
        html_content += f"""
                <button class="filter-btn" data-store="{store.lower()}" onclick="filterByStore('{store}')">{store}</button>
"""
    
    html_content += """
            </div>
            <div class="filter-group" id="partFilters">
                <button class="filter-btn active" data-part="all" onclick="filterByPart('all')">All Parts</button>
"""
    
    for part in sorted(part_counts.keys()):
        html_content += f"""
                <button class="filter-btn" data-part="{part.lower()}" onclick="filterByPart('{part}')">{part}</button>
"""
    
    html_content += """
            </div>
        </div>

        <div class="section">
            <div class="section-header" onclick="toggleSection(this)">
                <h2>All Deals <span class="badge">{}</span></h2>
                <span class="toggle-icon">▼</span>
            </div>
            <div class="section-content">
                <table id="mainTable">
                    <thead>
                        <tr>
                            <th onclick="sortTable('mainTable', 0)">Store <span class="sort-icon">↕</span></th>
                            <th onclick="sortTable('mainTable', 1)">Part <span class="sort-icon">↕</span></th>
                            <th onclick="sortTable('mainTable', 2)">Product <span class="sort-icon">↕</span></th>
                            <th onclick="sortTable('mainTable', 3, true)">Sale Price <span class="sort-icon">↕</span></th>
                            <th onclick="sortTable('mainTable', 4, true)">Original <span class="sort-icon">↕</span></th>
                            <th onclick="sortTable('mainTable', 5, true)">Discount <span class="sort-icon">↕</span></th>
                        </tr>
                    </thead>
                    <tbody>
""".format(total_products)

    for item in all_products:
        percent_off = calculate_percent_off(item.get("price_new"), item.get("price_old"))
        try:
            pct_value = float(percent_off.strip("%"))
            if pct_value >= 40:
                discount_class = "high"
            elif pct_value >= 25:
                discount_class = "medium"
            else:
                discount_class = "low"
        except:
            discount_class = "low"
            
        store = item.get("store", "Unknown")
        store_class = f"store-{store.lower().replace(' ', '')}"
        
        price_old_display = f"${item['price_old']}" if item.get('price_old') else "N/A"
        
        html_content += f"""
                        <tr data-store="{store}" data-part="{item.get('part', '')}">
                            <td><span class="store-badge {store_class}">{store}</span></td>
                            <td><span class="part-badge">{item.get('part', 'N/A')}</span></td>
                            <td class="product-name"><a href="{item['url']}" target="_blank" rel="noopener">{item['name']}</a></td>
                            <td class="price price-new">${item['price_new']}</td>
                            <td class="price price-old">{price_old_display}</td>
                            <td><span class="discount {discount_class}">{percent_off}</span></td>
                        </tr>
"""

    html_content += """
                    </tbody>
                </table>
            </div>
        </div>
"""

    if changes:
        total_changes = sum(len(c) for c in changes.values())
        html_content += f"""
        <div class="section changes-section">
            <div class="section-header" onclick="toggleSection(this)">
                <h2>Recent Changes <span class="badge">{total_changes}</span></h2>
                <span class="toggle-icon">▼</span>
            </div>
            <div class="section-content">
                <table id="changesTable">
                    <thead>
                        <tr>
                            <th>Type</th>
                            <th>Store</th>
                            <th>Product</th>
                            <th>Sale Price</th>
                            <th>Original</th>
                            <th>Discount</th>
                            <th>Date</th>
                        </tr>
                    </thead>
                    <tbody>
"""
        for site, site_changes in changes.items():
            for change in site_changes:
                if change["type"] == "new":
                    item = change["item"]
                    price_old_display = f"${item['price_old']}" if item.get('price_old') else "N/A"
                    percent_off = calculate_percent_off(item.get("price_new"), item.get("price_old"))
                    try:
                        pct_value = float(percent_off.strip("%"))
                        if pct_value >= 40:
                            discount_class = "high"
                        elif pct_value >= 25:
                            discount_class = "medium"
                        else:
                            discount_class = "low"
                    except:
                        discount_class = "low"
                    html_content += f"""
                        <tr class="change-row new">
                            <td><span class="discount high">New</span></td>
                            <td>{item.get('store', site.split('_')[0])}</td>
                            <td class="product-name"><a href="{item['url']}" target="_blank">{item['name']}</a></td>
                            <td class="price price-new">${item['price_new']}</td>
                            <td class="price price-old">{price_old_display}</td>
                            <td><span class="discount {discount_class}">{percent_off}</span></td>
                            <td>{current_date}</td>
                        </tr>
"""
                elif change["type"] == "price_change":
                    percent_off = calculate_percent_off(change['new'], change['old'])
                    try:
                        pct_value = float(percent_off.strip("%"))
                        if pct_value >= 40:
                            discount_class = "high"
                        elif pct_value >= 25:
                            discount_class = "medium"
                        else:
                            discount_class = "low"
                    except:
                        discount_class = "low"
                    html_content += f"""
                        <tr class="change-row price-change">
                            <td><span class="discount medium">Price Drop</span></td>
                            <td>{site.split('_')[0]}</td>
                            <td class="product-name"><a href="{change['url']}" target="_blank">{change['name']}</a></td>
                            <td class="price price-new">${change['new']}</td>
                            <td class="price price-old">${change['old']}</td>
                            <td><span class="discount {discount_class}">{percent_off}</span></td>
                            <td>{current_date}</td>
                        </tr>
"""
                elif change["type"] == "removed":
                    item = change["item"]
                    price_old_display = f"${item['price_old']}" if item.get('price_old') else "N/A"
                    html_content += f"""
                        <tr class="change-row removed">
                            <td><span class="discount low">Removed</span></td>
                            <td>{item.get('store', site.split('_')[0])}</td>
                            <td class="product-name">{item['name']}</td>
                            <td class="price">-</td>
                            <td class="price price-old">{price_old_display}</td>
                            <td>-</td>
                            <td>{current_date}</td>
                        </tr>
"""
        html_content += """
                    </tbody>
                </table>
            </div>
        </div>
"""

    html_content += """
        <footer>
            <p>Data scraped from Zumiez, Skate Warehouse, CCS, and Tactics</p>
        </footer>
    </div>

    <script>
        let currentStoreFilter = 'all';
        let currentPartFilter = 'all';

        function filterProducts() {
            const searchTerm = document.getElementById('searchInput').value.toLowerCase().trim();
            const rows = document.querySelectorAll('#mainTable tbody tr');
            
            rows.forEach(row => {
                const text = row.textContent.toLowerCase();
                const store = (row.dataset.store || '').toLowerCase();
                const part = (row.dataset.part || '').toLowerCase();
                
                const matchesSearch = searchTerm === '' || text.includes(searchTerm);
                const matchesStore = currentStoreFilter === 'all' || store === currentStoreFilter.toLowerCase();
                const matchesPart = currentPartFilter === 'all' || part === currentPartFilter.toLowerCase();
                
                row.style.display = matchesSearch && matchesStore && matchesPart ? '' : 'none';
            });
            
            updateNoResults();
        }

        function filterByStore(store) {
            currentStoreFilter = store;
            
            document.querySelectorAll('#storeFilters .filter-btn').forEach(btn => {
                const btnStore = btn.dataset.store || '';
                btn.classList.toggle('active', btnStore === store.toLowerCase() || (store === 'all' && btnStore === 'all'));
            });
            
            filterProducts();
        }

        function filterByPart(part) {
            currentPartFilter = part;
            
            document.querySelectorAll('#partFilters .filter-btn').forEach(btn => {
                const btnPart = btn.dataset.part || '';
                btn.classList.toggle('active', btnPart === part.toLowerCase() || (part === 'all' && btnPart === 'all'));
            });
            
            filterProducts();
        }

        function sortTable(tableId, colIndex, isNumeric = false) {
            const table = document.getElementById(tableId);
            const tbody = table.querySelector('tbody');
            const rows = Array.from(tbody.querySelectorAll('tr'));
            const header = table.querySelectorAll('th')[colIndex];
            
            const isAsc = header.dataset.sort !== 'asc';
            
            table.querySelectorAll('th').forEach(th => {
                th.classList.remove('sorted');
                delete th.dataset.sort;
            });
            
            header.classList.add('sorted');
            header.dataset.sort = isAsc ? 'asc' : 'desc';
            
            rows.sort((a, b) => {
                let aVal = a.cells[colIndex].textContent.trim();
                let bVal = b.cells[colIndex].textContent.trim();
                
                if (isNumeric) {
                    aVal = parseFloat(aVal.replace(/[$%,]/g, '')) || 0;
                    bVal = parseFloat(bVal.replace(/[$%,]/g, '')) || 0;
                    return isAsc ? aVal - bVal : bVal - aVal;
                } else {
                    return isAsc ? aVal.localeCompare(bVal) : bVal.localeCompare(aVal);
                }
            });
            
            tbody.innerHTML = '';
            rows.forEach(row => tbody.appendChild(row));
        }

        function toggleSection(header) {
            header.classList.toggle('collapsed');
            header.nextElementSibling.classList.toggle('collapsed');
        }

        function updateNoResults() {
            const table = document.getElementById('mainTable');
            const tbody = table.querySelector('tbody');
            const visibleRows = tbody.querySelectorAll('tr:not([style*="display: none"])');
            
            let noResultsEl = document.querySelector('.no-results');
            
            if (visibleRows.length === 0) {
                if (!noResultsEl) {
                    noResultsEl = document.createElement('div');
                    noResultsEl.className = 'no-results';
                    noResultsEl.innerHTML = '<div class="no-results-icon">🔍</div><p>No products match your filters</p>';
                    table.parentNode.appendChild(noResultsEl);
                }
                noResultsEl.style.display = 'block';
            } else if (noResultsEl) {
                noResultsEl.style.display = 'none';
            }
        }
    </script>
</body>
</html>
"""

    success = safe_write_file(output_file, html_content)
    if success:
        logging.info(f"HTML chart saved to {output_file}")
    return success


def main():
    scrapers = [
        ZumiezDecksScraper(),
        ZumiezScraper("Zumiez", "https://www.zumiez.com/skate/skateboard-wheels.html?customFilters=promotion_flag:Sale", "Wheels"),
        ZumiezScraper("Zumiez", "https://www.zumiez.com/skate/skateboard-trucks.html?customFilters=promotion_flag:Sale", "Trucks"),
        ZumiezScraper("Zumiez", "https://www.zumiez.com/skate/skateboard-bearings.html?customFilters=promotion_flag:Sale", "Bearings"),
        
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

    for scraper in scrapers:
        key = f"{scraper.name}_{scraper.part}"
        logging.info(f"Scraping {key}...")
        try:
            items = scraper.scrape()
            curr_data[key] = items
            logging.info(f"Got {len(items)} items from {key}")
        except Exception as e:
            logging.error(f"Failed to scrape {key}: {e}")
            curr_data[key] = []

    changes = compare(prev_data, curr_data)
    
    if changes:
        logging.info("Changes detected:")
        for site, site_changes in changes.items():
            logging.info(f"  {site}: {len(site_changes)} changes")
    else:
        logging.info("No changes detected")

    save_current(curr_data)
    generate_html_chart(curr_data, changes)
    
    logging.info("Scraping complete!")


if __name__ == "__main__":
    main()
