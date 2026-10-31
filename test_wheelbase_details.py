"""Deck wheelbase read from product pages once per listing and kept in history."""

import datetime
import json
import unittest

import re
import subprocess
from pathlib import Path

from dimensions import extract_specs
from history import _copy_media, _ordered_entry
from page import _specs_for
from part_specs import MIN_SPEC_COUNT
from report import build_report_html
from stores.details import RECHECK_DAYS, fill_wheelbases, page_text, pending

TODAY = "2026-10-30"


def _deck(store, url, name="Baker Brand Logo Deck 8.25", part="Decks"):
    return {"name": name, "url": url, "store": store, "part": part, "price_new": "49.99", "price_old": "69.99"}


def _history(*items):
    return {item["url"]: {"name": item["name"], "store": item["store"], "part": item["part"], "prices": {}} for item in items}


class FakeSite:
    def __init__(self, pages):
        self.pages = pages
        self.asked = []

    def __call__(self, url, accept):
        self.asked.append(url)
        return self.pages.get(url)


TACTICS = _deck("Tactics", "https://www.tactics.com/baker/brand-logo-deck")
SW = _deck("SkateWarehouse", "https://www.skatewarehouse.com/descpage-BAKER825.html")
CCS = _deck("CCS", "https://shop.ccs.com/products/real-oval-8-5", name="Real Oval Deck 8.5")
ZUMIEZ = _deck("Zumiez", "https://www.zumiez.com/baker-deck.html")
WHEELS = _deck("Tactics", "https://www.tactics.com/spitfire/f4", name="Spitfire F4 54mm", part="Wheels")


class WheelbaseDetailTests(unittest.TestCase):
    def test_pages_are_read_once_and_the_value_lands_in_history(self):
        site = FakeSite({
            TACTICS["url"]: "<html><script>var wb = 99;</script><div>Width: 8.25&quot; Wheelbase: 14.25&quot;</div></html>",
            SW["url"]: "<p>Steep concave. 7-ply.</p>",
            "https://shop.ccs.com/products/real-oval-8-5.js": json.dumps(
                {"description": "<ul><li>8.25\" x 31.8\" WB 14.25</li><li>8.5\" x 32\" WB 14.38</li></ul>"}),
        })
        current = {"Tactics_Decks": [TACTICS], "SkateWarehouse_Decks": [SW], "CCS_Decks": [CCS],
                   "Zumiez_Decks": [ZUMIEZ], "Tactics_Wheels": [WHEELS]}
        history = _history(TACTICS, SW, CCS, ZUMIEZ, WHEELS)
        read, found = fill_wheelbases(current, history, today=TODAY, fetch=site, sleep=lambda seconds: None)
        self.assertEqual((read, found), (3, 2))
        self.assertEqual(sorted(site.asked), sorted([TACTICS["url"], SW["url"], "https://shop.ccs.com/products/real-oval-8-5.js"]),
                         "Zumiez and wheels are never fetched")
        self.assertEqual(history[TACTICS["url"]]["wheelbase"], 14.25)
        self.assertEqual(TACTICS["wheelbase"], 14.25)
        self.assertEqual(history[CCS["url"]]["wheelbase"], 14.38, "a multi-size description pairs by the deck's width")
        self.assertNotIn("wheelbase", history[SW["url"]])
        self.assertEqual(history[SW["url"]]["wheelbase_checked"], TODAY)
        # The page reads it from history on later runs, when the item has none.
        self.assertEqual(_specs_for(dict(TACTICS, wheelbase=None), history[TACTICS["url"]])["wheelbase"], 14.25)

        # The next run fetches nothing: known values and recent "none" are both settled.
        fresh = {key: [dict(item, wheelbase=None) for item in items] for key, items in current.items()}
        site.asked.clear()
        self.assertEqual(fill_wheelbases(fresh, history, today=TODAY, fetch=site, sleep=lambda seconds: None), (0, 0))
        self.assertEqual(site.asked, [])
        # A page without one is tried again after RECHECK_DAYS.
        later = datetime.date.fromisoformat(TODAY) + datetime.timedelta(days=RECHECK_DAYS)
        self.assertEqual([url for _store, url, _item, _entry in pending(fresh, history, today=later)], [SW["url"]])
        self.assertEqual(pending(fresh, history, today=later - datetime.timedelta(days=1)), [])

    def test_a_failed_fetch_is_retried_and_failed_stores_are_skipped(self):
        site = FakeSite({})
        current = {"Tactics_Decks": [TACTICS], "SkateWarehouse_Decks": [SW]}
        history = _history(TACTICS, SW)
        self.assertEqual(fill_wheelbases(current, history, skip_keys={"SkateWarehouse_Decks"}, today=TODAY,
                                         fetch=site, sleep=lambda seconds: None), (0, 0))
        self.assertEqual(site.asked, [TACTICS["url"]])
        self.assertNotIn("wheelbase_checked", history[TACTICS["url"]], "unread pages are not marked checked")

    def test_the_budget_is_shared_store_by_store_and_requests_are_spaced(self):
        decks = [_deck("Tactics", f"https://www.tactics.com/d/{n}") for n in range(5)]
        decks += [_deck("SoCal", f"https://socalskateshop.com/d{n}.html") for n in range(5)]
        history = _history(*decks)
        current = {"Tactics_Decks": decks[:5], "SoCal_Decks": decks[5:]}
        order = [store for store, _url, _item, _entry in pending(current, history, today=datetime.date(2026, 10, 30))]
        self.assertEqual(order[:4], ["Tactics", "SoCal", "Tactics", "SoCal"])
        waits = []
        site = FakeSite({deck["url"]: "<p>Wheelbase: 14.25</p>" for deck in decks})
        fill_wheelbases(current, history, today=TODAY, fetch=site, sleep=waits.append, limit=4)
        self.assertEqual(len(site.asked), 4)
        self.assertTrue(any(wait > 4.9 for wait in waits), "SoCal's crawl delay is honored")

    def test_ccs_reads_the_product_data_and_bad_json_is_unread(self):
        site = FakeSite({"https://shop.ccs.com/products/real-oval-8-5.js": "not json"})
        self.assertIsNone(page_text("CCS", CCS["url"], site))

    def test_wheelbase_checked_survives_saving(self):
        entry = {"name": "x", "store": "Tactics", "part": "Decks", "prices": {}, "wheelbase": 14.25, "wheelbase_checked": TODAY}
        saved = _ordered_entry(entry)
        self.assertEqual((saved["wheelbase"], saved["wheelbase_checked"]), (14.25, TODAY))
        self.assertNotIn("wheelbase_checked", _ordered_entry(dict(entry, wheelbase_checked="soon")))



POWELL = 'Deck Specs: Width: 9.43" Length: 32.12" Wheelbase: 14" & 14.62"" Nose: 6.68" & 6.2" Tail: 6.5"'


class DualDrillingTests(unittest.TestCase):
    """Decks drilled for two wheelbases (Powell re-issues) keep both."""

    def test_one_label_listing_two_keeps_both(self):
        specs = extract_specs("Powell Peralta Mike Frazier Yellow Man Re-Issue Deck - Green", POWELL)
        self.assertEqual((specs["wheelbase"], specs["wheelbases"]), (14.0, [14.0, 14.62]))
        for text in ('Wheelbase: 14.25" or 14.5"', "WB 14.25 / 14.5", "Wheel Base: 14.25 and 14.5"):
            self.assertEqual(extract_specs("Deck", text)["wheelbases"], [14.25, 14.5], text)
        # One per size is not dual drilling.
        self.assertEqual(extract_specs("Baker Deck 8.25", '8.25" x 31.8" WB 14.25 | 8.5" x 32" WB 14.38')["wheelbases"], [])

    def test_both_reach_history_and_the_page(self):
        deck = _deck("SoCal", "https://socalskateshop.com/powell-frazier.html",
                     name="Powell Peralta Mike Frazier Yellow Man Re-Issue Deck 9.43")
        history = _history(deck)
        site = FakeSite({deck["url"]: f"<div>{POWELL}</div>"})
        fill_wheelbases({"SoCal_Decks": [deck]}, history, today=TODAY, fetch=site, sleep=lambda seconds: None)
        saved = _ordered_entry(history[deck["url"]])
        self.assertEqual((saved["wheelbase"], saved["wheelbases"]), (14.0, [14.0, 14.62]))
        copied = {}
        _copy_media(copied, deck)
        self.assertEqual(copied["wheelbases"], [14.0, 14.62])

        # The Wheelbase filter shows once enough decks have one (MIN_SPEC_COUNT).
        singles = [dict(_deck("SoCal", f"https://socalskateshop.com/poorhouse-{n}.html",
                              name=f"Poorhouse Pop Deck {n} 8.5x32.375"), wheelbase=14.5) for n in range(MIN_SPEC_COUNT)]
        html = build_report_html({"SoCal_Decks": [dict(deck, wheelbase=None)] + singles}, {},
                                 {deck["url"]: saved}, generated_at="2026-10-30T12:00:00+00:00")
        self.assertIn('data-wheelbase="14,14.62"', html)
        self.assertIn('data-wheelbase="14.5"', html)
        select = html.split('id="wheelbaseSelect"', 1)[1].split("</select>", 1)[0]
        self.assertEqual(re.findall(r'<option value="([^"]+)"', select), ["all", "14-14.25", "14.5-14.75"])
        # 14" is the 14–14.25 quarter. 14.5 and 14.62 share 14.5–14.75.
        # The empty quarter between them is not a chip.
        self.assertIn('data-value="14-14.25"', html)
        self.assertIn('data-value="14.5-14.75"', html)
        self.assertNotIn('data-value="14.25-14.5"', html)
        quarter = html.split('data-value="14-14.25"', 1)[1].split("</button>", 1)[0]
        self.assertIn(">1<", quarter)
        shared = html.split('data-value="14.5-14.75"', 1)[1].split("</button>", 1)[0]
        self.assertIn(f">{MIN_SPEC_COUNT + 1}<", shared)

    def test_the_filter_counts_and_quick_view_use_each_wheelbase(self):
        source = (Path(__file__).resolve().parent / "page.js").read_text(encoding="utf-8")
        helper = source[source.index("function wheelbaseList("):source.index("function kindMatch(")]
        match = source[source.index("function rowMatchesNow("):]
        self.assertIn("!wheelbaseAllowed(row, chosenWheels)", match[:match.index("\n}\n")])
        self.assertIn("wheelbaseList(row).forEach(wheel =>", source)
        self.assertIn('''addSpec("Wheelbase", String(dataset.wheelbase || "").split(",").filter(Boolean).join('" & '), '"');''', source)
        script = helper + r'''
const row = { dataset: { wheelbase: "14,14.62" } };
if (wheelbaseList(row).join("|") !== "14|14.62") throw new Error("split");
if (wheelbaseList({ dataset: {} }).length) throw new Error("empty");
if (["14", "14.62"].some(choice => wheelbaseList(row).indexOf(choice) < 0)) throw new Error("either value matches");
if (wheelbaseList(row).indexOf("14.6") >= 0) throw new Error("no partial match");
'''
        result = subprocess.run(["node", "-e", script], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
