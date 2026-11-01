"""Which candidate stores can ShredDeals read, and how? Read-only.

For each store in audit/store_candidates.json (or given with --url) this
reads robots.txt first and only fetches what it allows, then reports:

* the platform (Shopify, BigCommerce, Magento, WooCommerce, ...), which
  decides whether stores/shopify.py can read it with a few lines of config;
* its sale / clearance / closeout sections;
* for Shopify, the sale collection's size, how many items are marked down,
  and the product types, variant option names and tags it uses. Those say
  which filters (Hub Type, Toptube Length, Drive Side...) the data supports.

At most a handful of requests per store, a few seconds apart; nothing is
saved besides the report. Runs in GitHub Actions ("Stores - Probe
Candidates"), so no local machine is needed.

    python -m audit.store_probe --sport bmx
    python -m audit.store_probe --url https://www.example.com --json out.json
"""

import argparse
import collections
import json
import re
import sys
import time
import urllib.error
import urllib.request
from html.parser import HTMLParser
from pathlib import Path
from urllib import robotparser
from urllib.parse import urljoin, urlsplit

CANDIDATES = Path(__file__).with_name("store_candidates.json")
USER_AGENT = "ShredDealsProbe/1.0 (+https://github.com/pchoward/salesscraper2; read-only deal research)"
DELAY = 3.0
TIMEOUT = 20
SALE_WORDS = re.compile(r"\b(sale|clearance|closeouts?|close-?out|deals?|specials?|outlet|scratch|markdown|discount)\b", re.I)
PLATFORMS = (
    ("Shopify", re.compile(r"cdn\.shopify\.com|Shopify\.theme|shopify-features", re.I)),
    ("BigCommerce", re.compile(r"cdn\d*\.bigcommerce\.com|bigcommerce", re.I)),
    ("Magento", re.compile(r"Magento|/static/version\d+|mage/cookies", re.I)),
    ("Salesforce Commerce", re.compile(r"demandware|/on/demandware\.store", re.I)),
    ("WooCommerce", re.compile(r"woocommerce|wp-content/plugins", re.I)),
    ("Squarespace", re.compile(r"squarespace", re.I)),
    ("Miva", re.compile(r"/mm5/", re.I)),
    ("Wix", re.compile(r"wixstatic|_wixCssImports", re.I)),
)


def _get(url, accept="text/html"):
    """``(status, text)``; status is an int, or the error's name."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": accept})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            return response.status, response.read(4_000_000).decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, ""
    except Exception as exc:  # DNS, TLS, timeouts: report, never crash the run
        return type(exc).__name__, ""


class _Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self._href = None
        self._text = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self._href = dict(attrs).get("href")
            self._text = []

    def handle_data(self, data):
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self._href is not None:
            self.links.append((self._href, " ".join("".join(self._text).split())))
            self._href = None


def platform_of(html):
    return [name for name, pattern in PLATFORMS if pattern.search(html or "")]


def sale_links(html, base, limit=10):
    """Links whose text or path says sale, clearance, closeout, deals..."""
    parser = _Links()
    try:
        parser.feed(html or "")
    except Exception:
        return []
    found = []
    seen = set()
    for href, text in parser.links:
        if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue
        url = urljoin(base, href)
        if urlsplit(url).netloc != urlsplit(base).netloc or url in seen:
            continue
        if SALE_WORDS.search(text) or SALE_WORDS.search(urlsplit(url).path.replace("-", " ").replace("/", " ")):
            seen.add(url)
            found.append({"text": text[:60], "url": url})
        if len(found) >= limit:
            break
    return found


def _money(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def shopify_sale(products):
    """What a Shopify sale collection holds and which spec fields it carries."""
    types = collections.Counter()
    options = collections.Counter()
    tags = collections.Counter()
    vendors = collections.Counter()
    marked = 0
    for product in products:
        types[(product.get("product_type") or "").strip() or "(none)"] += 1
        vendors[(product.get("vendor") or "").strip() or "(none)"] += 1
        for option in product.get("options") or []:
            name = option.get("name") if isinstance(option, dict) else option
            if name and name != "Title":
                options[name] += 1
        for tag in product.get("tags") or []:
            tags[tag] += 1
        for variant in product.get("variants") or []:
            price, compare = _money(variant.get("price")), _money(variant.get("compare_at_price"))
            if price is not None and compare and compare > price:
                marked += 1
                break
    return {
        "products": len(products),
        "marked_down": marked,
        "product_types": types.most_common(20),
        "variant_options": options.most_common(12),
        "vendors": vendors.most_common(12),
        "tags": tags.most_common(15),
    }


def probe(store, fetch=_get, sleep=time.sleep):
    # A URL naming a Shopify collection (https://shop/collections/ski-sale)
    # samples that collection instead of the biggest sale-looking one.
    wanted = None
    match = re.search(r"/collections/([^/?#]+)", store["url"])
    if match:
        wanted = match.group(1)
        store = dict(store, url=store["url"][:match.start()])
    base = store["url"].rstrip("/") + "/"
    report = {"name": store.get("name") or base, "url": base, "robots": None, "platform": [], "sale_links": [],
              "shopify": None, "notes": []}
    calls = [0]

    def get(url, accept="text/html"):
        if calls[0]:
            sleep(DELAY)
        calls[0] += 1
        return fetch(url, accept)

    status, text = get(urljoin(base, "/robots.txt"), "text/plain")
    robots = robotparser.RobotFileParser()
    robots.parse(text.splitlines() if status == 200 else [])
    delay = robots.crawl_delay(USER_AGENT) or robots.crawl_delay("*")
    report["robots"] = {"status": status, "crawl_delay": delay}

    def allowed(path):
        if robots.can_fetch(USER_AGENT, urljoin(base, path)):
            return True
        report["notes"].append(f"robots.txt disallows {path}")
        return False

    if not allowed("/"):
        return report
    status, html = get(base)
    report["home_status"] = status
    if status != 200:
        report["notes"].append(f"homepage returned {status}")
        return report
    report["platform"] = platform_of(html)
    report["sale_links"] = sale_links(html, base)
    if "Shopify" not in report["platform"]:
        return report
    shop = {}
    if allowed("/collections.json"):
        status, body = get(urljoin(base, "/collections.json?limit=250"), "application/json")
        try:
            collections_ = json.loads(body).get("collections") or [] if status == 200 else []
        except ValueError:
            collections_ = []
        sale = [c for c in collections_ if SALE_WORDS.search((c.get("title") or "") + " " + (c.get("handle") or "").replace("-", " "))]
        shop["sale_collections"] = [{"handle": c.get("handle"), "title": c.get("title"), "products": c.get("products_count")} for c in sale][:12]
        best = max(sale, key=lambda c: c.get("products_count") or 0, default=None)
        if wanted:
            best = next((c for c in collections_ if c.get("handle") == wanted), {"handle": wanted, "products_count": None})
            report["name"] = f"{report['name']} ({wanted})"
        if best and allowed(f"/collections/{best['handle']}/products.json"):
            status, body = get(urljoin(base, f"/collections/{best['handle']}/products.json?limit=250"), "application/json")
            try:
                products = json.loads(body).get("products") or [] if status == 200 else []
            except ValueError:
                products = []
            shop["sampled"] = best["handle"]
            shop.update(shopify_sale(products))
    report["shopify"] = shop
    return report


def markdown(reports):
    lines = ["| Store | Platform | robots.txt | Sale sections | Shopify sale sample |", "|---|---|---|---|---|"]
    for report in reports:
        robots = report.get("robots") or {}
        delay = f", crawl-delay {robots['crawl_delay']}" if robots.get("crawl_delay") else ""
        shop = report.get("shopify") or {}
        sample = ""
        if shop.get("sampled"):
            sample = f"`{shop['sampled']}`: {shop.get('products', 0)} items, {shop.get('marked_down', 0)} marked down"
        links = ", ".join(f"[{link['text'] or 'link'}]({link['url']})" for link in report.get("sale_links", [])[:4])
        lines.append(f"| [{report['name']}]({report['url']}) | {', '.join(report.get('platform') or []) or '?'} | "
                     f"{robots.get('status')}{delay} | {links or '-'} | {sample or '-'} |")
    for report in reports:
        shop = report.get("shopify") or {}
        if not (shop.get("product_types") or report.get("notes")):
            continue
        lines += ["", f"#### {report['name']}"]
        for note in report.get("notes") or []:
            lines.append(f"- {note}")
        for key, label in (("sale_collections", "Sale collections"), ("product_types", "Product types"),
                           ("variant_options", "Variant options (filter candidates)"), ("vendors", "Brands"), ("tags", "Tags")):
            value = shop.get(key)
            if value:
                if key == "sale_collections":
                    text = ", ".join(f"{c['title']} ({c['products']})" for c in value)
                else:
                    text = ", ".join(f"{name} ({count})" for name, count in value)
                lines.append(f"- **{label}:** {text}")
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--sport", choices=("bmx", "mtb", "ski", "all"), default="bmx")
    parser.add_argument("--url", action="append", help="probe these URLs instead of the candidate list")
    parser.add_argument("--json", help="also write the full report as JSON here")
    parser.add_argument("--summary", help="append the markdown report here (e.g. $GITHUB_STEP_SUMMARY)")
    args = parser.parse_args(argv)
    if args.url:
        stores = [{"name": url, "url": url} for url in args.url]
    else:
        candidates = json.loads(CANDIDATES.read_text(encoding="utf-8"))
        sports = ("bmx", "mtb", "ski") if args.sport == "all" else (args.sport,)
        stores, seen = [], set()
        for sport in sports:
            for store in candidates.get(sport, []):
                if store["url"] not in seen:
                    seen.add(store["url"])
                    stores.append(store)
    reports = []
    for store in stores:
        print(f"Probing {store['url']} ...", file=sys.stderr)
        reports.append(probe(store))
    text = markdown(reports)
    print(text)
    if args.summary:
        with open(args.summary, "a", encoding="utf-8") as handle:
            handle.write(f"## Store probe ({args.sport})\n\n" + text)
    if args.json:
        Path(args.json).write_text(json.dumps(reports, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
