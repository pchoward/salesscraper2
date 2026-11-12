"""One evening email for BMX, Ski and MTB (owner, 2026-11-12)."""

import datetime
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import notify
import sports
import sports_email

SINCE = datetime.datetime(2026, 11, 12, 21, 37, tzinfo=datetime.timezone.utc)
WHEN = datetime.date(2026, 11, 12)


def _item(name, part, sale, original, store="Albe's BMX"):
    return {"name": name, "part": part, "price_new": sale, "price_old": original, "store": store,
            "url": f"https://example.com/{name.replace(' ', '-').lower()}"}


class SportsEmailTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(self.root, ignore_errors=True))

    def _save(self, sport_id, generated_at, new_items=(), drops=()):
        folder = self.root / sport_id
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "report_inputs.json").write_text(json.dumps({
            "generated_at": generated_at,
            "digest": {"new_items": list(new_items), "drops": list(drops)}}), encoding="utf-8")

    def _sections(self, *ids):
        with mock.patch.object(sports.Sport, "data_path", lambda sport: self.root / sport.id):
            return [s for s in (sports_email.load_section(sports.get(i), SINCE) for i in ids) if s]

    def test_one_email_for_every_sport_scraped_this_run(self):
        self._save("bmx", "2026-11-12T21:50:00+00:00", [_item("Sunday Primer", "Bikes", "300", "400")])
        self._save("ski", "2026-11-12T22:05:00+00:00", [_item("Line Pandora 94", "Skis", "400", "600", "evo")])
        self._save("mtb", "2026-11-11T21:50:00+00:00", [_item("Old Tire", "Tires", "30", "60")])  # yesterday
        sections = self._sections("bmx", "ski", "mtb")
        self.assertEqual([s.sport.id for s in sections], ["bmx", "ski"])
        self.assertEqual(sports_email.subject_line(sections, WHEN), "ShredDeals BMX & Ski: 2 new, 0 price drops (Nov 12)")
        html = sports_email.render_html(sections, WHEN)
        self.assertIn('data-sport="bmx"', html)
        self.assertIn("https://shreddeals.com/ski/sale_items_chart.html", html)
        self.assertNotIn("Old Tire", html)
        self.assertIn("ShredDeals", html)
        self.assertNotIn("Skateboard sale tracker", html)
        self.assertIn("Sunday Primer", sports_email.render_plain(sections, WHEN))

    def test_biggest_markdowns_first_and_capped(self):
        items = [_item(f"Grip {n}", "Steering", "10", str(10 + n)) for n in range(1, sports_email.LIMIT + 6)]
        self._save("bmx", "2026-11-12T21:50:00+00:00", items)
        section = self._sections("bmx")[0]
        self.assertEqual(len(section.new_items), sports_email.LIMIT)
        self.assertEqual(section.more_new, 5)
        self.assertEqual(section.total_new, sports_email.LIMIT + 5)
        self.assertEqual(section.new_items[0]["name"], f"Grip {sports_email.LIMIT + 5}")
        self.assertIn("5 more new on the BMX page", sports_email.render_html([section], WHEN))

    def test_nothing_new_sends_nothing(self):
        self._save("bmx", "2026-11-12T21:50:00+00:00")
        with mock.patch.object(sports.Sport, "data_path", lambda sport: self.root / sport.id), \
                mock.patch.object(notify, "_smtp_send") as smtp:
            self.assertFalse(sports_email.send(["bmx", "ski"], since=SINCE, env={}))
        smtp.assert_not_called()

    def test_sends_with_skate_settings_and_never_raises(self):
        self._save("mtb", "2026-11-12T22:20:00+00:00", [_item("Fox 36 Fork", "Forks", "700", "1100", "Jenson")])
        env = {"SMTP_HOST": "smtp.resend.com", "SMTP_USER": "resend", "SMTP_PASSWORD": "x",
               "EMAIL_FROM": "ShredDeals <alerts@shreddeals.com>", "EMAIL_TO": "owner@example.com"}
        with mock.patch.object(sports.Sport, "data_path", lambda sport: self.root / sport.id), \
                mock.patch.object(notify, "_smtp_send") as smtp:
            self.assertTrue(sports_email.send(["mtb"], since=SINCE, env=env, dry_run=False, when=WHEN))
            message = smtp.call_args[0][1]
            self.assertEqual(message["Subject"], "ShredDeals MTB: 1 new, 0 price drops (Nov 12)")
            self.assertEqual(message["From"], "ShredDeals <alerts@shreddeals.com>")
            smtp.side_effect = OSError("down")
            self.assertFalse(sports_email.send(["mtb"], since=SINCE, env=env, dry_run=False))

    def test_skate_email_says_shreddeals(self):
        digest = notify.Digest(new_items=[_item("Baker Deck", "Decks", "50", "70", "Tactics")])
        self.assertTrue(notify.subject_line(digest, WHEN).startswith("ShredDeals Skate: 1 new"))
        html = notify.render_html(digest, notify.DEFAULT_REPORT_URL, WHEN)
        self.assertIn("ShredDeals</p>", html)
        self.assertNotIn("Skateboard sale tracker", html)

    def test_workflow_sends_after_the_scrapes(self):
        text = (Path(__file__).parent / ".github/workflows/scrape-sports.yml").read_text(encoding="utf-8")
        self.assertLess(text.index("python scraper.py --sport"), text.index("python sports_email.py --since"))
        self.assertLess(text.index("python sports_email.py"), text.index("Commit and push"))


if __name__ == "__main__":
    unittest.main()
