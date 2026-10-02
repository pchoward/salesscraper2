"""Post-scrape bookkeeping. Failures here must not stop the scrape or the commit."""

import datetime
import logging

from filters import item_passes_filters
from health import broken_store_warnings, record_run, results_from_run, suspect_store_warnings
from history import all_time_low_status, apply_lifecycle, prune_price_history, update_price_history
from matching import cross_store_groups
from site_sales import describe_sales, record_catalog, sale_banners
from watchlist import match_watchlist

logger = logging.getLogger("pipeline")


def _day(today):
    if today is None:
        return datetime.date.today().isoformat()
    if isinstance(today, datetime.datetime):
        return today.date().isoformat()
    if isinstance(today, datetime.date):
        return today.isoformat()
    return str(today)


def apply_run_updates(
    current_data,
    failed_keys,
    history,
    health,
    today=None,
    site_sales=None,
    scanned_at=None,
    suspect_keys=None,
):
    """Update price history and store health. Never raises.

    Failed store/part keys are recorded as failures and are not written into
    price history (retained rows are not a new observation).
    """
    day = _day(today)
    stats = None
    # A non-dict (for example a corrupt JSON list) must not be saved back as {}.
    save_history = isinstance(history, dict)
    if not save_history:
        if history is not None:
            logger.error("Price history was not an object; leaving the file unchanged")
        history = {}
    else:
        try:
            history = update_price_history(
                current_data,
                history,
                today=day,
                skip_keys=failed_keys,
            )
        except Exception as exc:
            logger.error("Price history update failed (continuing): %s", exc)
            if not isinstance(history, dict):
                history = {}
        try:
            history, stats = prune_price_history(history, today=day, current_data=current_data)
        except Exception as exc:
            logger.error("Price history prune failed (continuing): %s", exc)
            if not isinstance(history, dict):
                history = {}
            stats = None
        try:
            if isinstance(history, dict):
                history = apply_lifecycle(
                    history,
                    current_data,
                    today=day,
                    skip_keys=failed_keys,
                )
        except Exception as exc:
            logger.error("Lifecycle update failed (continuing): %s", exc)

    warnings = []
    try:
        results = results_from_run(current_data, failed_keys, suspect_keys)
        health = record_run(health, day, results, scanned_at=scanned_at)
        warnings = broken_store_warnings(health)
        warnings.extend(suspect_store_warnings(suspect_keys, health, day))
    except Exception as exc:
        logger.error("Store health update failed (continuing): %s", exc)
        warnings = []
        if not isinstance(health, dict) or not isinstance(health.get("runs"), list):
            health = {"runs": [], "baseline": {}}

    try:
        site_sales = record_catalog(
            site_sales,
            current_data,
            today=day,
            failed_keys=failed_keys,
            history=history if isinstance(history, dict) else None,
        )
    except Exception as exc:
        logger.error("Site-wide sale update failed (continuing): %s", exc)
        if not isinstance(site_sales, dict):
            site_sales = None
    return {
        "history": history if isinstance(history, dict) else {},
        "health": health if isinstance(health, dict) else {"runs": [], "baseline": {}},
        "warnings": warnings,
        "stats": stats,
        "save_history": save_history,
        "site_sales": site_sales if isinstance(site_sales, dict) else None,
    }


def _visible(current_data):
    products = []
    for items in (current_data or {}).values():
        for item in items or []:
            if item_passes_filters(item):
                products.append(item)
    return products


def decorate_digest(
    digest,
    current_data,
    history,
    warnings,
    previous_data=None,
    today=None,
    site_sales=None,
    scanned_at=None,
):
    """Attach warnings, all-time lows, and cross-store groups. Never raises.

    Sets ``at_all_time_low`` on digest items so the email can badge them.
    Call this after the catalog has been saved; the flag is not stored in
    ``previous_data.json``.
    """
    if digest is None:
        return digest
    try:
        digest.warnings = list(warnings or [])
    except Exception as exc:
        logger.error("Could not attach store warnings (continuing): %s", exc)
        return digest
    try:
        products = _visible(current_data)
        lows = []
        for item in products:
            if all_time_low_status(item, history).get("flagged"):
                lows.append(item)
        digest.all_time_lows = lows
        flagged = {id(item) for item in lows}

        def stamp(item):
            if not isinstance(item, dict):
                return False
            is_low = id(item) in flagged or all_time_low_status(item, history).get("flagged")
            item["at_all_time_low"] = bool(is_low)
            return bool(is_low)

        for item in digest.new_items or []:
            stamp(item)
        for change in digest.drops or []:
            if not isinstance(change, dict):
                continue
            change["at_all_time_low"] = stamp(change.get("item") or {})
        digest.cross_store = cross_store_groups(products)
    except Exception as exc:
        logger.error("Price extras failed (continuing): %s", exc)
        if not getattr(digest, "all_time_lows", None):
            digest.all_time_lows = []
        if not getattr(digest, "cross_store", None):
            digest.cross_store = []
    try:
        hits, alerts = match_watchlist(
            _visible(current_data),
            previous=previous_data,
            history=history,
            today=today or _day(None),
        )
        digest.watch_hits = hits
        digest.watch_alerts = alerts
    except Exception as exc:
        logger.error("Watchlist match failed (continuing): %s", exc)
        digest.watch_hits = []
        digest.watch_alerts = []
    try:
        digest.site_sales = describe_sales(site_sales, today or _day(None))
        digest.sale_banners = sale_banners(
            site_sales,
            today or _day(None),
            scanned_at=scanned_at,
        )
    except Exception as exc:
        logger.error("Site-sale summary failed (continuing): %s", exc)
        digest.site_sales = []
        digest.sale_banners = []
    return digest
