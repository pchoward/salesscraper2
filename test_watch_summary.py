"""Email watchlist: only changed watched deals get cards (owner, 2026-11-16)."""

import datetime
import unittest

import notify
from report import Digest

WHEN = datetime.date(2026, 11, 16)


def _hit(name, note, reasons=()):
    return {"rule_id": note, "note": note, "reasons": list(reasons),
            "item": {"name": name, "store": "TGM", "url": f"https://example.com/{len(name)}",
                     "price_new": "69.95", "price_old": "96.95", "part": "Decks"}}


class WatchSummaryTests(unittest.TestCase):
    def setUp(self):
        heroin = "Heroin decks 8.6 inches and wider"
        powell = "Powell Peralta decks 8.6 inches and wider"
        self.digest = Digest(new_items=[{"name": "EDGLRD Koston Deck", "store": "Zumiez", "part": "Decks",
                                         "price_new": "59.99", "price_old": "77.95", "url": "https://z/1"}])
        self.digest.watch_hits = ([_hit(f"Heroin Deck {n}", heroin) for n in range(21)]
                                  + [_hit(f"Powell Deck {n}", powell) for n in range(4)]
                                  + [_hit("Heroin Swampy Egg 11", heroin, ["new on sale"])])
        self.digest.watch_alerts = [self.digest.watch_hits[-1]]

    def test_changed_deals_get_cards_unchanged_get_a_count(self):
        html = notify.render_html(self.digest, notify.DEFAULT_REPORT_URL, WHEN)
        self.assertIn("Heroin Swampy Egg 11", html)
        self.assertNotIn("Heroin Deck 3", html)
        self.assertNotIn("Powell Deck 0", html)
        self.assertIn("Heroin decks 8.6 inches and wider: <strong>21</strong>", html)
        self.assertIn("Powell Peralta decks 8.6 inches and wider: <strong>4</strong>", html)
        self.assertLess(html.index(": <strong>21</strong>"), html.index(": <strong>4</strong>"))
        plain = notify.render_plain(self.digest, notify.DEFAULT_REPORT_URL, WHEN)
        self.assertIn("- Heroin decks 8.6 inches and wider: 21", plain)
        self.assertNotIn("Powell Deck 0", plain)

    def test_unchanged_watch_deals_alone_send_no_email(self):
        digest = Digest()
        digest.watch_hits = [_hit("Heroin Deck 1", "Heroin decks")]
        digest.watch_alerts = []
        self.assertFalse(notify.should_send(digest))


if __name__ == "__main__":
    unittest.main()
