"""Catalog diff and HTML report.

The digest is the page: new listings and real drops in the sale price.
All Deals stays available, collapsed. Removed rows are omitted when that
store/part scrape failed, and anything rejected by filters.py is left out.

Broken-store warnings (two bad runs in a row) sit at the top. All-time lows
and a conservative cross-store comparison follow the digest.

``build_digest`` is the same split the HTML uses. ``notify.py`` sends email
from that object and does not re-decide what counts as new or a drop.
"""

import datetime
import logging
from html import escape

from health import warning_text
from history import all_time_low_status, price_trend, summarize_entry
from matching import cross_store_groups

logger = logging.getLogger("report")

from filters import (
    calculate_percent_off,
    extract_deck_size,
    is_meaningful_drop,
    item_passes_filters,
    normalize_product_name,
    normalize_url,
    passes_filters,
    percent_off_value,
)


def _price(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def compare_catalogs(prev, curr, failed_keys=None):
    """Diff two catalogs.

    New rows and price drops must pass ``passes_filters``. A price drop is a
    decrease of at least $2 or 5% versus the previous sale price (not MSRP).
    Removals are recorded only when that key was scraped successfully and the
    previous item still passes the filters.
    """
    failed_keys = set(failed_keys or [])
    changes = {}

    for site, items in (curr or {}).items():
        prev_map = {}
        for previous in (prev or {}).get(site, []):
            url = normalize_url(previous.get("url"))
            if url:
                prev_map[url] = previous

        diffs = []
        current_urls = set()
        for item in items or []:
            if not item_passes_filters(item):
                continue
            url = normalize_url(item.get("url"))
            if not url:
                continue
            current_urls.add(url)
            previous = prev_map.get(url)
            if not previous or not item_passes_filters(previous):
                diffs.append({"type": "new", "item": item})
                continue
            old_price = _price(previous.get("price_new"))
            new_price = _price(item.get("price_new"))
            if not is_meaningful_drop(old_price, new_price):
                continue
            delta = old_price - new_price
            percent = (delta / old_price) * 100 if old_price else 0
            diffs.append(
                {
                    "type": "price_drop",
                    "url": url,
                    "name": item.get("name"),
                    "old": previous.get("price_new"),
                    "new": item.get("price_new"),
                    "delta": round(delta, 2),
                    "percent_vs_prior": round(percent, 1),
                    "item": item,
                }
            )

        if site not in failed_keys:
            for url, previous in prev_map.items():
                if url in current_urls or not item_passes_filters(previous):
                    continue
                diffs.append({"type": "removed", "item": previous})

        if diffs:
            changes[site] = diffs
    return changes


def get_price_stats(url, history):
    history = history or {}
    entry = None
    if isinstance(history, dict):
        entry = history.get(url) or history.get(normalize_url(url))
    empty = {"lowest": None, "is_lowest": False, "trend": "stable", "history_days": 0}
    if not isinstance(entry, dict):
        return empty
    summary = summarize_entry(entry)
    prices = summary["prices"]
    if not prices and summary.get("all_time_low") is None:
        return empty
    current = prices[max(prices)] if prices else None
    lowest = summary.get("all_time_low")
    is_lowest = current is not None and lowest is not None and current <= lowest
    return {
        "lowest": lowest,
        "is_lowest": is_lowest,
        "trend": price_trend(entry),
        "history_days": summary["observation_count"],
    }


def _discount_class(price_new, price_old):
    percent = percent_off_value(price_new, price_old)
    if percent is None:
        return "low"
    if percent >= 40:
        return "high"
    if percent >= 25:
        return "medium"
    return "low"


def _money(value):
    amount = _price(value)
    if amount is None:
        return "N/A"
    return f"${amount:.2f}"


def _drop_label(change):
    delta = change.get("delta")
    percent = change.get("percent_vs_prior")
    if delta is None or percent is None:
        old_price = _price(change.get("old"))
        new_price = _price(change.get("new"))
        if old_price is None or new_price is None or old_price <= 0:
            return "N/A"
        delta = old_price - new_price
        percent = (delta / old_price) * 100
    return f"−${delta:.2f} (−{percent:.1f}% vs prior sale)"


def _display_name(item):
    return normalize_product_name((item or {}).get("name", ""))


def _split_changes(changes, failed_keys):
    failed_keys = set(failed_keys or [])
    new_items = []
    drops = []
    removed = []
    for site, site_changes in (changes or {}).items():
        for change in site_changes:
            kind = change.get("type")
            if kind == "new":
                item = change.get("item") or {}
                if item_passes_filters(item):
                    new_items.append(item)
            elif kind in ("price_drop", "price_change"):
                item = change.get("item") or {}
                name = item.get("name") or change.get("name")
                part = item.get("part") or ""
                url = item.get("url") or change.get("url") or ""
                price_new = item.get("price_new", change.get("new"))
                price_old = item.get("price_old")
                if not passes_filters(name, part, url, price_new, price_old):
                    continue
                if not is_meaningful_drop(change.get("old"), change.get("new")):
                    continue
                drops.append(change)
            elif kind == "removed" and site not in failed_keys:
                item = change.get("item") or {}
                if item_passes_filters(item):
                    removed.append((site, item))
    return new_items, drops, removed


def _visible_products(data):
    products = []
    for items in (data or {}).values():
        for item in items or []:
            if item_passes_filters(item):
                products.append(item)
    return products


def _store_class(store):
    return "store-" + "".join(ch for ch in (store or "").lower() if ch.isalnum())


def _product_link(item):
    name = escape(_display_name(item))
    url = escape(normalize_url(item.get("url", "")), quote=True)
    if not url:
        return name
    return f'<a href="{url}" target="_blank" rel="noopener">{name}</a>'


def _deck_size_value(item):
    """Prefer a width parsed from the name over a previously stored size."""
    parsed = extract_deck_size(item.get("name", ""))
    if parsed:
        return parsed
    stored = item.get("size")
    return str(stored) if stored else ""


def _size_cell(item):
    if item.get("part") != "Decks":
        return "-", ""
    size = _deck_size_value(item)
    if not size:
        return "-", ""
    shown = escape(size)
    return f'<span class="size-badge">{shown}"</span>', size


def _atl_badge(item, price_history):
    status = all_time_low_status(item, price_history)
    if not status.get("flagged"):
        return ""
    title = escape(status.get("title") or "All-time low", quote=True)
    return f'<span class="atl-badge" title="{title}">ALL-TIME LOW</span>'


def _price_extras(item, price_history):
    stats = get_price_stats(item.get("url", ""), price_history)
    bits = [_atl_badge(item, price_history)]
    if stats["trend"] == "down":
        bits.append('<span class="trend-down">↓</span>')
    elif stats["trend"] == "up":
        bits.append('<span class="trend-up">↑</span>')
    history = ""
    if stats["history_days"] > 1:
        history = f'<div class="price-history">Tracked {stats["history_days"]} days</div>'
    return "".join(bit for bit in bits if bit) + history


CSS = """
:root {
    --primary: #2563eb;
    --primary-dark: #1d4ed8;
    --secondary: #64748b;
    --success: #22c55e;
    --bg-primary: #f8fafc;
    --bg-card: #ffffff;
    --text-primary: #1e293b;
    --text-secondary: #64748b;
    --border: #e2e8f0;
    --shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1);
    --shadow-lg: 0 10px 15px -3px rgb(0 0 0 / 0.1), 0 4px 6px -4px rgb(0 0 0 / 0.1);
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    background: var(--bg-primary);
    color: var(--text-primary);
    line-height: 1.6;
    min-height: 100vh;
}
.container { max-width: 1400px; margin: 0 auto; padding: 2rem; }
header {
    text-align: center;
    margin-bottom: 2rem;
    padding: 2rem;
    background: linear-gradient(135deg, var(--primary) 0%, var(--primary-dark) 100%);
    border-radius: 16px;
    color: white;
    box-shadow: var(--shadow-lg);
}
header h1 { font-size: 2.25rem; font-weight: 700; margin-bottom: 0.5rem; }
header p { opacity: 0.9; font-size: 1rem; }
.stats-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 1rem;
    margin-bottom: 2rem;
}
.stat-card {
    background: var(--bg-card);
    padding: 1.5rem;
    border-radius: 12px;
    box-shadow: var(--shadow);
    text-align: center;
}
.stat-card .number { font-size: 2rem; font-weight: 700; color: var(--primary); }
.stat-card .label {
    color: var(--text-secondary);
    font-size: 0.875rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}
.stat-card.emphasis { outline: 2px solid var(--primary); }
.notice {
    background: #fff7ed;
    border: 1px solid #fdba74;
    color: #9a3412;
    padding: 0.75rem 1rem;
    border-radius: 10px;
    margin-bottom: 1rem;
}
.lede {
    color: var(--text-secondary);
    margin: 0 0 1rem;
    padding: 0 0.25rem;
}
.controls {
    display: flex;
    flex-wrap: wrap;
    gap: 1rem;
    margin-bottom: 1.5rem;
    padding: 1.5rem;
    background: var(--bg-card);
    border-radius: 12px;
    box-shadow: var(--shadow);
}
.search-box { flex: 1; min-width: 250px; position: relative; }
.search-box input {
    width: 100%;
    padding: 0.75rem 1rem 0.75rem 2.75rem;
    border: 2px solid var(--border);
    border-radius: 8px;
    font-size: 1rem;
}
.search-box input:focus { outline: none; border-color: var(--primary); }
.search-box::before {
    content: "🔍";
    position: absolute;
    left: 1rem;
    top: 50%;
    transform: translateY(-50%);
}
.filter-group { display: flex; gap: 0.5rem; flex-wrap: wrap; }
.filter-btn {
    padding: 0.5rem 1rem;
    border: 2px solid var(--border);
    background: var(--bg-card);
    border-radius: 8px;
    cursor: pointer;
    font-size: 0.875rem;
    font-weight: 500;
}
.filter-btn.active { background: var(--primary); border-color: var(--primary); color: white; }
.section { margin-bottom: 2rem; }
.section-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 1rem 1.5rem;
    background: var(--bg-card);
    border-radius: 12px 12px 0 0;
    border-bottom: 2px solid var(--border);
    cursor: pointer;
    user-select: none;
}
.section-header h2 {
    font-size: 1.25rem;
    font-weight: 600;
    display: flex;
    align-items: center;
    gap: 0.5rem;
}
.section-header .badge {
    background: var(--primary);
    color: white;
    padding: 0.25rem 0.75rem;
    border-radius: 999px;
    font-size: 0.875rem;
    font-weight: 500;
}
.section-header .toggle-icon { font-size: 1.5rem; color: var(--secondary); transition: transform 0.3s; }
.section-header.collapsed .toggle-icon { transform: rotate(-90deg); }
.section-content {
    background: var(--bg-card);
    border-radius: 0 0 12px 12px;
    overflow: hidden;
    box-shadow: var(--shadow);
}
.section-content.collapsed { display: none; }
.subsection { padding: 1rem 1.25rem 0.25rem; }
.subsection h3 { font-size: 1rem; margin-bottom: 0.75rem; }
table { width: 100%; border-collapse: collapse; }
th {
    background: linear-gradient(135deg, #334155 0%, #1e293b 100%);
    color: white;
    padding: 1rem;
    text-align: left;
    font-weight: 600;
    font-size: 0.875rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    cursor: pointer;
    white-space: nowrap;
}
td { padding: 1rem; border-bottom: 1px solid var(--border); vertical-align: middle; }
tr:hover td { background: #f8fafc; }
.product-name { font-weight: 500; max-width: 420px; }
.product-name a { color: var(--text-primary); text-decoration: none; }
.product-name a:hover { color: var(--primary); }
.price { font-weight: 600; font-family: 'SF Mono', Consolas, monospace; }
.price-new { color: var(--success); font-size: 1.1rem; }
.price-old { color: var(--text-secondary); text-decoration: line-through; font-size: 0.9rem; }
.delta { color: #166534; font-weight: 600; }
.discount { display: inline-block; padding: 0.25rem 0.75rem; border-radius: 999px; font-weight: 600; font-size: 0.875rem; }
.discount.high { background: #dcfce7; color: #166534; }
.discount.medium { background: #fef3c7; color: #92400e; }
.discount.low { background: #fee2e2; color: #991b1b; }
.store-badge, .part-badge, .size-badge {
    display: inline-block;
    padding: 0.25rem 0.5rem;
    border-radius: 4px;
    font-size: 0.75rem;
    font-weight: 600;
}
.store-zumiez { background: #fce7f3; color: #be185d; }
.store-skatewarehouse { background: #dbeafe; color: #1d4ed8; }
.store-ccs { background: #d1fae5; color: #059669; }
.store-tactics { background: #fef3c7; color: #d97706; }
.part-badge { background: #f1f5f9; color: var(--text-secondary); font-weight: 500; }
.size-badge { background: #e0e7ff; color: #3730a3; font-size: 0.875rem; }
.alert {
    background: #fef2f2;
    border: 1px solid #fca5a5;
    color: #991b1b;
    padding: 1rem 1.25rem;
    border-radius: 12px;
    margin-bottom: 1.5rem;
}
.alert strong { display: block; font-size: 1.05rem; margin-bottom: 0.35rem; }
.alert p { margin: 0; }
.alert ul { margin: 0.5rem 0 0 1.2rem; }
.atl-badge, .lowest-badge {
    display: inline-block;
    padding: 0.2rem 0.5rem;
    border-radius: 4px;
    font-size: 0.7rem;
    font-weight: 600;
    background: #fef08a;
    color: #854d0e;
    margin-left: 0.35rem;
    vertical-align: middle;
}
.compare-grid { display: flex; flex-direction: column; gap: 0.75rem; padding: 1rem 1.25rem 1.25rem; }
.compare-card { border: 1px solid var(--border); border-radius: 10px; padding: 0.85rem 1rem; }
.compare-label { font-weight: 600; margin-bottom: 0.55rem; }
.compare-offers { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 0.5rem; }
.offer { border: 1px solid var(--border); border-radius: 8px; padding: 0.55rem 0.75rem; background: #fff; }
.offer.cheapest { background: #dcfce7; border-color: #86efac; }
.offer .who { font-size: 0.75rem; font-weight: 700; }
.offer .amt { font-family: 'SF Mono', Consolas, monospace; font-size: 1.05rem; font-weight: 700; }
.offer.cheapest .amt { color: #166534; }
.offer .nm { font-size: 0.75rem; color: var(--text-secondary); margin-top: 0.15rem; }
.offer .nm a { color: inherit; }
.trend-up { color: #dc2626; font-size: 0.75rem; margin-left: 0.25rem; }
.trend-down { color: #16a34a; font-size: 0.75rem; margin-left: 0.25rem; }
.price-history { font-size: 0.7rem; color: var(--text-secondary); margin-top: 0.25rem; }
.change-row.removed td { background: #fef2f2; }
.empty { text-align: center; padding: 1.5rem; color: var(--text-secondary); }
footer { text-align: center; padding: 2rem; color: var(--text-secondary); font-size: 0.875rem; }
@media (max-width: 768px) {
    .container { padding: 1rem; }
    header h1 { font-size: 1.5rem; }
    .controls { flex-direction: column; }
    table { display: block; overflow-x: auto; }
    th, td { padding: 0.75rem; font-size: 0.875rem; }
    .product-name { max-width: 200px; }
}
"""

JS = """
let currentStoreFilter = 'all';
let currentPartFilter = 'all';
let currentSizeFilter = 'all';

function filterProducts() {
    const searchTerm = document.getElementById('searchInput').value.toLowerCase().trim();
    const rows = document.querySelectorAll('#mainTable tbody tr');
    rows.forEach(row => {
        const text = row.textContent.toLowerCase();
        const store = (row.dataset.store || '').toLowerCase();
        const part = (row.dataset.part || '').toLowerCase();
        const size = row.dataset.size || '';
        const matchesSearch = searchTerm === '' || text.includes(searchTerm);
        const matchesStore = currentStoreFilter === 'all' || store === currentStoreFilter.toLowerCase();
        const matchesPart = currentPartFilter === 'all' || part === currentPartFilter.toLowerCase();
        const matchesSize = currentSizeFilter === 'all' || size === currentSizeFilter;
        row.style.display = matchesSearch && matchesStore && matchesPart && matchesSize ? '' : 'none';
    });
}

function setActive(groupId, attr, value) {
    document.querySelectorAll('#' + groupId + ' .filter-btn').forEach(btn => {
        const current = btn.dataset[attr] || '';
        btn.classList.toggle('active', current === value.toLowerCase() || (value === 'all' && current === 'all'));
    });
}

function filterByStore(store) {
    currentStoreFilter = store;
    setActive('storeFilters', 'store', store);
    filterProducts();
}
function filterByPart(part) {
    currentPartFilter = part;
    setActive('partFilters', 'part', part);
    filterProducts();
}
function filterBySize(size) {
    currentSizeFilter = size;
    setActive('sizeFilters', 'size', size);
    filterProducts();
}

function sortTable(tableId, colIndex, isNumeric) {
    const table = document.getElementById(tableId);
    const tbody = table.querySelector('tbody');
    const rows = Array.from(tbody.querySelectorAll('tr'));
    const header = table.querySelectorAll('th')[colIndex];
    const isAsc = header.dataset.sort !== 'asc';
    table.querySelectorAll('th').forEach(th => {
        th.classList.remove('sorted');
        delete th.dataset.sort;
    });
    header.classList.add('sorted');
    header.dataset.sort = isAsc ? 'asc' : 'desc';
    rows.sort((a, b) => {
        let aVal = a.cells[colIndex].textContent.trim();
        let bVal = b.cells[colIndex].textContent.trim();
        if (isNumeric) {
            aVal = parseFloat(aVal.replace(/[$%−,]/g, '').replace('−', '-')) || 0;
            bVal = parseFloat(bVal.replace(/[$%−,]/g, '').replace('−', '-')) || 0;
            return isAsc ? aVal - bVal : bVal - aVal;
        }
        return isAsc ? aVal.localeCompare(bVal) : bVal.localeCompare(aVal);
    });
    rows.forEach(row => tbody.appendChild(row));
}

function toggleSection(header) {
    header.classList.toggle('collapsed');
    header.nextElementSibling.classList.toggle('collapsed');
}
"""


def _filter_buttons(group_id, attr, onclick, values):
    rows = [
        f'<button class="filter-btn active" data-{attr}="all" onclick="{onclick}(\'all\')">All</button>'
    ]
    for value in values:
        safe = escape(str(value))
        rows.append(
            f'<button class="filter-btn" data-{attr}="{escape(str(value).lower(), quote=True)}" '
            f'onclick="{onclick}(\'{escape(str(value), quote=True)}\')">{safe}</button>'
        )
    return f'<div class="filter-group" id="{group_id}">{"".join(rows)}</div>'


class Digest:
    """New listings, meaningful sale-price drops, and successful-scrape removals.

    ``warnings`` are broken-store alerts. They are not part of the catalog
    diff; ``pipeline.decorate_digest`` attaches them, along with all-time
    lows and cross-store groups for the email.
    """

    def __init__(
        self,
        new_items=None,
        drops=None,
        removed=None,
        warnings=None,
        all_time_lows=None,
        cross_store=None,
    ):
        self.new_items = list(new_items or [])
        self.drops = list(drops or [])
        self.removed = list(removed or [])
        self.warnings = list(warnings or [])
        self.all_time_lows = list(all_time_lows or [])
        self.cross_store = list(cross_store or [])


def _collect_warnings(digest):
    try:
        return [warning for warning in (getattr(digest, "warnings", None) or []) if warning]
    except Exception:
        logger.exception("Store warnings could not be read")
        return []


def _collect_lows(products, price_history):
    try:
        lows = [item for item in products if all_time_low_status(item, price_history).get("flagged")]
    except Exception:
        logger.exception("All-time low list failed")
        return []
    order = {"Decks": 0, "Wheels": 1, "Trucks": 2, "Bearings": 3}
    lows.sort(key=lambda item: (order.get(item.get("part"), 9), _display_name(item)))
    return lows


def _collect_groups(products):
    try:
        return cross_store_groups(products)
    except Exception:
        logger.exception("Cross-store comparison failed")
        return []


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


def _atl_section(low_items, price_history):
    if not low_items:
        return []
    rows = [
        '<div class="section" id="atlSection">',
        '<div class="section-header collapsed" onclick="toggleSection(this)">'
        f'<h2>All-time lows <span class="badge">{len(low_items)}</span></h2>'
        '<span class="toggle-icon">▼</span></div>',
        '<div class="section-content collapsed">',
        '<p class="lede">Current sale price equals the lowest price tracked for that listing. '
        "A listing needs at least 3 observations spanning 7 days, so a brand-new deal is not "
        "flagged just because its first price is the only price.</p>",
        '<table id="atlTable"><thead><tr>'
        "<th>Store</th><th>Part</th><th>Product</th><th>Sale price</th><th>Low since</th><th>Observations</th>"
        "</tr></thead><tbody>",
    ]
    for item in low_items:
        status = all_time_low_status(item, price_history)
        store = item.get("store") or "Unknown"
        rows.append(
            "<tr>"
            f'<td><span class="store-badge {_store_class(store)}">{escape(store)}</span></td>'
            f'<td><span class="part-badge">{escape(item.get("part") or "")}</span></td>'
            f'<td class="product-name">{_product_link(item)} {_atl_badge(item, price_history)}</td>'
            f'<td class="price price-new">{_money(item.get("price_new"))}</td>'
            f'<td>{escape(status.get("low_date") or "")}</td>'
            f'<td>{status.get("observations") or ""}</td>'
            "</tr>"
        )
    rows.append("</tbody></table></div></div>")
    return rows


def _compare_section(groups):
    if not groups:
        return []
    rows = [
        '<div class="section" id="compareSection">',
        '<div class="section-header" onclick="toggleSection(this)">'
        f'<h2>Across stores <span class="badge">{len(groups)}</span></h2>'
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
                name_html = f'<a href="{escape(url, quote=True)}" target="_blank" rel="noopener">{name}</a>'
            else:
                name_html = name
            offers.append(
                f'<div class="{klass}" data-store="{escape(store, quote=True)}">'
                f'<div class="who"><span class="store-badge {_store_class(store)}">{escape(store)}</span></div>'
                f'<div class="amt">{_money(price)}</div>'
                f'<div class="nm">{name_html}</div>'
                "</div>"
            )
        rows.append(
            '<div class="compare-card">'
            f'<div class="compare-label">{escape(group.get("label") or "")} '
            f'<span class="part-badge">{escape(group.get("part") or "")}</span></div>'
            f'<div class="compare-offers">{"".join(offers)}</div>'
            "</div>"
        )
    rows.append("</div></div></div>")
    return rows


def build_digest(changes, failed_keys=None):
    """Split a catalog diff the same way the HTML report does.

    New rows and price drops already passed ``passes_filters`` and the
    meaningful-drop rule inside ``compare_catalogs`` / ``_split_changes``.
    Removals are included only for keys that scraped successfully.
    """
    new_items, drops, removed = _split_changes(changes, failed_keys)
    return Digest(new_items, drops, removed)


def build_report_html(data, changes, price_history=None, failed_keys=None, generated_at=None, digest=None):
    price_history = price_history or {}
    failed_keys = list(failed_keys or [])
    products = _visible_products(data)
    if digest is None:
        digest = build_digest(changes, failed_keys)
    new_items = digest.new_items
    drops = digest.drops
    removed = digest.removed

    if generated_at is None:
        generated_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    current_date = generated_at[:10]

    store_counts = {}
    part_counts = {}
    sizes = set()
    for item in products:
        store = item.get("store") or "Unknown"
        part = item.get("part") or "Unknown"
        store_counts[store] = store_counts.get(store, 0) + 1
        part_counts[part] = part_counts.get(part, 0) + 1
        if part == "Decks":
            size = _deck_size_value(item)
            if size:
                sizes.add(size)
    all_sizes = sorted(sizes, key=lambda value: float(value))
    warnings = _collect_warnings(digest)
    low_items = _collect_lows(products, price_history)
    groups = _collect_groups(products)

    chunks = [
        "<!DOCTYPE html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="UTF-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1.0">',
        f"<title>Skateboard Sale Tracker | {escape(current_date)}</title>",
        '<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">',
        f"<style>{CSS}</style>",
        "</head>",
        "<body>",
        '<div class="container">',
        "<header>",
        "<h1>Skateboard Sale Tracker</h1>",
        f"<p>Last updated: {escape(generated_at)}</p>",
        "</header>",
    ]
    alert = _alert_html(warnings)
    if alert:
        chunks.append(alert)
    chunks.append('<div class="stats-grid">')
    chunks.append(
        f'<div class="stat-card emphasis"><div class="number">{len(new_items)}</div><div class="label">New deals</div></div>'
    )
    chunks.append(
        f'<div class="stat-card emphasis"><div class="number">{len(drops)}</div><div class="label">Price drops</div></div>'
    )
    if low_items:
        chunks.append(
            f'<div class="stat-card"><div class="number">{len(low_items)}</div><div class="label">All-time lows</div></div>'
        )
    chunks.append(
        f'<div class="stat-card"><div class="number">{len(products)}</div><div class="label">Tracked deals</div></div>'
    )
    for store, count in sorted(store_counts.items()):
        chunks.append(
            f'<div class="stat-card"><div class="number">{count}</div><div class="label">{escape(store)}</div></div>'
        )
    chunks.append("</div>")

    if failed_keys:
        listed = ", ".join(escape(key) for key in failed_keys)
        chunks.append(
            f'<div class="notice">Scrape failed for {listed}. '
            "Previous listings for those categories were kept, and removals are hidden.</div>"
        )

    chunks.append('<div class="section">')
    chunks.append(
        '<div class="section-header" onclick="toggleSection(this)">'
        f'<h2>Digest <span class="badge">{len(new_items) + len(drops)}</span></h2>'
        '<span class="toggle-icon">▼</span></div>'
    )
    chunks.append('<div class="section-content">')
    chunks.append(
        '<p class="lede">New listings and sale-price drops of at least $2 or 5% '
        "versus the previous tracked sale price. This is not a discount off MSRP.</p>"
    )

    chunks.append('<div class="subsection"><h3>New</h3>')
    if new_items:
        chunks.append(
            '<table id="newTable"><thead><tr>'
            "<th>Store</th><th>Part</th><th>Size</th><th>Product</th>"
            "<th>Sale price</th><th>Original</th><th>Off original</th>"
            "</tr></thead><tbody>"
        )
        for item in new_items:
            size_html, _size = _size_cell(item)
            percent = calculate_percent_off(item.get("price_new"), item.get("price_old"))
            discount_class = _discount_class(item.get("price_new"), item.get("price_old"))
            store = item.get("store") or "Unknown"
            chunks.append(
                "<tr>"
                f'<td><span class="store-badge {_store_class(store)}">{escape(store)}</span></td>'
                f'<td><span class="part-badge">{escape(item.get("part") or "")}</span></td>'
                f"<td>{size_html}</td>"
                f'<td class="product-name">{_product_link(item)} {_atl_badge(item, price_history)}</td>'
                f'<td class="price price-new">{_money(item.get("price_new"))}</td>'
                f'<td class="price price-old">{_money(item.get("price_old")) if item.get("price_old") else "N/A"}</td>'
                f'<td><span class="discount {discount_class}">{escape(percent)}</span></td>'
                "</tr>"
            )
        chunks.append("</tbody></table>")
    else:
        chunks.append('<p class="empty">No new deals.</p>')
    chunks.append("</div>")

    chunks.append('<div class="subsection"><h3>Price drops</h3>')
    if drops:
        chunks.append(
            '<table id="dropTable"><thead><tr>'
            "<th>Store</th><th>Part</th><th>Product</th>"
            "<th>Prior sale</th><th>Now</th><th>Change vs prior sale</th>"
            "</tr></thead><tbody>"
        )
        for change in drops:
            item = change.get("item") or {}
            store = item.get("store") or "Unknown"
            part = item.get("part") or ""
            link_item = {
                "name": item.get("name") or change.get("name"),
                "url": item.get("url") or change.get("url"),
                "price_new": item.get("price_new", change.get("new")),
            }
            chunks.append(
                "<tr>"
                f'<td><span class="store-badge {_store_class(store)}">{escape(store)}</span></td>'
                f'<td><span class="part-badge">{escape(part)}</span></td>'
                f'<td class="product-name">{_product_link(link_item)} {_atl_badge(link_item, price_history)}</td>'
                f'<td class="price price-old">{_money(change.get("old"))}</td>'
                f'<td class="price price-new">{_money(change.get("new"))}</td>'
                f'<td class="delta">{escape(_drop_label(change))}</td>'
                "</tr>"
            )
        chunks.append("</tbody></table>")
    else:
        chunks.append('<p class="empty">No meaningful price drops.</p>')
    chunks.append("</div></div></div>")

    chunks.extend(_atl_section(low_items, price_history))
    chunks.extend(_compare_section(groups))

    chunks.append(
        '<div class="controls">'
        '<div class="search-box"><input type="text" id="searchInput" placeholder="Search all deals..." onkeyup="filterProducts()"></div>'
        + _filter_buttons("storeFilters", "store", "filterByStore", sorted(store_counts))
        + _filter_buttons("partFilters", "part", "filterByPart", sorted(part_counts))
        + _filter_buttons("sizeFilters", "size", "filterBySize", all_sizes)
        + "</div>"
    )

    chunks.append('<div class="section">')
    chunks.append(
        '<div class="section-header collapsed" onclick="toggleSection(this)">'
        f'<h2>All Deals <span class="badge">{len(products)}</span></h2>'
        '<span class="toggle-icon">▼</span></div>'
    )
    chunks.append('<div class="section-content collapsed">')
    chunks.append(
        '<table id="mainTable"><thead><tr>'
        '<th onclick="sortTable(\'mainTable\', 0, false)">Store</th>'
        '<th onclick="sortTable(\'mainTable\', 1, false)">Part</th>'
        '<th onclick="sortTable(\'mainTable\', 2, true)">Size</th>'
        '<th onclick="sortTable(\'mainTable\', 3, false)">Product</th>'
        '<th onclick="sortTable(\'mainTable\', 4, true)">Sale price</th>'
        '<th onclick="sortTable(\'mainTable\', 5, true)">Original</th>'
        '<th onclick="sortTable(\'mainTable\', 6, true)">Off original</th>'
        "</tr></thead><tbody>"
    )
    for item in products:
        size_html, size_value = _size_cell(item)
        percent = calculate_percent_off(item.get("price_new"), item.get("price_old"))
        discount_class = _discount_class(item.get("price_new"), item.get("price_old"))
        store = item.get("store") or "Unknown"
        extras = _price_extras(item, price_history)
        chunks.append(
            f'<tr data-store="{escape(store, quote=True)}" data-part="{escape(item.get("part") or "", quote=True)}" data-size="{escape(size_value, quote=True)}">'
            f'<td><span class="store-badge {_store_class(store)}">{escape(store)}</span></td>'
            f'<td><span class="part-badge">{escape(item.get("part") or "")}</span></td>'
            f"<td>{size_html}</td>"
            f'<td class="product-name">{_product_link(item)}</td>'
            f'<td class="price price-new">{_money(item.get("price_new"))}{extras}</td>'
            f'<td class="price price-old">{_money(item.get("price_old")) if item.get("price_old") else "N/A"}</td>'
            f'<td><span class="discount {discount_class}">{escape(percent)}</span></td>'
            "</tr>"
        )
    chunks.append("</tbody></table></div></div>")

    if removed:
        chunks.append('<div class="section">')
        chunks.append(
            '<div class="section-header collapsed" onclick="toggleSection(this)">'
            f'<h2>Removed <span class="badge">{len(removed)}</span></h2>'
            '<span class="toggle-icon">▼</span></div>'
        )
        chunks.append(
            '<div class="section-content collapsed">'
            '<p class="lede">Only shown when that store and part scraped successfully.</p>'
            '<table id="removedTable"><thead><tr>'
            "<th>Store</th><th>Part</th><th>Product</th><th>Last sale price</th>"
            "</tr></thead><tbody>"
        )
        for _site, item in removed:
            store = item.get("store") or "Unknown"
            chunks.append(
                '<tr class="change-row removed">'
                f'<td><span class="store-badge {_store_class(store)}">{escape(store)}</span></td>'
                f'<td><span class="part-badge">{escape(item.get("part") or "")}</span></td>'
                f'<td class="product-name">{escape(_display_name(item))}</td>'
                f'<td class="price">{_money(item.get("price_new"))}</td>'
                "</tr>"
            )
        chunks.append("</tbody></table></div></div>")

    chunks.append(
        "<footer><p>Zumiez, Skate Warehouse, CCS, and Tactics. "
        "Decks are kept at ≥10% off for known street brands and ≥15% off otherwise, "
        "widths about 7.5–9.5\". Wheels, trucks, and bearings use brand allowlists. "
        "All-time low is the lowest tracked sale price after at least 3 observations spanning 7 days. "
        "Across stores matches brand, model, and size.</p></footer>"
    )
    chunks.append("</div>")
    chunks.append(f"<script>{JS}</script>")
    chunks.append("</body></html>")
    return "\n".join(chunks)
