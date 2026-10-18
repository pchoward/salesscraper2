"""Listing identity in price history: URL churn, URL reuse, variants, and the audit."""

import copy
import datetime
import unittest

from history import (
    GONE_AFTER_MISSES,
    MAX_IDENTITY_NOTES,
    all_time_low_status,
    prune_price_history,
    reconcile_moved_urls,
    record_misses,
    update_price_history,
)
from history_identity import audit_history, listing_identity, size_signature, sizes_conflict

TODAY = datetime.date(2026, 10, 18)

CCS_OLD = "https://shop.ccs.com/collections/clearance/products/polar-aaron-herrington-cowboy-cop-skateboard-deck-8-25"
CCS_NEW = "https://shop.ccs.com/products/polar-aaron-herrington-cowboy-cop-skateboard-deck-8-25"
CCS_SALE = "https://shop.ccs.com/collections/sale/products/polar-aaron-herrington-cowboy-cop-skateboard-deck-8-25"
CCS_WIDER = "https://shop.ccs.com/collections/clearance/products/polar-aaron-herrington-cowboy-cop-skateboard-deck-8-625"
SW_PAIR = "https://www.skatewarehouse.com/Independent_Eric_Dressen_Stage_4_Hollow_Truck/descpage-INED4TR.html?color=BK"
SW_SINGLE = "https://www.skatewarehouse.com/SINGLE_Indy_Dressen_Stage_4_Hollow_Truck/descpage-INED4TR.html?color=BK"
SW_DECK = "https://www.skatewarehouse.com/Deathwish_Pedro_Delfino_Slam_Deck/descpage-DWPDSMDK.html"
ZUMIEZ = "https://www.zumiez.com/edglrd-tech-script-8-25-skateboard-deck.html"
ZUMIEZ_TWIN = "https://www.zumiez.com/edglrd-tech-script-8-25-skateboard-deck-1.html"
TACTICS_22 = "https://www.tactics.com/ace/af-1-hollow-skateboard-trucks/polished-silver-22"
TACTICS_33 = "https://www.tactics.com/ace/af-1-hollow-skateboard-trucks/polished-silver-33"


def _day(offset):
    return (TODAY + datetime.timedelta(days=offset)).isoformat()


def _item(url, name, price, store="CCS", part="Decks", old="99.95"):
    return {"url": url, "name": name, "price_new": price, "price_old": old, "store": store, "part": part}


def _catalog(*items):
    catalog = {}
    for item in items:
        catalog.setdefault(f"{item['store']}_{item['part']}", []).append(item)
    return catalog


def _run(history, days):
    """Feed ``[(offset, catalog), ...]`` through the daily path the scraper uses."""
    previous = None
    for offset, catalog in days:
        current = copy.deepcopy(catalog)
        carried = record_misses(previous, current, history) if previous is not None else set()
        update_price_history(current, history, today=_day(offset), skip_urls=carried)
        previous = current
    return history


COWBOY = "Polar Aaron Herrington Cowboy Cop Skateboard Deck"


class ListingIdentityTests(unittest.TestCase):
    def test_shopify_handle_is_the_same_product_under_any_collection(self):
        old, new, sale = (listing_identity(url) for url in (CCS_OLD, CCS_NEW, CCS_SALE))
        self.assertEqual(old["basis"], "shopify-handle")
        self.assertEqual(old["key"], new["key"])
        self.assertEqual(old["key"], sale["key"])
        self.assertNotEqual(old["key"], listing_identity(CCS_WIDER)["key"])

    def test_shopify_url_with_a_query_is_only_its_url(self):
        identity = listing_identity(CCS_NEW + "?variant=4412")
        self.assertEqual(identity["basis"], "url")
        self.assertEqual(identity["key"], CCS_NEW + "?variant=4412")

    def test_retailer_codes_and_variants_never_widen_the_key(self):
        pair, single = listing_identity(SW_PAIR), listing_identity(SW_SINGLE)
        self.assertEqual(pair["retailer_code"], "INED4TR")
        self.assertEqual(single["retailer_code"], "INED4TR")
        self.assertEqual(pair["variant"], "BK")
        self.assertNotEqual(pair["key"], single["key"])
        self.assertEqual(listing_identity(TACTICS_22)["variant"], "polished-silver-22")
        self.assertNotEqual(listing_identity(TACTICS_22)["key"], listing_identity(TACTICS_33)["key"])
        self.assertEqual(listing_identity(ZUMIEZ_TWIN)["variant"], "-1")
        self.assertNotEqual(listing_identity(ZUMIEZ)["key"], listing_identity(ZUMIEZ_TWIN)["key"])
        self.assertEqual(listing_identity(" https://example.com/x ")["key"], "https://example.com/x")
        self.assertEqual(listing_identity(None)["key"], "")

    def test_size_signature_and_conflicts(self):
        narrow = size_signature("Deathwish Pedro Delfino Slam Deck 8.25 x 31.5", "Decks")
        wide = size_signature("Deathwish Pedro Delfino Slam Deck 8.5 x 31.875", "Decks")
        self.assertEqual(sizes_conflict(narrow, wide), {"width": ('8.25"', '8.5"')})
        rounded = size_signature('Deathwish Pedro Delfino Slam 8.125" Deck', "Decks")
        self.assertEqual(sizes_conflict(rounded, size_signature("Deathwish Pedro Delfino Slam Deck 8.12 x 31.5", "Decks")), {})
        self.assertEqual(sizes_conflict(narrow, size_signature(COWBOY, "Decks")), {})


class UrlChurnTests(unittest.TestCase):
    def _old_history(self):
        history = {}
        _run(
            history,
            [
                (-20, _catalog(_item(CCS_OLD, COWBOY, "59.95"))),
                (-12, _catalog(_item(CCS_OLD, COWBOY, "49.95"))),
                (-2, _catalog(_item(CCS_OLD, COWBOY, "54.95"))),
            ],
        )
        return history

    def test_shopify_path_change_keeps_history(self):
        history = self._old_history()
        _run(
            history,
            [
                (-2, _catalog(_item(CCS_OLD, COWBOY, "54.95"))),
                (-1, _catalog(_item(CCS_NEW, COWBOY, "49.95"))),
                (0, _catalog(_item(CCS_NEW, COWBOY, "49.95"))),
            ],
        )
        self.assertNotIn(CCS_OLD, history)
        entry = history[CCS_NEW]
        self.assertEqual(entry["previous_urls"], [CCS_OLD])
        self.assertEqual(entry["first_seen"], _day(-20))
        self.assertEqual(entry["observation_count"], 5)
        self.assertEqual(entry["all_time_low"], 49.95)
        self.assertEqual(entry["all_time_low_date"], _day(-12))
        self.assertTrue(all_time_low_status(_item(CCS_NEW, COWBOY, "49.95"), history)["flagged"])

    def test_moved_listing_is_not_a_miss_or_a_phantom_row(self):
        history = self._old_history()
        current = _catalog(_item(CCS_NEW, COWBOY, "49.95"))
        carried = record_misses(_catalog(_item(CCS_OLD, COWBOY, "54.95")), current, history)
        self.assertEqual(carried, set())
        self.assertEqual([item["url"] for item in current["CCS_Decks"]], [CCS_NEW])
        self.assertNotIn("miss_streak", history[CCS_NEW])
        update_price_history(current, history, today=_day(-1))
        record_misses(current, _catalog(_item(CCS_NEW, COWBOY, "49.95")), history)
        self.assertEqual(sorted(history), [CCS_NEW])

    def test_no_move_while_the_old_url_is_still_listed(self):
        history = self._old_history()
        _run(history, [(-1, _catalog(_item(CCS_OLD, COWBOY, "54.95"), _item(CCS_NEW, COWBOY, "49.95")))])
        self.assertIn(CCS_OLD, history)
        self.assertEqual(history[CCS_NEW]["observation_count"], 1)
        self.assertNotIn("previous_urls", history[CCS_NEW])

    def test_no_move_when_two_old_rows_share_the_handle(self):
        history = self._old_history()
        history[CCS_SALE] = copy.deepcopy(history[CCS_OLD])
        moves = reconcile_moved_urls(history, _catalog(_item(CCS_NEW, COWBOY, "49.95")))
        self.assertEqual(moves, [])
        self.assertIn(CCS_OLD, history)
        self.assertIn(CCS_SALE, history)

    def test_no_move_into_a_url_that_already_has_history(self):
        history = self._old_history()
        history[CCS_NEW] = {"name": COWBOY, "store": "CCS", "part": "Decks", "prices": {_day(-30): 70.0}}
        self.assertEqual(reconcile_moved_urls(history, _catalog(_item(CCS_NEW, COWBOY, "49.95"))), [])
        self.assertIn(CCS_OLD, history)

    def test_no_move_across_parts_or_stores(self):
        history = self._old_history()
        history[CCS_OLD]["part"] = "Accessories"
        self.assertEqual(reconcile_moved_urls(history, _catalog(_item(CCS_NEW, COWBOY, "49.95"))), [])
        history[CCS_OLD]["part"] = "Decks"
        history[CCS_OLD]["store"] = "Muir Skate"
        self.assertEqual(reconcile_moved_urls(history, _catalog(_item(CCS_NEW, COWBOY, "49.95"))), [])

    def test_failed_scrape_or_carried_listing_does_not_trigger_a_move(self):
        history = self._old_history()
        catalog = _catalog(_item(CCS_NEW, COWBOY, "49.95"))
        self.assertEqual(reconcile_moved_urls(history, catalog, skip_keys=["CCS_Decks"]), [])
        self.assertEqual(reconcile_moved_urls(history, catalog, skip_urls=[CCS_NEW]), [])
        self.assertIn(CCS_OLD, history)


class NoFalseMergeTests(unittest.TestCase):
    def test_conflicting_retailer_code_keeps_pair_and_single_apart(self):
        # Seen in the catalog: a pair at $29.98, later a SINGLE at $15.00, same code.
        history = {}
        pair = "Independent Eric Dressen Stage 4 Hollow Truck Black"
        single = "SINGLE Indy Dressen Stage 4 Hollow Truck Black"
        days = [(offset, _catalog(_item(SW_PAIR, pair, "29.98", "SkateWarehouse", "Trucks", "59.95"))) for offset in (-30, -20, -10)]
        days += [(offset, _catalog(_item(SW_SINGLE, single, "15.00", "SkateWarehouse", "Trucks", "30.00"))) for offset in (-8, 0)]
        _run(history, days)
        self.assertEqual(history[SW_PAIR]["all_time_low"], 29.98)
        self.assertEqual(history[SW_SINGLE]["observation_count"], 2)
        self.assertNotIn("previous_urls", history[SW_SINGLE])
        self.assertFalse(all_time_low_status(_item(SW_SINGLE, single, "15.00", "SkateWarehouse", "Trucks"), history)["flagged"])

    def test_same_name_variants_and_twins_stay_apart(self):
        history = {}
        _run(
            history,
            [
                (
                    offset,
                    _catalog(
                        _item(CCS_OLD, COWBOY, "49.95"),
                        _item(CCS_WIDER, COWBOY, "59.95"),
                        _item(ZUMIEZ, 'EDGLRD Tech Script 8.25" Skateboard Deck', "39.99", "Zumiez"),
                        _item(ZUMIEZ_TWIN, 'EDGLRD Tech Script 8.25" Skateboard Deck', "44.99", "Zumiez"),
                        _item(TACTICS_22, "Ace AF-1 Hollow Skateboard Trucks - polished silver 22", "64.95", "Tactics", "Trucks"),
                        _item(TACTICS_33, "Ace AF-1 Hollow Skateboard Trucks - polished silver 33", "69.95", "Tactics", "Trucks"),
                    ),
                )
                for offset in (-3, -2, -1)
            ],
        )
        self.assertEqual(len(history), 6)
        for url in history:
            self.assertEqual(history[url]["observation_count"], 3, url)
            self.assertNotIn("previous_urls", history[url])
        self.assertEqual(history[CCS_WIDER]["all_time_low"], 59.95)
        self.assertEqual(history[ZUMIEZ_TWIN]["all_time_low"], 44.99)

    def test_equal_name_at_a_new_non_shopify_url_starts_its_own_history(self):
        history = {}
        name = 'EDGLRD Tech Script 8.25" Skateboard Deck'
        _run(
            history,
            [
                (-20, _catalog(_item(ZUMIEZ, name, "39.99", "Zumiez"))),
                (-19, _catalog(_item(ZUMIEZ, name, "39.99", "Zumiez"))),
                (-1, _catalog(_item(ZUMIEZ_TWIN, name, "44.99", "Zumiez"))),
                (0, _catalog(_item(ZUMIEZ_TWIN, name, "44.99", "Zumiez"))),
            ],
        )
        self.assertIn(ZUMIEZ, history)
        self.assertEqual(history[ZUMIEZ_TWIN]["first_seen"], _day(-1))


class SizeChangeOnSameUrlTests(unittest.TestCase):
    NARROW = "Deathwish Pedro Delfino Slam Deck 8.25 x 31.5"
    WIDE = "Deathwish Pedro Delfino Slam Deck 8.5 x 31.875"

    def _sw(self, name, price):
        return _catalog(_item(SW_DECK, name, price, "SkateWarehouse", "Decks", "89.95"))

    def test_width_change_restarts_the_series(self):
        # The real case: this URL sold the 8.25 at $64.98, then the 8.5 at $69.98.
        history = {}
        _run(history, [(offset, self._sw(self.NARROW, "64.98")) for offset in (-40, -30, -20)])
        _run(history, [(offset, self._sw(self.WIDE, "69.98")) for offset in (-10, -5)])
        entry = history[SW_DECK]
        self.assertEqual(entry["all_time_low"], 69.98)
        self.assertEqual(entry["first_seen"], _day(-10))
        self.assertEqual(entry["observation_count"], 2)
        self.assertEqual(sorted(entry["prices"]), [_day(-10), _day(-5)])
        earlier = entry["earlier_products"]
        self.assertEqual(len(earlier), 1)
        self.assertEqual(earlier[0]["name"], self.NARROW)
        self.assertEqual(earlier[0]["all_time_low"], 64.98)
        self.assertEqual(earlier[0]["observation_count"], 3)
        self.assertEqual(earlier[0]["replaced_on"], _day(-10))
        self.assertEqual(earlier[0]["reason"], 'width 8.25" -> 8.5"')
        # The new size is not an all-time low until it has its own 3 observations over 7 days.
        self.assertFalse(all_time_low_status(_item(SW_DECK, self.WIDE, "69.98"), history)["flagged"])
        _run(history, [(0, self._sw(self.WIDE, "69.98"))])
        self.assertTrue(all_time_low_status(_item(SW_DECK, self.WIDE, "69.98"), history)["flagged"])

    def test_wheel_and_truck_size_changes_restart(self):
        cases = [
            ("Wheels", "Spitfire Formula Four Classic 53mm 99a Wheels", "Spitfire Formula Four Classic 54mm 99a Wheels"),
            ("Wheels", "Spitfire Formula Four Classic 53mm 99a Wheels", "Spitfire Formula Four Classic 53mm 101a Wheels"),
            ("Trucks", "Independent Stage 11 Hollow 149 Truck", "Independent Stage 11 Hollow 144 Truck"),
        ]
        for part, before, after in cases:
            history = {}
            url = f"https://www.zumiez.com/{part.lower()}.html"
            _run(history, [(-3, _catalog(_item(url, before, "40.00", "Zumiez", part, "60.00")))])
            _run(history, [(-1, _catalog(_item(url, after, "45.00", "Zumiez", part, "60.00")))])
            self.assertEqual(history[url]["earlier_products"][0]["name"], before, part)
            self.assertEqual(history[url]["observation_count"], 1, part)

    def test_renames_without_a_size_change_keep_history(self):
        cases = [
            # Seen in the catalog: the pro name was reworded on the same URL.
            ('Anti-Hero Van Der Linden I Farted In Yoga 8.38" Skateboard Deck', 'Anti-Hero Daan I Farted In Yoga 8.38" Skateboard Deck'),
            ('Baker Figgy Divine Evil 8.125" Deck', "Baker Figgy Divine Evil Deck 8.12 x 31.875"),
            # A name with no size cannot conflict with one that has a size.
            (COWBOY, "Polar Aaron Herrington Cowboy Cop Skateboard Deck 8.25"),
        ]
        for before, after in cases:
            history = {}
            url = "https://www.zumiez.com/renamed.html"
            _run(history, [(-3, _catalog(_item(url, before, "50.00", "Zumiez")))])
            _run(history, [(-1, _catalog(_item(url, after, "45.00", "Zumiez")))])
            self.assertNotIn("earlier_products", history[url], before)
            self.assertEqual(history[url]["observation_count"], 2, before)


class RetentionTests(unittest.TestCase):
    def test_prune_keeps_identity_notes_and_bounds_them(self):
        history = {
            CCS_NEW: {
                "name": COWBOY,
                "store": "CCS",
                "part": "Decks",
                "first_seen": _day(-200),
                "last_seen": _day(-1),
                "observation_count": 40,
                "all_time_low": 39.95,
                "all_time_low_date": _day(-150),
                "previous_urls": [f"https://shop.ccs.com/collections/c{i}/products/x" for i in range(8)],
                "earlier_products": [{"name": "old", "replaced_on": _day(-100)}],
                "prices": {_day(-120): 39.95, _day(-1): 49.95},
            }
        }
        catalog = _catalog(_item(CCS_NEW, COWBOY, "49.95"))
        pruned, _stats = prune_price_history(history, today=TODAY, current_data=catalog)
        entry = pruned[CCS_NEW]
        self.assertEqual(len(entry["previous_urls"]), MAX_IDENTITY_NOTES)
        self.assertEqual(entry["previous_urls"][-1], "https://shop.ccs.com/collections/c7/products/x")
        self.assertEqual(entry["earlier_products"], [{"name": "old", "replaced_on": _day(-100)}])
        self.assertEqual(list(entry["prices"]), [_day(-1)])
        self.assertEqual(entry["all_time_low"], 39.95)
        again, _stats = prune_price_history(pruned, today=TODAY, current_data=catalog)
        self.assertEqual(again, pruned)

    def test_rows_that_normalize_together_merge_their_notes(self):
        history = {
            CCS_NEW: {"name": COWBOY, "store": "CCS", "part": "Decks", "previous_urls": [CCS_OLD], "prices": {_day(-2): 50.0}},
            CCS_NEW + " ": {"name": COWBOY, "store": "CCS", "part": "Decks", "previous_urls": [CCS_SALE], "prices": {_day(-1): 45.0}},
        }
        pruned, _stats = prune_price_history(history, today=TODAY, current_data=_catalog(_item(CCS_NEW, COWBOY, "45.00")))
        self.assertEqual(sorted(pruned[CCS_NEW]["previous_urls"]), sorted([CCS_OLD, CCS_SALE]))

    def test_ordinary_miss_still_needs_two_scans(self):
        history = {}
        _run(history, [(-2, _catalog(_item(CCS_OLD, COWBOY, "49.95")))])
        current = _catalog(_item(CCS_WIDER, COWBOY, "59.95"))
        carried = record_misses(_catalog(_item(CCS_OLD, COWBOY, "49.95")), current, history)
        self.assertEqual(carried, {CCS_OLD})
        self.assertEqual(history[CCS_OLD]["miss_streak"], 1)
        self.assertLess(history[CCS_OLD]["miss_streak"], GONE_AFTER_MISSES)


class AuditTests(unittest.TestCase):
    def _snapshots(self):
        pair = "Independent Eric Dressen Stage 4 Hollow Truck Black"
        single = "SINGLE Indy Dressen Stage 4 Hollow Truck Black"
        filler = _item("https://www.zumiez.com/filler.html", 'Baker Filler 8.5" Deck', "40.00", "Zumiez")
        snapshots = []
        for offset in range(-30, 1):
            items = [filler]
            items.append(_item(SW_DECK, SizeChangeOnSameUrlTests.NARROW if offset < -15 else SizeChangeOnSameUrlTests.WIDE, "64.98", "SkateWarehouse", "Decks", "89.95"))
            if offset < -10:
                items.append(_item(SW_PAIR, pair, "29.98", "SkateWarehouse", "Trucks", "59.95"))
                items.append(_item(CCS_OLD, COWBOY, "49.95"))
                items.append(_item("https://www.zumiez.com/skf-like.html", 'Baker Gone Again 8.5" Deck', "40.00", "Zumiez"))
            else:
                items.append(_item(SW_SINGLE, single, "15.00", "SkateWarehouse", "Trucks", "30.00"))
                items.append(_item(CCS_NEW, COWBOY, "49.95"))
                items.append(_item("https://www.zumiez.com/skf-like-1.html", 'Baker Gone Again 8.5" Deck', "40.00", "Zumiez"))
            items.append(_item(ZUMIEZ, 'EDGLRD Tech Script 8.25" Skateboard Deck', "39.99", "Zumiez"))
            items.append(_item(ZUMIEZ_TWIN, 'EDGLRD Tech Script 8.25" Skateboard Deck', "44.99", "Zumiez"))
            if not -25 <= offset <= -15:
                items.append(_item("https://www.zumiez.com/back.html", 'Baker Back Again 8.5" Deck', "45.00", "Zumiez"))
            if offset == -5:
                items.append(dict(filler))
            snapshots.append((f"{_day(offset)}T0800", _catalog(*items)))
        return snapshots

    def test_audit_finds_each_kind_and_changes_nothing(self):
        history = {SW_DECK: {"name": SizeChangeOnSameUrlTests.WIDE, "store": "SkateWarehouse", "part": "Decks", "width": 8.25}}
        before = copy.deepcopy(history)
        snapshots = self._snapshots()
        report = audit_history(history, snapshots)
        self.assertEqual(history, before)
        self.assertEqual(
            report["counts"],
            {
                "size_changed_same_url": 1,
                "shared_retailer_code": 1,
                "variant_ambiguity": 1,
                "shopify_handle_moved": 1,
                "possible_url_churn": 1,
                "duplicate_in_scan": 1,
                "history_gap": 1,
            },
        )
        kinds = {finding["kind"]: finding for finding in report["findings"]}
        self.assertEqual(kinds["size_changed_same_url"]["risk"], "false merge")
        self.assertEqual(kinds["size_changed_same_url"]["urls"], [SW_DECK])
        self.assertEqual(kinds["shared_retailer_code"]["urls"], sorted([SW_PAIR, SW_SINGLE]))
        self.assertIn("never joined", kinds["shared_retailer_code"]["action"])
        self.assertEqual(kinds["variant_ambiguity"]["urls"], sorted([ZUMIEZ, ZUMIEZ_TWIN]))
        self.assertEqual(kinds["shopify_handle_moved"]["urls"], sorted([CCS_OLD, CCS_NEW]))
        self.assertEqual(kinds["possible_url_churn"]["risk"], "fragmentation")
        self.assertIn("not proof", kinds["possible_url_churn"]["action"])
        self.assertEqual(kinds["history_gap"]["urls"], ["https://www.zumiez.com/back.html"])
        self.assertEqual(audit_history(history, list(reversed(snapshots))), report)

    def test_audit_of_stored_history_alone(self):
        history = {
            SW_DECK: {"name": SizeChangeOnSameUrlTests.WIDE, "store": "SkateWarehouse", "part": "Decks", "width": 8.25, "first_seen": _day(-30), "last_seen": _day(-1)},
            SW_PAIR: {"name": "Independent Eric Dressen Stage 4 Hollow Truck Black", "store": "SkateWarehouse", "part": "Trucks", "first_seen": _day(-40), "last_seen": _day(-12)},
            SW_SINGLE: {"name": "SINGLE Indy Dressen Stage 4 Hollow Truck Black", "store": "SkateWarehouse", "part": "Trucks", "first_seen": _day(-10), "last_seen": _day(0)},
        }
        report = audit_history(history)
        self.assertEqual(report["counts"], {"size_changed_same_url": 1, "shared_retailer_code": 1})
        self.assertIn('stored width 8.25" but the name now says 8.5"', report["findings"][0]["detail"])
        self.assertEqual(audit_history({}), {"counts": {}, "findings": []})
        self.assertEqual(audit_history(None, [("2026-01-01", None)]), {"counts": {}, "findings": []})


if __name__ == "__main__":
    unittest.main()
