"""Run bookkeeping must not raise, and must not wipe a corrupt history file."""

import unittest
import copy
import datetime
from contextlib import ExitStack
from unittest.mock import patch

from health import record_run
from history import record_misses, update_price_history
from report import compare_catalogs

from pipeline import apply_run_updates, decorate_digest, prepare_run
from report import Digest


def _deck():
    return {
        "name": "Baker Figgy Divine Evil 8.25 Deck",
        "url": "https://example.com/baker",
        "price_new": "40.00",
        "price_old": "70.00",
        "part": "Decks",
        "store": "Zumiez",
    }


class PipelineTests(unittest.TestCase):
    def test_corrupt_inputs_do_not_raise_or_replace_history(self):
        result = apply_run_updates(
            {"Zumiez_Decks": [_deck()]},
            set(),
            history=["not", "a", "dict"],
            health={"runs": "broken"},
            today="2026-09-30",
        )
        self.assertFalse(result["save_history"])
        self.assertIsInstance(result["health"], dict)
        self.assertIsInstance(result["health"]["runs"], list)
        self.assertIsInstance(result["warnings"], list)

    def test_normal_run_records_health_and_skips_failed_scrape_prices(self):
        result = apply_run_updates(
            {
                "Zumiez_Decks": [_deck()],
                "CCS_Decks": [_deck()],
            },
            failed_keys={"CCS_Decks"},
            history={},
            health={"runs": [], "baseline": {}},
            today="2026-09-30",
        )
        self.assertTrue(result["save_history"])
        self.assertIn("https://example.com/baker", result["history"])
        self.assertEqual(result["history"]["https://example.com/baker"]["observation_count"], 1)
        decks = result["health"]["runs"][0]["results"]
        self.assertEqual(decks["Zumiez_Decks"]["count"], 1)
        self.assertFalse(decks["Zumiez_Decks"]["failed"])
        self.assertTrue(decks["CCS_Decks"]["failed"])
        self.assertEqual(decks["CCS_Decks"]["count"], 0)

    def test_decorate_adds_warning_and_low_flag_without_raising(self):
        item = _deck()
        history = {
            item["url"]: {
                "name": item["name"],
                "store": "Zumiez",
                "part": "Decks",
                "first_seen": "2026-09-01",
                "last_seen": "2026-09-30",
                "observation_count": 4,
                "all_time_low": 40.0,
                "all_time_low_date": "2026-09-20",
                "prices": {
                    "2026-09-01": 55.0,
                    "2026-09-10": 50.0,
                    "2026-09-20": 40.0,
                    "2026-09-30": 40.0,
                },
            }
        }
        digest = Digest(new_items=[item])
        warning = {"store": "CCS", "part": "Wheels", "kind": "error", "dates": ["2026-09-29", "2026-09-30"]}
        decorate_digest(digest, {"Zumiez_Decks": [item]}, history, [warning])
        self.assertEqual(digest.warnings, [warning])
        self.assertTrue(item["at_all_time_low"])
        self.assertEqual(len(digest.all_time_lows), 1)
        decorate_digest(None, {}, {}, [])


class FailedWatchTests(unittest.TestCase):
    def test_suspect_retained_items_are_not_watch_alerts(self):
        from unittest.mock import patch
        item = _deck()
        digest = Digest(new_items=[])
        with patch('pipeline.match_watchlist', return_value=([], [])) as matcher:
            decorate_digest(digest, {'Zumiez_Decks':[item]}, {}, [], failed_keys={'Zumiez_Decks'})
        self.assertEqual(matcher.call_args.args[0], [])


class CompletenessPipelineTests(unittest.TestCase):
    key = "Zumiez_Decks"

    def catalog(self, count, store="Zumiez"):
        items = []
        for index in range(count):
            item = _deck()
            item["url"] = f"https://example.com/{store}/{index}"
            item["store"] = store
            items.append(item)
        return {f"{store}_Decks": items}

    def health(self, end=None):
        end = end or datetime.date(2026, 9, 30)
        state = {"runs": [], "baseline": {}}
        for offset in range(3):
            day = (end - datetime.timedelta(days=2-offset)).isoformat()
            state = record_run(state, day, {
                self.key: {"count": 100, "failed": False},
                "CCS_Decks": {"count": 10, "failed": False},
            })
        return state

    def test_partial_full_failure_and_recovery_do_not_advance_missing_products(self):
        previous = self.catalog(100)
        history = update_price_history(previous, {}, today="2026-09-30")
        missing_url = previous[self.key][-1]["url"]
        history[missing_url]["miss_streak"] = 1
        history[missing_url]["stage"] = "price_drop"
        # A listing absent even from the previous catalog must also be protected.
        orphan = copy.deepcopy(history[missing_url])
        orphan["last_seen"] = "2026-09-01"
        history["https://example.com/orphan"] = orphan
        health = self.health()
        for day, count, failed in [("2026-10-01", 20, set()), ("2026-10-02", None, {self.key})]:
            raw = self.catalog(count) if count is not None else {self.key: None}
            raw.update(self.catalog(10, "CCS"))
            prepared = prepare_run(raw, failed, previous, health, today=day)
            self.assertEqual(prepared["failed_keys"], {self.key})
            current = prepared["current_data"]
            self.assertEqual(len(current[self.key]), 100)
            carried = record_misses(previous, current, history, prepared["failed_keys"])
            self.assertNotIn(self.key, compare_catalogs(previous, current, prepared["failed_keys"]))
            result = apply_run_updates(current, prepared["failed_keys"], history, health, today=day,
                                       suspect_keys=prepared["suspect_keys"], skip_urls=carried,
                                       health_results=prepared["health_results"])
            history, health = result["history"], result["health"]
            self.assertEqual(history[missing_url]["miss_streak"], 1)
            self.assertEqual(history[missing_url]["last_seen"], "2026-09-30")
            self.assertEqual(history[missing_url]["observation_count"], 1)
            self.assertEqual(history["https://example.com/orphan"]["stage"], "price_drop")
            self.assertEqual(history["https://example.com/orphan"]["miss_streak"], 1)
            diagnostic = health["runs"][-1]["results"][self.key]["diagnostics"]
            self.assertEqual(diagnostic["actual_count"], count or 0)
            self.assertEqual(diagnostic["expected_count"], 100)
            self.assertTrue(result["warnings"])
            self.assertEqual(result["warnings"][0]["part"], "Decks")
            previous = current
        prepared = prepare_run(self.catalog(100), set(), previous, health, today="2026-10-03")
        self.assertEqual(prepared["failed_keys"], set())
        record_misses(previous, prepared["current_data"], history, prepared["failed_keys"])
        recovered = apply_run_updates(prepared["current_data"], set(), history, health, today="2026-10-03",
                                      health_results=prepared["health_results"])
        self.assertEqual(recovered["warnings"], [])
        self.assertNotIn("miss_streak", recovered["history"][missing_url])
        self.assertEqual(recovered["history"][missing_url]["observation_count"], 2)
        self.assertEqual(recovered["health"]["baseline"][self.key]["date"], "2026-10-03")

    def test_counts_are_raw_not_inflated_by_first_miss_retention(self):
        previous = self.catalog(100)
        history = update_price_history(previous, {}, today="2026-09-30")
        prepared = prepare_run(self.catalog(95), set(), previous, self.health(), today="2026-10-01")
        current = prepared["current_data"]
        carried = record_misses(previous, current, history, prepared["failed_keys"])
        self.assertEqual(len(current[self.key]), 100)
        result = apply_run_updates(current, set(), history, self.health(), today="2026-10-01",
                                   skip_urls=carried, health_results=prepared["health_results"])
        self.assertEqual(result["health"]["runs"][-1]["results"][self.key]["count"], 95)
        self.assertEqual(result["health"]["runs"][-1]["results"][self.key]["diagnostics"]["actual_count"], 95)
        self.assertEqual(result["warnings"], [])

    def test_direct_bookkeeping_also_protects_lifecycle_on_partial_results(self):
        previous = self.catalog(100)
        history = update_price_history(previous, {}, today="2026-09-30")
        url = previous[self.key][-1]["url"]
        history[url].update(miss_streak=1, stage="price_drop")
        result = apply_run_updates(self.catalog(20), set(), history, self.health(), today="2026-10-18")
        self.assertIn(self.key, result["failed_keys"])
        self.assertEqual(result["history"][url]["stage"], "price_drop")
        self.assertEqual(result["history"][url]["miss_streak"], 1)
        self.assertEqual(result["history"][url]["last_seen"], "2026-09-30")

    def test_failed_nonempty_results_and_missing_failed_keys_keep_previous_rows(self):
        previous = self.catalog(100)
        for raw in [self.catalog(20), {}]:
            prepared = prepare_run(raw, {self.key}, previous, self.health(), today="2026-10-01")
            self.assertEqual(prepared["current_data"], previous)
            self.assertEqual(prepared["health_results"][self.key]["count"], 0)
            self.assertEqual(prepared["health_results"][self.key]["diagnostics"]["reason"], "scrape_failed")

    def test_whole_store_empty_keeps_existing_aggregate_warning_and_diagnostics(self):
        previous = self.catalog(100)
        prepared = prepare_run({self.key: []}, set(), previous, self.health(), today="2026-10-01")
        self.assertEqual(prepared["current_data"], previous)
        self.assertEqual(prepared["suspect_keys"], {self.key})
        result = apply_run_updates(prepared["current_data"], prepared["failed_keys"], {}, self.health(),
                                   today="2026-10-01", suspect_keys=prepared["suspect_keys"],
                                   health_results=prepared["health_results"])
        warning, = result["warnings"]
        self.assertEqual(warning["kind"], "suspect")
        diagnostic = result["health"]["runs"][-1]["results"][self.key]["diagnostics"]
        self.assertEqual(diagnostic["actual_count"], 0)
        self.assertEqual(diagnostic["expected_count"], 100)
        self.assertEqual(diagnostic["reason"], "whole_store_empty")

    def test_runner_classifies_before_stock_diff_and_writes_raw_health_counts(self):
        import scraper
        today = datetime.datetime.now(datetime.timezone.utc).date()
        previous = self.catalog(100)
        raw = self.catalog(20)
        health = self.health(end=today-datetime.timedelta(days=1))
        history = update_price_history(previous, {}, today=(today-datetime.timedelta(days=1)).isoformat())
        url = previous[self.key][-1]["url"]
        history[url].update(miss_streak=1, stage="new")
        with ExitStack() as stack:
            stack.enter_context(patch.dict('os.environ', {'NOTIFICATION_ENGINE_ENABLED': ''}))
            for name, value in {"build_scrapers": [], "run_stores": (raw, set()), "load_previous": previous,
                                "load_state": health, "load_price_history": history, "load_site_sales": {},
                                "build_report_html": "report"}.items():
                stack.enter_context(patch.object(scraper, name, return_value=value))
            mocks = {name: stack.enter_context(patch.object(scraper, name)) for name in
                     ["confirm_stock", "save_current", "save_price_history", "save_health", "save_site_sales", "safe_write_file", "send_digest", "send_admin_warnings",
                      "save_report_inputs", "discard_report_inputs"]}
            scraper.main()
        self.assertEqual(mocks["confirm_stock"].call_args.args[2], {self.key})
        self.assertEqual(len(mocks["save_current"].call_args.args[0][self.key]), 100)
        saved_health = mocks["save_health"].call_args.args[0]
        saved = saved_health["runs"][-1]["results"][self.key]
        self.assertTrue(saved["suspect"])
        self.assertEqual(saved["diagnostics"]["actual_count"], 20)
        digest = mocks["send_digest"].call_args.args[0]
        self.assertFalse(digest.removed)
        self.assertTrue(digest.warnings)
        self.assertEqual(mocks["send_admin_warnings"].call_args.args[0], digest.warnings)
        # The page's inputs are saved for rebuild_page.py, with the scrape's own time.
        inputs = mocks["save_report_inputs"].call_args.args
        self.assertIs(inputs[1], digest)
        self.assertEqual(inputs[2], {self.key})
        mocks["discard_report_inputs"].assert_not_called()
        saved_history = mocks["save_price_history"].call_args.args[0]
        self.assertEqual(saved_history[url]["miss_streak"], 1)
        self.assertEqual(saved_history[url]["observation_count"], 1)


if __name__ == "__main__":
    unittest.main()
