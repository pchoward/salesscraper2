"""Safeguards carried over from codex/bmx-catalog-quality onto the current BMX
and Ski adapters:

* a sale product a store deliberately leaves out (no category, or the sport's
  rules reject it) is an intentional assortment change, not a retailer
  disappearance: no miss, no carry-over, no "removed"/"Disappeared", and its
  history is kept;
* a wheel size the store's tags and title disagree on is withheld.
"""

import copy
import json
import unittest

import sports
from history import apply_lifecycle, prune_price_history, record_misses, recently_gone
from report import compare_catalogs
from sports.bmx import specs, stores
from stores import shopify

KEY = "Powers BMX_Bikes"
PADSET = "https://www.powersbmx.com/products/padset"
BIKE = "https://www.powersbmx.com/products/mini"

FEED = {"products": [
    {"title": "Wing Padset", "vendor": "SE BIKES", "handle": "padset", "product_type": "Pad Sets",
     "variants": [{"id": 1, "price": "15.99", "compare_at_price": "25.99"}]},
    {"title": "Mini Race Bike", "vendor": "SE Bikes", "handle": "mini", "product_type": "Race BMX - Mini",
     "variants": [{"id": 2, "price": "299", "compare_at_price": "399"}]},
    {"title": "Logo Hoodie", "vendor": "Powers", "handle": "hoodie", "product_type": "Sweatshirts",
     "variants": [{"id": 3, "price": "40", "compare_at_price": "60"}]},
    {"title": "Full Price Pegs", "vendor": "Odyssey", "handle": "pegs", "product_type": "Pegs",
     "variants": [{"id": 4, "price": "30", "compare_at_price": "30"}]},
]}


def item(url, name, price):
    return {"name": name, "url": url, "price_new": price, "price_old": "399", "part": "Bikes", "store": "Powers BMX"}


def entry(name):
    return {"name": name, "store": "Powers BMX", "part": "Bikes", "prices": {"2026-11-01": 299.0},
            "first_seen": "2026-11-01", "last_seen": "2026-11-01", "stage": "new"}


class ExclusionTests(unittest.TestCase):
    def test_the_store_records_what_it_leaves_out_and_why(self):
        store = shopify.ShopifyStore("Powers BMX", "Powers BMX", "https://www.powersbmx.com", types=stores.TYPES,
                                     brand_of=stores.POWERS.brand_of, title_part=stores.title_part,
                                     unknown_by_title=True, track_exclusions=True)
        with sports.BMX.active():
            products = shopify.load_sale_products(store, fetch=lambda url: FEED if "page=1" in url else {"products": []},
                                                  sleep=lambda seconds: None)
            found = shopify.exclusions(store, products)
        self.assertEqual(set(found), {PADSET, "https://www.powersbmx.com/products/hoodie"},
                         "kept bikes and full-price items are not exclusions")
        self.assertTrue(all(reason.startswith("catalog scope: ") for reason in found.values()))
        self.assertIn("no category", found[PADSET])

    def test_only_opted_in_stores_track_exclusions(self):
        self.assertTrue(all(store.track_exclusions for store in stores.STORES))
        from sports.ski import stores as ski_stores
        self.assertTrue(all(store.track_exclusions for store in ski_stores.STORES))
        from stores import spot
        self.assertFalse(spot.SHOP.track_exclusions, "Skate stores are unchanged")
        self.assertEqual(shopify.ShopifyScraper(spot.SHOP, "Decks").catalog_scope_exclusions, {})


class HistoryTests(unittest.TestCase):
    def test_a_reclassified_listing_is_not_a_disappearance(self):
        previous = {KEY: [item(PADSET, "SE Bikes Wing Padset", "15.99"), item(BIKE, "SE Bikes Mini Race Bike", "299")]}
        current = {KEY: [item(BIKE, "SE Bikes Mini Race Bike", "299")]}
        history = {PADSET: entry("SE Bikes Wing Padset"), BIKE: entry("SE Bikes Mini Race Bike")}
        before = copy.deepcopy(history[PADSET]["prices"])
        excluded = {PADSET: "catalog scope: no category for product type 'Pad Sets'"}
        with sports.BMX.active():
            for day in ("2026-11-02", "2026-11-03"):
                carried = record_misses(previous, copy.deepcopy(current), history, today=day, scope_exclusions=excluded)
                self.assertNotIn(PADSET, carried, "not carried as if it might come back")
                pruned, stats = prune_price_history(history, today=day, current_data=current)
                self.assertIn(PADSET, pruned, "its price history is kept")
                apply_lifecycle(pruned, current, today=day)
                self.assertEqual(recently_gone(pruned, current, today=day), [], "not shown as Disappeared")
                history = pruned
            changes = compare_catalogs(previous, current, excluded_urls=excluded)
        self.assertNotIn("miss_streak", history[PADSET])
        self.assertEqual(history[PADSET]["prices"], before)
        self.assertEqual([change["type"] for change in changes.get(KEY, [])], [], "no 'removed' change")

    def test_a_real_disappearance_still_counts(self):
        previous = {KEY: [item(BIKE, "SE Bikes Mini Race Bike", "299")]}
        history = {BIKE: entry("SE Bikes Mini Race Bike")}
        with sports.BMX.active():
            carried = record_misses(previous, {KEY: []}, history, today="2026-11-02", scope_exclusions={})
            changes = compare_catalogs(previous, {KEY: []})
        self.assertIn(BIKE, carried, "a first miss is carried, as before")
        self.assertEqual(history[BIKE]["miss_streak"], 1)
        self.assertEqual([change["type"] for change in changes[KEY]], ["removed"])


class WheelSizeConflictTests(unittest.TestCase):
    def test_disagreeing_tag_and_title_withhold_the_size(self):
        self.assertIsNone(specs.wheel_size('Cult 20" Front Wheel', ['Wsize_22"']))
        self.assertEqual(specs.wheel_size('Cult 20" Front Wheel', ['Wsize_20"']), "20")
        self.assertEqual(specs.wheel_size("Cult Front Wheel", ['Wsize_22"']), "22")
        self.assertIsNone(specs.wheel_size("Cult Wheel", ['Wsize_20"', 'Wsize_22"']))


if __name__ == "__main__":
    unittest.main()
