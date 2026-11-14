"""One evening email for BMX, Ski and MTB (owner, 2026-11-12).

Skate keeps its own morning email (notify.py). The sports workflow scrapes
BMX, Ski and MTB one after another; each scrape saves its new listings and
price drops in ``catalogs/<sport>/report_inputs.json``. After the last one,

    python sports_email.py --since 2026-11-12T21:37:00+00:00 bmx ski mtb

sends one email with a section per sport, using the same SMTP settings and
recipients as the Skate email. A sport whose scrape failed (its saved inputs
are older than ``--since``) is left out, so yesterday's deals are never sent
twice. Each sport lists its biggest markdowns first, at most ``LIMIT`` new
listings and ``LIMIT`` price drops; the rest are on that sport's page.

Never raises: mail problems are logged and the workflow carries on.
"""

import argparse
import datetime
import json
import logging
from email.message import EmailMessage
from html import escape

import sports
from filters import calculate_percent_off
import notify
from report import Digest

logger = logging.getLogger("sports_email")

SITE = "https://shreddeals.com/"
LIMIT = 40  # listings of each kind per sport
PREVIEW_PATH = "email_preview_sports.html"


class Section:
    def __init__(self, sport, new_items, drops, more_new=0, more_drops=0):
        self.sport = sport
        self.new_items = new_items
        self.drops = drops
        self.more_new = more_new
        self.more_drops = more_drops

    @property
    def url(self):
        # The main page opened on this sport, with its menus and tabs; the
        # sport's catalog page on its own has no navigation (owner, 2026-11-14).
        return f"{SITE}?sport={self.sport.id}"

    @property
    def total_new(self):
        return len(self.new_items) + self.more_new

    @property
    def total_drops(self):
        return len(self.drops) + self.more_drops


def _when(text):
    try:
        moment = datetime.datetime.fromisoformat(str(text))
    except ValueError:
        return None
    return moment if moment.tzinfo else moment.replace(tzinfo=datetime.timezone.utc)


def _percent(item):
    try:
        return float(str(calculate_percent_off(item.get("price_new"), item.get("price_old"))).rstrip("%"))
    except (TypeError, ValueError):
        return 0.0


def _biggest_first(rows, item_of):
    return sorted(rows, key=lambda row: -_percent(item_of(row) or {}))


def load_section(sport, since=None):
    """This run's new listings and drops for ``sport``, or None when there
    are none or the saved inputs are from an earlier run."""
    path = sport.data_path() / "report_inputs.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if since is not None:
        made = _when(payload.get("generated_at"))
        if made is None or made < since:
            logger.info("%s: no scrape since %s; left out", sport.label, since.isoformat())
            return None
    saved = payload.get("digest") or {}
    new_items = _biggest_first([i for i in saved.get("new_items") or [] if isinstance(i, dict)], lambda i: i)
    drops = _biggest_first([c for c in saved.get("drops") or [] if isinstance(c, dict)], lambda c: c.get("item"))
    if not new_items and not drops:
        return None
    return Section(sport, new_items[:LIMIT], drops[:LIMIT],
                   max(0, len(new_items) - LIMIT), max(0, len(drops) - LIMIT))


def _count_text(new, drops):
    return f"{new} new, {drops} {'price drop' if drops == 1 else 'price drops'}"


def _counts(sections):
    return _count_text(sum(s.total_new for s in sections), sum(s.total_drops for s in sections))


def _labels(sections):
    names = [section.sport.label for section in sections]
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " & " + names[-1]


def subject_line(sections, when=None):
    return f"{notify.BRAND} {_labels(sections)}: {_counts(sections)} ({notify._short_date(when)})"


def _by_part(section):
    grouped = {}
    for item in section.new_items:
        grouped.setdefault(notify._part_name(item), ([], []))[0].append(item)
    for change in section.drops:
        grouped.setdefault(notify._drop_part(change), ([], []))[1].append(change)
    order = [part for part in section.sport.parts if part in grouped]
    order += [part for part in grouped if part not in order]
    return [(part, *grouped[part]) for part in order]


def _more_line(section):
    bits = []
    if section.more_new:
        bits.append(f"{section.more_new} more new")
    if section.more_drops:
        bits.append(f"{section.more_drops} more price drop{'' if section.more_drops == 1 else 's'}")
    return f"{' and '.join(bits)} on the {section.sport.label} page" if bits else ""


def render_plain(sections, when=None):
    lines = [f"{notify.BRAND} · {_labels(sections)} deals — {notify._long_date(when)}", _counts(sections), ""]
    for section in sections:
        lines += [f"=== {section.sport.label.upper()} ===",
                  f"{_count_text(section.total_new, section.total_drops)} · {section.url}", ""]
        for part, new_items, drops in _by_part(section):
            lines.append(part.upper())
            if new_items:
                lines.append("New")
                for item in new_items:
                    lines.extend(notify._plain_new(item))
            if drops:
                lines.append("Price drops")
                for change in drops:
                    lines.extend(notify._plain_drop(change))
            lines.append("")
        more = _more_line(section)
        if more:
            lines += [f"{more}: {section.url}", ""]
    lines.append("Biggest markdowns first. Price drops are at least $2 or 5% versus the previous tracked sale price.")
    return "\n".join(lines).rstrip() + "\n"


def _html_sport_band(section):
    url = escape(section.url, quote=True)
    return (
        '<tr><td bgcolor="#1e3a8a" style="background:#1e3a8a;padding:16px 20px;font-family:Arial,Helvetica,sans-serif;">'
        f'<span data-sport="{escape(section.sport.id, quote=True)}" style="color:#ffffff;font-size:20px;'
        f'font-weight:700;">{escape(section.sport.label)}</span>'
        f'<span style="color:#bfdbfe;font-size:13px;">&nbsp;&nbsp;'
        f'{escape(_count_text(section.total_new, section.total_drops))}</span>'
        f'<br><a href="{url}" style="color:#bfdbfe;font-size:12px;text-decoration:underline;">'
        f"Open the {escape(section.sport.label)} page</a></td></tr>"
    )


def _html_more(section):
    more = _more_line(section)
    if not more:
        return ""
    url = escape(section.url, quote=True)
    return ('<tr><td style="padding:0 20px 20px;font-family:Arial,Helvetica,sans-serif;font-size:13px;">'
            f'<a href="{url}" style="color:#1d4ed8;text-decoration:underline;">{escape(more)}</a></td></tr>')


def render_html(sections, when=None):
    summary = _counts(sections)
    title = subject_line(sections, when)
    chunks = [
        "<!DOCTYPE html>", '<html lang="en">', "<head>", '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1.0">',
        f"<title>{escape(title)}</title>", "</head>",
        '<body style="margin:0;padding:0;background:#f1f5f9;">',
        f'<div style="display:none;max-height:0;overflow:hidden;mso-hide:all;">{escape(summary)}.</div>',
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" bgcolor="#f1f5f9" '
        'style="background:#f1f5f9;margin:0;padding:0;">',
        '<tr><td align="center" style="padding:24px 12px;">',
        '<table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0" bgcolor="#ffffff" '
        'style="width:600px;max-width:600px;background:#ffffff;border-radius:12px;overflow:hidden;">',
        notify._html_header(when, summary, heading=f"{_labels(sections)} deals"),
    ]
    for section in sections:
        chunks.append(_html_sport_band(section))
        for part, new_items, drops in _by_part(section):
            chunks.append(notify._html_part(part, new_items, drops))
        more = _html_more(section)
        if more:
            chunks.append(more)
    chunks.append(
        '<tr><td style="padding:20px 24px 28px;font-family:Arial,Helvetica,sans-serif;font-size:12px;'
        'line-height:1.5;color:#64748b;">Biggest markdowns first. Price drops are at least $2 or 5% versus the '
        f'previous tracked sale price.<br><a href="{SITE}" style="color:#1d4ed8;text-decoration:underline;">'
        "shreddeals.com</a></td></tr>")
    chunks.extend(["</table>", "</td></tr>", "</table>", "</body>", "</html>"])
    return "\n".join(chunks)


def build_message(sections, config, when=None):
    message = EmailMessage()
    message["Subject"] = subject_line(sections, when)
    message["From"] = config.sender
    message["To"] = ", ".join(config.recipients)
    message.set_content(render_plain(sections, when))
    message.add_alternative(render_html(sections, when), subtype="html")
    return message


def send(sport_ids, since=None, env=None, dry_run=None, preview_path=PREVIEW_PATH, when=None):
    """Send one email for these sports. Returns True when sent or previewed. Never raises."""
    try:
        sections = [section for section in (load_section(sports.get(sport_id), since) for sport_id in sport_ids)
                    if section]
        if not sections:
            logger.info("Sports email skipped: no new listings or price drops")
            return False
        config = notify.load_smtp_config(env)
        if dry_run is None:
            dry_run = config.dry_run
        if dry_run:
            notify.write_preview(preview_path, subject_line(sections, when), render_html(sections, when))
            logger.info("Sports email dry run: wrote %s", preview_path)
            return True
        if config.missing:
            logger.warning("Sports email skipped: missing %s", ", ".join(config.missing))
            return False
        notify._smtp_send(config, build_message(sections, config, when))
        logger.info("Sports email sent (%s)", _labels(sections))
        return True
    except Exception as exc:
        logger.error("Sports email failed (%s)", type(exc).__name__)
        return False


def main(argv=None):
    parser = argparse.ArgumentParser(description="Email BMX, Ski and MTB's new deals in one message.")
    parser.add_argument("sports", nargs="+", choices=sorted(set(sports.SPORTS) - {"skate"}))
    parser.add_argument("--since", help="ISO time the scrapes started; older saved results are left out")
    parser.add_argument("--dry-run", action="store_true", help=f"write {PREVIEW_PATH} instead of sending")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    since = _when(args.since) if args.since else None
    send(args.sports, since=since, dry_run=True if args.dry_run else None)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
