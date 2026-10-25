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
from history import record_misses
from notify import send_digest, send_admin_warnings
from notification_engine import send_notifications
from pipeline import apply_run_updates, decorate_digest, prepare_run
from rebuild_page import discard_report_inputs, save_report_inputs
from report import build_digest, build_report_html, compare_catalogs
from stores.stock import confirm_stock
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
    return safe_write_file("price_history.json", json.dumps(history, indent=2) + "\n")


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

    health_before = load_state()
    prepared = prepare_run(curr_data, failed_keys, prev_data, health_before, today=scanned_at[:10])
    curr_data = prepared["current_data"]
    failed_keys = prepared["failed_keys"]
    suspect_keys = prepared["suspect_keys"]

    price_history = load_price_history()
    carried = set()
    stock_before = {url: entry["stock"] for url, entry in (price_history or {}).items()
                    if isinstance(entry, dict) and entry.get("stock") == "out_of_stock"}
    if isinstance(price_history, dict):
        try:
            carried = record_misses(prev_data, curr_data, price_history, failed_keys)
            logging.info("Carried %s listings after a single miss", len(carried))
            confirm_stock(price_history, curr_data, failed_keys)
        except Exception as exc:
            logging.error("Miss tracking failed (continuing): %s", exc)
            carried = set()

    changes = compare_catalogs(prev_data, curr_data, failed_keys)
    digest = build_digest(changes, failed_keys)

    if changes:
        logging.info("Changes detected:")
        for site, site_changes in changes.items():
            logging.info("  %s: %s changes", site, len(site_changes))
    else:
        logging.info("No changes detected")

    health = health_before
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
            suspect_keys=suspect_keys,
            skip_urls=carried,
            health_results=prepared["health_results"],
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
            suspect_keys=suspect_keys,
            skip_urls=carried,
            health_results=prepared["health_results"],
        )
    history_saved = False
    if updates.get("save_history"):
        history_saved = save_price_history(updates["history"])
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

    data_saved = save_current(curr_data)
    try:
        decorate_digest(
            digest,
            curr_data,
            updates["history"],
            updates["warnings"],
            previous_data=prev_data,
            site_sales=updates.get("site_sales"),
            scanned_at=scanned_at,
            failed_keys=failed_keys,
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
    # What rebuild_page.py needs to rebuild this exact page later, after a
    # UI-only change. Only when the data it describes was saved.
    try:
        if data_saved and (history_saved or not updates.get("save_history")):
            save_report_inputs(changes, digest, failed_keys, scanned_at, history_saved)
        else:
            discard_report_inputs()
    except Exception as exc:
        logging.error("Could not save report inputs (continuing): %s", exc)
        discard_report_inputs()

    # Operational warnings have a separate administrator-only delivery route.
    # Logged SMTP problems stay here so the workflow can still commit.
    dry_run = True if "--email-dry-run" in sys.argv[1:] else None
    send_admin_warnings(updates["warnings"], dry_run=dry_run)
    if os.environ.get("NOTIFICATION_ENGINE_ENABLED", "").lower() in {"1", "true"}:
        stock_before.update({url: entry["stock"] for url, entry in updates["history"].items()
                             if isinstance(entry, dict) and entry.get("stock") == "out_of_stock"})
        send_notifications(digest, curr_data, updates["history"], failed_keys,
                           previous=prev_data, stock_evidence=stock_before,
                           skip_urls=carried, dry_run=dry_run, day=scanned_at[:10])
    else:
        send_digest(digest, dry_run=dry_run)

    # Opt-in subscriber alerts through the alerts Worker. Off unless
    # ALERTS_DELIVERY_ENABLED is set; never affects the owner's digest above.
    if os.environ.get("ALERTS_DELIVERY_ENABLED", "").lower() in {"1", "true"} and not dry_run:
        try:
            from alerts_delivery import deliver_subscriber_alerts

            evidence = dict(stock_before)
            evidence.update({url: entry["stock"] for url, entry in updates["history"].items()
                             if isinstance(entry, dict) and entry.get("stock") == "out_of_stock"})
            deliver_subscriber_alerts(curr_data, updates["history"], failed_keys, previous=prev_data,
                                      stock_evidence=evidence, skip_urls=carried, day=scanned_at[:10])
        except Exception as exc:
            logging.error("Subscriber alerts failed (continuing): %s", type(exc).__name__)

    logging.info("Scraping complete!")


if __name__ == "__main__":
    main()
