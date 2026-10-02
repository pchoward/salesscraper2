"""Run each store on its own so one failure cannot stop the others."""

import logging
import signal

from stores.errors import StoreTimeout

logger = logging.getLogger("stores.runner")

# A store is up to four category pages. Selenium retries make a hung browser
# the thing this limit is for; Skate Deluxe is plain HTTP and finishes sooner.
DEFAULT_STORE_TIMEOUT = 720


def _groups(scrapers):
    order = []
    grouped = {}
    for scraper in scrapers or []:
        name = scraper.name
        if name not in grouped:
            order.append(name)
            grouped[name] = []
        grouped[name].append(scraper)
    return [(name, grouped[name]) for name in order]


def _key(scraper):
    return f"{scraper.name}_{scraper.part}"


def run_stores(scrapers, timeout=DEFAULT_STORE_TIMEOUT):
    """Scrape every store. Return ``(results, failed_keys)``.

    ``results[key]`` is a list, or None when that store/part failed or the
    store timed out before the part finished. A timeout or exception is
    logged here and does not leave this function.
    """
    results = {}
    failed = set()
    for name, batch in _groups(scrapers):
        logger.info("Starting store %s (%s parts)", name, len(batch))
        try:
            outcome = _run_one_store(name, batch, timeout)
        except Exception as exc:
            logger.error("Store %s crashed: %s", name, exc)
            outcome = {_key(scraper): None for scraper in batch}
        for key, items in outcome.items():
            results[key] = items
            if items is None:
                failed.add(key)
                logger.error("Recorded failure for %s", key)
            else:
                logger.info("Got %s items from %s", len(items), key)
        _log_counts(name, batch, outcome)
    return results, failed


def _log_counts(name, batch, outcome):
    for scraper in batch:
        key = _key(scraper)
        items = outcome.get(key)
        kept = None if items is None else len(items)
        logger.info(
            "%s before filters: %s candidates; after filters: %s",
            key,
            getattr(scraper, "candidates", 0),
            "failed" if kept is None else kept,
        )


def _run_one_store(name, batch, timeout):
    results = {}
    timed_out = False

    def _handle(signum, frame):
        raise StoreTimeout(f"{name} exceeded {int(timeout)}s")

    previous = signal.getsignal(signal.SIGALRM)
    signal.signal(signal.SIGALRM, _handle)
    signal.alarm(int(timeout))
    try:
        for scraper in batch:
            key = _key(scraper)
            logger.info("Scraping %s...", key)
            try:
                items = scraper.scrape()
            except StoreTimeout:
                raise
            except Exception as exc:
                logger.error("Failed to scrape %s: %s", key, exc)
                items = None
            if items is None:
                logger.warning("Scrape failed for %s", key)
            results[key] = items
    except StoreTimeout as exc:
        timed_out = True
        logger.error("Store timed out: %s", exc)
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, previous)
    if timed_out:
        for scraper in batch:
            results.setdefault(_key(scraper), None)
    return results
