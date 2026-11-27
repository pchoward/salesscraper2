"""The owner's answers on the Store monitor issue (#326, 2026-11-26): drop
SkatePro, let the Tactics Decks and Albe's Frames & Forks drops through,
show Tactics' Black Friday code, and read the Black Friday pages while the
sale lasts."""

import datetime
import unittest

import health
import promos
import sale_watch
from stores import skatewarehouse, tactics

TODAY = datetime.date(2026, 11, 26)


def _names(scrapers):
    return {getattr(getattr(s, "shop", None), "store", None) or getattr(s, "store", None) or getattr(s, "name", "")
            for s in scrapers}


class SkateProDroppedTests(unittest.TestCase):
    def test_no_sport_reads_skatepro(self):
        import sports.bmx.stores as bmx
        import sports.ski.stores as ski
        from stores.registry import build_scrapers
        for scrapers in (build_scrapers(), bmx.scrapers(), ski.scrapers()):
            self.assertNotIn("SkatePro", _names(scrapers))


class AcceptedDropTests(unittest.TestCase):
    def state(self, key):
        runs = [{"date": f"2026-11-{day:02d}", "results": {key: {"count": 50}}} for day in range(10, 26)]
        runs.append({"date": "2026-11-26", "results": {key: {"count": 4}}})
        return {"runs": runs}

    def test_a_confirmed_drop_restarts_the_baseline(self):
        for key, day, samples in (("Albe's BMX_Frames & Forks", "2026-11-27", 1), ("Tactics_Decks", "2026-11-28", 0)):
            self.assertIn(key, health.ACCEPTED_DROPS)
            state = self.state(key)
            self.assertEqual(health.rolling_baseline(state, key, day)["baseline_samples"], samples)
            result = health.assess_run({key: [{}] * 4}, [], state, day)[key]
            self.assertFalse(result["failed"])  # listed, not held
            self.assertEqual(result["count"], 4)

    def test_other_keys_are_still_guarded(self):
        state = self.state("Zumiez_Wheels")
        result = health.assess_run({"Zumiez_Wheels": [{}] * 4}, [], state, "2026-11-27")["Zumiez_Wheels"]
        self.assertTrue(result["failed"])
        self.assertEqual(result["diagnostics"]["reason"], "partial_catalog_drop")


class BlackFridayPageTests(unittest.TestCase):
    INFO = ('<a href="/black-friday-sale/skate">Skate</a><a href="/tactics/black-friday-sale/skateboard-decks/">Decks</a>'
            '<a href="/black-friday-sale/snowboard">Snow</a><a href="https://www.tactics.com/black-friday-sale/mens-shoes">'
            'Shoes</a>')

    def setUp(self):
        tactics._black_friday.clear()

    def tearDown(self):
        tactics._black_friday.clear()

    def test_tactics_reads_only_its_shoe_grids_while_the_sale_lasts(self):
        fetch = lambda url: (url, self.INFO)
        # Skate grids aren't read (2026-11-27): their 20% is the code on full-price items.
        self.assertEqual(tactics.black_friday_urls("skate", fetch, TODAY), [])
        self.assertEqual(tactics.black_friday_urls("shoes", fetch, TODAY),
                         ["https://www.tactics.com/black-friday-sale/mens-shoes"])
        self.assertEqual(tactics.black_friday_urls("shoes", fetch, tactics.BLACK_FRIDAY_UNTIL), [])

    def test_a_gone_info_page_adds_nothing(self):
        self.assertEqual(tactics.black_friday_urls("skate", lambda url: (None, None), TODAY), [])

    def test_skatewarehouse_black_friday_until_the_sale_ends(self):
        self.assertEqual(skatewarehouse.seasonal(TODAY), (skatewarehouse.BLACK_FRIDAY,))
        self.assertEqual(skatewarehouse.seasonal(skatewarehouse.BLACK_FRIDAY_UNTIL), ())
        self.assertIn(skatewarehouse.BLACK_NOVEMBER, skatewarehouse.PROMO_URLS["Decks"])

    def test_sale_watch_counts_promo_pages_as_read(self):
        home = ('<a href="/catpage-BFCM26PORT.html">Black Friday Sale</a>'
                '<a href="/Black_November_Sale__Up_To_60_Off/catpage-BNSALE.html">Up to 60% Off</a>'
                '<a href="/Cyber_Monday/catpage-CYBER26.html">Cyber Monday deals</a>')
        fetch = lambda url: "User-agent: *\nDisallow:\n" if url.endswith("robots.txt") else home
        found = sale_watch.homepage_links("https://www.skatewarehouse.com/",
                                          [skatewarehouse.BLACK_NOVEMBER, skatewarehouse.BLACK_FRIDAY], fetch)
        self.assertEqual([entry["label"] for entry in found], ["Cyber Monday deals"])


class TacticsCodeTests(unittest.TestCase):
    def test_promo_check_follows_the_info_page(self):
        home = '<a href="/info/black-friday">Black Friday</a><a href="/info/shipping">Shipping</a>'
        self.assertEqual(promos.sale_links(home, "https://www.tactics.com"), ["https://www.tactics.com/info/black-friday"])
        found = promos.find("<h1>Black Friday Sale</h1><p>20% Off With Code: BFCM26</p><p>Ends Dec 1.</p>", TODAY)
        self.assertEqual(promos.describe(found[0]), "20% off with code BFCM26, until Dec 1")


if __name__ == "__main__":
    unittest.main()
