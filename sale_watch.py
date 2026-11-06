"""Sale sections the scraper does not read yet (owner, 2026-11-04).

Black Friday sales start in places a store's usual sale page doesn't cover:
a new Shopify collection ("black-friday-specials", "flash-sale") or a
homepage link ("Pre-Black Friday Clearance" -> /limited-time-deals). Each
Skate run lists the ones it finds and doesn't read, in the run's summary and
``sale_sections.json``. It reads only: one collection list per Shopify store
and one homepage per other store, robots.txt respected, nothing emailed.
"""

import datetime
import json
import logging
import os
import re
import time
import urllib.parse
import urllib.request
import urllib.robotparser

logger = logging.getLogger("sale_watch")

PATH = "sale_sections.json"
DELAY = 2.0
_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

# A collection handle that names a sale ("holiday-2026-complete-collection"
# is a product drop, not a sale).
SALE_HANDLE = re.compile(r"sale|clearance|closeout|deal|black[-_]?friday|blacker|cyber|doorbuster|flash|outlet|"
                         r"markdown|blowout|bfcm|warehouse[-_]?sale", re.I)
# A homepage link to a seasonal sale.
SALE_LINK = re.compile(r"black[\s_-]*friday|blacker|cyber|doorbuster|door[\s-]buster|limited[\s-]*time[\s-]*deals?|"
                       r"bfcm|flash[\s-]*sale|early[\s-]*access|holiday[\s-]*sale|warehouse[\s-]*sale", re.I)
# Handles that are never a skate sale, whatever their name says.
IGNORE = re.compile(r"snow|ski\b|disc[-_]?golf|apparel|pants|shirt|tee|hood|jacket|sock|hat|beanie|"
                    r"test|do[-_]?not[-_]?use|gift[-_]?card", re.I)


def _get(url, timeout=30):
    request = urllib.request.Request(url, headers={"User-Agent": _UA, "Accept": "*/*"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read().decode("utf-8", "replace")
    except Exception as exc:
        logger.info("sale watch: could not read %s: %s", url, exc)
        return None


def _allowed(base, path, fetch):
    text = fetch(base.rstrip("/") + "/robots.txt")
    if text is None:
        return True
    parser = urllib.robotparser.RobotFileParser()
    parser.parse(text.splitlines())
    return parser.can_fetch("*", base.rstrip("/") + path)


def _marked_down(product):
    for variant in (product or {}).get("variants") or []:
        try:
            if float(variant.get("compare_at_price") or 0) > float(variant.get("price") or 0) > 0:
                return True
        except (TypeError, ValueError):
            continue
    return False


def shopify_sections(base, read_handles, fetch=_get, covered=None, sale_re=None, ignore=None, limit=None,
                     sleep=None):
    """Sale-like collections at ``base`` not in ``read_handles`` that hold
    marked-down products the run did not already read (``covered``: product
    ids). Old or empty seasonal collections are left out."""
    if not _allowed(base, "/collections.json", fetch):
        return []
    collections = []
    for page in range(1, (4 if limit is not None else 1) + 1):
        url = base.rstrip("/") + "/collections.json?limit=250" + (f"&page={page}" if page > 1 else "")
        text = fetch(url)
        try:
            batch = json.loads(text or "")["collections"]
        except (ValueError, KeyError, TypeError):
            batch = None
        if not batch:
            if page == 1:
                return []
            break
        collections.extend(batch)
        if len(batch) < 250:
            break
    if limit is not None:
        # A store with dozens of sale collections: look at the newest first,
        # so a sale that just launched (evo's "up-to-60-off-snow") is checked
        # before older standing promos.
        collections.sort(key=lambda entry: str((entry or {}).get("published_at") or (entry or {}).get("updated_at") or ""),
                         reverse=True)
    found = []
    for entry in collections:
        handle = str((entry or {}).get("handle") or "")
        if not handle or handle in read_handles or not (sale_re or SALE_HANDLE).search(handle) \
                or (ignore or IGNORE).search(handle):
            continue
        if limit is not None and limit <= 0:
            break
        if limit is not None:
            limit -= 1
        if sleep:
            sleep(DELAY)
        text = fetch(f"{base.rstrip('/')}/collections/{handle}/products.json?limit=250")
        try:
            products = json.loads(text or "")["products"]
        except (ValueError, KeyError, TypeError):
            continue
        missing = [p for p in products if _marked_down(p) and (covered is None or p.get("id") not in covered)]
        if not missing:
            continue
        found.append({"label": (entry.get("title") or handle)[:80], "count": len(missing),
                      "url": f"{base.rstrip('/')}/collections/{handle}"})
    return found


def homepage_links(home, read_urls, fetch=_get):
    """Homepage links to seasonal sales that are not among ``read_urls``."""
    parsed = urllib.parse.urlsplit(home)
    if not _allowed(f"{parsed.scheme}://{parsed.netloc}", parsed.path or "/", fetch):
        return []
    html = fetch(home)
    if not html:
        return []
    read = {_clean(url) for url in read_urls}
    found, seen = [], set()
    for href, text in re.findall(r'<a[^>]+href="([^"#]+)"[^>]*>(.*?)</a>', html, re.S | re.I):
        label = " ".join(re.sub(r"<[^>]+>", " ", text).split())[:80]
        url = urllib.parse.urljoin(home, href)
        if not SALE_LINK.search(href + " " + label) or _clean(url) in read or _clean(url) in seen:
            continue
        seen.add(_clean(url))
        found.append({"label": label or href, "url": url})
    return found


def _clean(url):
    return str(url or "").split("?", 1)[0].split("#", 1)[0].rstrip("/").lower()


def _ids(products):
    return {p.get("id") for p in products or () if isinstance(p, dict)} or None


def _shopify_stores():
    """(name, base, handles we read, product ids this run read) for the
    Skate shops read through Shopify."""
    from stores import ccs, exodus, kinetic, spot, tgm
    out = []
    for shop in (tgm.SHOP, kinetic.SHOP, spot.SHOP, exodus.SHOP):
        handles = {url.split("/collections/", 1)[1].split("/", 1)[0] for url in shop.sale_jsons if "/collections/" in url}
        out.append((shop.store, shop.base, handles, _ids(shop.cache.get("products"))))
    out.append(("CCS", "https://shop.ccs.com", {"clearance"}, _ids(ccs._CACHE.get("products"))))
    return out


def _homepages():
    """(name, homepage, URLs we read) for the other Skate stores."""
    from stores import tactics
    from stores.registry import build_scrapers
    urls = {}
    for scraper in build_scrapers():
        urls.setdefault(scraper.name, set()).add(getattr(scraper, "url", "") or "")
    urls.setdefault("Tactics", set()).update(tactics.DEAL_URLS)
    pages = (("Zumiez", "https://www.zumiez.com/"), ("Tactics", "https://www.tactics.com/"),
             ("SkateWarehouse", "https://www.skatewarehouse.com/"), ("SoCal", "https://socalskateshop.com/"))
    return [(name, home, urls.get(name, set())) for name, home in pages]


def check(fetch=_get, sleep=time.sleep, shops=None, homepages=None):
    """{store: [{label, url}]} of sale sections no scraper reads."""
    report = {}
    for name, base, handles, covered in (shops if shops is not None else _shopify_stores()):
        sleep(DELAY)
        found = shopify_sections(base, handles, fetch, covered)
        if found:
            report[name] = found
    for name, home, read in (homepages if homepages is not None else _homepages()):
        sleep(DELAY)
        found = homepage_links(home, read, fetch)
        if found:
            report.setdefault(name, []).extend(found)
    return report


def markdown(report):
    if not report:
        return "## Sale sections we don't read\n\nNone found: every sale section the stores show is covered.\n"
    lines = ["## Sale sections we don't read", "",
             "New or seasonal sale sections (Black Friday, flash sales...). Worth adding if they hold skate gear.", ""]
    for store, entries in sorted(report.items()):
        for entry in entries:
            count = f" ({entry['count']} marked down we don't list)" if entry.get("count") else ""
            lines.append(f"- **{store}**: [{entry['label']}]({entry['url']}){count}")
    return "\n".join(lines) + "\n"


def run(path=PATH, summary=None, now=None):
    """Check, save ``path`` and add to the GitHub run summary. Never raises."""
    try:
        report = check()
    except Exception as exc:  # a broken check must never fail the scrape
        logger.warning("sale watch skipped: %s", exc)
        return None
    stamp = (now or datetime.datetime.now(datetime.timezone.utc)).isoformat(timespec="seconds")
    try:
        with open(path, "w", encoding="utf-8") as handle:
            json.dump({"checked_at": stamp, "stores": report}, handle, indent=2, sort_keys=True)
            handle.write("\n")
    except OSError as exc:
        logger.warning("sale watch: could not save %s: %s", path, exc)
    summary = summary if summary is not None else os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        try:
            with open(summary, "a", encoding="utf-8") as handle:
                handle.write(markdown(report))
        except OSError:
            pass
    for store, entries in sorted(report.items()):
        for entry in entries:
            logger.warning("Sale section not read: %s %s (%s)", store, entry["label"], entry["url"])
    return report
