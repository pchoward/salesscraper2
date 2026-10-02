"""Headless Chrome fetch shared by the Selenium store parsers."""

import logging
import random
import shutil
import time

from fake_useragent import UserAgent
from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

from stores.errors import StoreTimeout
from stores.files import safe_write_file

def fetch_page(url, max_retries=3, timeout=30):
    ua = UserAgent()
    
    for attempt in range(max_retries):
        user_agent = ua.random
        logging.info(f"Using user agent: {user_agent}")

        options = Options()
        
        chromium_path = shutil.which("chromium") or shutil.which("google-chrome") or shutil.which("google-chrome-stable")
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
        except StoreTimeout:
            raise
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
            except StoreTimeout:
                raise
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

        except StoreTimeout:
            raise
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
