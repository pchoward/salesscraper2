"""Store-wide promo codes (owner, 2026-11-19).

Some sales aren't markdowns: Fanatik's Black Friday is "20% off with code
2026-BFCM-20 at checkout". Prices in the product feed don't change, so no
listing is marked down and nothing shows on ShredDeals. Those sales are
shown as a notice instead ("Fanatik: 20% off with code 2026-BFCM-20, until
Dec 2"), never as cheaper listings: which items a code covers and its
restrictions aren't knowable from outside.

**Detection.** Twice a day, before the Skate and the BMX/Ski/MTB scrapes
(``promo-check.yml``: ``python promos.py``), for every store any sport reads,
each once: its homepage, then up to ``MAX_LINKS`` sale pages the homepage links to
("/collections/fanatik-black-friday", "/pages/sales"). On each page, the
visible text, the page description and Shopify "/discount/<CODE>" links are
searched for a code next to a discount ("20% off", "save 20%", "$25 off").
robots.txt is respected. Store text is untrusted: only the store name, the
code, the discount and an end date are kept, each checked against a strict
pattern; no store wording is shown.

Left out: sign-up, first-order, app, member, student/military, birthday,
referral and shipping-only codes, which aren't sales.

**Lifetime.** ``promos.json`` (repo root) keeps each code with the sports
its store serves and the day it was first and last seen. A code not seen on a successful
read of its store is dropped; one whose store couldn't be read is kept for up
to three days, and none past its end date.
"""

import datetime
import html as html_lib
import json
import logging
import re
import time
import urllib.parse
import urllib.request
import urllib.robotparser

logger = logging.getLogger("promos")

import os as _os

PATH = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "promos.json")
MAX_LINKS = 3
DELAY = 1.5
KEEP_DAYS = 3
_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

# A homepage link to a sale page worth reading.
_SALE_LINK = re.compile(
    r"black[\s_-]*(?:friday|november|week)|cyber|bfcm|doorbuster|holiday[\s_-]*sale|flash[\s_-]*sale|"
    r"(?:^|[/_-])sales?(?:$|[/_-])|promo|deals?(?:$|[/_-])|clearance|warehouse[\s_-]*sale", re.I)
_CODE = r"([A-Z0-9](?:[A-Z0-9_-]{1,22})[A-Z0-9])"
_CODE_PHRASES = (
    re.compile(r"(?i:use|with|enter|apply|promo|discount|coupon)\s+(?i:the\s+)?(?i:promo\s+|discount\s+|coupon\s+)?"
               r"(?i:code)\s*[:\-]?\s*[\"'“‘]?" + _CODE + r"\b"),
    re.compile(r"\b(?i:code)\s*:\s*[\"'“‘]?" + _CODE + r"\b"),
    re.compile(r"\bCODE\s+" + _CODE + r"\b"),
)
_DISCOUNT_LINK = re.compile(r"/discount/([A-Za-z0-9][A-Za-z0-9_-]{1,22}[A-Za-z0-9])(?:[?\"'#/]|$)")
_PERCENT = re.compile(r"(?:(\d{1,2})\s*%\s*off|save\s+(?:up\s+to\s+)?(\d{1,2})\s*%|(?:extra|additional)\s+(\d{1,2})\s*%)",
                      re.I)
_AMOUNT = re.compile(r"\$\s?(\d{1,3})\s*off|save\s+\$\s?(\d{1,3})\b", re.I)
_MONTH = (r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|sep(?:t(?:ember)?)?|"
          r"oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)")
_ENDS = re.compile(r"(?:ends?|through|thru|until|till|expires?|valid\s+through|runs\s+[^.]{0,20}?[-–]\s*)\s*(?:on\s+)?"
                   r"(?:[a-z]+day,?\s+)?(" + _MONTH + r")\.?\s+(\d{1,2})(?:st|nd|rd|th)?(?:,?\s*(\d{4}))?", re.I)
# Codes that aren't sales.
_NOT_A_SALE = re.compile(
    r"first\s+(?:order|purchase|time)|sign\s*-?\s*up|subscribe|newsletter|e-?mail|\bsms\b|\btexts?\b|"
    r"\bapp\b|member|student|military|teacher|nurse|first\s+responder|birthday|refer|loyalty|rewards?|"
    r"gift\s*card|free\s+shipping|shipping\s+code", re.I)
_STOPWORDS = {"CODE", "HERE", "BELOW", "ABOVE", "AT", "CHECKOUT", "THE", "AND", "FOR", "OFF", "SALE", "NOW", "SHOP",
              "SAVE", "APPLY", "APPLIED", "AUTOMATICALLY", "DISCOUNT", "PROMO", "COUPON", "TODAY", "ONLY", "ALL",
              "YOUR", "ORDER", "ORDERS", "USD", "SHIPPING"}
_MONTHS = {name: number for number, name in enumerate(
    ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"), start=1)}


def page_text(raw):
    """Visible text plus the page description (Fanatik puts the code there)."""
    raw = str(raw or "")
    described = " ".join(m.group(1) for m in re.finditer(
        r'<meta[^>]+(?:name|property)="(?:description|og:description)"[^>]+content="([^"]*)"', raw, re.I))
    body = re.sub(r"(?is)<(script|style|noscript|template)[^>]*>.*?</\1>", " ", raw)
    body = re.sub(r"<[^>]+>", " ", body)
    return re.sub(r"\s+", " ", html_lib.unescape(described + " " + body)).strip()


def _valid_code(code):
    code = str(code or "")
    return (3 <= len(code) <= 24 and code.upper() == code and code not in _STOPWORDS
            and re.fullmatch(r"[A-Z0-9][A-Z0-9_-]*[A-Z0-9]", code) is not None and re.search(r"[A-Z0-9]{2}", code))


_ENDS_NUMERIC = re.compile(r"(?:ends?|through|thru|until|till|expires?)\s*(?:on\s+)?(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\b",
                           re.I)


def _end_date(text, today):
    match = _ENDS.search(text)
    numeric = _ENDS_NUMERIC.search(text)
    if match:
        month = _MONTHS.get(match.group(1)[:3].lower())
        day = int(match.group(2))
        year = int(match.group(3)) if match.group(3) else today.year
    elif numeric:
        month, day = int(numeric.group(1)), int(numeric.group(2))
        year = int(numeric.group(3)) if numeric.group(3) else today.year
        if year < 100:
            year += 2000
        match = numeric
    else:
        return ""
    try:
        end = datetime.date(year, month, day)
    except (TypeError, ValueError):
        return ""
    if not match.group(3) and end < today - datetime.timedelta(days=60):
        end = end.replace(year=year + 1)  # "until Jan 5" read in December
    return end.isoformat()


def _discount(window):
    percent = _PERCENT.search(window)
    if percent:
        value = int(next(group for group in percent.groups() if group))
        if 5 <= value <= 80:
            return {"percent": value}
    amount = _AMOUNT.search(window)
    if amount:
        value = int(next(group for group in amount.groups() if group))
        if value >= 5:
            return {"amount": value}
    return None


def find(raw, today=None):
    """Promo codes in one page: [{"code", "percent"|"amount", "ends"}]."""
    today = today or datetime.date.today()
    text = page_text(raw)
    candidates = []
    for pattern in _CODE_PHRASES:
        for match in pattern.finditer(text):
            candidates.append((match.group(1), match.start(), match.end()))
    for match in _DISCOUNT_LINK.finditer(str(raw or "")):
        code = urllib.parse.unquote(match.group(1)).upper()
        spot = text.upper().find(code)
        candidates.append((code, max(spot, 0), max(spot, 0) + len(code)))
    found = {}
    for code, start, end in candidates:
        if not _valid_code(code) or code in found:
            continue
        window = text[max(0, start - 180):end + 180]
        # The words right around the code decide whether it's a sign-up code.
        near = text[max(0, start - 90):end + 60]
        if _NOT_A_SALE.search(near):
            continue
        discount = _discount(window)
        if not discount:
            continue
        # The end date usually follows the code ("... code X. Ends Dec 2"); a
        # date before it may belong to the promo above on the same page.
        ends = _end_date(text[start:end + 180], today) or _end_date(text[max(0, start - 120):start], today)
        found[code] = dict(code=code, ends=ends, **discount)
    return list(found.values())


def sale_links(raw, base):
    """Same-site links on a homepage that look like sale pages, at most MAX_LINKS."""
    host = urllib.parse.urlsplit(base).netloc.lower()
    links = []
    for match in re.finditer(r'href="([^"#]+)"', str(raw or ""), re.I):
        url = urllib.parse.urljoin(base + "/", html_lib.unescape(match.group(1)))
        parts = urllib.parse.urlsplit(url)
        if parts.scheme != "https" or parts.netloc.lower() != host or parts.query:
            continue
        if not re.match(r"^/(?:[a-z]{2}(?:-[a-z]{2})?/)?(?:collections|pages|sale|deals|promotions?|black)", parts.path, re.I):
            continue
        if parts.path.rstrip("/").endswith("/products.json") or "/products/" in parts.path:
            continue
        if not _SALE_LINK.search(parts.path):
            continue
        url = f"https://{parts.netloc}{parts.path}"
        if url not in links:
            links.append(url)
    # Seasonal pages first: "black-friday" before a standing "/collections/sale".
    links.sort(key=lambda url: 0 if re.search(r"black|cyber|bfcm|doorbuster|holiday|flash|promo", url, re.I) else 1)
    return links[:MAX_LINKS]


def _fetch(url, timeout=25):
    request = urllib.request.Request(url, headers={"User-Agent": _UA, "Accept": "text/html"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read(3_000_000).decode("utf-8", "replace")


def _robots(base, fetch):
    parser = urllib.robotparser.RobotFileParser()
    try:
        parser.parse(fetch(base + "/robots.txt").splitlines())
    except Exception:
        parser.parse([])
    return parser


def scan_store(name, base, fetch=None, sleep=time.sleep, today=None):
    """(promos, read_ok) for one store. Never raises."""
    fetch = fetch or _fetch
    try:
        robots = _robots(base, fetch)
        home_url = base.rstrip("/") + "/"
        if not robots.can_fetch(_UA, home_url):
            return [], False
        home = fetch(home_url)
    except Exception as exc:
        logger.info("%s: homepage not read (%s)", name, type(exc).__name__)
        return [], False
    promos = {promo["code"]: dict(promo, url=home_url) for promo in find(home, today)}
    for url in sale_links(home, base.rstrip("/")):
        if not robots.can_fetch(_UA, url):
            continue
        sleep(DELAY)
        try:
            page = fetch(url)
        except Exception as exc:
            logger.info("%s: %s not read (%s)", name, url, type(exc).__name__)
            continue
        for promo in find(page, today):
            promos.setdefault(promo["code"], dict(promo, url=url))
    return [dict(promo, store=name) for promo in promos.values()], True


def stores_of(scrapers):
    """{store name: homepage} for a run's scrapers, in order."""
    stores = {}
    for scraper in scrapers or ():
        shop = getattr(scraper, "shop", None)
        name = getattr(shop, "store", None) or getattr(scraper, "store", None) or getattr(scraper, "name", None)
        base = (getattr(shop, "base", None) or getattr(scraper, "base", None) or getattr(scraper, "base_url", None)
                or getattr(scraper, "url", None))
        if not name or not base:
            continue
        parts = urllib.parse.urlsplit(str(base))
        if parts.scheme == "https" and parts.netloc:
            stores.setdefault(str(name), f"https://{parts.netloc}")
    return stores


def merge(previous, found, read, today):
    """Today's promo list from the last one and this run's reads.

    ``found``: promos seen today; ``read``: store names read successfully."""
    today_s = today.isoformat()
    earlier = {(p.get("store"), p.get("code")): p for p in (previous or []) if isinstance(p, dict)}
    result = {}
    for promo in found:
        key = (promo["store"], promo["code"])
        first = (earlier.get(key) or {}).get("first_seen") or today_s
        result[key] = dict(promo, first_seen=first, last_seen=today_s)
    oldest = (today - datetime.timedelta(days=KEEP_DAYS)).isoformat()
    for key, promo in earlier.items():
        if key in result or key[0] in read:
            continue
        if (promo.get("last_seen") or "") >= oldest:
            result[key] = promo
    return sorted((p for p in result.values() if not p.get("ends") or p["ends"] >= today_s),
                  key=lambda p: (p.get("store") or "", p.get("code") or ""))


def load(path=PATH):
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
        return list(data.get("promos") or [])
    except (OSError, ValueError, AttributeError):
        return []


def all_stores():
    """{homepage: (store name, [sport ids])} for every sport's scrapers."""
    import os
    import sports
    stores = {}
    root = os.getcwd()
    for sport in sports.SPORTS.values():
        try:
            with sport.session():
                if sport.is_default:
                    from scraper import build_scrapers
                    scrapers = build_scrapers()
                else:
                    scrapers = sport.build_scrapers()
        except Exception as exc:
            logger.warning("%s: stores not listed (%s)", sport.label, type(exc).__name__)
            continue
        finally:
            os.chdir(root)
        for name, base in stores_of(scrapers).items():
            entry = stores.setdefault(base, (name, []))
            if sport.id not in entry[1]:
                entry[1].append(sport.id)
    return stores


def run(stores=None, today=None, path=PATH, fetch=None, sleep=time.sleep):
    """Scan the stores, update ``promos.json`` and return the current promos.
    ``stores``: {homepage: (name, [sport ids])} (default: every sport's).
    Never raises: a failure keeps the previous file."""
    today = today or datetime.date.today()
    try:
        stores = all_stores() if stores is None else stores
        previous = load(path)
        found, read = [], set()
        for index, (base, (name, sport_ids)) in enumerate(stores.items()):
            if index:
                sleep(DELAY)
            promos, ok = scan_store(name, base, fetch=fetch, sleep=sleep, today=today)
            if ok:
                read.add(name)
            found.extend(dict(promo, sports=sorted(sport_ids)) for promo in promos)
        current = merge(previous, found, read, today)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump({"updated": today.isoformat(), "promos": current}, handle, indent=1, ensure_ascii=False)
            handle.write("\n")
        logger.info("Promo codes: %s current (%s of %s stores read)", len(current), len(read), len(stores))
        return current
    except Exception as exc:
        logger.error("Promo check failed (continuing): %s", type(exc).__name__)
        return load(path)


def for_sport(sport_id, promos=None, path=PATH):
    """Current promos at stores ``sport_id`` reads."""
    promos = load(path) if promos is None else promos
    return [promo for promo in promos if sport_id in (promo.get("sports") or ())]


def new_today(promos, today=None):
    today_s = (today or datetime.date.today()).isoformat()
    return [promo for promo in promos or [] if promo.get("first_seen") == today_s]


def describe(promo, code=True):
    """"20% off with code 2026-BFCM-20, until Dec 2" ("20% off, until Dec 2"
    with ``code=False``, when the code is shown on its own)."""
    if promo.get("percent"):
        offer = f"{promo['percent']}% off"
    elif promo.get("amount"):
        offer = f"${promo['amount']} off"
    else:
        offer = "Discount"
    text = f"{offer} with code {promo.get('code')}" if code else offer
    if promo.get("ends"):
        try:
            end = datetime.date.fromisoformat(promo["ends"])
            text += f", until {end.strftime('%b')} {end.day}"
        except ValueError:
            pass
    return text


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    for promo in run():
        print(f"{promo['store']}: {describe(promo)} ({', '.join(promo.get('sports') or [])})")
