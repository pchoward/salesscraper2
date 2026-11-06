import datetime
import json
import os
import tempfile
import unittest

import sale_events as se


def _days(start, count):
    first = datetime.date.fromisoformat(start)
    return [(first + datetime.timedelta(days=n)).isoformat() for n in range(count)]


def _history(store, n, prices_by_day):
    """n listings at ``store``; prices_by_day(i, day) -> price or None."""
    out = {}
    for i in range(n):
        prices = {}
        for day in _days("2026-08-01", 160):
            price = prices_by_day(i, day)
            if price is not None:
                prices[day] = price
        out[f"https://{store}.test/{i}"] = {"store": store, "part": "Decks", "prices": prices}
    return out


class DetectTest(unittest.TestCase):
    def test_a_uniform_cut_that_goes_back_up_is_one_sale(self):
        history = _history("Shop", 40, lambda i, day: 80.0 if "2026-09-03" <= day < "2026-09-11" else 100.0)
        (event,) = se.detect(se._changes(history)["Shop"])
        self.assertEqual((event["start"], event["end"], event["cut"]), ("2026-09-03", "2026-09-11", 20))
        self.assertTrue(event["uniform"])
        self.assertEqual((event["listings"], event["tracked"], event["kind"]), (40, 40, "sale"))
        self.assertEqual(se.moment_for(event["start"]), "Labor Day")

    def test_new_listings_are_not_a_sale(self):
        # Our coverage widening: 200 new listings appear, none cut.
        history = _history("Shop", 20, lambda i, day: 100.0)
        history.update(_history("Shop2", 200, lambda i, day: 50.0 if day >= "2026-10-02" else None))
        for entry in history.values():
            entry["store"] = "Shop"
        self.assertEqual(se.detect(se._changes(history)["Shop"]), [])

    def test_a_few_markdowns_are_not_a_sale(self):
        history = _history("Shop", 100, lambda i, day: 70.0 if i < 5 and day >= "2026-09-10" else 100.0)
        self.assertEqual(se.detect(se._changes(history)["Shop"]), [])

    def test_cuts_over_a_few_days_are_one_start_and_a_later_cut_a_step(self):
        def price(i, day):
            if day < "2026-11-20":
                return 100.0
            if day < "2026-12-10":
                return 75.0 if (i < 20 or day >= "2026-11-22") else 100.0
            return 70.0 if day < "2026-12-26" else 100.0
        (event,) = se.detect(se._changes(_history("SW", 40, price))["SW"])
        self.assertEqual(event["start"], "2026-11-20")       # Nov 22 joined the start
        self.assertEqual(event["end"], "2026-12-26")         # extended to Christmas, one event
        self.assertEqual(event["cut"], 25)
        self.assertEqual([step["from"] for step in event["steps"]], ["2026-12-10"])
        self.assertEqual(se.moment_for(event["start"]), "Black Friday / Cyber Week")
        self.assertIn("7% more from Dec 10", se.what(event))

    def test_cuts_never_reversed_are_a_markdown(self):
        history = _history("Shop", 40, lambda i, day: 80.0 if day >= "2026-08-10" else 100.0)
        (event,) = se.detect(se._changes(history)["Shop"])
        self.assertEqual((event["kind"], event["end"]), ("markdown", None))
        self.assertEqual(se.summary({"events": [event]}, "2026-11-28")["running"], None)

    def test_a_sale_running_when_the_history_began(self):
        history = _history("Shop", 30, lambda i, day: 80.0 if day < "2026-08-11" else 100.0)
        (event,) = se.detect(se._changes(history)["Shop"])
        self.assertEqual((event["start"], event["end"], event["cut"]), (None, "2026-08-11", 20))
        self.assertEqual(se.when(event), "ended Aug 11")


class DealsTest(unittest.TestCase):
    def test_headline_never_says_sitewide(self):
        uniform = [{"price_new": 80, "price_old": 100}] * 8 + [{"price_new": 50, "price_old": 100}] * 2
        self.assertEqual(se.headline(se.describe_deals(uniform)), "most deals 20% off")
        spread = [{"price_new": 100 - off, "price_old": 100} for off in (10, 20, 30, 30, 40, 40, 60)]
        self.assertEqual(se.headline(se.describe_deals(spread)), "up to 60% off (most 20-40%)")
        self.assertEqual(se.headline(se.describe_deals([{"price_new": 10, "price_old": 10}])), "")


class LogTest(unittest.TestCase):
    def test_running_sale_keeps_each_headline_change(self):
        history = _history("Shop", 30, lambda i, day: 75.0 if day >= "2026-11-20" else 100.0)
        for entry in history.values():
            entry["prices"] = {d: p for d, p in entry["prices"].items() if d <= "2026-11-25"}
        deals = {"Shop_Decks": [{"store": "Shop", "price_new": 75, "price_old": 100}] * 5}
        state = se.update({}, history, deals, "2026-11-25")
        deals2 = {"Shop_Decks": [{"store": "Shop", "price_new": 70, "price_old": 100}] * 5}
        state = se.update(json.loads(json.dumps(state)), history, deals2, "2026-11-26")
        (event,) = state["stores"]["Shop"]["events"]
        self.assertEqual([h["text"] for h in event["headlines"]], ["most deals 25% off", "most deals 30% off"])
        self.assertIn("now most deals 30% off (was most deals 25% off)", se.describe_event(event))

    def test_events_older_than_the_history_are_kept(self):
        old = {"stores": {"Shop": {"events": [{"start": "2025-11-20", "end": "2025-12-26", "kind": "sale", "cut": 25,
                                                "cut_low": 25, "cut_high": 25, "uniform": True, "listings": 50,
                                                "tracked": 60, "steps": [], "moment": "Black Friday / Cyber Week"}]}}}
        history = _history("Shop", 20, lambda i, day: 100.0)
        state = se.update(old, history, {}, "2026-11-06")
        self.assertEqual([e["start"] for e in state["stores"]["Shop"]["events"]], ["2025-11-20"])
        rows = dict(se.lines(state, "2026-11-06"))["Shop"]
        self.assertTrue(rows[0].startswith("Last sale: Extra 25% off 50 of 60"))
        self.assertIn("(Black Friday / Cyber Week)", rows[0])

    def test_rhythm_needs_three_sales_and_is_worded_as_no_promise(self):
        events = [{"start": s, "end": e, "kind": "sale", "cut": 20, "cut_low": 20, "cut_high": 20, "uniform": True,
                   "listings": 30, "tracked": 40, "steps": []}
                  for s, e in (("2026-06-01", "2026-06-05"), ("2026-07-01", "2026-07-04"), ("2026-07-31", "2026-08-03"))]
        info = se.summary({"events": events[:2]}, "2026-08-10")
        self.assertIsNone(info["rhythm"])
        info = se.summary({"events": events}, "2026-08-10")
        self.assertEqual(info["rhythm"], {"days": 30, "based_on": 3})
        self.assertEqual(info["next"], {"around": "2026-08-30", "based_on": 3})
        rows = dict(se.lines({"stores": {"Shop": {"events": events}}}, "2026-08-10"))["Shop"]
        self.assertTrue(any("not a promise" in row and "Aug 30, 2026" in row for row in rows))

    def test_run_saves_and_never_raises(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "sale_events.json")
            self.assertIsNotNone(se.run(_history("Shop", 5, lambda i, d: 100.0), {}, "2026-11-06", path=path))
            self.assertTrue(os.path.exists(path))
            self.assertIsNone(se.run({"x": {"store": "S", "prices": {"2026-01-01": 1, "2026-01-02": 2}}},
                                     {"bad": [object()]}, "2026-11-06", path=os.path.join(folder, "no", "x.json")))

    def test_moments(self):
        self.assertEqual(se.moment_for("2026-11-20"), "Black Friday / Cyber Week")  # Thanksgiving Nov 26
        self.assertEqual(se.moment_for("2026-12-15"), "Christmas")
        self.assertEqual(se.moment_for("2026-05-22"), "Memorial Day")
        self.assertEqual(se.moment_for("2026-10-14"), "")


class PageTest(unittest.TestCase):
    def test_sale_history_section(self):
        import page
        state = {"stores": {"Tactics": {"events": [{"start": "2026-09-03", "end": "2026-09-11", "kind": "sale", "cut": 20,
                                                   "cut_low": 20, "cut_high": 20, "uniform": True, "listings": 72,
                                                   "tracked": 83, "steps": [], "moment": "Labor Day"}]}}}
        html = page._sale_history_html(state, "2026-11-06")
        self.assertIn("Sale history", html)
        self.assertIn("Extra 20% off 72 of 83 deals we track · Sep 3 - Sep 11 (Labor Day)", html)
        self.assertEqual(page._sale_history_html({}, "2026-11-06"), "")
        self.assertIn("Sale history", page._activity_html([], "2026-11-06T10:00:00", html))


if __name__ == "__main__":
    unittest.main()
