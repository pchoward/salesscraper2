#!/usr/bin/env python3
"""The PR status comment: one sticky comment, readable in the GitHub phone app.

    python ci/pr_comment.py SUMMARY_JSON --sha SHA --run-url URL --ci CONCLUSION
        [--preview-url URL] [--images-base URL] > comment.md

``SUMMARY_JSON`` is ci/smoke.mjs's summary. ``--images-base`` is where the
screenshots were published (raw URLs on the ci-previews branch); without it
the comment points to the run's artifact instead.
"""

import argparse
import html
import json
import re
from pathlib import Path

MARKER = "<!-- skatedeals-pr-preview -->"
ICON = {"pass": "✅", "fail": "❌", "skip": "➖"}
VIEWS = ("desktop", "mobile")
SHOT = re.compile(r"^(desktop|mobile)-(home|search|quickview|sport)\.png$")
# summary.json comes from the PR's own run, so it is untrusted: only known
# views, statuses and screenshot names, and escaped, shortened text get through.


def _text(value, limit=120):
    clean = re.sub(r"[\r\n|`*_\[\]<>()!]", " ", str(value or ""))
    return html.escape(clean[:limit], quote=True)


def _clean(summary):
    summary = summary if isinstance(summary, dict) else {}
    checks = []
    for entry in (summary.get("checks") or [])[:40]:
        if not isinstance(entry, dict) or entry.get("view") not in VIEWS:
            continue
        status = entry.get("status") if entry.get("status") in ICON else "fail"
        checks.append({"view": entry["view"], "name": _text(entry.get("name"), 60) or "check",
                       "status": status, "detail": _text(entry.get("detail"), 300)})
    shots = [name for name in (summary.get("screenshots") or []) if isinstance(name, str) and SHOT.match(name)]
    return {"checks": checks, "screenshots": shots}


CI_TEXT = {"success": "✅ passed", "failure": "❌ failed", "cancelled": "⚪ cancelled", "timed_out": "❌ timed out"}


def render(summary, sha, run_url, ci, preview_url="", images_base=""):
    summary = _clean(summary)
    checks = summary["checks"] or [
        {"view": "desktop", "name": "Browser checks ran", "status": "fail", "detail": "no results; see the run log"}
    ]
    failed = [entry for entry in checks if entry.get("status") == "fail"]
    lines = [MARKER, "### SkateDeals PR preview"]
    status = "❌ " + f"{len(failed)} browser check(s) failed" if failed else "✅ browser checks passed"
    lines.append(f"**Tests:** {CI_TEXT.get(ci, _text(ci, 20) or 'unknown')} · **Browser:** {status} · `{_text(sha, 7)}`")
    lines.append("")
    if preview_url:
        lines.append(f"**[Open the preview]({preview_url})**: labeled PREVIEW; alerts and analytics are off.")
    else:
        lines.append("Live preview link: not set up (see docs/level2-autonomy.md, \"Preview hosting\"). Screenshots below.")
    lines.append("")
    # Checks: one row per check, a mark per view, so it fits a phone.
    names = []
    for entry in checks:
        if entry["name"] not in names:
            names.append(entry["name"])
    by = {(entry["view"], entry["name"]): entry for entry in checks}
    lines.append("| Check | Desktop | Phone |")
    lines.append("|---|:-:|:-:|")
    for name in names:
        marks = [ICON.get((by.get((view, name)) or {}).get("status"), "") for view in VIEWS]
        lines.append(f"| {name} | {marks[0]} | {marks[1]} |")
    if failed:
        lines.append("")
        lines.append("<details open><summary>What failed</summary>")
        lines.append("")
        for entry in failed:
            detail = entry.get("detail") or ""
            lines.append(f"- **{entry['view']} · {entry['name']}**: {detail}")
        lines.append("</details>")
    shots = summary.get("screenshots") or []
    if shots and images_base:
        lines.append("")
        pairs = []
        for name in ("home", "search", "quickview", "sport"):
            row = [f"{view}-{name}.png" for view in VIEWS if f"{view}-{name}.png" in shots]
            if row:
                pairs.append((name, row))
        lines.append("<table><tr><th>Desktop</th><th>Phone</th></tr>")
        for name, row in pairs:
            cells = []
            for view in VIEWS:
                file = f"{view}-{name}.png"
                if file in row:
                    url = f"{images_base.rstrip('/')}/{file}"
                    width = 320 if view == "desktop" else 160
                    cells.append(f'<td><a href="{url}"><img src="{url}" width="{width}" alt="{view} {name}"></a></td>')
                else:
                    cells.append("<td></td>")
            lines.append("<tr>" + "".join(cells) + "</tr>")
        lines.append("</table>")
    elif shots:
        lines.append("")
        lines.append(f"Screenshots: in the run's **pr-preview** artifact ([run]({run_url})).")
    lines.append("")
    lines.append(f"<sub>[Workflow run]({run_url}) · built from committed data; no store was scraped, no email sent. "
                 "Nothing merges or deploys to production automatically.</sub>")
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("summary")
    parser.add_argument("--sha", required=True)
    parser.add_argument("--run-url", required=True)
    parser.add_argument("--ci", default="")
    parser.add_argument("--preview-url", default="")
    parser.add_argument("--images-base", default="")
    args = parser.parse_args(argv)
    try:
        summary = json.loads(Path(args.summary).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        summary = {"checks": [{"view": "desktop", "name": "Browser checks ran", "status": "fail",
                               "detail": "no summary.json; see the run log"}]}
    print(render(summary, args.sha, args.run_url, args.ci, args.preview_url, args.images_base), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
