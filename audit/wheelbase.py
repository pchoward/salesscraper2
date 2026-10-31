"""Which stores publish deck wheelbase, and can we read it?

Read-only and polite: a handful of deck pages per store from the last
scrape's catalog (previous_data.json), 2 seconds apart. Shopify stores are
read through their product data (``/products/<handle>.js``); the others
through the product page itself. Nothing is saved.

    python -m audit.wheelbase              # 8 decks per store
    python -m audit.wheelbase --per-store 4 --store Tactics
"""

import argparse
import json
import re
import time
import urllib.request
from collections import defaultdict
from urllib.parse import urlsplit

from bs4 import BeautifulSoup

from dimensions import extract_specs
from history_identity import SHOPIFY_HOSTS

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
MENTION = re.compile(r"wheel\s*-?\s*base|\bW\.?B\.?\b", re.IGNORECASE)
_HANDLE = re.compile(r"/products/([^/?#]+)")


def _get(url, accept, timeout=30):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": accept})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, ""
    except Exception as exc:
        return type(exc).__name__, ""


def page_text(url):
    """``(status, plain text)`` for one deck: Shopify product data, or the page."""
    parts = urlsplit(url)
    handle = _HANDLE.search(parts.path)
    if parts.hostname in SHOPIFY_HOSTS and handle:
        status, body = _get(f"https://{parts.hostname}/products/{handle.group(1)}.js", "application/json")
        if not body:
            return status, ""
        try:
            product = json.loads(body)
        except ValueError:
            return "bad json", ""
        html = product.get("description") or ""
        tags = " ".join(product.get("tags") or [])
        return status, BeautifulSoup(html, "html.parser").get_text(" ", strip=True) + " " + tags
    status, html = _get(url, "text/html")
    soup = BeautifulSoup(html or "", "html.parser")
    for node in soup(["script", "style", "noscript"]):
        node.decompose()
    return status, soup.get_text(" ", strip=True)


def snippet(text):
    match = MENTION.search(text)
    if not match:
        return ""
    return " ".join(text[max(0, match.start() - 40):match.end() + 40].split())


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--per-store", type=int, default=8)
    parser.add_argument("--store", action="append", help="only these stores (repeatable)")
    parser.add_argument("--delay", type=float, default=2.0)
    args = parser.parse_args(argv)

    with open("previous_data.json", encoding="utf-8") as handle:
        data = json.load(handle)
    decks = defaultdict(list)
    for key, items in data.items():
        if not key.endswith("_Decks"):
            continue
        for item in items:
            store = item.get("store") or key.split("_")[0]
            if args.store and store not in args.store:
                continue
            if len(decks[store]) < args.per_store and item.get("url"):
                decks[store].append(item)

    summary = []
    first = True
    for store, items in decks.items():
        print(f"\n== {store}")
        read = mentioned = parsed = 0
        for item in items:
            if not first:
                time.sleep(args.delay)
            first = False
            status, text = page_text(item["url"])
            if not text:
                print(f"  [{status}] could not read {item['url']}")
                continue
            read += 1
            found = snippet(text)
            value = extract_specs(item.get("name") or "", text)["wheelbase"]
            mentioned += bool(found)
            parsed += value is not None
            print(f"  [{status}] {item.get('name', '')[:60]}")
            print(f"        wheelbase: {value if value is not None else '-'}   text: {found or '(no mention)'}")
        summary.append((store, len(items), read, mentioned, parsed))

    print("\nstore            tried  read  mentions  parsed")
    for store, tried, read, mentioned, parsed in summary:
        print(f"{store:16} {tried:5} {read:5} {mentioned:9} {parsed:7}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
