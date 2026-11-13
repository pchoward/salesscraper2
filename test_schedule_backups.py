"""Backup crons (owner, 2026-11-04: GitHub ran the 07:17 Skate cron at 15:03
and skipped the next day's entirely, so Skate went stale)."""

import datetime
import json
import os
import tempfile
import unittest
from pathlib import Path

import yaml

from schedule import MAIN_CRONS, gate_should_scrape

ROOT = Path(__file__).resolve().parent
NOW = datetime.datetime(2026, 11, 4, 16, 0, tzinfo=datetime.timezone.utc)


def crons(name):
    data = yaml.safe_load((ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8"))
    return [entry["cron"] for entry in data[True]["schedule"]]


class BackupTests(unittest.TestCase):
    def health(self, day, failed=False):
        handle = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
        json.dump({"runs": [{"date": day, "scanned_at": f"{day}T12:00:00+00:00",
                             "results": {"Store_Part": {"count": 3, "failed": failed}}}], "baseline": {}}, handle)
        handle.close()
        self.addCleanup(os.remove, handle.name)
        return handle.name

    def test_each_workflow_has_one_main_cron_and_backups(self):
        for name in ("scrape.yml", "scrape-sports.yml"):
            listed = crons(name)
            self.assertEqual(len([c for c in listed if c in MAIN_CRONS]), 1, name)
            self.assertGreaterEqual(len(listed), 3, name)

    def test_every_backup_skips_after_todays_success(self):
        done = self.health("2026-11-04")
        for cron in crons("scrape.yml"):
            self.assertEqual(gate_should_scrape("schedule", cron, done, now=NOW), cron in MAIN_CRONS, cron)

    def test_sports_backup_waits_for_every_sport(self):
        today, yesterday = self.health("2026-11-04"), self.health("2026-11-03")
        backup = [c for c in crons("scrape-sports.yml") if c not in MAIN_CRONS][0]
        self.assertFalse(gate_should_scrape("schedule", backup, [today, today, today], now=NOW))
        self.assertTrue(gate_should_scrape("schedule", backup, [today, yesterday, today], now=NOW))
        self.assertTrue(gate_should_scrape("schedule", backup, [today, "missing/scrape_health.json"], now=NOW))

    def test_sports_workflow_steps_follow_the_gate(self):
        text = (ROOT / ".github" / "workflows" / "scrape-sports.yml").read_text(encoding="utf-8")
        self.assertIn("HEALTH_PATHS: catalogs/bmx/scrape_health.json", text)
        self.assertEqual(text.count("if: steps.gate.outputs.scrape == 'true'"), 7)


if __name__ == "__main__":
    unittest.main()
