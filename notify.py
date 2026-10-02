"""Email the skate sale digest over SMTP.

Sends when the digest has at least one new item, a meaningful price drop,
or a broken-store warning (a store/part empty or failed two runs in a row).
Removals alone do not send mail. A warning sends even when there are no deals.
Settings come from the environment. Missing settings are logged and skipped.
SMTP errors are logged and do not propagate, so a mail failure cannot fail
the scrape.

Dry run (EMAIL_DRY_RUN=1, or --dry-run / --email-dry-run) writes the HTML
message to a local file instead of connecting.
"""

import argparse
import datetime
import json
import logging
import os
import smtplib
import ssl
from email.message import EmailMessage
from html import escape

from filters import calculate_percent_off, item_passes_filters, normalize_product_name, normalize_url
from health import warning_text
from report import Digest
from site_sales import activity_line

logger = logging.getLogger("notify")

# GitHub Pages serves the repo root from main:
# https://pchoward.github.io/salesscraper2/sale_items_chart.html
DEFAULT_REPORT_URL = "https://pchoward.github.io/salesscraper2/sale_items_chart.html"
PART_ORDER = ("Decks", "Wheels", "Trucks", "Bearings")
PREVIEW_PATH = "email_preview.html"
SAMPLE_BANNER = (
    "Sample preview, not a live alert. The new items and price drops below are "
    "synthetic, using products from the current catalog. Nothing was sent."
)

_TRUTHY = {"1", "true", "yes", "on"}
_STORE_COLORS = {
    "zumiez": ("#fce7f3", "#9d174d"),
    "skatewarehouse": ("#dbeafe", "#1e40af"),
    "ccs": ("#d1fae5", "#047857"),
    "tactics": ("#fef3c7", "#b45309"),
    "skatedeluxe": ("#ede9fe", "#6d28d9"),
    "muirskate": ("#ccfbf1", "#0f766e"),
}


class SmtpConfig:
    def __init__(self, host, port, user, password, sender, recipients, security, report_url, dry_run, missing):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.sender = sender
        self.recipients = recipients
        self.security = security
        self.report_url = report_url
        self.dry_run = dry_run
        self.missing = missing


def should_send(digest):
    """True when the email has something to say.

    Removals do not count. A broken-store warning does, even with no deals.
    """
    if digest is None:
        return False
    if digest.new_items or digest.drops:
        return True
    if getattr(digest, "warnings", None):
        return True
    return bool(getattr(digest, "watch_alerts", None))


def _truthy(value):
    return str(value or "").strip().lower() in _TRUTHY


def _clean(value):
    return str(value or "").strip()


def load_smtp_config(env=None):
    """Read SMTP settings. ``missing`` lists required names that are unset."""
    source = os.environ if env is None else env
    host = _clean(source.get("SMTP_HOST"))
    user = _clean(source.get("SMTP_USER"))
    password = source.get("SMTP_PASSWORD")
    password = "" if password is None else str(password).strip()
    sender = _clean(source.get("EMAIL_FROM")) or user
    recipients = [part.strip() for part in str(source.get("EMAIL_TO") or "").split(",") if part.strip()]
    port_raw = _clean(source.get("SMTP_PORT")) or "587"
    security = (_clean(source.get("SMTP_SECURITY")) or "starttls").lower()
    report_url = _clean(source.get("REPORT_URL")) or DEFAULT_REPORT_URL
    dry_run = _truthy(source.get("EMAIL_DRY_RUN"))

    missing = []
    port = 587
    try:
        port = int(port_raw)
    except ValueError:
        missing.append("SMTP_PORT")
    if not host:
        missing.append("SMTP_HOST")
    if not user:
        missing.append("SMTP_USER")
    if not password:
        missing.append("SMTP_PASSWORD")
    if not sender:
        missing.append("EMAIL_FROM")
    if not recipients:
        missing.append("EMAIL_TO")
    if security not in {"starttls", "ssl"}:
        missing.append("SMTP_SECURITY")

    return SmtpConfig(
        host=host,
        port=port,
        user=user,
        password=password,
        sender=sender,
        recipients=recipients,
        security=security,
        report_url=report_url,
        dry_run=dry_run,
        missing=missing,
    )


def _as_date(when):
    if when is None:
        when = datetime.datetime.now()
    if isinstance(when, datetime.datetime):
        return when.date()
    return when


def _short_date(when):
    day = _as_date(when)
    return f"{day.strftime('%b')} {day.day}"


def _long_date(when):
    day = _as_date(when)
    return f"{day.strftime('%B')} {day.day}, {day.year}"


def _warnings(digest):
    return list(getattr(digest, "warnings", None) or [])


def _watch_alerts(digest):
    alerts = getattr(digest, "watch_alerts", None)
    if not alerts:
        return []
    return list(alerts)


def summary_counts(digest):
    new_count = len(digest.new_items)
    drop_count = len(digest.drops)
    drop_word = "price drop" if drop_count == 1 else "price drops"
    base = f"{new_count} new, {drop_count} {drop_word}"
    warnings = _warnings(digest)
    alerts = _watch_alerts(digest)
    if not warnings and not alerts:
        return base
    if warnings:
        word = "store warning" if len(warnings) == 1 else "store warnings"
        if new_count == 0 and drop_count == 0:
            base = f"{len(warnings)} {word}"
        else:
            base = f"{base}, {len(warnings)} {word}"
    elif new_count == 0 and drop_count == 0 and alerts:
        word = "watchlist alert" if len(alerts) == 1 else "watchlist alerts"
        return f"{len(alerts)} {word}"
    if alerts and not (new_count == 0 and drop_count == 0 and not warnings):
        word = "watchlist alert" if len(alerts) == 1 else "watchlist alerts"
        base = f"{base}, {len(alerts)} {word}"
    return base


def subject_line(digest, when=None):
    return f"Skate deals: {summary_counts(digest)} ({_short_date(when)})"


def _money(value, currency=None):
    try:
        amount = float(value)
    except (TypeError, ValueError):
        return "N/A"
    symbol = "€" if str(currency or "USD").upper() == "EUR" else "$"
    return f"{symbol}{amount:.2f}"


def _display_name(item):
    return normalize_product_name((item or {}).get("name", "")) or "Untitled"


def _product_url(item):
    return normalize_url((item or {}).get("url", ""))


def _store_name(item):
    return (item or {}).get("store") or "Unknown"


def _part_name(item):
    part = ((item or {}).get("part") or "Other").strip()
    return part or "Other"


def _drop_bits(change):
    delta = change.get("delta")
    percent = change.get("percent_vs_prior")
    old_price = change.get("old")
    new_price = change.get("new")
    currency = ((change or {}).get("item") or {}).get("currency")
    symbol = "€" if str(currency or "USD").upper() == "EUR" else "$"
    if delta is None or percent is None:
        try:
            old_amount = float(old_price)
            new_amount = float(new_price)
        except (TypeError, ValueError):
            return _money(old_price, currency), "N/A"
        if old_amount <= 0:
            return _money(old_price, currency), "N/A"
        delta = old_amount - new_amount
        percent = (delta / old_amount) * 100
    change_label = f"−{symbol}{float(delta):.2f} (−{float(percent):.1f}% vs prior sale)"
    return _money(old_price, currency), change_label


def _drop_part(change):
    item = change.get("item") or {}
    if item.get("part"):
        return _part_name(item)
    if change.get("part"):
        return _part_name({"part": change.get("part")})
    return "Other"


def iter_sections(digest):
    """Yield ``(part, new_items, drops)`` with the catalog part order first."""
    grouped = {}
    for item in digest.new_items:
        grouped.setdefault(_part_name(item), {"new": [], "drops": []})["new"].append(item)
    for change in digest.drops:
        grouped.setdefault(_drop_part(change), {"new": [], "drops": []})["drops"].append(change)
    ordered = [part for part in PART_ORDER if part in grouped]
    ordered.extend(part for part in grouped if part not in ordered)
    for part in ordered:
        yield part, grouped[part]["new"], grouped[part]["drops"]


def _section_summary(new_items, drops):
    bits = []
    if new_items:
        bits.append(f"{len(new_items)} new")
    if drops:
        word = "price drop" if len(drops) == 1 else "price drops"
        bits.append(f"{len(drops)} {word}")
    return " · ".join(bits)


def _is_atl(item, change=None):
    if isinstance(change, dict) and change.get("at_all_time_low"):
        return True
    return bool(isinstance(item, dict) and item.get("at_all_time_low"))


def _all_time_low_line(digest):
    lows = list(getattr(digest, "all_time_lows", None) or [])
    count = len(lows)
    if count <= 0:
        return ""
    if count == 1:
        return "1 tracked deal is at an all-time low. It is marked on the full report."
    return f"{count} tracked deals are at an all-time low. They are marked on the full report."


def _email_cross_store(digest):
    """Groups where the cheapest store is at least $2 or 5% under the highest."""
    picked = []
    for group in getattr(digest, "cross_store", None) or []:
        prices = []
        for offer in group.get("offers") or []:
            try:
                prices.append(float(offer.get("price")))
            except (TypeError, ValueError):
                continue
        if len(prices) < 2:
            continue
        low = min(prices)
        high = max(prices)
        gap = high - low
        if high <= 0 or (gap < 2 and gap / high < 0.05):
            continue
        picked.append((gap, group))
    picked.sort(key=lambda pair: pair[0], reverse=True)
    return [group for _gap, group in picked[:8]]


def _plain_cross_store(group):
    lines = [group.get("label") or "Same product"]
    cheapest = group.get("cheapest_price")
    for offer in group.get("offers") or []:
        price = offer.get("price")
        mark = ""
        try:
            if cheapest is not None and abs(float(price) - float(cheapest)) < 0.001:
                mark = " (lowest)"
        except (TypeError, ValueError):
            mark = ""
        lines.append(f"- {offer.get('store') or 'Unknown'}: {_money(price, offer.get('currency'))}{mark}")
        if offer.get("url"):
            lines.append(f"  {offer['url']}")
    lines.append("")
    return lines


def _html_warnings(digest):
    warnings = _warnings(digest)
    if not warnings:
        return ""
    items = []
    for warning in warnings:
        text = warning_text(warning) if isinstance(warning, dict) else str(warning)
        items.append(f"<li>{escape(text)}</li>")
    return (
        '<tr><td bgcolor="#fef2f2" style="background:#fef2f2;padding:16px 24px;'
        'font-family:Arial,Helvetica,sans-serif;border-bottom:1px solid #fca5a5;">'
        '<p style="margin:0;font-size:15px;font-weight:700;color:#991b1b;">Store check failed</p>'
        '<p style="margin:6px 0 0;font-size:13px;line-height:1.5;color:#7f1d1d;">'
        "These categories usually have sale items. The last two runs came back empty or failed. "
        "A single empty run does not send this warning.</p>"
        '<ul style="margin:8px 0 0;padding-left:18px;color:#7f1d1d;font-size:13px;line-height:1.5;">'
        f"{''.join(items)}</ul></td></tr>"
    )


def _html_low_note(digest):
    text = _all_time_low_line(digest)
    if not text:
        return ""
    return (
        '<tr><td style="padding:4px 24px 0;font-family:Arial,Helvetica,sans-serif;font-size:13px;'
        'line-height:1.5;color:#854d0e;">'
        f"{escape(text)}</td></tr>"
    )


def _html_cross_store(digest):
    groups = _email_cross_store(digest)
    if not groups:
        return ""
    rows = [
        '<tr><td bgcolor="#0f172a" style="background:#0f172a;padding:10px 20px;'
        'font-family:Arial,Helvetica,sans-serif;">'
        '<span data-section="across-stores" style="color:#ffffff;font-size:14px;font-weight:700;'
        'letter-spacing:0.04em;">Across stores</span>'
        '<span style="color:#94a3b8;font-size:12px;">&nbsp;&nbsp;Same product, lower price</span>'
        "</td></tr>",
        '<tr><td style="padding:8px 20px 0;font-family:Arial,Helvetica,sans-serif;font-size:12px;'
        'line-height:1.4;color:#64748b;">Shown when the cheapest store is at least $2 or 5% under '
        "the highest. The lowest price is marked.</td></tr>",
    ]
    for group in groups:
        offers = []
        cheapest = group.get("cheapest_price")
        for offer in group.get("offers") or []:
            price = offer.get("price")
            try:
                is_low = cheapest is not None and abs(float(price) - float(cheapest)) < 0.001
            except (TypeError, ValueError):
                is_low = False
            weight = "700" if is_low else "400"
            color = "#166534" if is_low else "#0f172a"
            mark = " · lowest" if is_low else ""
            url = offer.get("url") or ""
            store = escape(offer.get("store") or "Unknown")
            amount = escape(_money(price, offer.get("currency")) + mark)
            if url:
                amount = f'<a href="{escape(url, quote=True)}" style="color:{color};text-decoration:underline;">{amount}</a>'
            offers.append(
                f'<span style="display:inline-block;margin:0 10px 6px 0;font-size:13px;font-weight:{weight};color:{color};">'
                f"{store} {amount}</span>"
            )
        rows.append(
            '<tr><td style="padding:8px 20px 0;font-family:Arial,Helvetica,sans-serif;">'
            f'<div style="font-size:14px;font-weight:700;color:#0f172a;">{escape(group.get("label") or "")}</div>'
            f'<div style="margin-top:4px;">{"".join(offers)}</div></td></tr>'
        )
    rows.append('<tr><td style="height:16px;font-size:0;line-height:0;">&nbsp;</td></tr>')
    return "\n".join(rows)


def _sale_rows(digest):
    rows = getattr(digest, "site_sales", None)
    if not rows:
        return []
    return [row for row in rows if isinstance(row, dict)]


def _hit_item(hit):
    if not isinstance(hit, dict):
        return {}
    item = hit.get("item")
    return item if isinstance(item, dict) else {}


def _plain_watch(digest):
    hits = getattr(digest, "watch_hits", None)
    alerts = _watch_alerts(digest)
    if hits is None and not alerts:
        return []
    lines = ["WATCHING"]
    if alerts:
        lines.append("Watchlist alerts are listed first.")
        for hit in alerts:
            item = _hit_item(hit)
            reasons = ", ".join(hit.get("reasons") or [])
            note = hit.get("note") or ""
            lines.append(f"- {_store_name(item)}: {_display_name(item)}")
            url = _product_url(item)
            if url:
                lines.append(f"  {url}")
            bits = [reasons]
            if note:
                bits.append(note)
            lines.append("  " + " · ".join(bit for bit in bits if bit))
    else:
        lines.append("No watchlist alerts today.")
    quiet = [hit for hit in (hits or []) if not hit.get("reasons")]
    if quiet:
        lines.append("Still on sale")
        for hit in quiet:
            item = _hit_item(hit)
            note = hit.get("note") or ""
            extra = f" · {note}" if note else ""
            lines.append(
                f"- {_store_name(item)}: {_display_name(item)} · {_money(item.get('price_new'), item.get('currency'))}{extra}"
            )
    lines.append("")
    return lines


def _sale_banners(digest):
    banners = getattr(digest, "sale_banners", None) or []
    return [str(banner) for banner in banners if banner]


def _plain_sales(digest):
    rows = _sale_rows(digest)
    banners = _sale_banners(digest)
    if not rows and not banners:
        return []
    lines = ["RETAILER ACTIVITY"]
    for banner in banners:
        lines.append(banner)
    for row in rows:
        lines.append(f"- {activity_line(row)}")
    lines.append("")
    return lines


def _html_watch(digest):
    hits = getattr(digest, "watch_hits", None)
    alerts = _watch_alerts(digest)
    if hits is None and not alerts:
        return ""
    rows = [
        '<tr><td bgcolor="#451a03" style="background:#451a03;padding:10px 20px;'
        'font-family:Arial,Helvetica,sans-serif;">'
        '<span data-section="watching" style="color:#ffffff;font-size:14px;font-weight:700;'
        'letter-spacing:0.04em;">Watching</span>'
        '<span style="color:#fdba74;font-size:12px;">&nbsp;&nbsp;From watchlist.yaml</span>'
        "</td></tr>"
    ]
    if not alerts and not hits:
        rows.append(
            '<tr><td style="padding:12px 20px 0;font-family:Arial,Helvetica,sans-serif;'
            'font-size:13px;color:#78350f;">No watchlist alerts today.</td></tr>'
        )
    for hit in alerts:
        item = _hit_item(hit)
        reasons = ", ".join(hit.get("reasons") or [])
        note = hit.get("note") or ""
        extra = (
            '<p style="margin:6px 0 0;font-size:13px;line-height:1.4;color:#9a3412;">'
            f"{escape(reasons)}"
            + (f" · {escape(note)}" if note else "")
            + "</p>"
        )
        rows.append(
            _html_card(
                _store_name(item),
                "Watch",
                "#ffedd5",
                "#9a3412",
                _product_link(_display_name(item), _product_url(item)),
                _price_line(
                    item.get("price_new"),
                    _money(item.get("price_old"), item.get("currency")) if item.get("price_old") else "N/A",
                    calculate_percent_off(item.get("price_new"), item.get("price_old")),
                    item.get("currency"),
                ),
                extra,
            )
        )
    for hit in hits or []:
        if hit.get("reasons"):
            continue
        item = _hit_item(hit)
        note = hit.get("note") or "On sale"
        extra = (
            '<p style="margin:6px 0 0;font-size:13px;line-height:1.4;color:#78350f;">'
            f"On sale · {escape(note)}</p>"
        )
        rows.append(
            _html_card(
                _store_name(item),
                "Watch",
                "#ffedd5",
                "#9a3412",
                _product_link(_display_name(item), _product_url(item)),
                _price_line(
                    item.get("price_new"),
                    _money(item.get("price_old"), item.get("currency")) if item.get("price_old") else "N/A",
                    calculate_percent_off(item.get("price_new"), item.get("price_old")),
                    item.get("currency"),
                ),
                extra,
            )
        )
    rows.append('<tr><td style="height:16px;font-size:0;line-height:0;">&nbsp;</td></tr>')
    return "\n".join(rows)


def _html_sales(digest):
    rows = _sale_rows(digest)
    banners = _sale_banners(digest)
    if not rows and not banners:
        return ""
    blocks = []
    for banner in banners:
        blocks.append(
            '<p style="margin:0 0 8px;padding:10px 12px;background:#fff7ed;border:1px solid #fdba74;'
            'border-radius:8px;color:#9a3412;font-size:14px;font-weight:700;line-height:1.4;">'
            f"{escape(banner)}</p>"
        )
    if rows:
        items = "".join(f"<li>{escape(activity_line(row))}</li>" for row in rows)
        blocks.append(
            '<p style="margin:0;font-size:13px;font-weight:700;color:#0f172a;">Retailer activity</p>'
            '<ul style="margin:6px 0 0;padding-left:18px;color:#334155;font-size:13px;line-height:1.5;">'
            f"{items}</ul>"
        )
    return (
        '<tr><td style="padding:4px 24px 8px;font-family:Arial,Helvetica,sans-serif;">'
        + "".join(blocks)
        + "</td></tr>"
    )


def render_plain(digest, report_url, when=None, banner=None):
    lines = [
        f"Skate deals — {_long_date(when)}",
        summary_counts(digest),
        "",
    ]
    if banner:
        lines.extend([banner, ""])
    warnings = _warnings(digest)
    if warnings:
        lines.append("STORE CHECK FAILED")
        lines.append(
            "These categories usually have sale items. The last two runs came back empty or failed."
        )
        for warning in warnings:
            text = warning_text(warning) if isinstance(warning, dict) else str(warning)
            lines.append(f"- {text}")
        lines.append("")
    lines.extend([f"Full report: {report_url}", ""])
    lines.extend(_plain_watch(digest))
    lines.extend(_plain_sales(digest))
    low_line = _all_time_low_line(digest)
    if low_line:
        lines.extend([low_line, ""])
    for part, new_items, drops in iter_sections(digest):
        lines.append(part.upper())
        if new_items:
            lines.append("New")
            for item in new_items:
                lines.extend(_plain_new(item))
        if drops:
            lines.append("Price drops")
            for change in drops:
                lines.extend(_plain_drop(change))
        lines.append("")
    cross_store = _email_cross_store(digest)
    if cross_store:
        lines.append("ACROSS STORES")
        lines.append("Same product, lower price at another store.")
        for group in cross_store:
            lines.extend(_plain_cross_store(group))
        lines.append("")
    lines.append(
        "Price drops are at least $2 or 5% versus the previous tracked sale price, not versus the original price."
    )
    lines.append("Removals are listed on the full report only, and only after a successful scrape.")
    return "\n".join(lines).rstrip() + "\n"


def _off_label(percent):
    if not percent or percent == "N/A":
        return "N/A"
    return f"{percent} off"


def _plain_new(item):
    name = _display_name(item)
    url = _product_url(item)
    percent = calculate_percent_off(item.get("price_new"), item.get("price_old"))
    currency = item.get("currency")
    original = _money(item.get("price_old"), currency) if item.get("price_old") else "N/A"
    rows = [
        f"- {_store_name(item)}: {name}",
    ]
    if url:
        rows.append(f"  {url}")
    low = " · all-time low" if _is_atl(item) else ""
    rows.append(f"  Sale {_money(item.get('price_new'), currency)} · Original {original} · {_off_label(percent)}{low}")
    return rows


def _plain_drop(change):
    item = change.get("item") or {}
    name = _display_name(item) if item.get("name") else (change.get("name") or "Untitled")
    url = _product_url(item) or normalize_url(change.get("url", ""))
    sale = item.get("price_new", change.get("new"))
    original = item.get("price_old")
    currency = item.get("currency")
    percent = calculate_percent_off(sale, original)
    prior, change_label = _drop_bits(change)
    rows = [f"- {_store_name(item)}: {name}"]
    if url:
        rows.append(f"  {url}")
    low = " · all-time low" if _is_atl(item, change) else ""
    rows.append(f"  Sale {_money(sale, currency)} · Prior sale {prior} · {change_label}{low}")
    rows.append(f"  Original {_money(original, currency) if original else 'N/A'} · {_off_label(percent)}")
    return rows


def render_html(digest, report_url, when=None, banner=None):
    summary = summary_counts(digest)
    title = subject_line(digest, when)
    safe_report = escape(report_url, quote=True)
    chunks = [
        "<!DOCTYPE html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1.0">',
        f"<title>{escape(title)}</title>",
        "</head>",
        '<body style="margin:0;padding:0;background:#f1f5f9;">',
        f'<div style="display:none;max-height:0;overflow:hidden;mso-hide:all;">{escape(summary)}. View the full report.</div>',
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" bgcolor="#f1f5f9" style="background:#f1f5f9;margin:0;padding:0;">',
        '<tr><td align="center" style="padding:24px 12px;">',
        '<table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0" bgcolor="#ffffff" style="width:600px;max-width:600px;background:#ffffff;border-radius:12px;overflow:hidden;">',
        _html_header(when, summary),
    ]
    if banner:
        chunks.append(
            '<tr><td bgcolor="#fff7ed" style="background:#fff7ed;color:#9a3412;padding:12px 24px;'
            'font-family:Arial,Helvetica,sans-serif;font-size:13px;line-height:1.5;border-bottom:1px solid #fdba74;">'
            f"{escape(banner)}</td></tr>"
        )
    warning_row = _html_warnings(digest)
    if warning_row:
        chunks.append(warning_row)
    chunks.append(_html_report_link(safe_report))
    watch_row = _html_watch(digest)
    if watch_row:
        chunks.append(watch_row)
    sales_row = _html_sales(digest)
    if sales_row:
        chunks.append(sales_row)
    low_note = _html_low_note(digest)
    if low_note:
        chunks.append(low_note)
    for part, new_items, drops in iter_sections(digest):
        chunks.append(_html_part(part, new_items, drops))
    cross_row = _html_cross_store(digest)
    if cross_row:
        chunks.append(cross_row)
    chunks.append(_html_footer(safe_report))
    chunks.extend(["</table>", "</td></tr>", "</table>", "</body>", "</html>"])
    return "\n".join(chunks)


def _html_header(when, summary):
    return (
        '<tr><td bgcolor="#1d4ed8" style="background:#1d4ed8;padding:28px 24px;'
        'font-family:Arial,Helvetica,sans-serif;">'
        '<p style="margin:0;font-size:12px;letter-spacing:0.08em;text-transform:uppercase;color:#dbeafe;">'
        "Skateboard sale tracker</p>"
        '<h1 style="margin:8px 0 0;font-size:26px;line-height:1.2;font-weight:700;color:#ffffff;">Skate deals</h1>'
        f'<p style="margin:8px 0 0;font-size:15px;line-height:1.4;color:#dbeafe;">{escape(_long_date(when))}'
        f" · {escape(summary)}</p>"
        "</td></tr>"
    )


def _html_report_link(safe_report):
    return (
        '<tr><td style="padding:20px 24px 8px;font-family:Arial,Helvetica,sans-serif;">'
        f'<a href="{safe_report}" style="display:inline-block;background:#1d4ed8;color:#ffffff;'
        'text-decoration:none;font-weight:700;font-size:14px;line-height:1;padding:12px 18px;border-radius:6px;">'
        "View full report</a>"
        f'<p style="margin:10px 0 0;font-size:12px;line-height:1.4;color:#64748b;">'
        f'<a href="{safe_report}" style="color:#1d4ed8;text-decoration:underline;">{safe_report}</a></p>'
        "</td></tr>"
    )


def _html_part(part, new_items, drops):
    summary = _section_summary(new_items, drops)
    rows = [
        '<tr><td bgcolor="#0f172a" style="background:#0f172a;padding:10px 20px;'
        'font-family:Arial,Helvetica,sans-serif;">'
        f'<span data-part="{escape(part, quote=True)}" style="color:#ffffff;font-size:14px;font-weight:700;'
        f'letter-spacing:0.04em;">{escape(part)}</span>'
        f'<span style="color:#94a3b8;font-size:12px;">&nbsp;&nbsp;{escape(summary)}</span>'
        "</td></tr>"
    ]
    if new_items:
        rows.append(_html_subhead("New"))
        for item in new_items:
            rows.append(_html_new_row(item))
    if drops:
        rows.append(_html_subhead("Price drops"))
        for change in drops:
            rows.append(_html_drop_row(change))
    rows.append('<tr><td style="height:16px;font-size:0;line-height:0;">&nbsp;</td></tr>')
    return "\n".join(rows)


def _html_subhead(label):
    return (
        '<tr><td style="padding:14px 20px 0;font-family:Arial,Helvetica,sans-serif;'
        'font-size:11px;font-weight:700;letter-spacing:0.08em;text-transform:uppercase;color:#64748b;">'
        f"{escape(label)}</td></tr>"
    )


def _store_badge(store):
    key = "".join(ch for ch in (store or "").lower() if ch.isalnum())
    bg, fg = _STORE_COLORS.get(key, ("#f1f5f9", "#334155"))
    return (
        f'<span style="display:inline-block;background:{bg};color:{fg};font-size:11px;font-weight:700;'
        f'letter-spacing:0.03em;padding:3px 8px;border-radius:4px;">{escape(store)}</span>'
    )


def _kind_badge(label, bg, fg):
    return (
        f'<span style="display:inline-block;background:{bg};color:{fg};font-size:11px;font-weight:700;'
        f'letter-spacing:0.04em;text-transform:uppercase;padding:3px 8px;border-radius:4px;">{escape(label)}</span>'
    )


def _product_link(name, url):
    safe_name = escape(name)
    if not url:
        return safe_name
    return (
        f'<a href="{escape(url, quote=True)}" style="color:#1e3a8a;text-decoration:underline;">{safe_name}</a>'
    )


def _html_new_row(item):
    name = _display_name(item)
    url = _product_url(item)
    currency = item.get("currency")
    percent = calculate_percent_off(item.get("price_new"), item.get("price_old"))
    original = _money(item.get("price_old"), currency) if item.get("price_old") else "N/A"
    return _html_card(
        _store_name(item),
        "New",
        "#dbeafe",
        "#1d4ed8",
        _product_link(name, url),
        _price_line(item.get("price_new"), original, percent, currency),
        "",
        atl=_is_atl(item),
    )


def _html_drop_row(change):
    item = change.get("item") or {}
    name = _display_name(item) if item.get("name") else (change.get("name") or "Untitled")
    url = _product_url(item) or normalize_url(change.get("url", ""))
    sale = item.get("price_new", change.get("new"))
    original_raw = item.get("price_old")
    currency = item.get("currency")
    percent = calculate_percent_off(sale, original_raw)
    original = _money(original_raw, currency) if original_raw else "N/A"
    prior, change_label = _drop_bits(change)
    extra = (
        '<p style="margin:6px 0 0;font-size:13px;line-height:1.4;color:#166534;">'
        f"Prior sale {escape(prior)} · {escape(change_label)}</p>"
    )
    return _html_card(
        _store_name(item),
        "Price drop",
        "#dcfce7",
        "#166534",
        _product_link(name, url),
        _price_line(sale, original, percent, currency),
        extra,
        atl=_is_atl(item, change),
    )


def _price_line(sale, original, percent, currency=None):
    sale_html = f'<strong style="color:#15803d;font-size:18px;">{escape(_money(sale, currency))}</strong>'
    if original and original != "N/A":
        original_html = (
            '<span style="color:#64748b;font-size:14px;text-decoration:line-through;">'
            f"&nbsp;&nbsp;{escape(original)}</span>"
        )
    else:
        original_html = '<span style="color:#64748b;font-size:14px;">&nbsp;&nbsp;Original N/A</span>'
    if not percent or percent == "N/A":
        return sale_html + original_html
    badge = (
        '&nbsp;<span style="display:inline-block;background:#ecfdf5;color:#166534;font-size:12px;'
        f'font-weight:700;padding:2px 8px;border-radius:999px;">{escape(_off_label(percent))}</span>'
    )
    return sale_html + original_html + badge


def _atl_email_badge():
    return (
        '&nbsp;<span style="display:inline-block;background:#fef08a;color:#854d0e;font-size:11px;'
        'font-weight:700;letter-spacing:0.04em;padding:3px 8px;border-radius:4px;">ALL-TIME LOW</span>'
    )


def _html_card(store, kind, kind_bg, kind_fg, link_html, price_html, extra_html, atl=False):
    atl_html = _atl_email_badge() if atl else ""
    return (
        '<tr><td style="padding:8px 20px 0;font-family:Arial,Helvetica,sans-serif;">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" '
        'style="border:1px solid #e2e8f0;border-radius:8px;">'
        '<tr><td style="padding:12px 14px;">'
        f"{_store_badge(store)}&nbsp;{_kind_badge(kind, kind_bg, kind_fg)}{atl_html}"
        '<div style="margin-top:8px;font-size:15px;line-height:1.4;font-weight:700;color:#0f172a;">'
        f"{link_html}</div>"
        f'<p style="margin:8px 0 0;font-size:14px;line-height:1.4;">{price_html}</p>'
        f"{extra_html}"
        "</td></tr></table></td></tr>"
    )


def _html_footer(safe_report):
    return (
        '<tr><td style="padding:20px 24px 28px;font-family:Arial,Helvetica,sans-serif;'
        'font-size:12px;line-height:1.5;color:#64748b;">'
        "Price drops are at least $2 or 5% versus the previous tracked sale price, not versus the original price. "
        "Removals stay on the full report, and only after that store and part scraped successfully."
        f'<br><a href="{safe_report}" style="color:#1d4ed8;text-decoration:underline;">Open the full report</a>'
        "</td></tr>"
    )


def build_message(digest, config, when=None, banner=None):
    message = EmailMessage()
    message["Subject"] = subject_line(digest, when)
    message["From"] = config.sender
    message["To"] = ", ".join(config.recipients)
    message.set_content(render_plain(digest, config.report_url, when, banner=banner))
    message.add_alternative(
        render_html(digest, config.report_url, when, banner=banner),
        subtype="html",
    )
    return message


def write_preview(path, subject, html, recipients=None):
    header = [f"<!-- Subject: {subject} -->"]
    if recipients:
        header.append(f"<!-- To: {', '.join(recipients)} -->")
    text = "\n".join(header) + "\n" + html
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)
    return path


def _smtp_send(config, message):
    context = ssl.create_default_context()
    if config.security == "ssl":
        with smtplib.SMTP_SSL(config.host, config.port, timeout=30, context=context) as smtp:
            smtp.login(config.user, config.password)
            smtp.send_message(message)
        return
    with smtplib.SMTP(config.host, config.port, timeout=30) as smtp:
        smtp.ehlo()
        smtp.starttls(context=context)
        smtp.ehlo()
        smtp.login(config.user, config.password)
        smtp.send_message(message)


def send_digest(digest, env=None, dry_run=None, preview_path=PREVIEW_PATH, when=None, banner=None):
    """Send the digest, or write a preview. Never raises.

    Returns True when a message was sent or a preview file was written.
    """
    try:
        return _send_digest(digest, env, dry_run, preview_path, when, banner)
    except Exception as exc:
        logger.error("Email failed: %s", exc)
        return False


def _send_digest(digest, env, dry_run, preview_path, when, banner):
    if not should_send(digest):
        logger.info("Email skipped: no new items or price drops")
        return False

    config = load_smtp_config(env)
    if dry_run is None:
        dry_run = config.dry_run
    if dry_run:
        html = render_html(digest, config.report_url, when, banner=banner)
        write_preview(preview_path, subject_line(digest, when), html, config.recipients)
        logger.info("Email dry run: wrote %s", preview_path)
        return True

    if config.missing:
        logger.warning("Email skipped: missing %s", ", ".join(config.missing))
        return False

    message = build_message(digest, config, when, banner=banner)
    _smtp_send(config, message)
    logger.info("Email sent to %s", ", ".join(config.recipients))
    return True


def _sample_label(item):
    copied = dict(item)
    name = normalize_product_name(copied.get("name") or "")
    if name and not name.startswith("[SAMPLE] "):
        copied["name"] = "[SAMPLE] " + name
    else:
        copied["name"] = name
    return copied


def _synthetic_drop(item):
    """A meaningful sale-price drop against a made-up prior sale price."""
    copied = _sample_label(item)
    try:
        current = float(copied.get("price_new"))
    except (TypeError, ValueError):
        return None
    prior = round(max(current + 2.0, current / 0.88), 2)
    if prior <= current:
        prior = round(current + 2.0, 2)
    delta = round(prior - current, 2)
    percent = round((delta / prior) * 100, 1) if prior else 0
    return {
        "type": "price_drop",
        "url": copied.get("url"),
        "name": copied.get("name"),
        "old": f"{prior:.2f}",
        "new": copied.get("price_new"),
        "delta": delta,
        "percent_vs_prior": percent,
        "item": copied,
    }


def _first_per_store(items):
    chosen = []
    seen = set()
    for item in items:
        store = item.get("store") or ""
        if store in seen:
            continue
        seen.add(store)
        chosen.append(item)
    return chosen


def build_sample_digest(catalog):
    """Synthetic new rows and price drops from a saved catalog.

    Names are prefixed with ``[SAMPLE]``. One new row and, when another store
    has the same part, one price drop per part. Bearings appear only when the
    catalog has a bearing that passes the filters.
    """
    by_part = {part: [] for part in PART_ORDER}
    for items in (catalog or {}).values():
        for item in items or []:
            part = item.get("part")
            if part in by_part and item_passes_filters(item):
                by_part[part].append(item)

    new_items = []
    drops = []
    for part in PART_ORDER:
        picks = _first_per_store(by_part[part])
        if not picks:
            continue
        new_items.append(_sample_label(picks[0]))
        if len(picks) > 1:
            drop = _synthetic_drop(picks[1])
            if drop:
                drops.append(drop)
    return Digest(new_items, drops, [])


def _load_catalog(path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def main(argv=None):
    if not logging.getLogger().handlers:
        logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Preview or send a skate sale digest email.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Write the rendered email to a file instead of sending",
    )
    parser.add_argument("--preview-path", default=PREVIEW_PATH, help="Dry-run output path")
    parser.add_argument(
        "--sample",
        action="store_true",
        help="Build a labeled sample from a saved catalog (previous_data.json)",
    )
    parser.add_argument("--catalog", default="previous_data.json", help="Catalog JSON for --sample")
    args = parser.parse_args(argv)
    if not args.sample:
        parser.error("pass --sample to render a catalog preview, or let scraper.py call send_digest()")

    catalog = _load_catalog(args.catalog)
    digest = build_sample_digest(catalog)
    dry_run = True if args.dry_run else None
    wrote = send_digest(
        digest,
        dry_run=dry_run,
        preview_path=args.preview_path,
        banner=SAMPLE_BANNER,
    )
    return 0 if wrote or not should_send(digest) else 1


if __name__ == "__main__":
    raise SystemExit(main())
