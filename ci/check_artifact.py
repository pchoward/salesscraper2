#!/usr/bin/env python3
"""Check a downloaded pr-preview artifact before anything publishes it.

The artifact is built by the PR's own code, so it is untrusted. This keeps
only what publishing needs and refuses the rest:

* pr.json names an open PR whose head is the commit the run tested;
* screenshots are real PNGs with the expected names, under a size cap;
* the site is the files ci/build_preview.py writes, under a size cap.

    python ci/check_artifact.py ARTIFACT_DIR --head-sha SHA --open-prs 12,13
        -> prints the PR number; exits 1 when anything is off.
"""

import argparse
import json
import re
import sys
from pathlib import Path

SHOT = re.compile(r"^(desktop|mobile)-(home|search|quickview|sport)\.png$")
SITE_FILES = {"index.html", "sale_items_chart.html", "history.json", "_headers"}
PNG = b"\x89PNG\r\n\x1a\n"
MAX_SHOT = 3 * 1024 * 1024
MAX_SITE = 40 * 1024 * 1024


class Refused(Exception):
    pass


def check(root, head_sha, open_prs):
    root = Path(root)
    try:
        meta = json.loads((root / "pr.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise Refused(f"pr.json unreadable: {exc}")
    number = meta.get("number")
    if not isinstance(number, int) or number <= 0:
        raise Refused("pr.json has no PR number")
    if meta.get("head_sha") != head_sha:
        raise Refused("pr.json names a different commit than the run")
    if number not in open_prs:
        raise Refused(f"PR #{number} is not an open PR with this head commit")
    shots = root / "shots"
    for path in sorted(shots.iterdir()) if shots.is_dir() else []:
        if path.name == "summary.json":
            continue
        if not SHOT.match(path.name) or path.is_symlink() or not path.is_file():
            raise Refused(f"unexpected file in shots/: {path.name}")
        if path.stat().st_size > MAX_SHOT or path.read_bytes()[:8] != PNG:
            raise Refused(f"{path.name} is not a PNG under {MAX_SHOT} bytes")
    site = root / "site"
    if site.is_dir():
        total = 0
        for path in site.iterdir():
            if path.name not in SITE_FILES or path.is_symlink() or not path.is_file():
                raise Refused(f"unexpected file in site/: {path.name}")
            total += path.stat().st_size
        if total > MAX_SITE:
            raise Refused(f"site is {total} bytes, over {MAX_SITE}")
    return number


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("artifact")
    parser.add_argument("--head-sha", required=True)
    parser.add_argument("--open-prs", default="", help="comma-separated open PR numbers whose head is --head-sha")
    args = parser.parse_args(argv)
    open_prs = {int(value) for value in args.open_prs.split(",") if value.strip().isdigit()}
    try:
        print(check(args.artifact, args.head_sha, open_prs))
    except Refused as exc:
        print(f"Refused: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
