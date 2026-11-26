"""Monthly specialist shop check (owner, 2026-11-26): our MTB product types
that no MTB-only shop sells, like front derailleurs, are listed for the
store monitor to triage. Nothing on the page changes."""

import json
import os
import tempfile
import unittest

import specialist_check as check
from stores import shopify

SPECIALIST = [
    {"title": "SRAM GX Eagle Rear Derailleur", "product_type": "Rear Derailleurs", "vendor": "SRAM"},
    {"title": "Maxxis Minion DHF Folding Tire", "product_type": "Tires", "vendor": "Maxxis"},
    {"title": "OneUp Dropper Post V3", "product_type": "Seatposts", "vendor": "OneUp Components"},
]


def item(name, store, kind, part="Drivetrain"):
    return {"name": name, "store": store, "product_type": kind, "part": part}


DATA = {
    "Cambria_Drivetrain": [item(f"Shimano Altus Front Derailleur {n}", "Cambria", "MTB Front Derailleurs")
                           for n in range(4)]
                          + [item(f"SRAM GX Rear Derailleur {n}", "Cambria", "MTB Rear Derailleurs") for n in range(4)],
    "Cambria_Tires": [item(f"Maxxis Assegai {n}", "Cambria", "MTB Tires Folding", "Tires") for n in range(5)],
    "Bike Mart_Cockpit": [item(f"Origin8 Stem Riser {n}", "Bike Mart", "Stem Riser", "Cockpit") for n in range(2)],
    "Fanatik_Drivetrain": [item(f"Fanatik Front Derailleur {n}", "Fanatik", "Front Derailleurs") for n in range(5)],
}


class KeyWordTests(unittest.TestCase):
    def test_filing_paths_and_generic_words_are_dropped(self):
        self.assertEqual(check.key_words("COMPONENTS/DERAILLEURS/FRONT DERAILLEURS MTB"), ["front", "derailleur"])
        self.assertEqual(check.key_words("MTB Tires Folding"), ["tire", "folding"])
        self.assertEqual(check.key_words("Accessories"), [])

    def test_any_word_order_counts_as_sold(self):
        bags = check.word_bags(SPECIALIST)
        self.assertTrue(check.sold_by_specialists("MTB Tires Folding", bags))
        self.assertFalse(check.sold_by_specialists("MTB Front Derailleurs", bags))
        self.assertIsNone(check.sold_by_specialists("MTB Parts", bags))


class CompareTests(unittest.TestCase):
    def test_flags_only_types_no_specialist_sells(self):
        flagged = check.compare(DATA, {"Fanatik": SPECIALIST})
        self.assertEqual([(e["store"], e["product_type"]) for e in flagged], [("Cambria", "MTB Front Derailleurs")])
        self.assertEqual(flagged[0]["listings"], 4)
        self.assertEqual(len(flagged[0]["samples"]), check.SAMPLES)
        self.assertTrue(flagged[0]["new"])

    def test_small_groups_and_the_specialists_own_listings_are_skipped(self):
        names = {e["store"] for e in check.compare(DATA, {"Fanatik": SPECIALIST})}
        self.assertNotIn("Bike Mart", names)  # 2 listings, under MIN_LISTINGS
        self.assertNotIn("Fanatik", names)

    def test_last_months_findings_are_not_new(self):
        previous = {"flagged": [{"store": "Cambria", "product_type": "MTB Front Derailleurs"}]}
        self.assertFalse(check.compare(DATA, {"Fanatik": SPECIALIST}, previous)[0]["new"])


class Store:
    def __init__(self, name):
        self.store, self.base, self.cache = name, f"https://{name.lower()}.example", {}


class CatalogTests(unittest.TestCase):
    def policy(self, body):
        from urllib import robotparser
        parser = robotparser.RobotFileParser()
        parser.parse(body.splitlines())
        return parser, 0

    def test_reads_pages_until_a_short_one(self):
        store = Store("Shop")
        store.cache["robots"] = self.policy("User-agent: *\nDisallow:\n")
        sizes = {1: shopify.PAGE_LIMIT, 2: 3}
        urls = []

        def fetch(url):
            urls.append(url)
            page = int(url.rsplit("page=", 1)[1])
            return {"products": [{"title": f"P{page}-{n}", "product_type": "Tires", "vendor": "X", "variants": []}
                                 for n in range(sizes[page])]}

        products = check.read_catalog(store, fetch, sleep=lambda _: None)
        self.assertEqual(len(products), shopify.PAGE_LIMIT + 3)
        self.assertEqual(set(products[0]), {"title", "product_type", "vendor"})
        self.assertEqual(len(urls), 2)

    def test_robots_disallow_means_no_request(self):
        store = Store("Shop")
        store.cache["robots"] = self.policy("User-agent: *\nDisallow: /products.json\n")
        calls = []
        self.assertIsNone(check.read_catalog(store, lambda url: calls.append(url), sleep=lambda _: None))
        self.assertEqual(calls, [])


class RunTests(unittest.TestCase):
    def test_writes_the_report_and_names_unread_shops(self):
        with tempfile.TemporaryDirectory() as folder:
            with open(os.path.join(folder, check.DATA), "w") as handle:
                json.dump(DATA, handle)
            read = lambda store: SPECIALIST if store.store == "Fanatik" else None
            report = check.run(folder, "2026-12-02", read)
            with open(os.path.join(folder, check.REPORT)) as handle:
                self.assertEqual(json.load(handle), report)
        self.assertEqual(report["specialists"], {"Fanatik": 3})
        self.assertEqual(report["unread"], ["Worldwide Cyclery", "The Lost Co."])
        self.assertIn("NEW Cambria / MTB Front Derailleurs (4)", check.markdown(report))

    def test_an_unread_specialist_is_still_not_compared(self):
        data = {"Worldwide Cyclery_Drivetrain": [item(f"Front Derailleur {n}", "Worldwide Cyclery", "Front Derailleurs")
                                                 for n in range(5)]}
        self.assertEqual(check.compare(data, {"Fanatik": SPECIALIST}, skip_stores=["Worldwide Cyclery"]), [])

    def test_nothing_written_when_no_shop_can_be_read(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertIsNone(check.run(folder, "2026-12-02", lambda store: None))
            self.assertFalse(os.path.exists(os.path.join(folder, check.REPORT)))


if __name__ == "__main__":
    unittest.main()
