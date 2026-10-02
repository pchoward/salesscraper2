"""Lifecycle, days at a price, score breakdown, URL state, and sale banners."""

import datetime
import unittest

from history import (
    apply_lifecycle,
    days_at_price,
    listing_stage,
    prune_price_history,
    recently_gone,
    update_price_history,
)
from notify import render_html, render_plain
from page import format_scan_et
from pipeline import apply_run_updates
from query_state import (
    STARTER_VIEWS,
    WIDTH_RANGES,
    bucket_contains,
    bucket_for_width,
    decode_query,
    encode_state,
)
from report import Digest, build_report_html
from score import deal_score
from site_sales import activity_line, describe_sales, empty_state, sale_banners


def _deck(price="50.00", url="https://example.com/baker", store="Zumiez", name=None):
    return {
        "name": name or "Baker Figgy Divine Evil Deck 8.25",
        "url": url,
        "price_new": price,
        "price_old": "80.00",
        "part": "Decks",
        "store": store,
    }


def _entry(prices, store="Zumiez"):
    days = sorted(prices)
    return {
        "name": "Baker Figgy Divine Evil Deck 8.25",
        "store": store,
        "part": "Decks",
        "first_seen": days[0],
        "last_seen": days[-1],
        "observation_count": len(prices),
        "all_time_low": min(prices.values()),
        "all_time_low_date": min(day for day, price in prices.items() if price == min(prices.values())),
        "prices": prices,
    }


class LifecycleTests(unittest.TestCase):
    def test_stage_moves_new_drop_low_sold_out_gone(self):
        url = "https://example.com/baker"
        history = {}
        catalog = {"Zumiez_Decks": [_deck("55.00")]}
        update_price_history(catalog, history, today="2026-09-01")
        apply_lifecycle(history, catalog, today="2026-09-01")
        self.assertEqual(history[url]["stage"], "new")

        catalog = {"Zumiez_Decks": [_deck("50.00")]}
        update_price_history(catalog, history, today="2026-09-08")
        apply_lifecycle(history, catalog, today="2026-09-08")
        self.assertEqual(history[url]["stage"], "price_drop")
        self.assertEqual(listing_stage(history[url], True, today="2026-09-08", at_low=False), "price_drop")

        catalog = {"Zumiez_Decks": [_deck("40.00")]}
        update_price_history(catalog, history, today="2026-09-20")
        apply_lifecycle(history, catalog, today="2026-09-20")
        self.assertEqual(history[url]["stage"], "all_time_low")

        apply_lifecycle(history, {}, today="2026-09-22")
        self.assertEqual(history[url]["stage"], "sold_out")
        gone = recently_gone(history, {}, today="2026-09-22")
        self.assertEqual(len(gone), 1)
        self.assertEqual(gone[0]["price"], 40.0)
        self.assertEqual(gone[0]["last_seen"], "2026-09-20")
        self.assertEqual(gone[0]["stage"], "sold_out")

        self.assertEqual(len(recently_gone(history, {}, today="2026-09-27")), 1)
        apply_lifecycle(history, {}, today="2026-09-28")
        self.assertEqual(history[url]["stage"], "gone")
        self.assertEqual(recently_gone(history, {}, today="2026-09-28"), [])

    def test_failed_scrape_does_not_mark_sold_out(self):
        url = "https://example.com/baker"
        history = {url: _entry({"2026-09-01": 55.0, "2026-09-08": 50.0})}
        history[url]["stage"] = "price_drop"
        apply_lifecycle(history, {}, today="2026-09-20", skip_keys={"Zumiez_Decks"})
        self.assertEqual(history[url]["stage"], "price_drop")
        self.assertEqual(recently_gone(history, {}, today="2026-09-20", skip_keys={"Zumiez_Decks"}), [])

    def test_return_from_sold_out_is_active_again(self):
        url = "https://example.com/baker"
        history = {url: _entry({"2026-09-01": 55.0, "2026-09-10": 40.0})}
        apply_lifecycle(history, {}, today="2026-09-12")
        self.assertEqual(history[url]["stage"], "sold_out")
        catalog = {"Zumiez_Decks": [_deck("40.00")]}
        update_price_history(catalog, history, today="2026-09-12")
        apply_lifecycle(history, catalog, today="2026-09-12")
        self.assertIn(history[url]["stage"], ("price_drop", "all_time_low"))

    def test_prune_keeps_stage(self):
        url = "https://example.com/baker"
        history = {url: _entry({"2026-09-01": 55.0, "2026-09-10": 40.0})}
        history[url]["stage"] = "sold_out"
        pruned, _stats = prune_price_history(history, today="2026-09-12", current_data={})
        self.assertEqual(pruned[url]["stage"], "sold_out")

    def test_pipeline_records_stage_without_raising(self):
        result = apply_run_updates(
            {"Zumiez_Decks": [_deck("40.00")]},
            set(),
            {},
            {"runs": [], "baseline": {}},
            today="2026-09-30",
            scanned_at="2026-09-30T12:21:37+00:00",
        )
        entry = result["history"]["https://example.com/baker"]
        self.assertEqual(entry["stage"], "new")
        self.assertEqual(result["health"]["runs"][0]["scanned_at"], "2026-09-30T12:21:37+00:00")


class DaysAtPriceTests(unittest.TestCase):
    def test_days_since_the_current_price_started(self):
        entry = _entry({"2026-09-01": 74.95, "2026-09-20": 39.99, "2026-09-21": 39.99})
        held = days_at_price(entry, "2026-09-21")
        self.assertEqual(held["days"], 1)
        self.assertEqual(held["price"], 39.99)
        self.assertEqual(held["since"], "2026-09-20")
        self.assertEqual(days_at_price(entry, "2026-09-20")["days"], 0)
        later = days_at_price(entry, "2026-10-01")
        self.assertEqual(later["days"], 11)


class ScoreBreakdownTests(unittest.TestCase):
    def test_breakdown_points_match_the_score_and_name_a_fresh_drop(self):
        item = _deck("42.40", name="Baker Figgy Divine Evil Deck 8.5")
        history = {
            item["url"]: _entry({"2026-09-01": 55.0, "2026-09-15": 50.0, "2026-09-30": 42.40})
        }
        drop = {"old": "50.00", "new": "42.40", "delta": 7.6, "percent_vs_prior": 15.2}
        result = deal_score(item, history, drop=drop, width=8.5, today="2026-09-30")
        scored = [factor for factor in result["breakdown"] if factor.get("points")]
        self.assertEqual(sum(factor["points"] for factor in scored), result["score"])
        labels = [factor["label"] for factor in result["breakdown"]]
        self.assertIn("47% off", labels)
        self.assertIn("$37.60 below original", labels)
        self.assertIn("Lowest tracked price", labels)
        self.assertTrue(any(label.startswith("Tracked ") for label in labels))
        self.assertIn("Freshly reduced", labels)
        self.assertIn("Popular size", labels)

    def test_older_drop_is_recently_reduced(self):
        item = _deck("42.40")
        history = {
            item["url"]: _entry(
                {
                    "2026-09-01": 55.0,
                    "2026-09-15": 50.0,
                    "2026-09-20": 42.40,
                    "2026-09-30": 42.40,
                }
            )
        }
        drop = {"old": "50.00", "new": "42.40", "delta": 7.6, "percent_vs_prior": 15.2}
        result = deal_score(item, history, drop=drop, width=8.0, today="2026-09-30")
        labels = [factor["label"] for factor in result["breakdown"]]
        self.assertIn("Recently reduced", labels)
        self.assertNotIn("Freshly reduced", labels)


class QueryStateTests(unittest.TestCase):
    def test_example_query_round_trip(self):
        query = "store=zumiez&type=deck&width=8.25&discount=40&sort=score"
        state = decode_query(query)
        self.assertEqual(state["store"], "Zumiez")
        self.assertEqual(state["part"], "Decks")
        self.assertEqual(state["widths"], ["8.25-8.375"])
        self.assertEqual(state["discount"], 40)
        self.assertEqual(state["sort"], "score")
        encoded = "store=zumiez&type=deck&width=8.25-8.375&discount=40&sort=score"
        self.assertEqual(encode_state(state), encoded)
        self.assertEqual(decode_query(encode_state(state)), state)

    def test_width_range_and_starter_views(self):
        state = decode_query("type=deck&width=8.25-8.5&discount=35")
        self.assertEqual(state["part"], "Decks")
        self.assertEqual(
            state["widths"],
            ["8.25-8.375", "8.375-8.5", "8.5-8.75"],
        )
        encoded = "type=deck&width=8.25-8.375%2C8.375-8.5%2C8.5-8.75&discount=35"
        self.assertEqual(encode_state(state), encoded)
        self.assertEqual(decode_query(encoded)["widths"], state["widths"])
        queries = {view["query"] for view in STARTER_VIEWS}
        self.assertIn("type=deck&width=8.25-8.5&discount=35", queries)
        self.assertIn("type=deck&width=8.5&max=50", queries)
        self.assertEqual(decode_query("type=deck&width=8.5&max=50")["widths"], ["8.5-8.75"])
        self.assertIn("store=skatewarehouse&change=new", queries)
        self.assertIn("watching=1&low=1", queries)
        watched = decode_query("watching=1&low=1")
        self.assertTrue(watched["watching"])
        self.assertTrue(watched["low"])
        self.assertEqual(watched["store"], "all")
        self.assertEqual(watched["widths"], [])

    def test_legacy_and_multi_width_params(self):
        self.assertEqual(decode_query("width=10")["widths"], ["10up"])
        self.assertEqual(decode_query("width=10.0")["widths"], ["10up"])
        self.assertEqual(decode_query("width=10.25")["widths"], ["10up"])
        self.assertEqual(decode_query("width=10.0+")["widths"], ["10up"])
        self.assertEqual(decode_query("width=9.5-10.0")["widths"], ["9.5-10.0"])
        self.assertEqual(decode_query("width=8.5-8.75")["widths"], ["8.5-8.75"])
        self.assertEqual(decode_query("width=lt7,10up")["widths"], ["lt7", "10up"])
        flipped = decode_query("width=10up,8.5-8.75")
        self.assertEqual(flipped["widths"], ["8.5-8.75", "10up"])
        self.assertEqual(decode_query(encode_state(flipped))["widths"], flipped["widths"])
        self.assertEqual(decode_query("width=abc")["widths"], [])

    def test_width_buckets_are_a_partition(self):
        samples = [
            (6.99, "lt7"),
            (7.0, "7.0-7.25"),
            (7.249, "7.0-7.25"),
            (7.25, "7.25-7.5"),
            (7.5, "7.5-7.75"),
            (7.75, "7.75-8.0"),
            (8.0, "8.0-8.125"),
            (8.124, "8.0-8.125"),
            (8.125, "8.125-8.25"),
            (8.25, "8.25-8.375"),
            (8.375, "8.375-8.5"),
            (8.499, "8.375-8.5"),
            (8.5, "8.5-8.75"),
            (8.749, "8.5-8.75"),
            (8.75, "8.75-9.0"),
            (9.0, "9.0-9.25"),
            (9.25, "9.25-9.5"),
            (9.5, "9.5-10.0"),
            (9.75, "9.5-10.0"),
            (9.999, "9.5-10.0"),
            (10.0, "10up"),
            (10.25, "10up"),
            (12.0, "10up"),
        ]
        for width, expected in samples:
            hits = [bucket.id for bucket in WIDTH_RANGES if bucket_contains(bucket, width)]
            self.assertEqual(hits, [expected], width)
            self.assertEqual(bucket_for_width(width).id, expected)

    def test_unknown_values_are_ignored(self):
        state = decode_query("store=nope&type=skate&sort=nope&width=abc")
        self.assertEqual(state["store"], "all")
        self.assertEqual(state["part"], "all")
        self.assertEqual(state["sort"], "rank")
        self.assertEqual(state["widths"], [])
        self.assertEqual(encode_state(state), "")


class ReportPolishTests(unittest.TestCase):
    def test_scan_time_is_eastern(self):
        self.assertEqual(format_scan_et("2026-10-01T12:56:14+00:00"), "Oct 1, 2026 8:56:14 AM ET")

    def test_grouped_card_and_days_at_price_render(self):
        left = _deck(
            "64.99",
            url="https://example.com/z",
            store="Zumiez",
            name="Baker Figgy Divine Evil Deck 8.125",
        )
        right = _deck(
            "44.99",
            url="https://example.com/s",
            store="SkateWarehouse",
            name="Baker Figgy Divine Evil Deck 8.12 x 31.875",
        )
        history = {
            left["url"]: _entry({"2026-07-20": 74.95, "2026-08-14": 64.99}, store="Zumiez"),
            right["url"]: _entry({"2026-07-20": 74.95, "2026-09-28": 44.99, "2026-09-29": 44.99}, store="SkateWarehouse"),
        }
        html = build_report_html(
            {"Zumiez_Decks": [left], "SkateWarehouse_Decks": [right]},
            {},
            price_history=history,
            generated_at="2026-09-30T12:56:14+00:00",
        )
        self.assertIn("from $44.99", html)
        self.assertIn("2 stores", html)
        self.assertIn("Best price:", html)
        self.assertIn("https://example.com/s", html)
        self.assertIn("d tracked", html)
        self.assertIn("d @ $", html)
        self.assertIn("Why ", html)
        self.assertIn("More filters", html)
        self.assertIn("Width range", html)
        self.assertIn("10.0+", html)
        self.assertNotIn('id="widthSelect"', html)
        self.assertIn("Save view", html)
        self.assertIn("Recently gone", html)
        self.assertIn("Retailer activity", html)
        self.assertIn("Oct 1, 2026 8:56:14 AM ET".replace("Oct 1", "Sep 30"), html)
        self.assertIn('id="morePanel"', html)
        self.assertIn("data-daysat=", html)

    def test_width_range_chips_count_decks_and_keep_zeros(self):
        wide = _deck(
            "55.00",
            url="https://example.com/wide",
            name="Powell Peralta Caballero Mask Deck 9.75x31.12",
        )
        wheel = {
            "name": "Bones STF 53mm Skateboard Wheels",
            "url": "https://example.com/bones",
            "price_new": "30.00",
            "price_old": "40.00",
            "part": "Wheels",
            "store": "Zumiez",
        }
        html = build_report_html(
            {"Zumiez_Decks": [wide], "Zumiez_Wheels": [wheel]},
            {},
            generated_at="2026-10-01T15:03:16+00:00",
        )
        self.assertIn("9.5 - 10.0 (1)", html)
        self.assertIn("10.0+ (0)", html)
        self.assertIn('data-range="9.5-10.0"', html)
        self.assertIn('class="chip is-zero" data-range="10up"', html)
        self.assertIn('data-range="all"', html)
        self.assertIn(">All</button>", html)
        self.assertNotIn("All widths", html)
        self.assertNotIn("Width min", html)
        self.assertIn("const WIDTH_RANGES = ", html)

    def test_sale_banner_and_email(self):
        state = empty_state()
        self.assertEqual(sale_banners(state, "2026-09-30"), [])
        rows = {row["store"]: row for row in describe_sales(state, "2026-09-30")}
        self.assertIn("last site-wide sale", activity_line(rows["SkateWarehouse"]))
        self.assertIn("2026-07-04", rows["SkateWarehouse"]["last_sale"])
        self.assertIn("no recorded site-wide sale", activity_line(rows["Zumiez"]))
        self.assertFalse(rows["SkateWarehouse"]["detected_today"])

        state["stores"]["SkateWarehouse"] = {"last_sale": "2026-08-11", "source": "detected"}
        day = datetime.date(2026, 8, 1)
        for offset in range(10):
            state["daily"][(day + datetime.timedelta(days=offset)).isoformat()] = {"SkateWarehouse": 40}
        state["daily"]["2026-08-11"] = {"SkateWarehouse": 140}
        banners = sale_banners(
            state,
            "2026-08-11",
            scanned_at="2026-08-11T12:00:00+00:00",
            now="2026-08-11T15:00:00+00:00",
        )
        self.assertEqual(
            banners,
            ["🔥 Skate Warehouse - site-wide sale detected (250% more items on sale) 3 hours ago"],
        )
        digest = Digest()
        digest.site_sales = describe_sales(state, "2026-08-11")
        digest.sale_banners = banners
        plain = render_plain(digest, "https://example.com/report")
        html = render_html(digest, "https://example.com/report")
        self.assertIn("site-wide sale detected (250% more items on sale)", plain)
        self.assertIn("Skate Warehouse: last site-wide sale today", plain)
        self.assertIn("site-wide sale detected (250% more items on sale)", html)
        self.assertIn("Retailer activity", html)


class DigestDefaultTests(unittest.TestCase):
    def test_fresh_page_selects_all_deals_and_not_a_digest_chip(self):
        html = build_report_html(
            {"Zumiez_Decks": [_deck()]},
            {},
            generated_at="2026-10-02T00:39:32+00:00",
        )
        line = html.split('id="changeLine"', 1)[1].split("</p>", 1)[0]
        self.assertLess(line.find('id="btnAll"'), line.find('id="btnNew"'))
        self.assertLess(line.find('id="btnNew"'), line.find('id="btnDrop"'))
        self.assertLess(line.find('id="btnDrop"'), line.find('id="btnLow"'))
        self.assertLess(line.find('id="btnLow"'), line.find('id="btnGone"'))
        self.assertIn('data-change="all"', line)
        self.assertIn(">All deals</button>", line)
        all_tag = line[line.find("<button"):line.find("</button>")]
        self.assertIn('id="btnAll"', all_tag)
        self.assertIn('aria-pressed="true"', all_tag)
        for chip in ("btnNew", "btnDrop", "btnLow", "btnGone"):
            start = line.find(f'id="{chip}"')
            tag = line[line.rfind("<button", 0, start):line.find(">", start)]
            self.assertIn('aria-pressed="false"', tag, chip)
            self.assertNotIn('aria-pressed="true"', tag, chip)
        self.assertIn('aria-label="Digest baseline"', html)
        self.assertNotIn(
            '.change-btn[aria-pressed="true"], .mode-btn[aria-pressed="true"]',
            html,
        )
        self.assertNotIn('if (state.change === "removed") return false', html)
        self.assertNotIn("deals.hidden", html)
        self.assertNotIn('snapshot.change === "new"', html)
        self.assertNotIn("state.cardNew = state.change", html)
        self.assertIn('kind === "all" || state.change === kind', html)
        blank = decode_query("")
        self.assertEqual(blank["change"], "all")
        self.assertFalse(blank["added"])
        self.assertFalse(blank["dropped"])
        self.assertFalse(blank["low"])
        self.assertEqual(encode_state(blank), "")
        cards = decode_query("added=1&dropped=1&low=1")
        self.assertEqual(cards["change"], "all")
        self.assertTrue(cards["added"] and cards["dropped"] and cards["low"])
        self.assertEqual(encode_state({"change": "new"}), "change=new")
        self.assertEqual(encode_state({"added": True, "change": "all"}), "added=1")
        watched = decode_query("watching=1&low=1")
        self.assertEqual(watched["change"], "all")
        self.assertTrue(watched["low"])


if __name__ == "__main__":
    unittest.main()
