"""Product-page stock check for listings that have already missed two scans.

Sold out is not "missing from the sale grid". The product page has to say the
item is out of stock. Anything else (still for sale, in stock at full price,
missing page, unreadble page) stays "no longer listed".
"""

import logging
import urllib.request

from bs4 import BeautifulSoup

logger = logging.getLogger("stores.stock")

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


def stock_from_html(store, html):
    """``out_of_stock`` when the product's own status says so, else None.

    None means the page did not confirm a stockout. Callers must not label
    that listing sold out.
    """
    if not html:
        return None
    soup = BeautifulSoup(html, "html.parser")
    name = (store or "").casefold()
    if "tactics" in name:
        node = soup.select_one(".product-head-orderable-status")
    elif "zumiez" in name:
        # Pickup availability uses a separate "out of stock" flag. Only the
        # product action line counts.
        node = soup.select_one(".ProductActions-Stock")
    else:
        node = soup.select_one(".product-head-orderable-status, .ProductActions-Stock, .availability")
    if node is None:
        return None
    text = node.get_text(" ", strip=True).casefold()
    if "out of stock" in text or "sold out" in text:
        return "out_of_stock"
    return None


def _fetch_static(url, timeout=25):
    request = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "text/html"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read().decode("utf-8", "replace")
    except Exception as exc:
        logger.info("Stock page unavailable for %s: %s", url, exc)
        return None


def _fetch_rendered(urls):
    """Load Zumiez product pages in one browser. URL → HTML or None."""
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    import shutil
    import time

    found = {}
    if not urls:
        return found
    options = Options()
    binary = shutil.which("google-chrome") or shutil.which("chromium")
    if binary:
        options.binary_location = binary
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1400,1200")
    options.add_argument(f"--user-agent={USER_AGENT}")
    driver = None
    try:
        driver_path = shutil.which("chromedriver")
        service = Service(executable_path=driver_path) if driver_path else Service()
        driver = webdriver.Chrome(service=service, options=options)
        driver.set_page_load_timeout(35)
        for url in urls:
            try:
                driver.get(url)
                time.sleep(2)
                found[url] = driver.page_source
            except Exception as exc:
                logger.info("Rendered stock page failed for %s: %s", url, exc)
                found[url] = None
    except Exception as exc:
        logger.error("Could not open a browser for stock checks: %s", exc)
    finally:
        if driver is not None:
            try:
                driver.quit()
            except Exception:
                pass
    return found


def confirm_stock(history, current_data, skip_keys=None):
    """Set ``stock`` to ``out_of_stock`` only when the product page says so.

    Listings still in the catalog, under the two-miss line, or on a failed
    store/part are not checked.
    """
    if not isinstance(history, dict):
        return history
    import datetime

    from history import GONE_AFTER_MISSES, RECENTLY_GONE_DAYS, _as_date, _filters_allow, _miss_streak, _store_key
    from filters import normalize_url

    skip = {str(key) for key in (skip_keys or [])}
    active = set()
    for items in (current_data or {}).values():
        for item in items or []:
            if isinstance(item, dict):
                url = normalize_url(item.get("url"))
                if url:
                    active.add(url)
    pending = []
    today = datetime.date.today()
    for url, entry in history.items():
        if not isinstance(entry, dict) or url in active:
            continue
        key = _store_key(entry)
        if key and key in skip:
            continue
        if _miss_streak(entry) < GONE_AFTER_MISSES:
            continue
        if entry.get("stock") == "out_of_stock":
            continue
        if not _filters_allow(entry, url):
            continue
        last = _as_date(entry.get("last_seen"))
        if last is None or (today - last).days > RECENTLY_GONE_DAYS:
            continue
        pending.append((url, entry))
    if not pending:
        return history
    logger.info("Checking product pages for %s listings missing twice", len(pending))
    rendered = []
    for url, entry in pending:
        store = entry.get("store") or ""
        if "zumiez" in store.casefold():
            rendered.append(url)
            continue
        status = stock_from_html(store, _fetch_static(url))
        if status == "out_of_stock":
            entry["stock"] = "out_of_stock"
    pages = _fetch_rendered(rendered)
    for url, entry in pending:
        if url not in pages:
            continue
        status = stock_from_html(entry.get("store") or "", pages.get(url))
        if status == "out_of_stock":
            entry["stock"] = "out_of_stock"
    return history
