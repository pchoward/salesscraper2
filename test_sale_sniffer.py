"""Flash-sale check (owner, 2026-11-04): cheap signals every ~2 hours start
the Skate scraper when a sale jumps or a new sale section appears."""

import datetime
import json
import unittest
from pathlib import Path

import yaml

import sale_sniffer as s

NOW = datetime.datetime(2026, 11, 5, 18, 0, tzinfo=datetime.timezone.utc)


class SignalTests(unittest.TestCase):
    def test_counts(self):
        fetch = lambda url: json.dumps({"collection": {"products_count": 412}}) if url.endswith("/collections/sale.json") else None
        self.assertEqual(s.shopify_count("https://tgm.example", "sale", fetch), 412)
        self.assertIsNone(s.shopify_count("https://tgm.example", "gone", fetch))
        self.assertEqual(s.results_count("<p>1-48 of 2,924 results</p>"), 2924)
        self.assertEqual(s.results_count("<span>57 Results</span>"), 57)
        self.assertIsNone(s.results_count("<p>nothing</p>"))

    def test_sources_cover_the_skate_sale_feeds(self):
        keys = [key for key, _, _ in s.sources()]
        for key in ("TGM:sale", "SPoT:blacker-friday-deals", "Exodus:sale-1", "CCS:clearance",
                    "Tactics:skateboard-decks/sale", "Tactics:limited-time-deals/skate"):
            self.assertIn(key, keys)


class DecisionTests(unittest.TestCase):
    def test_jumps_and_new_sections(self):
        before = {"counts": {"TGM:sale": 240, "SPoT:sale": 40, "Tactics:x": 57}, "sections": ["https://a/old"]}
        now = {"counts": {"TGM:sale": 410, "SPoT:sale": 49, "Tactics:x": 60, "New:feed": 500},
               "sections": ["https://a/old", "https://a/flash"]}
        self.assertEqual(s.changes(before, now), ["TGM:sale sale grew 240 -> 410", "new sale section https://a/flash"])
        self.assertEqual(s.changes(None, now), [], "the first check is only a baseline")

    def test_guard_rails(self):
        self.assertEqual(s.allowed({}, NOW), (True, ""))
        self.assertFalse(s.allowed({}, NOW, busy=True)[0])
        recent = {"triggers": [(NOW - datetime.timedelta(hours=1)).isoformat()]}
        self.assertFalse(s.allowed(recent, NOW)[0])
        today = NOW.astimezone(s.EASTERN).replace(hour=1)
        three = {"triggers": [(today + datetime.timedelta(minutes=m)).isoformat() for m in (0, 1, 2)]}
        self.assertFalse(s.allowed(three, NOW + datetime.timedelta(hours=8))[0])
        yesterday = {"triggers": [(NOW - datetime.timedelta(days=1)).isoformat()] * 3}
        self.assertTrue(s.allowed(yesterday, NOW)[0])

    def test_sniff_triggers_once_and_remembers(self):
        state = {"last": {"counts": {"TGM:sale": 100}, "sections": []}}
        started = []
        read = lambda: {"counts": {"TGM:sale": 200}, "sections": []}
        state, lines = s.sniff(state, NOW, read=read, busy=lambda: False, start=lambda: started.append(1) or True,
                               trigger=True)
        self.assertEqual(started, [1])
        self.assertIn("Started the Skate scraper.", lines)
        self.assertEqual(state["last"]["counts"]["TGM:sale"], 200)
        state, lines = s.sniff(state, NOW + datetime.timedelta(hours=4), read=read, busy=lambda: False,
                               start=lambda: started.append(1) or True, trigger=True)
        self.assertEqual(started, [1], "the same count does not trigger again")

    def test_dry_run_and_busy_never_start(self):
        state = {"last": {"counts": {"TGM:sale": 100}, "sections": []}}
        read = lambda: {"counts": {"TGM:sale": 200}, "sections": []}
        boom = lambda: (_ for _ in ()).throw(AssertionError("started"))
        _, lines = s.sniff(state, NOW, read=read, busy=lambda: False, start=boom, trigger=False)
        self.assertIn("Would start the Skate scraper (dry run).", lines)
        _, lines = s.sniff(state, NOW, read=read, busy=lambda: True, start=boom, trigger=True)
        self.assertTrue(any(line.startswith("Not scraping") for line in lines))

    def test_a_failed_signal_keeps_its_last_value(self):
        state = {"last": {"counts": {"TGM:sale": 100, "SPoT:sale": 40}, "sections": []}}
        state, _ = s.sniff(state, NOW, read=lambda: {"counts": {"TGM:sale": 101}, "sections": []})
        self.assertEqual(state["last"]["counts"], {"TGM:sale": 101, "SPoT:sale": 40})


class WorkflowTests(unittest.TestCase):
    def test_schedule_permissions_and_cache(self):
        text = (Path(__file__).resolve().parent / ".github/workflows/sale-sniffer.yml").read_text(encoding="utf-8")
        data = yaml.safe_load(text)
        self.assertEqual(data[True]["schedule"][0]["cron"], "23 */2 * * *")
        self.assertEqual(data["permissions"], {"contents": "read", "actions": "write"})
        self.assertIn("python sale_sniffer.py --state sniff_state.json --trigger", text)
        self.assertIn("actions/cache/save@v4", text)
        self.assertNotIn("secrets.", text)


if __name__ == "__main__":
    unittest.main()


class PagesGuardTests(unittest.TestCase):
    def gh(self, runs, posted):
        def call(args):
            if args[0] == "-X":
                posted.append(args[-1])
                return {}
            return {"workflow_runs": runs}
        return call

    def test_failed_deploy_is_rerun_at_most_twice(self):
        runs = [{"id": 7, "name": "pages build and deployment", "status": "completed", "conclusion": "failure",
                 "head_sha": "8dd0dfc123"}]
        posted, state = [], {}
        for _ in range(3):
            state, line = s.pages_guard(state, "o/r", gh=self.gh(runs, posted))
        self.assertEqual(posted, ["repos/o/r/actions/runs/7/rerun-failed-jobs"] * 2)
        self.assertIn("leaving it for a person", line)

    def test_healthy_or_running_deploys_are_left_alone(self):
        for run in ({"conclusion": "success", "status": "completed"}, {"conclusion": None, "status": "in_progress"}):
            posted = []
            _, line = s.pages_guard({}, "o/r", gh=self.gh([dict(run, id=1, name="pages build and deployment")], posted))
            self.assertEqual((posted, line), ([], ""))
        older_failure = [{"id": 2, "name": "pages build and deployment", "status": "completed", "conclusion": "success"},
                         {"id": 1, "name": "pages build and deployment", "status": "completed", "conclusion": "failure"}]
        posted = []
        s.pages_guard({}, "o/r", gh=self.gh(older_failure, posted))
        self.assertEqual(posted, [], "only the latest deploy matters")

    def test_a_broken_gh_never_fails_the_check(self):
        def broken(args):
            raise RuntimeError("HTTP 403")
        state, line = s.pages_guard({}, "o/r", gh=broken)
        self.assertIn("skipped", line)
