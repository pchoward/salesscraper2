"""Describe discovery configuration and inspect locally saved evidence only."""

import argparse
import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit
import xml.etree.ElementTree as ET

from bs4 import BeautifulSoup
from stores import ccs, skatewarehouse, tactics, zumiez

RETAILERS = {
    "Zumiez": (zumiez, "www.zumiez.com"),
    "Tactics": (tactics, "www.tactics.com"),
    "SkateWarehouse": (skatewarehouse, "www.skatewarehouse.com"),
    "CCS": (ccs, "shop.ccs.com"),
}


def inventory():
    """Instantiate configuration only: never invoke scrape/parse/fetch or caches."""
    rows = []
    for store, (module, _host) in RETAILERS.items():
        for scraper in module.scrapers():
            urls = list(getattr(scraper, "urls", [scraper.url]))
            if store == "Zumiez":
                pagination = "rendered grid; page=N; stop on short page without next link or repeated URLs"
                cap, size = zumiez.MAX_SALE_PAGES, zumiez.PAGE_SIZE
                limit_behavior = "returns accumulated products at cap; no explicit incomplete signal"
            elif store == "Tactics":
                pagination = "follow pagination-next; stop on missing next link or repeated/redirected URL"
                cap, size = tactics.MAX_SALE_PAGES, None
                limit_behavior = "returns accumulated pages at cap; no explicit incomplete signal"
            elif store == "CCS" and isinstance(scraper, ccs.CCSCatalogScraper):
                pagination = "products.json; page=N and limit; stop on short batch; shared clearance feed"
                cap, size = ccs.MAX_PAGES, ccs.PAGE_LIMIT
                limit_behavior = "fails the feed at cap or on a failed page"
            else:
                pagination = "one HTML fetch per configured URL; no pagination traversal"
                cap, size = 1, None
                limit_behavior = "additional pages are not discovered"
            rows.append({
                "store": store, "category": scraper.part, "entry_points": urls,
                "implementation": f"stores/{module.__name__.split('.')[-1]}.py:{type(scraper).__name__}",
                "pagination": pagination, "max_pages_per_entry": cap,
                "page_size": size, "limit_behavior": limit_behavior,
                "runtime_note": ("Sneaker brand queries depend on tracked.yaml and live robots permissions; listed URL is fallback."
                                 if store == "Zumiez" and scraper.part == "Sneakers" else None),
            })
    return rows


def _url(raw, source, host, product=False):
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        parsed = urlsplit(urljoin(source, raw.strip()))
    except ValueError:
        return None
    if parsed.scheme not in {"http", "https"} or parsed.hostname != host or parsed.username or parsed.password:
        return None
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path.rstrip("/"), "" if product else parsed.query, ""))


def _structured_products(value, source, host):
    urls = set()
    if isinstance(value, list):
        for element in value:
            urls.update(_structured_products(element, source, host))
    elif isinstance(value, dict):
        types = value.get("@type", [])
        types = [types] if isinstance(types, str) else types
        if "Product" in types:
            url = _url(value.get("url"), source, host, product=True)
            if url:
                urls.add(url)
        if "ItemList" in types:
            for element in value.get("itemListElement", []):
                if not isinstance(element, dict):
                    continue
                item = element.get("item", element)
                raw = item.get("url") if isinstance(item, dict) else item
                url = _url(raw, source, host, product=True)
                if url:
                    urls.add(url)
        for child in value.values():
            if isinstance(child, (list, dict)):
                urls.update(_structured_products(child, source, host))
    return urls


def inspect_evidence(body, kind, source_url, store):
    """Extract candidate identities and pagination evidence; not sale eligibility."""
    host = RETAILERS[store][1]
    if not _url(source_url, source_url, host):
        raise ValueError(f"source_url must belong to {host}")
    products, next_urls, indexes, indexed = set(), set(), set(), set()
    notes = []
    if kind == "json":
        payload = json.loads(body)
        if not isinstance(payload, dict) or not isinstance(payload.get("products"), list):
            raise ValueError("JSON evidence must contain a products list")
        if store != "CCS":
            raise ValueError("products.json evidence is supported for CCS only")
        for product in payload["products"]:
            if isinstance(product, dict) and isinstance(product.get("handle"), str):
                url = _url('/products/' + product['handle'], source_url, host, product=True)
                if url:
                    products.add(url)
        if len(payload["products"]) >= ccs.PAGE_LIMIT:
            notes.append("Full feed batch: another page is needed to establish completion.")
    elif kind == "sitemap":
        root = ET.fromstring(body)
        tag = root.tag.rsplit("}", 1)[-1]
        if tag not in {"urlset", "sitemapindex"}:
            raise ValueError("Expected a sitemap urlset or sitemapindex")
        for node in root:
            # Read page loc only, never image:loc or other nested namespaces.
            for child in node:
                if child.tag == root.tag.replace(tag, "loc"):
                    url = _url(child.text, source_url, host)
                    if url:
                        (indexes if tag == "sitemapindex" else indexed).add(url)
        notes.append("Sitemap URLs do not establish sale status, category, stock, or filter eligibility.")
    elif kind == "html":
        soup = BeautifulSoup(body, "html.parser")
        selectors = {
            "Zumiez": "a.ProductCard-Link",
            "Tactics": ".browse-grid-item a[href], .product-thumb a[href], .product-card a[href], article.product a[href]",
            "CCS": ".product-item a[href], .product-card a[href], a[href*='/products/']",
            "SkateWarehouse": "a[href*='descpage-']",
        }
        links = list(soup.select(selectors[store]))
        if store == "SkateWarehouse":
            links.extend(a for a in soup.select('a[href]') if re.search(r"\$\s*\d", a.get_text()))
        for link in links:
            url = _url(link.get("href"), source_url, host, product=True)
            if url:
                products.add(url)
        for node in soup.select('[data-product]') if store == "CCS" else []:
            try:
                value = json.loads(node["data-product"])
                handle = value.get("handle") if isinstance(value, dict) else None
                if isinstance(handle, str):
                    url = _url('/products/' + handle, source_url, host, product=True)
                    if url:
                        products.add(url)
            except (ValueError, TypeError):
                notes.append("Unreadable embedded product data; candidate count is a lower bound.")
        for node in soup.select('script[type="application/ld+json"]'):
            try:
                products.update(_structured_products(json.loads(node.string or node.get_text()), source_url, host))
            except (ValueError, TypeError):
                notes.append("Unreadable JSON-LD; candidate count is a lower bound.")
        for link in soup.select("a[rel~=next], a.pagination-next, .pagination-next a, a.PaginationLink, a[href*='page=']"):
            url = _url(link.get("href"), source_url, host)
            if url and url != _url(source_url, source_url, host):
                next_urls.add(url)
        if not products:
            notes.append("No recognized product identities: empty inventory is not established (shell/selector mismatch possible).")
    else:
        raise ValueError(f"Unsupported evidence kind: {kind}")
    return {"product_urls": sorted(products), "pagination_urls": sorted(next_urls),
            "sitemap_indexes": sorted(indexes), "sitemap_urls": sorted(indexed), "notes": sorted(set(notes))}


def audit(manifest=None, catalog=None):
    configuration = inventory()
    report = {"mode": "offline-read-only", "configuration": configuration, "observations": [],
              "limitations": ["Candidate differences are not confirmed missed valid products: category, sale status, availability, policy, filters, and scan dates need review.",
                              "No network requests, parser calls, debug files, or catalog/health/history writes are performed."]}
    if manifest is None:
        return report
    manifest = Path(manifest)
    evidence = json.loads(manifest.read_text(encoding="utf-8"))
    if not isinstance(evidence, dict) or evidence.get("version") != 1 or not isinstance(evidence.get("observations"), list):
        raise ValueError("Expected version 1 manifest with observations list")
    report["evidence_label"] = evidence.get("label", "Unlabelled local evidence; verify provenance and capture dates")
    coverage = {(r["store"], r["category"]) for r in configuration}
    groups = {}
    for entry in evidence["observations"]:
        if not isinstance(entry, dict):
            raise ValueError("Each observation must be an object")
        key = (entry.get("store"), entry.get("category"))
        if key not in coverage:
            raise ValueError(f"Unknown configured store/category: {key}")
        path = manifest.parent / entry["file"]
        parsed = inspect_evidence(path.read_text(encoding="utf-8"), entry["kind"], entry["source_url"], key[0])
        group = groups.setdefault(key, {"pages": [], "product_urls": set(), "pagination_urls": set(), "source_urls": set()})
        group["pages"].append(dict(source_url=entry["source_url"], file=entry["file"], kind=entry["kind"], **parsed))
        group["product_urls"].update(parsed["product_urls"])
        group["pagination_urls"].update(parsed["pagination_urls"])
        group["source_urls"].add(entry["source_url"])
    saved = json.loads(Path(catalog).read_text(encoding="utf-8")) if catalog else None
    if saved is not None and not isinstance(saved, dict):
        raise ValueError("Catalog must be an object keyed by store_category")
    for (store, category), group in sorted(groups.items()):
        known = None
        if saved is not None:
            rows = saved.get(f"{store}_{category}")
            if isinstance(rows, list):
                known = {_url(row.get("url"), 'https://' + RETAILERS[store][1], RETAILERS[store][1], product=True)
                         for row in rows if isinstance(row, dict)} - {None}
        source_urls = {_url(u, u, RETAILERS[store][1]) for u in group["source_urls"]}
        report["observations"].append({
            "store": store, "category": category, "pages": group["pages"],
            "observed_unique_candidates": len(group["product_urls"]),
            "saved_filtered_count": len(known) if known is not None else None,
            "candidates_not_in_saved_catalog": sorted(group["product_urls"] - known) if known is not None else None,
            "unprovided_pagination_urls": sorted(group["pagination_urls"] - source_urls),
        })
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, help="Version 1 manifest of local HTML/JSON/XML evidence")
    parser.add_argument("--catalog", type=Path, help="Optional local previous_data.json for candidate comparison")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    args = parser.parse_args(argv)
    if args.catalog and not args.manifest:
        parser.error("--catalog requires --manifest")
    try:
        report = audit(args.manifest, args.catalog)
    except (OSError, ValueError, KeyError, TypeError, ET.ParseError) as exc:
        parser.error(str(exc))
    if args.format == "json":
        print(json.dumps(report, indent=2))
    else:
        print("SkateDeals discovery audit — OFFLINE / READ ONLY")
        if report.get("evidence_label"):
            print(report["evidence_label"])
        for row in report["configuration"]:
            print(f"\n{row['store']} / {row['category']}: {row['pagination']}; cap={row['max_pages_per_entry']}")
            for url in row["entry_points"]:
                print(f"  {url}")
        for row in report["observations"]:
            print(f"\nOBSERVED {row['store']} / {row['category']}: {row['observed_unique_candidates']} unique candidates; saved filtered count={row['saved_filtered_count']}")
            print(f"  Unprovided pagination URLs: {len(row['unprovided_pagination_urls'])}")
            for page in row["pages"]:
                print(f"  Evidence: {page['file']} ({page['source_url']})")
                if page["sitemap_indexes"] or page["sitemap_urls"]:
                    print(f"    Sitemap: {len(page['sitemap_indexes'])} child indexes, {len(page['sitemap_urls'])} page URLs; not sale-product counts")
                for note in page["notes"]:
                    print(f"    {note}")
            if row["candidates_not_in_saved_catalog"] is not None:
                print(f"  Candidates absent from saved catalog (not verified misses): {len(row['candidates_not_in_saved_catalog'])}")
        for note in report["limitations"]:
            print(f"\nCaution: {note}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
