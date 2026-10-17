"""CCS clearance listings."""

import json
import logging
import re
import urllib.request
from html import unescape

from bs4 import BeautifulSoup

from filters import extract_deck_size, normalize_product_name, normalize_url
from part_specs import ordered_shoe_sizes, shoe_size_token, shoe_sizes_in
from stores.base import Scraper
from stores.browser import save_debug_file
from tracked import accessory_rule, sneaker_rule

# Shopify's collection JSON is not disallowed. /collections/clearance/bearings
# does not filter the rendered grid, and the old card title selector is gone.
CLEARANCE_JSON = "https://shop.ccs.com/collections/clearance/products.json"
PAGE_LIMIT = 250
MAX_PAGES = 30
_CACHE = {}
_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

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


def _fetch_json(url, timeout=60):
    request = urllib.request.Request(
        url,
        headers={"User-Agent": _USER_AGENT, "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8", "replace"))
    except Exception as exc:
        logging.error("CCS catalog fetch failed for %s: %s", url, exc)
        return None


def load_clearance_products(fetch=None):
    """Every product in the clearance collection, or None when a page fails.

    Bearings, sneakers, and accessories share one download. A caller that
    passes ``fetch`` does not read or write that cache.
    """
    own_fetch = fetch is None
    if own_fetch and "products" in _CACHE:
        return _CACHE["products"]
    fetch = fetch or _fetch_json
    products = []
    for page in range(1, MAX_PAGES + 1):
        payload = fetch(f"{CLEARANCE_JSON}?limit={PAGE_LIMIT}&page={page}")
        if not isinstance(payload, dict) or not isinstance(payload.get("products"), list):
            return None
        batch = payload["products"]
        products.extend(batch)
        if len(batch) < PAGE_LIMIT:
            break
    else:
        logging.error("CCS clearance catalog exceeded %s pages", MAX_PAGES)
        return None
    if own_fetch:
        _CACHE["products"] = products
    return products


def _plain(html):
    text = re.sub(r"<[^>]+>", " ", str(html or ""))
    return re.sub(r"\s+", " ", unescape(text)).strip()


def _amount(value):
    """Dollar amount. An int is cents, which is how the HTML card encodes price."""
    if value is None or value is False or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value / 100.0
    if isinstance(value, float):
        return value
    text = str(value).strip().replace("$", "").replace(",", "")
    if not text or text.lower() == "null":
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _money(value):
    amount = _amount(value)
    if amount is None:
        return None
    return f"{amount:.2f}"


def _variants_of(product):
    variants = product.get("variants") if isinstance(product, dict) else None
    if isinstance(variants, list) and variants:
        return [variant for variant in variants if isinstance(variant, dict)]
    if isinstance(product, dict) and product.get("price") is not None:
        return [{
            "title": product.get("variant_title") or "",
            "option1": product.get("option1") or "",
            "price": product.get("price"),
            "compare_at_price": product.get("compare_at_price"),
        }]
    return []


def _on_sale(variant):
    price = _amount(variant.get("price"))
    compare = _amount(variant.get("compare_at_price"))
    if price is None or compare is None:
        return False
    return compare > price


def _variant_size(variant):
    for field in ("option1", "option2", "option3", "title"):
        raw = variant.get(field) or ""
        token = shoe_size_token(raw, exact=True)
        if token:
            return token
        marked = shoe_sizes_in(raw)
        if marked:
            return marked[0]
    return ""


def _loads_product(raw):
    text = unescape(str(raw or "").strip())
    if not text:
        return None
    for candidate in (text, text.replace("`", '"')):
        try:
            loaded = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(loaded, dict):
            return loaded
    return None


def products_from_html(html):
    """Product dicts from rendered clearance cards. Links with no price are skipped."""
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    products = []
    for card in soup.select("article.product-item[data-product], .product-item[data-product]"):
        product = _loads_product(card.get("data-product"))
        if not product:
            continue
        if not product.get("title"):
            heading = card.select_one(".product-item__title, img[alt]")
            if heading:
                product["title"] = heading.get("alt") if heading.name == "img" else heading.get_text(strip=True)
        if not _variants_of(product):
            continue
        products.append(product)
    return products


def _catalog_match(product, part):
    title = product.get("title") or ""
    kind = str(product.get("product_type") or "").strip()
    description = _plain(product.get("body_html") or "")
    if part == "Bearings":
        if kind.casefold() == "bearings":
            return True
        # Hardware such as "bearing spacers" keeps its own type.
        if not kind and re.search(r"\bbearings?\b", title, re.IGNORECASE):
            return True
        return False
    if part == "Sneakers":
        return bool(sneaker_rule(title, description))
    if part == "Accessories":
        return bool(accessory_rule(title, kind))
    return False


class CCSCatalogScraper(Scraper):
    """Bearings, sneakers, and accessories from the clearance products.json feed."""

    def __init__(self, part):
        super().__init__("CCS", CLEARANCE_JSON, part)

    def scrape(self):
        products = load_clearance_products()
        if products is None:
            return None
        return self.products_from(products)

    def parse(self, html):
        save_debug_file(f"ccs_debug_{self.part.lower()}.html", html or "")
        return self.products_from(products_from_html(html))

    def products_from(self, products):
        kept = []
        seen = set()
        for product in products or []:
            if not isinstance(product, dict) or not _catalog_match(product, self.part):
                continue
            handle = str(product.get("handle") or "").strip()
            title = normalize_product_name(product.get("title") or "")
            if not handle or not title:
                continue
            href = normalize_url(f"https://shop.ccs.com/products/{handle}")
            if href in seen:
                continue
            sale = [variant for variant in _variants_of(product) if _on_sale(variant)]
            if not sale:
                continue
            cheapest = min(sale, key=lambda variant: _amount(variant.get("price")))
            price_new = _money(cheapest.get("price"))
            price_old = _money(cheapest.get("compare_at_price"))
            description = _plain(product.get("body_html") or "")
            product_type = str(product.get("product_type") or "").strip()
            if not self._keep(title, href, price_new, price_old, description, product_type):
                continue
            seen.add(href)
            item = {
                "name": title,
                "url": href,
                "price_new": price_new,
                "price_old": price_old,
                "availability": "Check store",
                "part": self.part,
                "store": "CCS",
                "description": description,
                "product_type": product_type,
            }
            images = product.get("images") or []
            if images and isinstance(images[0], dict) and images[0].get("src"):
                item["image"] = images[0]["src"]
            if self.part == "Sneakers":
                sizes = []
                for variant in sale:
                    token = _variant_size(variant)
                    if token and token not in sizes:
                        sizes.append(token)
                if sizes:
                    item["shoe_sizes"] = ordered_shoe_sizes(sizes)
            kept.append(item)
            logging.info("Parsed CCS %s: %s", self.part, title)
        logging.info("Parsed %s CCS %s products", len(kept), self.part)
        return kept


def scrapers():
    return [
        CCSDecksScraper(),
        CCSScraper("CCS", "https://shop.ccs.com/collections/clearance/skateboard-wheels", "Wheels"),
        CCSScraper("CCS", "https://shop.ccs.com/collections/clearance/skateboard-trucks", "Trucks"),
        CCSCatalogScraper("Bearings"),
        CCSCatalogScraper("Sneakers"),
        CCSCatalogScraper("Accessories"),
    ]
