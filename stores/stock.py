"""Product-page stock check for listings that have already missed two scans.

Sold out is not "missing from the sale grid". The product page has to say the
item is out of stock. Anything else (still for sale, in stock at full price,
missing page, unreadble page) stays "no longer listed".
"""

import logging
import urllib.error
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


def listing_stock(store, html):
    """``out_of_stock``, ``in_stock`` when the same status line says "in stock", else None."""
    status = stock_from_html(store, html)
    if status or not html:
        return status
    soup = BeautifulSoup(html, "html.parser")
    name = (store or "").casefold()
    selector = ".product-head-orderable-status" if "tactics" in name else ".ProductActions-Stock"
    node = soup.select_one(selector)
    if node is not None and "in stock" in node.get_text(" ", strip=True).casefold():
        return "in_stock"
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


# Product pages checked per scraper run before keeping the rest unchecked.
MAX_IN_STOCK_CHECKS = 80


def mark_sold_out(items, store, rendered=False, fetch_static=None, fetch_rendered=None, limit=MAX_IN_STOCK_CHECKS):
    """Every listing, with ``stock`` set from its product page.

    Some sale grids (Zumiez helmets and pads) list items that are sold out in
    every size. Those stay in the report, marked ``stock: out_of_stock`` and
    "Sold out", so a watch can tell when they come back. ``in_stock`` is set
    only when the page's status line says so. An unreadable page, or one past
    ``limit``, sets nothing.
    """
    items = list(items or [])
    urls = [item.get("url") for item in items[:limit] if item.get("url")]
    if not urls:
        return items
    if rendered:
        pages = (fetch_rendered or _fetch_rendered)(urls)
    else:
        fetch = fetch_static or _fetch_static
        pages = {url: fetch(url) for url in urls}
    status = {url: listing_stock(store, html) for url, html in pages.items()}
    sold_out = sum(value == "out_of_stock" for value in status.values())
    if sold_out:
        logger.info("%s: %s listings are out of stock on their product page", store, sold_out)
    if len(items) > limit:
        logger.warning("%s: only the first %s of %s listings were stock-checked", store, limit, len(items))
    for item in items:
        value = status.get(item.get("url"))
        if value:
            item["stock"] = value
        if value == "out_of_stock":
            item["availability"] = "Sold out"
    return items


# Pacing for the stock check (store monitor, 2026-11-27): evo answered 429
# "Too Many Requests" to product pages read ~75 ms apart, then refused the
# MTB run's robots.txt (403), so all of evo's MTB listings were held. Each
# store's pages are now spaced, capped per run and checked against its
# robots.txt, and a store that says "slow down" (429/403) isn't asked again
# this run.
STOCK_DELAY = 1.5  # seconds between one store's product pages
MAX_PER_STORE = 40  # product pages per store per run
STOP_STATUSES = (403, 429)


class _Refused(Exception):
    pass


def _fetch_checked(url, timeout=25):
    """Page HTML, None when unreadable; raises _Refused on 429/403."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        if exc.code in STOP_STATUSES:
            raise _Refused(exc.code) from None
        logger.info("Stock page unavailable for %s: %s", url, exc)
        return None
    except Exception as exc:
        logger.info("Stock page unavailable for %s: %s", url, exc)
        return None


def _host(url):
    from urllib.parse import urlsplit
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}" if parts.scheme and parts.netloc else ""


def polite_pages(urls, fetch=None, policy=None, sleep=None, delay=STOCK_DELAY, per_store=MAX_PER_STORE):
    """{url: html or None} for ``urls``, store by store: robots.txt checked,
    pages spaced and capped, and a store that refuses is left alone."""
    import time as _time
    from stores.shopify import _USER_AGENT as SHOP_AGENT, robots_policy
    fetch = fetch or _fetch_checked
    policy = policy or robots_policy
    sleep = sleep or _time.sleep
    by_host = {}
    for url in urls:
        by_host.setdefault(_host(url), []).append(url)
    pages = {}
    for host, wanted in by_host.items():
        rules = policy(host) if host else None
        if rules is None:
            logger.info("Stock check: %s robots.txt unreadable; its pages not read", host or "(no host)")
            continue
        parser, crawl_delay = rules
        read = 0
        for url in wanted:
            if read >= per_store:
                logger.info("Stock check: %s capped at %s pages this run", host, per_store)
                break
            if not parser.can_fetch(SHOP_AGENT, url):
                continue
            if read:
                sleep(max(delay, crawl_delay or 0))
            try:
                pages[url] = fetch(url)
            except _Refused as refused:
                logger.warning("Stock check: %s answered %s; no more of its pages this run", host, refused)
                break
            read += 1
    return pages


def confirm_stock(history, current_data, skip_keys=None, fetch=None, policy=None, sleep=None):
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
    static = []
    for url, entry in pending:
        store = entry.get("store") or ""
        (rendered if "zumiez" in store.casefold() else static).append(url)
    static_pages = polite_pages(static, fetch=fetch, policy=policy, sleep=sleep)
    for url, entry in pending:
        if url in static_pages:
            status = stock_from_html(entry.get("store") or "", static_pages[url])
            if status == "out_of_stock":
                entry["stock"] = "out_of_stock"
    pages = _fetch_rendered(rendered[:MAX_PER_STORE]) if rendered else {}
    for url, entry in pending:
        if url not in pages:
            continue
        status = stock_from_html(entry.get("store") or "", pages.get(url))
        if status == "out_of_stock":
            entry["stock"] = "out_of_stock"
    return history
