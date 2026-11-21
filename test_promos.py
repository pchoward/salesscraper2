"""Store-wide promo codes (owner, 2026-11-19): detected, kept, shown in emails."""

import datetime
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import notify
import promos
import sports
import sports_email
from report import Digest

from page import _promo_strip

TODAY = datetime.date(2026, 11, 19)
# Fanatik's Black Friday collection page, as served 2026-11-19 (trimmed).
FANATIK_BF = """<html><head>
<meta name="description" content="Save 20% on eligible mountain bike parts during Fanatik&#39;s Black Friday Sale.
Use code 2026-BFCM-20. Ends December 2, 2026.">
<script>var x = "use code FAKE99 for 99% off";</script></head><body>
<p>Sale Runs Nov 18 - Dec 2</p><h1>Fanatik Black Friday</h1>
<p>Save 20% on all eligible products with code 2026-BFCM-20</p>
<p>Discount applied at checkout. Some restrictions apply.</p>
<a href="/discount/2026-BFCM-20?redirect=%2Fcollections%2Ffanatik-black-friday">Apply discount code</a>
</body></html>"""
FANATIK_HOME = """<html><body>
<a href="/collections/fanatik-black-friday">Black Friday</a>
<a href="/pages/black-friday-cyber-monday-deals">BFCM deals</a>
<a href="/pages/sales">Sales</a> <a href="/collections/fanatik-outlet">Outlet</a>
<a href="/products/fox-36">Fox 36</a> <a href="https://other.example.com/black-friday">elsewhere</a>
<p>Join our newsletter and get 10% off your first order with code WELCOME10</p></body></html>"""


class FindTests(unittest.TestCase):
    def test_fanatik_black_friday(self):
        self.assertEqual(promos.find(FANATIK_BF, TODAY), [{"code": "2026-BFCM-20", "ends": "2026-12-02", "percent": 20}])

    def test_sales_and_not_sales(self):
        cases = {
            "Extra 25% off sale items with code CYBER25 through Dec 1": [("CYBER25", 25, None, "2026-12-01")],
            "Save $50 off orders over $300, use code BIG50. Ends 11/30": [("BIG50", None, 50, "2026-11-30")],
            "Use Code: SNOW15 for 15% off all goggles until January 5": [("SNOW15", 15, None, "2027-01-05")],
            "Get 10% off your first order with code WELCOME10": [],
            "Sign up for our newsletter and use code HELLO15 for 15% off": [],
            "Download our app: 20% off with code APP20": [],
            "Free shipping with code FREESHIP on orders over $50": [],
            "Military and first responders save 15% with code HERO15": [],
            "Use code below at checkout for 20% off": [],
            "Our code of conduct: 20% of profits go to trail building": [],
        }
        for text, expected in cases.items():
            got = [(p["code"], p.get("percent"), p.get("amount"), p["ends"]) for p in promos.find(f"<p>{text}</p>", TODAY)]
            self.assertEqual(got, expected, text)

    def test_nearest_discount_and_brand_scope(self):
        # Zeitbike's promotions page, 2026-11-20: a headline "up to 60%" for
        # dealers above the public 25% code, limited to one brand.
        page = ("<h2>GET UP TO 60% OFF KNOG BIKE LOCKS</h2><p>Dealers: Please log in using your wholesale account to "
                "see volume discounts up to 60%! Non Dealers: Get 25% Off on KNOG products. Enter discount code: "
                "KNOG25.</p><h2>GET UP TO 45% OFF FREETOWN HELMETS &amp; TRAILERS</h2>")
        found = promos.find(page, TODAY)
        self.assertEqual(found, [{"code": "KNOG25", "ends": "", "percent": 25, "applies_to": "KNOG products"}])
        self.assertEqual(promos.describe(found[0], code=False), "25% off KNOG products")
        # "on all eligible products" is store-wide, not a scope.
        self.assertNotIn("applies_to", promos.find(FANATIK_BF, TODAY)[0])

    def test_end_date_follows_its_own_code(self):
        page = ("<p>Pedals 40% off. Hurry, sale ends December 01, 2026!</p>"
                "<p>Fanatik Black Friday: 20% off. Enter Code: 2026-BFCM-20 at checkout. Hurry, sale ends December 02, 2026!</p>")
        self.assertEqual(promos.find(page, TODAY)[0]["ends"], "2026-12-02")

    def test_sale_links(self):
        links = promos.sale_links(FANATIK_HOME, "https://www.fanatikbike.com")
        self.assertEqual(links, ["https://www.fanatikbike.com/collections/fanatik-black-friday",
                                 "https://www.fanatikbike.com/pages/black-friday-cyber-monday-deals",
                                 "https://www.fanatikbike.com/pages/sales"])

    def test_describe(self):
        self.assertEqual(promos.describe({"code": "2026-BFCM-20", "percent": 20, "ends": "2026-12-02"}),
                         "20% off with code 2026-BFCM-20, until Dec 2")
        self.assertEqual(promos.describe({"code": "BIG50", "amount": 50, "ends": ""}), "$50 off with code BIG50")
        self.assertEqual(promos.describe({"code": "X20", "percent": 20, "ends": "2026-12-02"}, code=False),
                         "20% off, until Dec 2")


class ScanTests(unittest.TestCase):
    def test_scan_follows_sale_links_and_respects_robots(self):
        pages = {"https://www.fanatikbike.com/robots.txt": "User-agent: *\nDisallow: /pages/sales\n",
                 "https://www.fanatikbike.com/": FANATIK_HOME,
                 "https://www.fanatikbike.com/collections/fanatik-black-friday": FANATIK_BF,
                 "https://www.fanatikbike.com/pages/black-friday-cyber-monday-deals": "<p>Shop the sale</p>"}
        asked = []
        def fetch(url):
            asked.append(url)
            return pages[url]
        found, ok = promos.scan_store("Fanatik", "https://www.fanatikbike.com", fetch=fetch, sleep=lambda s: None,
                                      today=TODAY)
        self.assertTrue(ok)
        self.assertEqual([(p["store"], p["code"], p["url"]) for p in found],
                         [("Fanatik", "2026-BFCM-20", "https://www.fanatikbike.com/collections/fanatik-black-friday")])
        self.assertNotIn("https://www.fanatikbike.com/pages/sales", asked)

    def test_unreadable_store(self):
        def fetch(url):
            raise OSError("down")
        self.assertEqual(promos.scan_store("X", "https://x.example", fetch=fetch, sleep=lambda s: None), ([], False))

    def test_lifetime(self):
        old = {"store": "Fanatik", "code": "2026-BFCM-20", "percent": 20, "ends": "2026-12-02",
               "first_seen": "2026-11-18", "last_seen": "2026-11-18", "sports": ["mtb"]}
        gone = dict(old, store="Bike Mart", code="GONE10", ends="")
        unread = dict(old, store="Cambria", code="KEEP10", ends="")
        stale = dict(old, store="Albe's", code="OLD10", ends="", last_seen="2026-11-10")
        ended = dict(old, store="Evo", code="DONE", ends="2026-11-18")
        found = [dict(old, first_seen=None, last_seen=None)]
        result = promos.merge([old, gone, unread, stale, ended], found, {"Fanatik", "Bike Mart"}, TODAY)
        self.assertEqual([(p["store"], p["code"]) for p in result], [("Cambria", "KEEP10"), ("Fanatik", "2026-BFCM-20")])
        self.assertEqual(result[1]["first_seen"], "2026-11-18")
        self.assertEqual(result[1]["last_seen"], "2026-11-19")

    def test_run_writes_file_with_sports(self):
        with tempfile.TemporaryDirectory() as folder:
            path = str(Path(folder) / "promos.json")
            fetch = lambda url: FANATIK_BF if url.endswith("/") else ""
            current = promos.run({"https://www.fanatikbike.com": ("Fanatik", ["mtb"])}, today=TODAY, path=path,
                                 fetch=fetch, sleep=lambda s: None)
            self.assertEqual(current[0]["sports"], ["mtb"])
            saved = json.loads(Path(path).read_text())
            self.assertEqual(saved["promos"][0]["code"], "2026-BFCM-20")
            self.assertEqual(promos.for_sport("mtb", path=path)[0]["store"], "Fanatik")
            self.assertEqual(promos.for_sport("skate", path=path), [])

    def test_stores_of_scrapers(self):
        from sports.mtb import stores
        found = promos.stores_of([type("S", (), {"shop": stores.FANATIK})(), type("S", (), {"shop": stores.EVOC})()])
        self.assertEqual(found, {"Fanatik": "https://www.fanatikbike.com", "EVOC": "https://evocsports.us"})


class EmailTests(unittest.TestCase):
    PROMO = {"store": "Fanatik", "code": "2026-BFCM-20", "percent": 20, "ends": "2026-12-02", "sports": ["mtb"],
             "url": "https://www.fanatikbike.com/collections/fanatik-black-friday",
             "first_seen": "2026-11-19", "last_seen": "2026-11-19"}

    def test_skate_email_shows_promos(self):
        digest = Digest()
        digest.promos = [dict(self.PROMO, store="Tactics", sports=["skate"])]
        digest.new_promos = digest.promos
        self.assertTrue(notify.should_send(digest))
        html = notify.render_html(digest, notify.DEFAULT_REPORT_URL, TODAY)
        self.assertIn('data-section="promos"', html)
        self.assertIn("20% off, until Dec 2", html)
        self.assertEqual(html.count("2026-BFCM-20"), 1)
        self.assertIn("- Tactics: 20% off with code 2026-BFCM-20, until Dec 2",
                      notify.render_plain(digest, notify.DEFAULT_REPORT_URL, TODAY))
        quiet = Digest()
        quiet.promos = digest.promos
        quiet.new_promos = []
        self.assertFalse(notify.should_send(quiet))

    def test_sports_email_sends_for_a_new_code_alone(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "promos.json"
            path.write_text(json.dumps({"promos": [self.PROMO]}))
            env = {"SMTP_HOST": "smtp.resend.com", "SMTP_USER": "resend", "SMTP_PASSWORD": "x",
                   "EMAIL_FROM": "ShredDeals <alerts@shreddeals.com>", "EMAIL_TO": "owner@example.com"}
            with mock.patch.object(sports.Sport, "data_path", lambda sport: Path(folder) / sport.id), \
                    mock.patch.object(notify, "_smtp_send") as smtp:
                self.assertTrue(sports_email.send(["bmx", "ski", "mtb"], env=env, dry_run=False, when=TODAY,
                                                  promos_path=str(path)))
                message = smtp.call_args[0][1]
                self.assertEqual(message["Subject"], "ShredDeals MTB: 0 new, 0 price drops (Nov 19)")
                self.assertIn("2026-BFCM-20", message.get_body(("plain",)).get_content())
                smtp.reset_mock()
                self.assertFalse(sports_email.send(["bmx", "ski", "mtb"], env=env, dry_run=False,
                                                   when=datetime.date(2026, 11, 20), promos_path=str(path)))
                smtp.assert_not_called()


class WorkflowTests(unittest.TestCase):
    def test_promo_check_runs_before_each_scrape_and_commits_only_promos(self):
        text = (Path(__file__).parent / ".github/workflows/promo-check.yml").read_text(encoding="utf-8")
        self.assertIn("python promos.py", text)
        self.assertIn("group: scrape-${{ github.ref }}", text)
        adds = [line.strip() for line in text.splitlines() if "git add" in line]
        self.assertEqual(adds, ["git add promos.json"])
        self.assertNotIn("${{ secrets.", text)


if __name__ == "__main__":
    unittest.main()


class PromoStripTests(unittest.TestCase):
    def test_sport_promo_markup_and_expired_offers(self):
        offers = [
            {"store": "Fanatik & Co", "code": "LIVE", "percent": 20,
             "url": "https://example.test/", "ends": "2099-01-01"},
            {"store": "Old", "code": "EXPIRED", "amount": 10,
             "url": "https://example.test/", "ends": "2000-01-01"},
        ]
        with mock.patch("promos.for_sport", return_value=offers) as current:
            markup = _promo_strip("mtb")
        current.assert_called_once_with("mtb")
        self.assertIn("Fanatik &amp; Co", markup)
        self.assertIn("20% off", markup)
        self.assertIn("<code>LIVE</code>", markup)
        self.assertNotIn("EXPIRED", markup)
        with mock.patch("promos.for_sport", return_value=[]):
            self.assertEqual(_promo_strip("ski"), "")
