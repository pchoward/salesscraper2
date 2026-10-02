"""Shared scraper interface. Each store module subclasses ``Scraper``."""

import logging

from filters import filter_reason
from media import attach_listing_media

from stores.browser import fetch_page

logger = logging.getLogger("stores")


class Scraper:
    """One store and one part (Decks, Wheels, Trucks, or Bearings).

    ``scrape`` returns a list of kept items, or None when the fetch failed.
    A parser error inside one product is logged and skipped. ``candidates``
    counts listings that reached the shared filters; the returned list is
    what those filters kept.
    """

    def __init__(self, name, url, part):
        self.name = name
        self.url = url
        self.part = part
        self.candidates = 0

    def scrape(self):
        html = fetch_page(self.url)
        if not html:
            return None
        return self.parse(html)

    def _keep(self, name, url, price_new, price_old):
        self.candidates += 1
        reason = filter_reason(name, self.part, url, price_new, price_old)
        if reason:
            logger.info("Filtered out (%s): %s (%s)", self.part, name, reason)
            return False
        return True

    def _finish(self, item, node, base):
        try:
            attach_listing_media(item, node, base)
        except Exception as exc:
            logger.error("Listing media failed for %s: %s", item.get("url"), exc)
        return item

    def parse(self, html):
        raise NotImplementedError
