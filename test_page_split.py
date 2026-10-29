"""The published page is a light shell: table cells wait as raw text, and the
price history is its own history.json, fetched when a chart needs it."""

import json
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

from page import _script_text, split_history, write_page
from report import build_report_html

URL = "https://www.zumiez.com/baker-figgy.html"
DECK = {
    "name": "Baker Figgy Divine Evil Deck 8.25",
    "url": URL,
    "price_new": "49.99",
    "price_old": "79.95",
    "part": "Decks",
    "store": "Zumiez",
}
HISTORY = {
    URL: {
        "name": DECK["name"],
        "store": "Zumiez",
        "part": "Decks",
        "first_seen": "2026-09-01",
        "last_seen": "2026-10-28",
        "observation_count": 3,
        "prices": {"2026-09-01": 64.99, "2026-10-01": 54.99, "2026-10-28": 49.99},
    }
}
GENERATED = "2026-10-28T15:23:36+00:00"


def _build():
    return build_report_html({"Zumiez_Decks": [DECK]}, {}, HISTORY, generated_at=GENERATED)


def _script(html, element_id):
    return html.split(f'id="{element_id}">', 1)[1].split("</script>", 1)[0]


class PageSplitTests(unittest.TestCase):
    def test_table_rows_are_attributes_only_and_their_cells_wait_as_text(self):
        html = _build()
        body = html.split('<table id="mainTable">', 1)[1].split("</table>", 1)[0]
        rows = re.findall(r'<tr class="deal-row[^"]*"[^>]*>(.*?)</tr>', body, re.S)
        self.assertEqual(rows, [""], "one row, no cells parsed up front")
        self.assertIn('data-url="https://www.zumiez.com/baker-figgy.html"', body)
        cells = _script(html, "tableRows")
        self.assertIn('class="product-name"', cells)
        self.assertIn('class="star"', cells)
        # The cards are unchanged: built in full on the server.
        self.assertIn('<article class="deal-card', html)

    def test_raw_text_cannot_end_its_script(self):
        self.assertEqual(_script_text('a</SCRIPT>b<!--c</td>'), 'a<\\/SCRIPT>b<\\!--c</td>')

    def test_history_moves_out_and_the_catalog_keeps_the_rest(self):
        html = _build()
        catalog = json.loads(_script(html, "catalogJson"))
        item = catalog["items"]["0"]
        for field in ("daily", "series", "seriesList", "chartNote"):
            self.assertNotIn(field, item)
        self.assertEqual(item["url"], URL)
        self.assertIn("offers", item, "the group view reads offers without waiting")

        page, history = split_history(html)
        self.assertNotIn('id="historyJson"', page)
        self.assertIn('id="tableRows"', page)
        self.assertIn(
            '<link rel="preload" href="history.json?v=2026-10-28T15%3A23%3A36%2B00%3A00" as="fetch" crossorigin="anonymous">',
            page,
        )
        data = json.loads(history)
        self.assertEqual(data["generated"], GENERATED)
        row = data["items"][URL]
        self.assertEqual([point[1] for point in row["daily"]][-1], 49.99)
        self.assertTrue(row["series"])
        self.assertEqual(row["seriesList"][0]["store"], "Zumiez")

    def test_write_page_publishes_both_files_and_reports_changes(self):
        html = _build()
        with tempfile.TemporaryDirectory() as directory:
            page_path = Path(directory) / "sale_items_chart.html"
            self.assertTrue(write_page(html, str(page_path)))
            history = Path(directory) / "history.json"
            self.assertTrue(history.exists())
            self.assertEqual((page_path.read_text(), history.read_text()), split_history(html))
            self.assertFalse(write_page(html, str(page_path)), "the same build changes nothing")
            self.assertFalse(list(Path(directory).glob("*.tmp")))
        # A page without inline history (an older build) is written as is.
        self.assertEqual(split_history("<html></html>"), ("<html></html>", None))

    def test_page_js_merges_fetched_history_by_url_and_survives_a_failed_fetch(self):
        source = Path(__file__).with_name("page.js").read_text(encoding="utf-8")
        block = source[source.index("let historyStatus"):source.index("function scanDay(")]
        script = r'''
const assert = require('node:assert/strict');
let catalogData = { generated: "G", items: { "0": { url: "https://a/x" }, "1": { url: "" } } };
function catalog() { return catalogData; }
const document = { getElementById: () => null };
console.warn = () => {};
let reply = null;
let asked = [];
global.fetch = url => { asked.push(url); return reply; };
''' + block + r'''
(async () => {
    reply = Promise.resolve({ ok: true, json: () => Promise.resolve({ items: {
        "https://a/x": { daily: [["2026-10-01", 5]] }, "#1": { daily: [["2026-10-02", 6]] } } }) });
    const ran = [];
    assert.equal(historyReady(), false);
    whenHistory(() => ran.push("a"));
    whenHistory(() => ran.push("b"));
    assert.deepEqual(asked, ["history.json?v=G"], "one fetch for every waiter");
    await new Promise(resolve => setTimeout(resolve, 0));
    assert.deepEqual(ran, ["a", "b"]);
    assert.equal(catalogData.items["0"].daily[0][1], 5);
    assert.equal(catalogData.items["1"].daily[0][1], 6, "a listing without a URL is keyed by id");
    whenHistory(() => ran.push("c"));
    assert.deepEqual(ran, ["a", "b", "c"], "ready history runs at once");

    historyStatus = "";
    asked = [];
    reply = Promise.resolve({ ok: false, status: 404 });
    let called = false;
    whenHistory(() => { called = true; });
    await new Promise(resolve => setTimeout(resolve, 0));
    assert.equal(historyStatus, "failed");
    assert.equal(called, false, "server-drawn charts stay when history cannot load");
    whenHistory(() => { called = true; });
    assert.deepEqual(asked, ["history.json?v=G"], "no retry loop");
})().catch(err => { console.error(err); process.exit(1); });
'''
        result = subprocess.run(["node", "-e", script], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_page_js_fills_table_cells_only_for_the_table_layout(self):
        source = Path(__file__).with_name("page.js").read_text(encoding="utf-8")
        fill = source[source.index("function fillTableRows("):source.index("function applyLayout(")]
        layout = source[source.index("function applyLayout("):source.index("let filterOrder")]
        self.assertIn("if (!cards) fillTableRows();", layout)
        for step in ("source.remove()", "applyStars()", "paintOfferPrices()", "refreshCharts()"):
            self.assertIn(step, fill)


if __name__ == "__main__":
    unittest.main()
