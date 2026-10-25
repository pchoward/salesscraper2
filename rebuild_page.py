#!/usr/bin/env python3
"""Rebuild ``sale_items_chart.html`` from saved data, without scraping.

UI changes (``page.py``, ``page.js``, ``page.css``, ``mobile.css``) only
reach the site when the report is rebuilt. Normally that happens at the end
of the daily scrape. This rebuilds it from what the last scrape saved:

* ``previous_data.json``: the catalog the scrape built the page from;
* ``price_history.json``: the history it used;
* ``report_inputs.json``: everything else it passed to ``build_report_html``:
  the catalog diff against the scrape before it (New, Price drops,
  Disappeared), the digest, the failed stores, and the scrape time.

So the rebuilt page shows the same changes and the same "generated at" time
as the scrape's page. Only the page code is new.

``report_inputs.json`` records a SHA-256 of the two data files as saved. If
either has changed since, the rebuild refuses, rather than pairing one run's
changes with another run's catalog. The scrape removes the file when it could
not save its data, for the same reason.

Nothing here contacts a store, sends email, or writes any file except
``sale_items_chart.html``.

    python rebuild_page.py                     # rebuild, or exit 1 with the reason
    python rebuild_page.py --skip-if-missing   # exit 0 when there is nothing to rebuild from yet
"""

import argparse
import hashlib
import json
import logging
import os
import sys
from pathlib import Path

from report import Digest

logger = logging.getLogger("rebuild_page")

INPUTS_PATH = "report_inputs.json"
DATA_PATH = "previous_data.json"
HISTORY_PATH = "price_history.json"
PAGE_PATH = "sale_items_chart.html"
VERSION = 1
# The Digest fields render_page reads. The others (warnings, all-time lows,
# watchlist hits) are for email only.
DIGEST_FIELDS = ("new_items", "drops", "removed", "cross_store")


class RebuildError(Exception):
    """The saved inputs cannot reproduce the last scrape's page."""


def _sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save_report_inputs(changes, digest, failed_keys, generated_at, history_saved,
                       path=INPUTS_PATH, data_path=DATA_PATH, history_path=HISTORY_PATH):
    """Record the scrape's ``build_report_html`` inputs. Call after the data files are saved.

    ``history_saved`` is False when the scrape built the page from an empty
    history and left ``price_history.json`` alone; the rebuild then does the
    same. Returns True when the file was written.
    """
    payload = {
        "version": VERSION,
        "generated_at": generated_at,
        "failed_keys": sorted(failed_keys or ()),
        "changes": changes or {},
        "digest": {field: list(getattr(digest, field, None) or []) for field in DIGEST_FIELDS},
        "history": "file" if history_saved else "empty",
        "fingerprints": {
            "data": _sha256(data_path),
            **({"history": _sha256(history_path)} if history_saved else {}),
        },
    }
    text = json.dumps(payload, indent=1, sort_keys=True, ensure_ascii=False) + "\n"
    temporary = f"{path}.tmp"
    try:
        with open(temporary, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.remove(temporary)
    return True


def discard_report_inputs(path=INPUTS_PATH):
    """Forget the inputs when the scrape could not save the data they describe."""
    try:
        os.remove(path)
    except FileNotFoundError:
        pass


def load_report_inputs(path=INPUTS_PATH, data_path=DATA_PATH, history_path=HISTORY_PATH):
    """Return ``build_report_html`` keyword arguments. Raises RebuildError."""
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise RebuildError(f"{path} is missing; run 'Scraper - Run Full Scrape' once to create it") from None
    except (OSError, ValueError) as exc:
        raise RebuildError(f"{path} could not be read ({type(exc).__name__})") from None
    if not isinstance(payload, dict) or payload.get("version") != VERSION:
        raise RebuildError(f"{path} has an unsupported format")
    fingerprints = payload.get("fingerprints") or {}
    try:
        if _sha256(data_path) != fingerprints.get("data"):
            raise RebuildError(f"{data_path} changed after the last scrape saved {path}; run the scrape instead")
        data = json.loads(Path(data_path).read_text(encoding="utf-8"))
        if payload.get("history") == "file":
            if _sha256(history_path) != fingerprints.get("history"):
                raise RebuildError(f"{history_path} changed after the last scrape saved {path}; run the scrape instead")
            history = json.loads(Path(history_path).read_text(encoding="utf-8"))
        else:
            history = {}
    except (OSError, ValueError) as exc:
        raise RebuildError(f"saved data could not be read ({type(exc).__name__})") from None

    saved = payload.get("digest") or {}
    digest = Digest(
        new_items=saved.get("new_items"),
        drops=saved.get("drops"),
        # JSON has no tuples; the scrape stores (site, item) pairs.
        removed=[tuple(pair) for pair in saved.get("removed") or []],
    )
    digest.cross_store = list(saved.get("cross_store") or [])
    return {
        "data": data,
        "changes": payload.get("changes") or {},
        "price_history": history,
        "failed_keys": list(payload.get("failed_keys") or []),
        "generated_at": payload.get("generated_at"),
        "digest": digest,
    }


def rebuild(path=INPUTS_PATH, data_path=DATA_PATH, history_path=HISTORY_PATH, page_path=PAGE_PATH):
    """Rebuild the page. Returns True when the file changed. Raises RebuildError."""
    from report import build_report_html

    inputs = load_report_inputs(path, data_path, history_path)
    html = build_report_html(**inputs)
    page = Path(page_path)
    if page.exists() and page.read_text(encoding="utf-8") == html:
        return False
    temporary = page.with_name(page.name + ".tmp")
    temporary.write_text(html, encoding="utf-8")
    os.replace(temporary, page)
    return True


def main(argv=None):
    parser = argparse.ArgumentParser(description="Rebuild sale_items_chart.html from the last scrape's saved data.")
    parser.add_argument("--skip-if-missing", action="store_true",
                        help=f"exit 0 when {INPUTS_PATH} does not exist yet")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")
    if args.skip_if_missing and not Path(INPUTS_PATH).exists():
        print(f"{INPUTS_PATH} does not exist yet; the next scrape creates it. Nothing rebuilt.")
        return 0
    try:
        changed = rebuild()
    except RebuildError as exc:
        print(f"Not rebuilt: {exc}", file=sys.stderr)
        return 1
    print(f"Rebuilt {PAGE_PATH}." if changed else f"{PAGE_PATH} is already current.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
