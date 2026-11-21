import datetime
import json
import tempfile
import unittest
from pathlib import Path

import drift

DAY = datetime.date(2026, 11, 21)


def run(date, counts, failed=()):
    return {"date": date, "scanned_at": date + "T07:17:00+00:00",
            "results": {key: {"count": count, "failed": key in failed,
                              "diagnostics": {"reason": "scrape_failed" if key in failed else "normal_variation"}}
                        for key, count in counts.items()}}


def dates(n):
    return [(DAY - datetime.timedelta(days=n - 1 - i)).isoformat() for i in range(n)]


class DriftChecks(unittest.TestCase):
    def test_held_counts_runs_in_a_row(self):
        days = dates(4)
        health = {"runs": [run(days[0], {"A_Decks": 5}),
                           run(days[1], {"A_Decks": 5}, failed={"A_Decks"}),
                           run(days[2], {"A_Decks": 5}, failed={"A_Decks"}),
                           run(days[3], {"A_Decks": 5, "B_Wheels": 3}, failed={"A_Decks", "B_Wheels"})]}
        found = {f["key"]: f for f in drift.held(health)}
        self.assertEqual(found["A_Decks"]["runs"], 3)
        self.assertEqual(found["A_Decks"]["level"], "action")
        self.assertEqual(found["B_Wheels"]["level"], "watch")

    def test_volume_drop_and_rise_by_store(self):
        days = dates(6)
        runs = [run(d, {"A_Decks": 30, "A_Wheels": 10, "B_Decks": 20}) for d in days[:-1]]
        runs.append(run(days[-1], {"A_Decks": 10, "A_Wheels": 5, "B_Decks": 80}))
        found = {f["store"]: f for f in drift.volume({"runs": runs})}
        self.assertEqual(found["A"]["change"], "drop")
        self.assertEqual(found["B"]["change"], "rise")

    def test_volume_leaves_held_stores_and_small_stores_alone(self):
        days = dates(6)
        runs = [run(d, {"A_Decks": 30, "C_Decks": 4}) for d in days[:-1]]
        runs.append(run(days[-1], {"A_Decks": 0, "C_Decks": 0}, failed={"A_Decks"}))
        self.assertEqual(drift.volume({"runs": runs}), [])

    def test_new_unmapped_types_are_reported_once(self):
        feed = {"stores": {"evo": {"unmapped_types": [["e-Mountain Completes", 44], ["Sealant", 3], ["Valves", 1]]}}}
        found = drift.new_unmapped(feed, {"evo": ["Sealant"]})
        self.assertEqual([f["product_type"] for f in found], ["e-Mountain Completes"])
        self.assertEqual(found[0]["level"], "action")

    def test_fill_drop(self):
        items = [{"name": f"Ski {i}", "brand": "K2", "technical_specs": {"waist": ["100 mm"]}} for i in range(20)]
        past = [drift.fill_rates({"evo_Skis": items})] * 3
        blank = [{"name": f"Ski {i}", "brand": "K2", "technical_specs": {}} for i in range(20)]
        found = drift.fill_drops(drift.fill_rates({"evo_Skis": blank}), past)
        self.assertEqual([(f["field"], f["share"]) for f in found], [("waist", 0)])

    def test_stale(self):
        self.assertEqual(drift.stale({"runs": [run(dates(1)[0], {})]}, DAY), [])
        old = (DAY - datetime.timedelta(days=3)).isoformat()
        self.assertEqual(drift.stale({"runs": [run(old, {})]}, DAY)[0]["days"], 3)

    def test_check_writes_report_and_history_and_first_run_only_records_types(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / "scrape_health.json").write_text(json.dumps({"runs": [run(DAY.isoformat(), {"A_Decks": 3})]}))
            (folder / "previous_data.json").write_text(json.dumps({"A_Decks": []}))
            (folder / "feed_summary.json").write_text(json.dumps(
                {"stores": {"A": {"unmapped_types": [["Gift Cards", 12]]}}}))
            first = drift.check(folder, DAY)
            self.assertEqual(first["findings"], [])
            history = json.loads((folder / "drift_history.json").read_text())
            self.assertEqual(history["unmapped_seen"], {"A": ["Gift Cards"]})
            (folder / "feed_summary.json").write_text(json.dumps(
                {"stores": {"A": {"unmapped_types": [["Gift Cards", 12], ["Snowboards", 40]]}}}))
            second = drift.check(folder, DAY)
            self.assertEqual([f["product_type"] for f in second["findings"]], ["Snowboards"])
            self.assertTrue((folder / "drift_report.json").exists())

    def test_markdown_lists_actions_first(self):
        text = drift.markdown([("Skate", {"findings": [
            {"kind": "stale", "last": "2026-11-18", "days": 3, "level": "action"}],
            "counts": {"action": 1, "watch": 0}})])
        self.assertIn("**act**: last scrape 2026-11-18 (3 days ago)", text)


if __name__ == "__main__":
    unittest.main()
