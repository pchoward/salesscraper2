#!/usr/bin/env python3
"""Daily sale scrape. Store parsers live in ``stores/``; this file runs them.

Each store is isolated. An exception or timeout is logged, recorded in
``scrape_health.json`` as a failed store/part, and does not stop the other
stores, the report, or the commit.
"""

import datetime
import json
import logging
import os
import sys

from health import HEALTH_PATH, load_state, state_json
from notify import send_digest
from pipeline import apply_run_updates, decorate_digest
from report import build_digest, build_report_html, compare_catalogs
from site_sales import SITE_SALES_PATH, load_state as load_site_sales
from site_sales import state_json as site_sales_json
from stores.files import safe_write_file
from stores.registry import build_scrapers
from stores.runner import run_stores

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


def load_price_history():
    """Load price history from JSON file.

    A missing file starts empty. A corrupt file is left untouched: the caller
    skips saving so a bad read cannot wipe the committed history.
    """
    try:
        with open("price_history.json", "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except FileNotFoundError:
        return {}
    except (json.JSONDecodeError, OSError) as exc:
        logging.error("Could not load price history (leaving the file unchanged): %s", exc)
        return None
    if not isinstance(data, dict):
        logging.error("Price history was not an object; leaving the file unchanged")
        return None
    return data


def save_price_history(history):
    """Save price history to JSON file"""
    safe_write_file("price_history.json", json.dumps(history, indent=2) + "\n")


def save_health(health):
    safe_write_file(HEALTH_PATH, state_json(health))


def save_site_sales(state):
    if not isinstance(state, dict):
        return False
    return safe_write_file(SITE_SALES_PATH, site_sales_json(state))


def load_previous(path="previous_data.json"):
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as handle:
                return json.load(handle)
        return {}
    except Exception as exc:
        logging.error("Error loading previous data: %s", exc)
        return {}


def save_current(data, path="previous_data.json"):
    try:
        return safe_write_file(path, json.dumps(data, indent=2))
    except Exception as exc:
        logging.error("Error saving current data: %s", exc)
        return False


def _log_filter_counts(scrapers, results):
    logging.info("Per-store item counts (before filters = candidates, after = kept):")
    totals = {}
    for scraper in scrapers:
        key = f"{scraper.name}_{scraper.part}"
        items = results.get(key)
        before = getattr(scraper, "candidates", 0)
        if items is None:
            after = "failed"
        else:
            after = len(items)
            bucket = totals.setdefault(scraper.name, {"before": 0, "after": 0})
            bucket["before"] += before
            bucket["after"] += after
        logging.info("  %s: before %s, after %s", key, before, after)
    for name, bucket in totals.items():
        logging.info("  %s total: before %s, after %s", name, bucket["before"], bucket["after"])


def main():
    scanned_at = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()
    scrapers = build_scrapers()
    prev_data = load_previous()
    curr_data, failed_keys = run_stores(scrapers)
    _log_filter_counts(scrapers, curr_data)

    for key, items in list(curr_data.items()):
        if items is None:
            failed_keys.add(key)
            retained = prev_data.get(key, [])
            curr_data[key] = retained
            logging.warning("Scrape failed for %s; retaining %s previous items", key, len(retained))

    changes = compare_catalogs(prev_data, curr_data, failed_keys)
    digest = build_digest(changes, failed_keys)

    if changes:
        logging.info("Changes detected:")
        for site, site_changes in changes.items():
            logging.info("  %s: %s changes", site, len(site_changes))
    else:
        logging.info("No changes detected")

    price_history = load_price_history()
    health = load_state()
    try:
        site_sales = load_site_sales()
    except Exception as exc:
        logging.error("Could not load site sales (continuing): %s", exc)
        site_sales = None
    if price_history is None:
        updates = apply_run_updates(
            curr_data,
            failed_keys,
            {},
            health,
            site_sales=site_sales,
            scanned_at=scanned_at,
        )
        updates["save_history"] = False
        updates["history"] = {}
    else:
        updates = apply_run_updates(
            curr_data,
            failed_keys,
            price_history,
            health,
            site_sales=site_sales,
            scanned_at=scanned_at,
        )
    if updates.get("save_history"):
        save_price_history(updates["history"])
        logging.info("Price history has %s listings", len(updates["history"]))
    try:
        save_health(updates["health"])
    except Exception as exc:
        logging.error("Could not save scrape health (continuing): %s", exc)
    try:
        if updates.get("site_sales"):
            save_site_sales(updates["site_sales"])
    except Exception as exc:
        logging.error("Could not save site sales (continuing): %s", exc)

    save_current(curr_data)
    try:
        decorate_digest(
            digest,
            curr_data,
            updates["history"],
            updates["warnings"],
            previous_data=prev_data,
            site_sales=updates.get("site_sales"),
            scanned_at=scanned_at,
        )
    except Exception as exc:
        logging.error("Digest extras failed (continuing): %s", exc)
    try:
        html = build_report_html(
            curr_data,
            changes,
            updates["history"],
            failed_keys,
            generated_at=scanned_at,
            digest=digest,
        )
        safe_write_file("sale_items_chart.html", html)
    except Exception as exc:
        logging.error("Report build failed (continuing): %s", exc)

    # Mail for new items, meaningful drops, or a broken-store warning.
    # Logged SMTP problems stay here so the workflow can still commit.
    dry_run = True if "--email-dry-run" in sys.argv[1:] else None
    send_digest(digest, dry_run=dry_run)

    logging.info("Scraping complete!")


if __name__ == "__main__":
    main()
