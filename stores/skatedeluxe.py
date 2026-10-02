"""Skate Deluxe sale listings.

skatedeluxe.com has no US storefront and no USD prices. The public shop is
euros (the page reports country DE / currency EUR) and the site says it does
not ship to the United States. Sale prices are stored as euro amounts with
``currency`` set to ``EUR`` so the report can show a euro sign.

The real sale catalog is ``/en/c/sale`` (every card on that listing has a
previous price). The ``/en/c/sale/skateboards/...`` paths canonicalize to the
full, mostly full-price category, so those are not used. Parts are split from
the mixed sale grid (decks, wheels, trucks, bearings, plus apparel and
cruisers). Apparel never becomes a part. Cruisers and longboards are removed
by the shared filters.
"""

import gzip
import http.cookiejar
import logging
import re
import time
import urllib.error
import urllib.request

from bs4 import BeautifulSoup

from filters import extract_deck_size, normalize_product_name, normalize_url
from stores.base import Scraper

logger = logging.getLogger("stores.skatedeluxe")

STORE = "Skate Deluxe"
SALE_URL = "https://www.skatedeluxe.com/en/c/sale"
BASE = "https://www.skatedeluxe.com"
CURRENCY = "EUR"
MAX_PAGES = 120
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

_PAGE_RE = re.compile(r"Page\s+(\d+)\s*/\s*(\d+)", re.IGNORECASE)
_EUR_RE = re.compile(r"(\d{1,3}(?:\.\d{3})+|\d+),(\d{2})")
_USD_RE = re.compile(r"(\d+\.\d{2})")
_PART_RULES = (
    ("Bearings", re.compile(r"\bbearings?\b", re.IGNORECASE)),
    ("Wheels", re.compile(r"\bwheels?\b", re.IGNORECASE)),
    ("Trucks", re.compile(r"\btrucks?\b", re.IGNORECASE)),
    ("Decks", re.compile(r"\bdecks?\b", re.IGNORECASE)),
)


def parse_euro(text):
    """``59,99`` or ``1.059,99`` to a dot-decimal string. None when absent."""
    match = _EUR_RE.search(str(text or ""))
    if match:
        whole = match.group(1).replace(".", "")
        return f"{int(whole)}.{match.group(2)}"
    dotted = _USD_RE.search(str(text or ""))
    if dotted:
        return dotted.group(1)
    return None


def classify_part(name, url=""):
    """Decks, Wheels, Trucks, Bearings, or None for everything else."""
    text = f"{name or ''} {url or ''}"
    if re.search(r"\btrucker\b", text, re.IGNORECASE) and not re.search(
        r"\btrucks?\b", name or "", re.IGNORECASE
    ):
        text = re.sub(r"\btrucker\b", " ", text, flags=re.IGNORECASE)
    for part, pattern in _PART_RULES:
        if pattern.search(text):
            return part
    return None


def _image_url(node):
    img = node.select_one("img")
    if img is None:
        return ""
    raw = img.get("data-sources") or img.get("data-src") or ""
    for piece in str(raw).split(","):
        url = piece.strip().split()[0]
        if url.startswith("http"):
            return url
    src = str(img.get("src") or "")
    if src.startswith("http"):
        return src
    return ""


def _card_name(node):
    link = node.select_one("a[href*='/p/']") or node.select_one("a[href]")
    title = ""
    if link is not None:
        title = str(link.get("title") or "").strip()
    if not title:
        brand_el = node.select_one(".listing-product-manufacturer")
        name_el = node.select_one(".listing-product-name")
        brand = brand_el.get_text(" ", strip=True) if brand_el else ""
        name = name_el.get_text(" ", strip=True) if name_el else ""
        title = f"{brand} {name}".strip()
    return normalize_product_name(title)


def parse_sale_html(html):
    """Sale cards from one Skate Deluxe listing page.

    Each card is a dict with name, url, prices, image, and part. Part is
    None for apparel and other non-hardgoods. Prices are euro strings.
    """
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    cards = []
    seen = set()
    for node in soup.select(".listing-product"):
        if node.select_one(".listing-product-name") is None and node.select_one("a[href*='/p/']") is None:
            continue
        link = node.select_one("a[href*='/p/']") or node.select_one("a[href]")
        if link is None:
            continue
        href = normalize_url(link.get("href") or "")
        if href.startswith("/"):
            href = BASE + href
        if not href or href in seen:
            continue
        name = _card_name(node)
        if not name:
            continue
        new_el = node.select_one(".listing-product-price-new")
        old_el = node.select_one(".listing-product-price-old")
        price_new = parse_euro(new_el.get_text(" ", strip=True) if new_el else "")
        price_old = parse_euro(old_el.get_text(" ", strip=True) if old_el else "")
        if not price_new:
            continue
        seen.add(href)
        cards.append(
            {
                "name": name,
                "url": href,
                "price_new": price_new,
                "price_old": price_old,
                "image": _image_url(node),
                "part": classify_part(name, href),
                "node": node,
            }
        )
    return cards


def page_progress(html):
    """``(current, total)`` from the listing label, or None."""
    if not html:
        return None
    soup = BeautifulSoup(html, "html.parser")
    label = soup.select_one(".listing-pagination-label")
    text = label.get_text(" ", strip=True) if label else ""
    match = _PAGE_RE.search(text)
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


def _decode_body(response):
    raw = response.read()
    encoding = (response.headers.get("Content-Encoding") or "").lower()
    if encoding == "gzip":
        raw = gzip.decompress(raw)
    charset = "utf-8"
    content_type = response.headers.get("Content-Type") or ""
    match = re.search(r"charset=([\w\-]+)", content_type, re.IGNORECASE)
    if match:
        charset = match.group(1)
    return raw.decode(charset, "replace")


def fetch_html(url, opener, timeout=45):
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip",
        },
    )
    try:
        with opener.open(request, timeout=timeout) as response:
            if getattr(response, "status", 200) >= 400:
                raise urllib.error.HTTPError(url, response.status, "bad status", response.headers, None)
            return _decode_body(response)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Skate Deluxe HTTP {exc.code} for {url}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Skate Deluxe fetch failed for {url}: {exc}") from exc


class SaleCatalog:
    """One download of ``/en/c/sale``, shared by every part scraper."""

    def __init__(self, fetch=None):
        self._fetch = fetch
        self._cards = None
        self._error = None

    def cards(self):
        if self._error is not None:
            raise self._error
        if self._cards is None:
            try:
                self._cards = self._fetch() if self._fetch else fetch_sale_pages()
            except Exception as exc:
                self._error = exc
                raise
        return self._cards


def fetch_sale_pages(max_pages=MAX_PAGES):
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    first = fetch_html(SALE_URL, opener)
    progress = page_progress(first)
    total = progress[1] if progress else 1
    total = max(1, min(total, max_pages))
    pages = [first]
    for page in range(2, total + 1):
        time.sleep(0.15)
        html = fetch_html(f"{SALE_URL}?page={page}", opener)
        found = page_progress(html)
        if found and found[0] != page:
            raise RuntimeError(f"Skate Deluxe page {page} came back as page {found[0]}")
        if not parse_sale_html(html):
            raise RuntimeError(f"Skate Deluxe page {page} returned no products")
        pages.append(html)
        logger.info("Skate Deluxe sale page %s/%s", page, total)
    cards = []
    seen = set()
    for html in pages:
        for card in parse_sale_html(html):
            if card["url"] in seen:
                continue
            seen.add(card["url"])
            cards.append(card)
    logger.info("Skate Deluxe sale catalog: %s cards across %s pages", len(cards), len(pages))
    if not cards:
        raise RuntimeError("Skate Deluxe sale catalog was empty")
    return cards


class SkateDeluxeScraper(Scraper):
    def __init__(self, part, catalog):
        super().__init__(STORE, SALE_URL, part)
        self.catalog = catalog

    def scrape(self):
        cards = self.catalog.cards()
        return self._from_cards(cards)

    def parse(self, html):
        return self._from_cards(parse_sale_html(html))

    def _from_cards(self, cards):
        products = []
        seen = set()
        for card in cards or []:
            if card.get("part") != self.part:
                continue
            href = card.get("url") or ""
            if not href or href in seen:
                continue
            name = card.get("name") or ""
            price_new = card.get("price_new")
            price_old = card.get("price_old")
            if not self._keep(name, href, price_new, price_old):
                continue
            seen.add(href)
            item = {
                "name": name,
                "url": href,
                "price_new": price_new,
                "price_old": price_old,
                "availability": "Check store",
                "part": self.part,
                "store": STORE,
                "currency": CURRENCY,
            }
            if self.part == "Decks":
                item["size"] = extract_deck_size(name)
            self._finish(item, card.get("node"), BASE)
            if card.get("image") and not item.get("image"):
                item["image"] = card["image"]
            products.append(item)
            logger.info("Parsed Skate Deluxe product: %s", name)
        logger.info("Parsed %s Skate Deluxe %s", len(products), self.part)
        return products


def scrapers(catalog=None):
    shared = catalog or SaleCatalog()
    return [SkateDeluxeScraper(part, shared) for part in ("Decks", "Wheels", "Trucks", "Bearings")]
