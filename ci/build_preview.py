#!/usr/bin/env python3
"""Build a PREVIEW copy of the site from a PR branch, for CI only.

Uses the data already committed in the branch (rebuild_page.py's inputs),
so nothing scrapes a store, sends email, or touches production data. The
copy is changed so it cannot be mistaken for, or act as, production:

* a fixed PREVIEW banner, a "PREVIEW" title prefix, and noindex;
* no subscriber alerts (the production Worker URL and Turnstile key are
  left out, so page.js keeps the alerts UI off);
* no Cloudflare Web Analytics beacon, so previews never count as visits.

    python ci/build_preview.py OUT_DIR [--label "PR #123 abc1234"] [--data-root DIR]

Other sports (BMX, Ski, MTB) are added when their catalogs/<id>/ data has
listings; their homepage tabs then open their own page.
"""

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import page  # noqa: E402

BANNER_ID = "previewBanner"
_BEACON = re.compile(r"<!-- Cloudflare Web Analytics -->.*?<!-- End Cloudflare Web Analytics -->", re.S)
_BEACON_SCRIPT = re.compile(r"<script[^>]*cloudflareinsights[^>]*>\s*</script>", re.I)


def _html_escape(text):
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def mark_preview(html, label=""):
    """The production page made into a labeled, inert preview."""
    note = "PREVIEW" + (f" · {label}" if label else "") + " · not the live site; alerts and analytics are off"
    banner = (
        f'<div id="{BANNER_ID}" role="note" style="position:sticky;top:0;z-index:1000;background:#b45309;color:#fff;'
        'font:600 13px/1.4 system-ui,sans-serif;padding:6px 12px;text-align:center">'
        f"{_html_escape(note)}</div>"
    )
    html = _BEACON.sub("", html)
    html = _BEACON_SCRIPT.sub("", html)
    html = html.replace("<title>", "<title>PREVIEW · ", 1)
    html = html.replace("</head>", '<meta name="robots" content="noindex,nofollow"></head>', 1)
    html = re.sub(r"(<body[^>]*>)", lambda match: match.group(1) + banner, html, count=1)
    return html


def build_sport_pages(out, label="", data_root=None):
    """Pages for the other sports that have scraped listings, from their
    catalogs/<id>/ data under ``data_root`` (the repository by default).
    Returns {sport id: page path} for the homepage; a sport with no
    listings yet is left out, so its tab keeps saying "coming soon"."""
    import rebuild_page
    import sports
    from report import build_report_html

    data_root = Path(data_root or ROOT).resolve()
    catalogs = {}
    for sport in sports.SPORTS.values():
        if sport.is_default:
            continue
        folder = data_root / sport.data_dir
        try:
            data = json.loads((folder / rebuild_page.DATA_PATH).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not any(items for items in data.values()):
            continue
        try:
            inputs = rebuild_page.load_report_inputs(folder / rebuild_page.INPUTS_PATH, folder / rebuild_page.DATA_PATH,
                                                     folder / rebuild_page.HISTORY_PATH)
        except rebuild_page.RebuildError as exc:
            print(f"{sport.label}: saved report inputs unusable ({exc}); building from the catalog alone.", file=sys.stderr)
            try:
                history = json.loads((folder / rebuild_page.HISTORY_PATH).read_text(encoding="utf-8"))
            except (OSError, ValueError):
                history = {}
            inputs = {"data": data, "changes": {}, "price_history": history}
        inputs.pop("sport", None)
        with sport.session(folder):
            html = build_report_html(**inputs, sport=sport)
        target = out.resolve() / sport.page_path
        page.write_page(mark_preview(html, label), str(target))
        catalogs[sport.id] = sport.page_path
    return catalogs


def build(out_dir, label="", data_root=None):
    """Write the preview site into ``out_dir``. Returns the list of files.

    ``data_root`` holds the other sports' catalogs/<id>/ folders (the
    ShredDeals preview workflow keeps them off main)."""
    import rebuild_page
    from report import build_report_html

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    # Alerts off: no production Worker URL or Turnstile key in the page.
    page.ALERTS_UI_CONFIG = {}
    try:
        html = build_report_html(**rebuild_page.load_report_inputs(
            ROOT / rebuild_page.INPUTS_PATH, ROOT / rebuild_page.DATA_PATH, ROOT / rebuild_page.HISTORY_PATH))
    except rebuild_page.RebuildError as exc:
        # The branch's data files and saved inputs disagree (or are missing):
        # build from the catalog alone. The change tabs are empty then.
        print(f"Saved report inputs unusable ({exc}); building from the catalog alone.", file=sys.stderr)
        data = json.loads((ROOT / rebuild_page.DATA_PATH).read_text(encoding="utf-8"))
        history = json.loads((ROOT / rebuild_page.HISTORY_PATH).read_text(encoding="utf-8"))
        html = build_report_html(data, {}, history)
    page.write_page(mark_preview(html, label), str(out / "sale_items_chart.html"))
    catalogs = build_sport_pages(out, label, data_root)
    from previews.publish import publish
    publish(out, catalogs=catalogs)
    homepage = out / "index.html"
    homepage.write_text(mark_preview(homepage.read_text(encoding="utf-8"), label), encoding="utf-8")
    (out / "_headers").write_text("/*\n  X-Robots-Tag: noindex, nofollow\n", encoding="utf-8")
    return sorted(path.name for path in out.iterdir())


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("out_dir")
    parser.add_argument("--label", default="")
    parser.add_argument("--data-root", help="folder holding catalogs/<sport>/ for BMX, Ski and MTB (default: the repository)")
    args = parser.parse_args(argv)
    files = build(args.out_dir, args.label, args.data_root)
    print("Preview written:", ", ".join(files))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
