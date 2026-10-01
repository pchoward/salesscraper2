"""Static sale report.

The published page is one HTML file. Filters, sorting, stars, and the price
drawer run in the browser. A problem in one section is logged and skipped.
"""

import datetime
import json
import logging
import os
from html import escape
from zoneinfo import ZoneInfo

from badges import classify_badges
from dimensions import dimension_key, extract_specs
from filters import (
    BEARING_BRANDS,
    DECK_BRANDS,
    TRUCK_BRANDS,
    WHEEL_BRANDS,
    calculate_percent_off,
    find_brand,
    item_passes_filters,
    normalize_product_name,
    normalize_url,
    percent_off_value,
)
from health import warning_text
from history import (
    STAGE_LABEL,
    all_time_low_status,
    days_at_price,
    listing_stage,
    recently_gone,
    summarize_entry,
)
from matching import cross_store_groups
from query_state import STARTER_VIEWS, WIDTH_RANGES, bucket_for_width
from score import FORMULA, deal_score
from site_sales import activity_line, describe_sales, display_name, load_state
from watchlist import load_watchlist, rule_matches

logger = logging.getLogger("page")

_HERE = os.path.dirname(os.path.abspath(__file__))
_BRANDS = {
    "decks": DECK_BRANDS + ("Powell Peralta",),
    "wheels": WHEEL_BRANDS + ("Powell Peralta",),
    "trucks": TRUCK_BRANDS,
    "bearings": BEARING_BRANDS,
}
_BRAND_ALIAS = {
    "anti hero": "Anti-Hero",
    "antihero": "Anti-Hero",
    "anti-hero": "Anti-Hero",
}
_PLACEHOLDER = (
    '<svg viewBox="0 0 64 64" width="68" height="68" aria-hidden="true">'
    '<rect width="64" height="64" fill="#e2e8f0"/>'
    '<rect x="8" y="28" width="48" height="8" rx="2" fill="#94a3b8"/>'
    "</svg>"
)


def _read_asset(name):
    path = os.path.join(_HERE, name)
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


def _price(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _money(value):
    amount = _price(value)
    if amount is None:
        return "N/A"
    return f"${amount:.2f}"


def _store_class(store):
    return "store-" + "".join(ch for ch in (store or "").lower() if ch.isalnum())


def _as_date(value):
    try:
        return datetime.date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _display_name(item):
    return normalize_product_name((item or {}).get("name", ""))


def _entry(history, url):
    if not isinstance(history, dict) or not url:
        return {}
    found = history.get(url) or history.get(normalize_url(url))
    return found if isinstance(found, dict) else {}


def listing_brand(name, part):
    brands = _BRANDS.get((part or "").strip().casefold(), ())
    found = find_brand(name, brands) if brands else None
    if not found:
        tokens = normalize_product_name(name).split()
        found = tokens[0] if tokens else ""
    return _BRAND_ALIAS.get(found.casefold(), found)


def _discount_class(price_new, price_old):
    percent = percent_off_value(price_new, price_old)
    if percent is None:
        return "low"
    if percent >= 40:
        return "high"
    if percent >= 25:
        return "medium"
    return "low"


def _specs_for(item, entry):
    specs = extract_specs(item.get("name") or "")
    for field in ("width", "length", "wheelbase"):
        if item.get(field) not in (None, ""):
            try:
                specs[field] = float(item.get(field))
            except (TypeError, ValueError):
                pass
        elif entry.get(field) not in (None, "") and specs.get(field) is None:
            try:
                specs[field] = float(entry.get(field))
            except (TypeError, ValueError):
                pass
    return specs


def _image_of(item, entry):
    image = str(item.get("image") or entry.get("image") or "").strip()
    if image.startswith("http"):
        return image
    return ""


def _prices_of(entry):
    summary = summarize_entry(entry) if entry else {"prices": {}}
    prices = summary.get("prices") or {}
    return {day: float(prices[day]) for day in sorted(prices)}


def _chain(prices):
    points = []
    last = None
    for day in sorted(prices):
        price = float(prices[day])
        if last is None or abs(price - last) > 0.001:
            points.append([day, round(price, 2)])
            last = price
    return points


def _daily_points(prices):
    return [[day, round(float(prices[day]), 2)] for day in sorted(prices or {})]


def _parse_generated(value):
    if isinstance(value, datetime.datetime):
        return value
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        pass
    try:
        return datetime.datetime.strptime(text[:19], "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None


def format_scan_et(value):
    """Exact scan time for the hover label, in US Eastern."""
    moment = _parse_generated(value)
    if moment is None:
        return str(value or "")
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=datetime.timezone.utc)
    local = moment.astimezone(ZoneInfo("America/New_York"))
    hour = local.strftime("%I").lstrip("0") or "12"
    return f"{local.strftime('%b')} {local.day}, {local.year} {hour}:{local.strftime('%M:%S %p')} ET"


def _held_label(days, at_days, price):
    label = f"{days}d tracked"
    if price is None:
        return label
    return f"{label} · {at_days}d @ ${float(price):.2f}"


def sparkline_svg(prices, width=72, height=22, css="spark"):
    ordered = [float(prices[day]) for day in sorted(prices or {})]
    if len(ordered) > 48:
        step = len(ordered) / 48
        sampled = [ordered[int(index * step)] for index in range(48)]
        sampled[-1] = ordered[-1]
        ordered = sampled
    if len(ordered) < 2:
        return ""
    low = min(ordered)
    high = max(ordered)
    span = high - low or 1
    last = len(ordered) - 1
    points = []
    for index, value in enumerate(ordered):
        x_pos = 1 + (index / last) * (width - 2)
        y_pos = 1 + (height - 4) * (1 - (value - low) / span)
        points.append(f"{x_pos:.1f},{y_pos:.1f}")
    color = "#15803d" if ordered[-1] <= ordered[0] else "#b91c1c"
    return (
        f'<svg class="{css}" viewBox="0 0 {width} {height}" width="{width}" height="{height}" aria-hidden="true">'
        f'<polyline fill="none" stroke="{color}" stroke-width="1.6" points="{" ".join(points)}"/>'
        "</svg>"
    )


def _thumb(image, alt, large=False):
    css = "hero" if large else "thumb"
    icon = _PLACEHOLDER
    if not image:
        return f'<span class="thumb-wrap{" hero-wrap" if large else ""}"><span class="{css} ph">{icon}</span></span>'
    safe = escape(image, quote=True)
    label = escape(alt or "", quote=True)
    size = 160 if large else 68
    return (
        f'<span class="thumb-wrap{" hero-wrap" if large else ""}">'
        f'<img class="{css}" src="{safe}" alt="{label}" width="{size}" height="{size}" loading="lazy" '
        'onerror="this.hidden=true;if(this.nextElementSibling)this.nextElementSibling.hidden=false">'
        f'<span class="{css} ph" hidden>{icon}</span></span>'
    )


def _product_link(item):
    name = escape(_display_name(item))
    url = escape(normalize_url(item.get("url", "")), quote=True)
    if not url:
        return name
    return f'<a class="product-link" href="{url}" target="_blank" rel="noopener">{name}</a>'


def _badge_html(badges, listed):
    pills = []
    for badge in badges:
        kind = escape(badge.get("kind") or "new")
        pills.append(f'<span class="pill pill-{kind}">{escape(badge.get("label") or "")}</span>')
    if listed:
        pills.append('<span class="pill pill-list">Watchlist</span>')
    if not pills:
        return ""
    return f'<div class="pills">{"".join(pills)}</div>'


def _option(value, label, selected=False):
    mark = " selected" if selected else ""
    return f'<option value="{escape(str(value), quote=True)}"{mark}>{escape(str(label))}</option>'


def _buttons(group_id, attr, onclick, values, active="all"):
    rows = [
        f'<button type="button" class="filter-btn active" data-{attr}="all" '
        f'onclick="{onclick}(\'all\')">All</button>'
    ]
    for value in values:
        rows.append(
            f'<button type="button" class="filter-btn" data-{attr}="{escape(str(value), quote=True)}" '
            f'onclick="{onclick}(\'{escape(str(value), quote=True)}\')">{escape(str(value))}</button>'
        )
    return f'<div class="filter-group" id="{group_id}">{"".join(rows)}</div>'


def _alert_html(warnings):
    if not warnings:
        return ""
    items = []
    for warning in warnings:
        text = warning_text(warning) if isinstance(warning, dict) else str(warning)
        items.append(f"<li>{escape(text)}</li>")
    return (
        '<div class="alert" id="storeAlerts" role="status">'
        "<strong>Store check failed</strong>"
        "<p>These categories usually have sale items. The last two runs came back empty or failed. "
        "A single empty run does not raise this warning.</p>"
        f"<ul>{''.join(items)}</ul></div>"
    )


def _atl_section(low_items, history):
    rows = [
        '<div class="section" id="atlSection">',
        '<div class="section-header collapsed" onclick="toggleSection(this)">',
        f'<h2>All-time lows <span class="badge">{len(low_items)}</span></h2>',
        '<span class="toggle-icon">▼</span></div>',
        '<div class="section-content collapsed">',
        '<p class="lede">Current sale price equals the lowest price tracked for that listing. '
        "A listing needs at least 3 observations spanning 7 days, so a brand-new deal is not "
        "flagged just because its first price is the only price.</p>",
        '<table id="atlTable"><thead><tr>',
        "<th>Store</th><th>Part</th><th>Product</th><th>Sale price</th><th>Low since</th><th>Observations</th>",
        "</tr></thead><tbody>",
    ]
    for item in low_items:
        try:
            status = all_time_low_status(item, history)
            store = item.get("store") or "Unknown"
            title = escape(status.get("title") or "All-time low", quote=True)
            rows.append(
                "<tr>"
                f'<td><span class="store-badge {_store_class(store)}">{escape(store)}</span></td>'
                f'<td><span class="part-badge">{escape(item.get("part") or "")}</span></td>'
                f'<td class="product-name">{_product_link(item)} '
                f'<span class="atl-badge" title="{title}">ALL-TIME LOW</span></td>'
                f'<td class="price price-new">{_money(item.get("price_new"))}</td>'
                f'<td>{escape(status.get("low_date") or "")}</td>'
                f'<td>{escape(str(status.get("observations") or ""))}</td>'
                "</tr>"
            )
        except Exception as exc:
            logger.error("All-time low row failed: %s", exc)
    rows.append("</tbody></table></div></div>")
    return "\n".join(rows)


def _compare_section(groups):
    if not groups:
        return ""
    rows = [
        '<div class="section" id="compareSection">',
        '<div class="section-header" onclick="toggleSection(this)">',
        f'<h2>Across stores <span class="badge">{len(groups)}</span></h2>',
        '<span class="toggle-icon">▼</span></div>',
        '<div class="section-content">',
        '<p class="lede">Same brand, model, and size at two or more stores. '
        "The lowest price is highlighted. Matching is conservative, so some real duplicates stay separate.</p>",
        '<div class="compare-grid">',
    ]
    for group in groups:
        offers = []
        for offer in group.get("offers") or []:
            price = offer.get("price")
            cheapest = price is not None and abs(price - group.get("cheapest_price", price)) < 0.001
            klass = "offer cheapest" if cheapest else "offer"
            store = offer.get("store") or ""
            name = escape(offer.get("name") or "")
            url = offer.get("url") or ""
            if url:
                name_html = (
                    f'<a href="{escape(url, quote=True)}" target="_blank" rel="noopener">{name}</a>'
                )
            else:
                name_html = name
            offers.append(
                f'<div class="{klass}" data-store="{escape(store, quote=True)}">'
                f'<div class="who"><span class="store-badge {_store_class(store)}">{escape(store)}</span></div>'
                f'<div class="amt">{_money(price)}</div>'
                f'<div class="nm">{name_html}</div></div>'
            )
        rows.append(
            '<div class="compare-card">'
            f'<div class="compare-label">{escape(group.get("label") or "")} '
            f'<span class="part-badge">{escape(group.get("part") or "")}</span></div>'
            f'<div class="compare-offers">{"".join(offers)}</div></div>'
        )
    rows.append("</div></div></div>")
    return "\n".join(rows)


def _bar_rows(pairs, label_key="label"):
    if not pairs:
        return "<p class=\"empty\">Nothing to show.</p>"
    peak = max(value for _label, value in pairs) or 1
    rows = []
    for label, value in pairs:
        width = max(2, round(100 * value / peak))
        rows.append(
            '<div class="bar-row">'
            f"<span>{escape(str(label))}</span>"
            f'<span class="bar"><i style="width:{width}%"></i></span>'
            f"<span>{escape(str(value))}</span></div>"
        )
    return "".join(rows)


def _stats_html(products, history):
    by_store = {}
    by_width = {}
    by_brand_count = {}
    by_brand_off = {}
    deck_prices = {}
    for item in products:
        store = item.get("store") or "Unknown"
        percent = percent_off_value(item.get("price_new"), item.get("price_old"))
        bucket = by_store.setdefault(store, [])
        if percent is not None:
            bucket.append(percent)
        if item.get("part") == "Decks":
            key = dimension_key((item.get("_specs") or {}).get("width"))
            if key:
                by_width[key] = by_width.get(key, 0) + 1
        brand = item.get("_brand") or ""
        if brand:
            by_brand_count[brand] = by_brand_count.get(brand, 0) + 1
            if percent is not None:
                by_brand_off.setdefault(brand, []).append(percent)
        if item.get("part") == "Decks" and brand:
            price = _price(item.get("price_new"))
            if price is not None:
                deck_prices.setdefault(brand, []).append(price)

    store_avg = []
    for store, values in sorted(by_store.items()):
        if not values:
            continue
        store_avg.append((store, f"{sum(values) / len(values):.0f}%"))
    width_pairs = sorted(by_width.items(), key=lambda pair: float(pair[0]))
    width_pairs = [(label, count) for label, count in width_pairs]
    brand_pairs = sorted(by_brand_count.items(), key=lambda pair: (-pair[1], pair[0]))[:8]
    cheap = []
    for brand, prices in deck_prices.items():
        if len(prices) < 2:
            continue
        cheap.append((brand, sum(prices) / len(prices), len(prices)))
    cheap.sort(key=lambda row: (row[1], row[0]))
    cheap_rows = [
        f"<tr><td>{escape(brand)}</td><td>{_money(avg)}</td><td>{count}</td></tr>"
        for brand, avg, count in cheap[:8]
    ]
    weeks = {}
    if isinstance(history, dict):
        for entry in history.values():
            if not isinstance(entry, dict) or entry.get("part") != "Decks":
                continue
            for day, price in (entry.get("prices") or {}).items():
                parsed = _as_date(day)
                amount = _price(price)
                if parsed is None or amount is None:
                    continue
                week = (parsed - datetime.timedelta(days=parsed.weekday())).isoformat()
                weeks.setdefault(week, []).append(amount)
    week_rows = []
    for week in sorted(weeks)[-12:]:
        values = weeks[week]
        week_rows.append(
            f"<tr><td>{escape(week)}</td><td>{_money(sum(values) / len(values))}</td><td>{len(values)}</td></tr>"
        )
    store_table = "".join(f"<tr><td>{escape(store)}</td><td>{escape(avg)}</td></tr>" for store, avg in store_avg)
    return (
        '<section id="statsPanel" hidden>'
        '<div class="section"><div class="section-header"><h2>Stats</h2></div><div class="section-content">'
        '<div class="stat-block"><h3>Average discount by retailer</h3>'
        f'<table><tbody>{store_table or "<tr><td>No discounts</td></tr>"}</tbody></table></div>'
        '<div class="stat-block"><h3>Deals by width</h3>'
        f'{_bar_rows(width_pairs)}</div>'
        '<div class="stat-block"><h3>Brands with the most markdowns</h3>'
        f'{_bar_rows(brand_pairs)}</div>'
        '<div class="stat-block"><h3>Lowest average deck prices by brand</h3>'
        '<table><thead><tr><th>Brand</th><th>Average sale</th><th>Decks</th></tr></thead>'
        f'<tbody>{"".join(cheap_rows) or "<tr><td colspan=3>Need at least two decks.</td></tr>"}</tbody></table></div>'
        '<div class="stat-block"><h3>Historical deck sale prices</h3>'
        "<p class=\"lede\">Average tracked deck sale price by week, from price history.</p>"
        '<table><thead><tr><th>Week</th><th>Average</th><th>Prices</th></tr></thead>'
        f'<tbody>{"".join(week_rows) or "<tr><td colspan=3>No history yet.</td></tr>"}</tbody></table></div>'
        "</div></div></section>"
    )


def _default_rank(record):
    score = record["score"]["score"]
    if record["drop_amount"]:
        return (0, -record["drop_amount"], -score)
    if record["added"]:
        return (1, -score, record["name"])
    return (2, -score, record["name"])


def _plural(count, singular, plural):
    return f"{count} {singular if count == 1 else plural}"


def render_page(data, changes, price_history=None, failed_keys=None, generated_at=None, digest=None):
    from report import build_digest

    price_history = price_history or {}
    failed_keys = list(failed_keys or [])
    if digest is None:
        digest = build_digest(changes, failed_keys)
    if generated_at is None:
        generated_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    today = str(generated_at)[:10]

    products = []
    for items in (data or {}).values():
        for item in items or []:
            if item_passes_filters(item):
                products.append(item)

    new_urls = set()
    for item in digest.new_items or []:
        url = normalize_url(item.get("url"))
        if url:
            new_urls.add(url)
    drop_by_url = {}
    for change in digest.drops or []:
        item = change.get("item") or {}
        url = normalize_url(item.get("url") or change.get("url"))
        if url:
            drop_by_url[url] = change

    try:
        rules = load_watchlist()
    except Exception as exc:
        logger.error("Watchlist load failed: %s", exc)
        rules = []
    try:
        sales = describe_sales(load_state(), today)
    except Exception as exc:
        logger.error("Site-sale line failed: %s", exc)
        sales = []
    try:
        groups = list(getattr(digest, "cross_store", None) or []) or cross_store_groups(products)
    except Exception as exc:
        logger.error("Cross-store groups failed: %s", exc)
        groups = []
    group_by_url = {}
    for group in groups:
        for offer in group.get("offers") or []:
            url = normalize_url(offer.get("url"))
            if url:
                group_by_url[url] = group

    records = []
    catalog_json = {}
    for item in products:
        try:
            url = normalize_url(item.get("url"))
            entry = _entry(price_history, url)
            specs = _specs_for(item, entry)
            prices = _prices_of(entry)
            drop = drop_by_url.get(url)
            added = url in new_urls
            badges = classify_badges(
                item,
                price_history,
                in_previous=not added,
                drop=drop,
                today=today,
            )
            status = all_time_low_status(item, price_history)
            score = deal_score(
                item,
                price_history,
                drop=drop,
                width=specs.get("width"),
                today=today,
            )
            first = str(entry.get("first_seen") or "")[:10]
            last = str(entry.get("last_seen") or "")[:10] or today
            first_day = _as_date(first)
            today_day = _as_date(today)
            days = (today_day - first_day).days if first_day and today_day else 0
            if days < 0:
                days = 0
            held = days_at_price(entry, today)
            at_days = held.get("days") or 0
            at_price = held.get("price")
            if at_price is None:
                at_price = _price(item.get("price_new"))
            try:
                stage = listing_stage(
                    entry,
                    True,
                    today=today,
                    at_low=bool(status.get("flagged")),
                )
            except Exception:
                stage = "new"
            listed = any(rule_matches(rule, item) for rule in rules)
            brand = listing_brand(item.get("name") or "", item.get("part"))
            hit_low = bool(status.get("flagged")) and (
                str(status.get("low_date") or "")[:10] == today or drop is not None
            )
            drop_amount = 0.0
            if drop is not None:
                try:
                    drop_amount = float(drop.get("delta") or 0)
                except (TypeError, ValueError):
                    drop_amount = 0.0
            image = _image_of(item, entry)
            width_key = dimension_key(specs.get("width")) if item.get("part") == "Decks" else ""
            length_key = dimension_key(specs.get("length")) or ""
            wheel_key = dimension_key(specs.get("wheelbase")) or ""
            percent = percent_off_value(item.get("price_new"), item.get("price_old"))
            record = {
                "item": item,
                "url": url,
                "name": _display_name(item),
                "store": item.get("store") or "Unknown",
                "part": item.get("part") or "",
                "brand": brand,
                "specs": specs,
                "badges": badges,
                "score": score,
                "days": days,
                "at_days": at_days,
                "at_price": at_price,
                "held": _held_label(days, at_days, at_price),
                "stage": stage,
                "first": first,
                "last": last,
                "listed": listed,
                "added": added,
                "drop": drop,
                "drop_amount": drop_amount,
                "lowest": bool(status.get("flagged")),
                "hit_low": hit_low,
                "image": image,
                "prices": prices,
                "chain": _chain(prices),
                "group": group_by_url.get(url),
                "width_key": width_key,
                "length_key": length_key,
                "wheel_key": wheel_key,
                "percent": percent,
                "search": " ".join(
                    bit
                    for bit in (
                        _display_name(item),
                        item.get("store") or "",
                        item.get("part") or "",
                        brand,
                        width_key,
                    )
                    if bit
                ),
            }
            item["_specs"] = specs
            item["_brand"] = brand
            records.append(record)
        except Exception as exc:
            logger.error("Skipping report row %s: %s", (item or {}).get("url"), exc)

    records.sort(key=_default_rank)
    for index, record in enumerate(records):
        record["id"] = str(index)
        record["rank"] = index
        catalog_json[record["id"]] = {
            "name": record["name"],
            "url": record["url"],
            "series": record["chain"],
            "daily": _daily_points(record["prices"]),
        }

    store_counts = {}
    part_counts = {}
    range_counts = {bucket.id: 0 for bucket in WIDTH_RANGES}
    brands = set()
    lengths = set()
    wheels = set()
    for record in records:
        store_counts[record["store"]] = store_counts.get(record["store"], 0) + 1
        part_counts[record["part"]] = part_counts.get(record["part"], 0) + 1
        if record["part"] == "Decks" and record["width_key"]:
            bucket = bucket_for_width(record["width_key"])
            if bucket is not None:
                range_counts[bucket.id] += 1
        if record["brand"]:
            brands.add(record["brand"])
        if record["length_key"]:
            lengths.add(record["length_key"])
        if record["wheel_key"]:
            wheels.add(record["wheel_key"])

    low_items = []
    try:
        low_items = [record["item"] for record in records if record["lowest"]]
        order = {"Decks": 0, "Wheels": 1, "Trucks": 2, "Bearings": 3}
        low_items.sort(key=lambda item: (order.get(item.get("part"), 9), _display_name(item)))
    except Exception as exc:
        logger.error("All-time low list failed: %s", exc)
        low_items = []

    new_count = len(digest.new_items or [])
    drop_count = len(digest.drops or [])
    gone_count = len(digest.removed or [])
    hit_count = sum(1 for record in records if record["hit_low"])
    warnings = []
    try:
        warnings = [warning for warning in (getattr(digest, "warnings", None) or []) if warning]
    except Exception as exc:
        logger.error("Store warnings could not be read: %s", exc)

    chunks = [
        "<!DOCTYPE html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="UTF-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1.0">',
        f"<title>Skateboard Sale Tracker | {escape(today)}</title>",
        '<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">',
        f"<style>{_read_asset('page.css')}</style>",
        "</head><body><div class=\"container\">",
        "<header>",
        "<h1>Skateboard Sale Tracker</h1>",
        "<p>"
        f'<span id="statusCounts">{len(records)} active deals, {new_count} new, {drop_count} drops</span>'
        ', last scan <span class="scan-wrap"><time id="lastScan" datetime="'
        f'{escape(str(generated_at), quote=True)}">{escape(str(generated_at))}</time>'
        f'<span class="scan-exact" id="scanExact">{escape(format_scan_et(generated_at))}</span></span></p>',
        "</header>",
    ]
    alert = _alert_html(warnings)
    if alert:
        chunks.append(alert)

    chunks.append(
        '<p class="lede" id="changeLine" '
        f'data-new="{new_count}" data-drops="{drop_count}" data-lows="{hit_count}" data-gone="{gone_count}">'
        "Digest of what changed. "
        '<span id="changePrefix">Since yesterday:</span> '
        f'<button type="button" class="change-btn" id="btnNew" data-change="new" onclick="setChange(\'new\')">'
        f"{escape(_plural(new_count, 'new deal', 'new deals'))}</button> "
        f'<button type="button" class="change-btn" id="btnDrop" data-change="drop" onclick="setChange(\'drop\')">'
        f"{escape(_plural(drop_count, 'price drop', 'price drops'))}</button> "
        f'<button type="button" class="change-btn" id="btnLow" data-change="lowest" onclick="setChange(\'lowest\')">'
        f"{hit_count} hit lowest tracked price</button> "
        f'<button type="button" class="change-btn" id="btnGone" data-change="removed" onclick="setChange(\'removed\')">'
        f"{escape(_plural(gone_count, 'deal disappeared', 'deals disappeared'))}</button></p>"
    )
    chunks.append(
        '<div class="mode">'
        '<button type="button" class="mode-btn" id="modeYesterday" aria-pressed="true" '
        'onclick="setVisitMode(\'yesterday\')">Since yesterday</button>'
        '<button type="button" class="mode-btn" id="modeVisit" aria-pressed="false" '
        'onclick="setVisitMode(\'visit\')">Since your last visit</button></div>'
        '<p class="lede" id="visitNote" hidden></p>'
    )

    chunks.append('<div class="stats-grid">')
    chunks.append(
        '<button type="button" class="stat-card emphasis" data-card="new" aria-pressed="false" '
        f'onclick="toggleCard(\'new\')"><div class="number">{new_count}</div><div class="label">New deals</div></button>'
    )
    chunks.append(
        '<button type="button" class="stat-card emphasis" data-card="drop" aria-pressed="false" '
        f'onclick="toggleCard(\'drop\')"><div class="number">{drop_count}</div><div class="label">Price drops</div></button>'
    )
    if low_items:
        chunks.append(
            '<button type="button" class="stat-card" data-card="lowest" aria-pressed="false" '
            f'onclick="toggleCard(\'lowest\')"><div class="number">{len(low_items)}</div>'
            '<div class="label">All-time lows</div></button>'
        )
    chunks.append(
        '<button type="button" class="stat-card" data-card="clear" onclick="toggleCard(\'clear\')">'
        f'<div class="number">{len(records)}</div><div class="label">Tracked deals</div></button>'
    )
    for store, count in sorted(store_counts.items()):
        chunks.append(
            '<button type="button" class="stat-card" data-card="store" '
            f'data-store="{escape(store, quote=True)}" aria-pressed="false" '
            f"onclick=\"toggleCard('store', '{escape(store, quote=True)}')\">"
            f'<div class="number">{count}</div><div class="label">{escape(store)}</div></button>'
        )
    chunks.append("</div>")

    try:
        chunks.append(_activity_html(sales, generated_at))
    except Exception as exc:
        logger.error("Retailer activity panel failed: %s", exc)
    if failed_keys:
        listed = ", ".join(escape(key) for key in failed_keys)
        chunks.append(
            f'<div class="notice">Scrape failed for {listed}. '
            "Previous listings for those categories were kept, and removals are hidden.</div>"
        )

    try:
        chunks.append(_atl_section(low_items, price_history))
    except Exception as exc:
        logger.error("All-time low section failed: %s", exc)
    try:
        chunks.append(_compare_section(groups))
    except Exception as exc:
        logger.error("Across-stores section failed: %s", exc)

    store_options = ['<option value="all">All stores</option>']
    for store in sorted(store_counts):
        store_options.append(_option(store, store))
    part_options = ['<option value="all">All types</option>']
    for part in ("Decks", "Wheels", "Trucks", "Bearings"):
        if part in part_counts:
            part_options.append(_option(part, part))
    brand_options = ['<option value="all">All brands</option>']
    for brand in sorted(brands, key=str.casefold):
        brand_options.append(_option(brand, brand))
    length_select = ""
    if lengths:
        options = ['<option value="all">All lengths</option>']
        for value in sorted(lengths, key=float):
            options.append(_option(value, value))
        length_select = (
            '<label class="field"><span>Length</span>'
            f'<select id="lengthSelect">{"".join(options)}</select></label>'
        )
    wheel_select = ""
    if wheels:
        options = ['<option value="all">All wheelbases</option>']
        for value in sorted(wheels, key=float):
            options.append(_option(value, value))
        wheel_select = (
            '<label class="field"><span>Wheelbase</span>'
            f'<select id="wheelbaseSelect">{"".join(options)}</select></label>'
        )
    chips = [
        '<button type="button" class="chip active" data-range="all" aria-pressed="true" '
        "onclick=\"toggleWidthRange('all')\">All</button>"
    ]
    for bucket in WIDTH_RANGES:
        count = range_counts[bucket.id]
        zero = " is-zero" if count == 0 else ""
        low = "" if bucket.min is None else bucket.min
        high = "" if bucket.max is None else bucket.max
        chips.append(
            f'<button type="button" class="chip{zero}" data-range="{escape(bucket.id, quote=True)}" '
            f'data-min="{low}" data-max="{high}" data-count="{count}" aria-pressed="false" '
            f"onclick=\"toggleWidthRange('{escape(bucket.id, quote=True)}')\">"
            f"{escape(bucket.label)} ({count})</button>"
        )

    chunks.append('<div class="sticky-bar" id="stickyBar">')
    chunks.append(
        '<div class="controls" id="basicFilters">'
        '<div class="search-box"><input type="text" id="searchInput" placeholder="Search deals"></div>'
        '<label class="field"><span>Store</span>'
        f'<select id="storeSelect">{"".join(store_options)}</select></label>'
        '<label class="field"><span>Type</span>'
        f'<select id="partSelect">{"".join(part_options)}</select></label>'
        '<label class="field"><span>Brand</span>'
        f'<select id="brandSelect">{"".join(brand_options)}</select></label>'
        '<label class="field"><span>Sort</span><select id="sortSelect">'
        '<option value="rank">Newest / biggest drop</option>'
        '<option value="score">Deal score</option>'
        '<option value="price">Sale price, low to high</option>'
        '<option value="price-desc">Sale price, high to low</option>'
        '<option value="original">Original price</option>'
        '<option value="discount">% off</option>'
        '<option value="size">Size</option>'
        '<option value="store">Store</option>'
        '<option value="brand">Brand</option>'
        '<option value="days">Days tracked</option>'
        '<option value="daysat">Days at this price</option>'
        "</select></label>"
        '<button type="button" class="text-btn" id="moreFilters" aria-expanded="false" aria-controls="morePanel">'
        'More filters <span id="moreCount" hidden></span></button>'
        "</div>"
    )
    chunks.append(
        '<div class="more-filters" id="morePanel" hidden>'
        '<label class="field"><span>Min price</span><input id="priceMin" type="number" min="0" step="1" inputmode="decimal"></label>'
        '<label class="field"><span>Max price</span><input id="priceMax" type="number" min="0" step="1" inputmode="decimal"></label>'
        '<label class="field"><span>Discount min</span><input id="discountMin" type="number" min="0" max="100" step="1"></label>'
        f"{length_select}{wheel_select}"
        "</div>"
    )
    chunks.append(
        '<div class="chip-row">'
        + _buttons("storeFilters", "store", "filterByStore", sorted(store_counts))
        + _buttons("partFilters", "part", "filterByPart", [part for part in ("Decks", "Wheels", "Trucks", "Bearings") if part in part_counts])
        + f'<div class="filter-group width-ranges" id="sizeFilters">'
        '<span class="range-label">Width range</span>'
        + f'{"".join(chips)}</div>'
        + "</div>"
    )
    chunks.append(
        '<div class="tool-row">'
        '<button type="button" class="text-btn" id="watchingToggle" aria-pressed="false" onclick="toggleWatching()">Watching</button>'
        '<button type="button" class="text-btn" id="groupToggle" aria-pressed="false" onclick="toggleGrouped()">Group across stores</button>'
        '<button type="button" class="text-btn" id="statsToggle" aria-pressed="false" onclick="toggleStats()">Stats</button>'
        '<button type="button" class="text-btn" id="saveView">Save view</button>'
        '<button type="button" class="text-btn" onclick="clearFilters()">Clear</button>'
        "</div></div>"
    )
    chunks.append(
        '<form class="save-view" id="saveViewForm" hidden>'
        '<input id="viewNameInput" type="text" maxlength="80" placeholder="Name this view" aria-label="View name">'
        '<button type="submit" class="text-btn">Save</button>'
        '<button type="button" class="text-btn" id="viewCancel">Cancel</button>'
        "</form>"
        '<div class="view-row" id="viewRow"></div>'
    )

    header_cells = [
        ("", ""),
        ("", ""),
        ("Store", "store"),
        ("Brand", "brand"),
        ("Type", "part"),
        ("Size", "size"),
        ("Product", "name"),
        ("Sale price", "price"),
        ("Original", "original"),
        ("% off", "discount"),
        ("Days", "days"),
        ("Score", "score"),
    ]
    head = []
    for label, key in header_cells:
        if not key:
            head.append("<th></th>")
        elif key == "days":
            head.append(
                '<th class="days-head">'
                '<button type="button" data-sort="days" onclick="sortBy(\'days\')">Tracked</button>'
                '<button type="button" data-sort="daysat" onclick="sortBy(\'daysat\')">At price</button>'
                "</th>"
            )
        else:
            title = f' title="{escape(FORMULA, quote=True)}"' if key == "score" else ""
            head.append(
                f'<th data-sort="{key}"{title} onclick="sortBy(\'{key}\')">{escape(label)}</th>'
            )
    chunks.append(
        '<div class="section" id="dealsSection">'
        '<div class="section-header"><h2>All Deals '
        f'<span class="badge">{len(records)}</span></h2></div>'
        '<div class="section-content">'
    )
    chunks.append(f'<div class="table-wrap"><table id="mainTable"><thead><tr>{"".join(head)}</tr></thead><tbody>')

    for record in records:
        try:
            chunks.append(_row_html(record))
            chunks.append(_detail_html(record))
        except Exception as exc:
            logger.error("Row render failed for %s: %s", record.get("url"), exc)
    chunks.append("</tbody></table></div>")
    chunks.append(_group_board(records))
    chunks.append("</div></div>")

    try:
        chunks.append(_gone_section(price_history, data, today, failed_keys))
    except Exception as exc:
        logger.error("Recently gone section failed: %s", exc)

    try:
        chunks.append(_stats_html(products, price_history))
    except Exception as exc:
        logger.error("Stats section failed: %s", exc)

    chunks.append(
        "<footer><p>Zumiez, Skate Warehouse, CCS, and Tactics. "
        "Decks stay at 10% off or more for known street brands and 15% otherwise, "
        "7.5 inches and wider. Named cruiser and longboard listings are still excluded. "
        f"{escape(FORMULA)} "
        "Stars are saved in this browser. Email alerts use watchlist.yaml. "
        "A site-wide sale is a day when a store's sale count is at least 2.5× its recent median and 30 items higher, "
        "after 7 quieter days. Skate Warehouse is seeded at 2026-07-04 until a later day clears that bar.</p>"
        '<p><a href="https://github.com/pchoward/salesscraper2/actions/workflows/scrape.yml">Run scraper now</a></p>'
        "</footer></div>"
    )
    chunks.append(
        '<div id="priceDrawer" hidden>'
        '<button type="button" id="drawerClose">Close</button>'
        '<h3 id="drawerTitle"></h3>'
        '<p class="drawer-chain" id="drawerChain"></p>'
        '<ul class="drawer-list" id="drawerList"></ul>'
        '<p><a id="drawerLink" target="_blank" rel="noopener"></a></p></div>'
    )
    payload = json.dumps(
        {
            "generated": str(generated_at),
            "scanLabel": format_scan_et(generated_at),
            "views": list(STARTER_VIEWS),
            "items": catalog_json,
        }
    ).replace("<", "\\u003c")
    chunks.append(
        '<div id="sparkPanel" hidden>'
        '<p class="spark-title" id="sparkPanelTitle"></p>'
        '<p class="spark-chain" id="sparkPanelText"></p>'
        "</div>"
        '<div id="sparkTip" hidden></div>'
    )
    chunks.append(f'<script type="application/json" id="catalogJson">{payload}</script>')
    ranges_literal = json.dumps(
        [
            {"id": bucket.id, "label": bucket.label, "min": bucket.min, "max": bucket.max}
            for bucket in WIDTH_RANGES
        ]
    )
    chunks.append(f"<script>const WIDTH_RANGES = {ranges_literal};\n{_read_asset('page.js')}</script>")
    chunks.append("</body></html>")
    return "\n".join(chunk for chunk in chunks if chunk)


def _attr(value):
    return escape("" if value is None else str(value), quote=True)


def _row_html(record):
    item = record["item"]
    percent = calculate_percent_off(item.get("price_new"), item.get("price_old"))
    discount = _discount_class(item.get("price_new"), item.get("price_old"))
    size_html = f'<span class="size-badge">{escape(record["width_key"])}</span>' if record["width_key"] else "—"
    drop_html = ""
    if record["drop"] is not None and record["drop_amount"]:
        prior_percent = record["drop"].get("percent_vs_prior")
        try:
            percent_text = f"{float(prior_percent):.1f}"
        except (TypeError, ValueError):
            percent_text = "0.0"
        drop_html = (
            f'<div class="delta">\u2212${record["drop_amount"]:.2f} '
            f'(\u2212{percent_text}% vs prior sale)</div>'
        )
    group_key = ""
    if record["group"]:
        group_key = record["group"].get("key") or ""
    listed = " on-list" if record["listed"] else ""
    original = _price(item.get("price_old"))
    return (
        f'<tr class="deal-row{listed}" tabindex="0" data-id="{record["id"]}" '
        f'data-url="{_attr(record["url"])}" data-store="{_attr(record["store"])}" '
        f'data-part="{_attr(record["part"])}" data-size="{_attr(record["width_key"])}" '
        f'data-brand="{_attr(record["brand"])}" data-name="{_attr(record["name"])}" '
        f'data-search="{_attr(record["search"])}" data-price="{_attr(_price(item.get("price_new")))}" '
        f'data-original="{_attr(original if original is not None else "")}" '
        f'data-discount="{_attr(round(record["percent"], 1) if record["percent"] is not None else "")}" '
        f'data-days="{record["days"]}" data-daysat="{record["at_days"]}" '
        f'data-score="{record["score"]["score"]}" data-rank="{record["rank"]}" '
        f'data-stage="{_attr(record.get("stage") or "")}" '
        f'data-length="{_attr(record["length_key"])}" data-wheelbase="{_attr(record["wheel_key"])}" '
        f'data-added="{1 if record["added"] else 0}" data-drop="{1 if record["drop"] is not None else 0}" '
        f'data-lowest="{1 if record["lowest"] else 0}" data-hitlow="{1 if record["hit_low"] else 0}" '
        f'data-group="{_attr(group_key)}">'
        f'<td>{_thumb(record["image"], record["name"])}</td>'
        '<td><button type="button" class="star" aria-pressed="false" aria-label="Watch this item">☆</button></td>'
        f'<td><span class="store-badge {_store_class(record["store"])}">{escape(record["store"])}</span></td>'
        f'<td>{escape(record["brand"])}</td>'
        f'<td><span class="part-badge">{escape(record["part"])}</span></td>'
        f"<td>{size_html}</td>"
        f'<td class="product-name">{_product_link(item)}'
        f'<div class="row-meta">{_badge_html(record["badges"], record["listed"])}'
        f'{_stage_html(record.get("stage"))}</div></td>'
        f'<td class="price-cell"><button type="button" class="price-btn" data-id="{record["id"]}">'
        f'<span class="price price-new">{_money(item.get("price_new"))}</span></button>'
        f'{_spark_html(record)}{drop_html}</td>'
        f'<td class="price price-old">{_money(item.get("price_old")) if item.get("price_old") else "N/A"}</td>'
        f'<td><span class="discount {discount}">{escape(percent)}</span></td>'
        f'<td class="days-cell">{escape(record["held"])}</td>'
        f'<td class="score-cell"><button type="button" class="score-btn" aria-expanded="false">'
        f'{record["score"]["score"]}'
        + ('<span class="hot">HOT</span>' if record["score"]["hot"] else "")
        + f'</button>{_why_html(record)}</td></tr>'
    )


def _spec_box(label, value):
    shown = dimension_key(value) if value not in (None, "") else ""
    if shown:
        shown = f'{shown}"'
    else:
        shown = "—"
    return f"<div><span>{escape(label)}</span>{escape(shown)}</div>"


def _detail_html(record):
    item = record["item"]
    specs = record["specs"]
    chain = " → ".join(f"${price:.2f}" for _day, price in record["chain"]) or "No price history yet."
    offers = []
    group = record["group"]
    if group:
        cheapest = group.get("cheapest_price")
        for offer in group.get("offers") or []:
            price = offer.get("price")
            cheap = price is not None and cheapest is not None and abs(float(price) - float(cheapest)) < 0.001
            klass = "mini-offer g-cheap" if cheap else "mini-offer"
            url = offer.get("url") or ""
            label = f'{escape(offer.get("store") or "")} {_money(price)}'
            if url:
                inner = f'<a href="{escape(url, quote=True)}" target="_blank" rel="noopener">{label}</a>'
            else:
                inner = label
            offers.append(f'<div class="{klass}">{inner}</div>')
    else:
        offers.append('<div class="mini-offer">No other tracked store has this exact product.</div>')
    url = record["url"]
    retailer = ""
    if url:
        retailer = (
            f'<p><a class="product-link" href="{escape(url, quote=True)}" target="_blank" rel="noopener">'
            f'View at {escape(record["store"])}</a></p>'
        )
    return (
        f'<tr class="detail-row" data-for="{record["id"]}" hidden><td colspan="12">'
        '<div class="detail-panel">'
        f'{_thumb(record["image"], record["name"], large=True)}'
        "<div>"
        f'<strong>{escape(record["name"])}</strong>'
        f'<div class="specs">{_spec_box("Width", specs.get("width"))}'
        f'{_spec_box("Length", specs.get("length"))}'
        f'{_spec_box("Wheelbase", specs.get("wheelbase"))}'
        f'<div><span>First seen</span>{escape(record["first"] or "—")}</div>'
        f'<div><span>Last seen</span>{escape(record["last"] or "—")}</div>'
        f'<div><span>Days tracked</span>{escape(record["held"])}</div>'
        f'<div><span>Stage</span>{escape(STAGE_LABEL.get(record.get("stage"), ""))}</div></div>'
        f"{retailer}"
        f'<div class="chart-box">{sparkline_svg(record["prices"], width=280, height=64)}'
        f'<p class="chain">{escape(chain)}</p></div>'
        f'<div class="offers">{"".join(offers)}</div>'
        "</div></div></td></tr>"
    )


def _offer_link(offer):
    price = _money(offer.get("price"))
    store = escape(offer.get("store") or "")
    label = f"{store} {price}"
    url = offer.get("url") or ""
    if not url:
        return label
    return f'<a href="{escape(url, quote=True)}" target="_blank" rel="noopener">{label}</a>'


def _group_board(records):
    cards = {}
    order = []
    for record in records:
        group = record["group"]
        if not group:
            continue
        key = group.get("key") or ""
        if key not in cards:
            cards[key] = group
            order.append(key)
    blocks = ['<div class="group-board" id="groupBoard" hidden>']
    if not order:
        blocks.append(
            '<p class="group-empty lede">No products are at more than one store under the conservative match. '
            "Rows stay separate.</p></div>"
        )
        return "\n".join(blocks)
    for key in order:
        group = cards[key]
        offers = sorted(
            group.get("offers") or [],
            key=lambda offer: (float(offer.get("price") or 0), offer.get("store") or ""),
        )
        if not offers:
            continue
        best = offers[0]
        rest = offers[1:]
        count = len(offers)
        store_word = "store" if count == 1 else "stores"
        summary = (
            f'{escape(group.get("label") or "Product")} - from {_money(best.get("price"))} - '
            f"{count} {store_word}"
        )
        others = "".join(f"<li>{_offer_link(offer)}</li>" for offer in rest)
        blocks.append(
            f'<article class="group-card" data-key="{escape(key, quote=True)}">'
            f'<button type="button" class="group-summary" aria-expanded="false">{summary}</button>'
            '<div class="group-detail" hidden>'
            f'<p class="best">Best price: {_offer_link(best)}</p>'
            f"<ul>{others}</ul></div></article>"
        )
    blocks.append("</div>")
    return "\n".join(blocks)


def _stage_html(stage):
    label = STAGE_LABEL.get(stage or "")
    if not label:
        return ""
    return f'<span class="stage stage-{escape(stage or "")}">{escape(label)}</span>'


def _why_html(record):
    score = record["score"]
    rows = []
    for factor in score.get("breakdown") or []:
        label = escape(factor.get("label") or "")
        points = factor.get("points")
        if points:
            rows.append(f"<li><span>{label}</span><b>+{int(points)}</b></li>")
        elif label:
            rows.append(f'<li class="why-note"><span>{label}</span></li>')
    return (
        f'<div class="why" id="why-{record["id"]}" role="tooltip">'
        f'<strong>Why {score["score"]}?</strong><ul>{"".join(rows)}</ul></div>'
    )


def _spark_html(record):
    spark = sparkline_svg(record["prices"])
    if not spark:
        return ""
    return (
        f'<button type="button" class="spark-hit" data-id="{record["id"]}" '
        'aria-label="Price history">'
        f"{spark}</button>"
    )


def _activity_html(sales, generated_at):
    if not sales:
        return ""
    banners = []
    for row in sales:
        if not row.get("detected_today") or row.get("extra_percent") is None:
            continue
        try:
            percent = int(row["extra_percent"])
        except (TypeError, ValueError):
            continue
        prefix = (
            f"🔥 {display_name(row.get('store'))} - site-wide sale detected "
            f"({percent}% more items on sale)"
        )
        banners.append(
            f'<p class="sale-banner" data-at="{escape(str(generated_at), quote=True)}">'
            f"{escape(prefix)} <span class=\"ago\">under an hour ago</span></p>"
        )
    items = "".join(f"<li>{escape(activity_line(row))}</li>" for row in sales)
    return (
        '<section class="activity" id="retailerActivity">'
        "<h2>Retailer activity</h2>"
        + "".join(banners)
        + f'<ul class="activity-list">{items}</ul></section>'
    )


def _gone_section(history, current_data, today, failed_keys):
    rows = recently_gone(history, current_data, today=today, skip_keys=failed_keys)
    body = []
    for row in rows:
        store = row.get("store") or "Unknown"
        body.append(
            "<tr>"
            f'<td><span class="store-badge {_store_class(store)}">{escape(store)}</span></td>'
            f'<td><span class="part-badge">{escape(row.get("part") or "")}</span></td>'
            f'<td class="product-name">{escape(row.get("name") or "")}</td>'
            f'<td class="price">{_money(row.get("price"))}</td>'
            f'<td>{escape(row.get("last_seen") or "")}</td>'
            f'<td><span class="stage stage-sold_out">SOLD OUT</span></td>'
            "</tr>"
        )
    note = (
        "Kept for 7 days after a listing leaves the sale catalog, with the last price and the last day it was seen. "
        "A failed scrape does not land here."
    )
    if not rows:
        note = "Nothing has disappeared in the last 7 days. " + note
    return (
        '<div class="section gone-section" id="goneSection">'
        '<div class="section-header collapsed" onclick="toggleSection(this)">'
        f'<h2>Recently gone <span class="badge">{len(rows)}</span></h2>'
        '<span class="toggle-icon">▼</span></div>'
        '<div class="section-content collapsed">'
        f'<p class="lede">{escape(note)}</p>'
        '<table id="goneTable"><thead><tr>'
        "<th>Store</th><th>Part</th><th>Product</th><th>Last price</th><th>Last seen</th><th>Stage</th>"
        f"</tr></thead><tbody>{''.join(body)}</tbody></table></div></div>"
    )
