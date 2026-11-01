"""Card price line: list price until a second tracked day, then the average.

A first-day card used to read "Average $2.50 / Now $2.50". The percent off is
still the store's claimed discount versus its list price. The client repaint
in page.js follows the same rule as the server markup.
"""

import subprocess
import unittest
from pathlib import Path

from report import build_report_html


def _deck(price, url, name, old="27.95", part="Decks"):
    item = {
        "name": name,
        "url": url,
        "price_new": price,
        "part": part,
        "store": "Zumiez",
        "image": "https://example.com/deck.jpg",
    }
    if old is not None:
        item["price_old"] = old
    return item


def _history(item, prices):
    days = sorted(prices)
    return {
        "name": item["name"],
        "store": item["store"],
        "part": item["part"],
        "first_seen": days[0],
        "last_seen": days[-1],
        "prices": prices,
    }


def _card(html, needle):
    return next(
        part.split("</article>", 1)[0]
        for part in html.split('<article class="deal-card')[1:]
        if needle in part
    )


def _page(items, history):
    data = {}
    for item in items:
        data.setdefault(item["store"] + "_" + item["part"], []).append(item)
    return build_report_html(
        data,
        {},
        price_history=history,
        generated_at="2026-11-01T18:00:00+00:00",
    )


class CardWasPriceTests(unittest.TestCase):
    def test_one_day_shows_list_price_and_list_discount(self):
        item = _deck("2.50", "https://example.com/first-day", "Baker First Day 8.0 Deck")
        html = _page([item], {item["url"]: _history(item, {"2026-11-01": 2.50})})
        card = _card(html, "first-day")
        self.assertIn("Was $27.95", card)
        self.assertIn("Now $2.50", card)
        self.assertIn(">·</span>", card)
        self.assertNotIn("Average ", card)
        self.assertNotIn(">/</span>", card)
        # (27.95 - 2.50) / 27.95 is 91%, not a comparison against the one tracked price.
        self.assertIn("↓ 91%", card)
        self.assertIn("not a tracked market price", card)

    def test_two_days_keep_the_tracked_average(self):
        item = _deck("2.50", "https://example.com/two-days", "Baker Two Days 8.0 Deck")
        html = _page(
            [item],
            {item["url"]: _history(item, {"2026-10-30": 10.00, "2026-11-01": 2.50})},
        )
        card = _card(html, "two-days")
        self.assertIn("Average $6.25", card)
        self.assertIn("Now $2.50", card)
        self.assertIn(">/</span>", card)
        self.assertNotIn("Was ", card)
        self.assertIn("↓ 91%", card)

    def test_missing_list_price_has_no_was_line(self):
        one = _deck("2.50", "https://example.com/no-list", "Bones Reds Bearings", old=None, part="Bearings")
        two = _deck(
            "2.50", "https://example.com/no-list-history", "Bones Swiss Bearings", old=None, part="Bearings"
        )
        html = _page(
            [one, two],
            {
                one["url"]: _history(one, {"2026-11-01": 2.50}),
                two["url"]: _history(two, {"2026-10-30": 4.00, "2026-11-01": 2.50}),
            },
        )
        short = _card(html, "no-list\"")
        self.assertIn("Now $2.50", short)
        self.assertIn("No list price", short)
        self.assertNotIn("Was ", short)
        self.assertNotIn("Average ", short)
        self.assertIn('class="avg-price" data-symbol="$" hidden', short)
        tracked = _card(html, "no-list-history")
        self.assertIn("Average $3.25", tracked)
        self.assertIn("No list price", tracked)
        self.assertNotIn("Was ", tracked)

    def test_client_repaint_matches_the_server_rule(self):
        source = Path("page.js").read_text(encoding="utf-8")
        script = "\n".join([
            source[source.index("function addDays("):source.index("function markerColor(")],
            source[source.index("function clipDailyPrices("):source.index("function sparkDirection(")],
            source[source.index("function paintOneCardStat("):source.index("function paintCardStats(")],
        ])
        script += r"""
const assert = require("node:assert/strict");
let chartWindow = 90;
let historyLoaded = true;
let waited = 0;
function historyReady() { return historyLoaded; }
function whenHistory(fn) { waited += 1; }
function catalog() { return catalogData; }
let catalogData = { generated: "2026-11-01", items: {} };

class Node {
    constructor(className, text) {
        this.className = className;
        this.textContent = text || "";
        this.hidden = false;
        this.dataset = {};
        this.children = [];
    }
    querySelector(selector) {
        const name = selector.replace(/^\./, "");
        return this.children.find(child => child.className.split(/\s+/).includes(name)) || null;
    }
}

function card(id, original, stat, sep) {
    const root = new Node("deal-card");
    root.dataset = { id: id, original: original, price: "2.50" };
    const avg = new Node("avg-price", stat);
    avg.dataset.symbol = "$";
    const slash = new Node("price-sep", sep);
    const now = new Node("now-price", "Now $2.50");
    root.children = [avg, slash, now];
    return root;
}

catalogData.items["1"] = { daily: [["2026-11-01", 2.5]] };
const first = card("1", "27.95", "Average $2.50", "/");
paintOneCardStat(first);
assert.equal(first.querySelector(".avg-price").textContent, "Was $27.95");
assert.equal(first.querySelector(".avg-price").hidden, false);
assert.equal(first.querySelector(".price-sep").textContent, "\u00b7");
assert.equal(first.querySelector(".price-sep").hidden, false);

catalogData.items["2"] = { daily: [["2026-10-30", 10], ["2026-11-01", 2.5]] };
const older = card("2", "27.95", "Was $27.95", "\u00b7");
paintOneCardStat(older);
assert.equal(older.querySelector(".avg-price").textContent, "Average $6.25");
assert.equal(older.querySelector(".price-sep").textContent, "/");

catalogData.items["3"] = { daily: [["2026-11-01", 2.5]] };
const bare = card("3", "", "Average $2.50", "/");
paintOneCardStat(bare);
assert.equal(bare.querySelector(".avg-price").hidden, true);
assert.equal(bare.querySelector(".price-sep").hidden, true);
assert.equal(bare.querySelector(".avg-price").textContent.includes("Was"), false);
assert.equal(bare.querySelector(".avg-price").textContent.includes("Average"), true);

chartWindow = 1;
catalogData.items["4"] = { daily: [["2026-10-30", 10], ["2026-11-01", 2.5]] };
const narrowed = card("4", "27.95", "Average $6.25", "/");
paintOneCardStat(narrowed);
assert.equal(narrowed.querySelector(".avg-price").textContent, "Was $27.95");
assert.equal(narrowed.querySelector(".price-sep").textContent, "\u00b7");

historyLoaded = false;
const waiting = card("5", "27.95", "Was $27.95", "\u00b7");
paintOneCardStat(waiting);
assert.equal(waiting.querySelector(".avg-price").textContent, "Was $27.95");
assert.equal(waited, 1);
"""
        result = subprocess.run(["node", "-e", script], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)


if __name__ == "__main__":
    unittest.main()
