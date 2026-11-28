"""Store newsletters -> promo strip (owner, 2026-11-27): codes from stores we
can't scrape (Jenson USA, Dan's Comp, Competitive Cyclist), read from their
mail with the same rules as store pages."""

import datetime
import json
import unittest
import unittest.mock

import alerts_delivery
import promos

SENT = int(datetime.datetime(2026, 11, 26, 15, tzinfo=datetime.timezone.utc).timestamp())
TODAY = datetime.date(2026, 11, 27)


def mail(store, text, subject="Black Friday", received=SENT):
    return {"store": store, "received_at": received, "subject": subject, "text": text}


class NewsletterPromoTests(unittest.TestCase):
    def test_codes_from_mail(self):
        found = promos.newsletter_promos([
            mail("Jenson USA", "View this email in your browser. Take 20% off everything with code BLACKFRIDAY20 "
                               "at checkout. Ends 12/2. Sign up for texts and get 10% off with code TEXT10."),
            mail("Dan's Comp", "Extra 15% off sale items with code CYBER15. Offer valid through December 3."),
        ], TODAY)
        by_store = {p["store"]: p for p in found}
        self.assertEqual(set(by_store), {"Jenson USA", "Dan's Comp"})
        jenson = by_store["Jenson USA"]
        self.assertEqual((jenson["code"], jenson["percent"], jenson["ends"]), ("BLACKFRIDAY20", 20, "2026-12-02"))
        self.assertEqual((jenson["url"], jenson["sports"], jenson["source"]),
                         ("https://www.jensonusa.com/", ["mtb"], "email"))
        self.assertEqual((by_store["Dan's Comp"]["sports"], by_store["Dan's Comp"]["reach"]), (["bmx"], "sale items"))

    def test_sign_up_codes_and_unknown_stores_are_left_out(self):
        self.assertEqual(promos.newsletter_promos([
            mail("Jenson USA", "Join our newsletter. Get 10% off with code WELCOME10 on your first order."),
            mail("Someone Else", "50% off everything with code EVIL50."),
        ], TODAY), [])

    def test_lifetime(self):
        old = SENT - 9 * 86400
        found = promos.newsletter_promos([
            mail("Competitive Cyclist", "25% off sitewide with code GOBIKE25.", received=old),  # no end date, 9 days old
            mail("Jenson USA", "Cyber Monday: 25% off sitewide with code CM25. Ends tonight.", received=SENT - 86400),
            mail("Dan's Comp", "30% off sitewide with code DC30.", received=old),
        ], TODAY)
        self.assertEqual(found, [])

    def test_newest_mail_wins(self):
        found = promos.newsletter_promos([
            mail("Jenson USA", "20% off with code HOLIDAY. Ends 12/2.", received=SENT - 86400),
            mail("Jenson USA", "25% off with code HOLIDAY. Ends 12/5.", received=SENT),
        ], TODAY)
        self.assertEqual([(p["percent"], p["ends"]) for p in found], [(25, "2026-12-05")])

    def test_store_pages_keep_their_fixed_window(self):
        # A sign-up line right after a page's code still rules it out on pages.
        text = "Take 20% off with code BF20. Sign up for texts and get 10% off with code TEXT10."
        self.assertEqual(promos.find(text, TODAY), [])
        self.assertEqual([p["code"] for p in promos.find(text, TODAY, sentences=True)], ["BF20"])


class FetchTests(unittest.TestCase):
    ENV = {"NEWSLETTERS_ENABLED": "1", "ALERTS_API_URL": "https://alerts.example.test", "ALERTS_HMAC_SECRET": "h" * 40}

    def test_off_unless_enabled_and_configured(self):
        self.assertIsNone(promos.fetch_newsletters({}))
        self.assertIsNone(promos.fetch_newsletters({**self.ENV, "ALERTS_HMAC_SECRET": "short"}))

    def test_a_signed_request(self):
        seen = {}

        def transport(method, url, headers, body):
            seen.update(method=method, url=url, headers=headers)
            return 200, json.dumps({"newsletters": [mail("Jenson USA", "x")]}).encode()

        now = SENT
        result = promos.fetch_newsletters(self.ENV, transport=transport, now=now)
        self.assertEqual(result[0]["store"], "Jenson USA")
        path = f"/v1/internal/newsletters?since={now - promos.NEWSLETTER_LOOKBACK * 86400}"
        self.assertEqual(seen["url"], "https://alerts.example.test" + path)
        headers = seen["headers"]
        expected = alerts_delivery.signature("h" * 40, "GET", path, headers["X-SkateDeals-Timestamp"],
                                             headers["X-SkateDeals-Nonce"], b"")
        self.assertEqual(headers["X-SkateDeals-Signature"], expected)

    def test_handed_over_as_a_file(self):
        import os
        import tempfile
        path = os.path.join(tempfile.mkdtemp(), "mail.json")
        with unittest.mock.patch.object(promos, "fetch_newsletters", return_value=[mail("Jenson USA", "x")]):
            self.assertTrue(promos.save_newsletters(path))
        self.assertEqual(promos.saved_newsletters(path)[0]["store"], "Jenson USA")
        self.assertIsNone(promos.saved_newsletters(path + ".missing"))
        with unittest.mock.patch.object(promos, "fetch_newsletters", return_value=None):
            self.assertFalse(promos.save_newsletters(path + ".off"))
        self.assertFalse(os.path.exists(path + ".off"))

    def test_unreachable_is_skipped(self):
        self.assertIsNone(promos.fetch_newsletters(self.ENV, transport=lambda *a: (500, b"{}"), now=SENT))


if __name__ == "__main__":
    unittest.main()
