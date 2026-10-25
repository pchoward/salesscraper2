"""Toolbar baseline, last-visit cleanup, and empty-result resets."""

import subprocess
import unittest
from pathlib import Path

from query_state import decode_query, encode_state
from report import build_report_html


ROOT = Path(__file__).resolve().parent


def _deck(price="40.00", url="https://example.com/deck", name="Baker Team Deck 8.0"):
    return {
        "name": name,
        "url": url,
        "price_new": price,
        "price_old": "80.00",
        "part": "Decks",
        "store": "Zumiez",
        "image": "https://example.com/deck.jpg",
    }


class ToolbarBaselineTests(unittest.TestCase):
    def test_dropdown_is_gone_and_previous_scrape_is_fixed(self):
        html = build_report_html(
            {"Zumiez_Decks": [_deck()]},
            {},
            generated_at="2026-10-21T12:00:00+00:00",
        )
        tool = html.split('class="tool-line"', 1)[1].split("</header>", 1)[0]
        self.assertLess(tool.find('class="search-box tool-search"'), tool.find('class="tool-deals"'))
        self.assertLess(tool.find('class="tool-deals"'), tool.find('id="sortSelect"'))
        self.assertLess(tool.find('id="sortSelect"'), tool.find('class="tool-display"'))
        self.assertIn(">vs previous scrape<", tool)
        self.assertIn('data-baseline="previous-scrape"', tool)
        self.assertIn('<option value="discount">% off</option>', tool)
        self.assertNotIn("baselineSelect", html)
        self.assertNotIn("Since your last visit", html)
        self.assertNotIn("Since yesterday", html)
        self.assertNotIn("setVisitMode", html)
        self.assertNotIn('id="visitNote"', html)
        self.assertIn('id="emptyState" class="empty-state" hidden', html)
        self.assertIn('id="goneEmpty" class="empty-state" hidden', html)
        self.assertIn('else if (value === "discount") sortBy("discount", "desc");', html)
        source = (ROOT / "page.js").read_text(encoding="utf-8")
        self.assertNotIn("state.visitMode", source)
        self.assertNotIn("function prepareVisit", source)
        self.assertNotIn("function setVisitMode", source)
        self.assertNotIn('visitMode === "visit"', source)
        self.assertIn("function scrapeBaseline(", source)
        self.assertIn("data.hitlow === \"1\"", source)
        self.assertNotIn("dataset.visitNew", source)
        self.assertNotIn("salesscraper2.snapshot", source.split("const LAST_VISIT_KEYS", 1)[0])
        cards = [
            part.split("</article>", 1)[0]
            for part in html.split('<article class="deal-card')[1:]
        ]
        self.assertGreaterEqual(len(cards), 1)
        for card in cards:
            self.assertIn(">Alert me</button>", card)
            self.assertIn('class="card-alert"', card)
        self.assertIn("appendQuickAlert(actions, card)", source)
        self.assertIn('setAttribute("aria-label", "Alert me about this deal")', source)
        self.assertIn(".quick-alert", (ROOT / "page.css").read_text(encoding="utf-8"))

    def test_old_visit_params_do_not_change_the_page(self):
        stale = decode_query("baseline=visit&visit=1&visitmode=visit&since=yesterday&change=new&q=baker")
        self.assertEqual(stale["q"], "baker")
        self.assertEqual(stale["change"], "new")
        self.assertEqual(stale["part"], "Decks")
        self.assertEqual(encode_state(stale), "q=baker&change=new")
        retired = decode_query("?baseline=visit&since=last")
        self.assertEqual(retired["change"], "all")
        self.assertEqual(encode_state(retired), "")
        self.assertNotIn("baseline", encode_state({"change": "drop", "q": ""}))

    def test_last_visit_storage_and_empty_resets(self):
        source = (ROOT / "page.js").read_text(encoding="utf-8")
        storage = source[source.find("const LAST_VISIT_KEYS"):source.find("function starSet(")]
        baseline = source[source.find("function updateChangeLine("):source.find("function openDrawer(")]
        resets = source[source.find("let filterOrder"):source.find("function goneRows(")]
        fill = source[source.find("function fillEmpty("):source.find("function paintEmptyState(")]
        self.assertIn('button.addEventListener("click", clearFilters)', fill)
        script = storage + baseline + resets + r"""
const store = {
  "salesscraper2.snapshot": "{\"items\":{\"https://example.com/a\":{\"price\":10}}}",
  "salesscraper2.lastVisit": "yesterday",
  "salesscraper2.last-visit": "1",
  "salesscraper2.visit": "1",
  "salesscraper2.visitMode": "visit",
  "salesscraper2.stars": "[\"https://example.com/a\"]",
  "salesscraper2.views": "[{\"name\":\"Decks\"}]",
  "salesscraper2.layout": "cards",
  "salesscraper2.filterSections": "{\"brand\":true}",
  "skatedeals.alerts.manage": "manage-token",
  "price-history-note": "keep"
};
const localStorage = {
  getItem(key) { return Object.prototype.hasOwnProperty.call(store, key) ? store[key] : null; },
  removeItem(key) { delete store[key]; }
};
forgetLastVisit();
["salesscraper2.snapshot", "salesscraper2.lastVisit", "salesscraper2.last-visit", "salesscraper2.visit", "salesscraper2.visitMode"].forEach(key => {
  if (Object.prototype.hasOwnProperty.call(store, key)) throw new Error("left " + key);
});
if (store["salesscraper2.stars"] !== "[\"https://example.com/a\"]") throw new Error("stars");
if (store["salesscraper2.views"] !== "[{\"name\":\"Decks\"}]") throw new Error("views");
if (store["salesscraper2.layout"] !== "cards") throw new Error("layout");
if (store["salesscraper2.filterSections"] !== "{\"brand\":true}") throw new Error("sections");
if (store["skatedeals.alerts.manage"] !== "manage-token") throw new Error("alerts");
if (store["price-history-note"] !== "keep") throw new Error("other");

const flags = scrapeBaseline({
  dataset: { added: "0", drop: "1", hitlow: "0", visitNew: "1", visitDrop: "0", visitLow: "1" }
});
if (flags.added || !flags.drop || flags.low) throw new Error("baseline " + JSON.stringify(flags));

const nodes = {
  changeLine: { dataset: { new: "4", drops: "2", lows: "1", gone: "3", visitNew: "9" } },
  changePrefix: { textContent: "" },
  btnNew: { textContent: "" },
  btnDrop: { textContent: "" },
  btnLow: { textContent: "" },
  btnGone: { textContent: "" }
};
const document = { getElementById(id) { return nodes[id] || null; } };
updateChangeLine();
if (nodes.btnNew.textContent !== "New 4") throw new Error(nodes.btnNew.textContent);
if (nodes.btnDrop.textContent !== "Price drops 2") throw new Error(nodes.btnDrop.textContent);
if (nodes.btnLow.textContent !== "Hit lowest 1") throw new Error(nodes.btnLow.textContent);
if (nodes.btnGone.textContent !== "Disappeared 3") throw new Error(nodes.btnGone.textContent);
if (nodes.changePrefix.textContent !== "vs previous scrape") throw new Error(nodes.changePrefix.textContent);

const entries = [
  { key: "brand", label: "Baker" },
  { key: "search", label: "Search: foo" }
];
rememberFilterOrder([{ key: "brand", label: "Baker" }]);
rememberFilterOrder(entries);
const tightSearch = emptyResetPlan(entries, { brand: 2, search: 9 }, filterOrder);
const labels = tightSearch.buttons.map(button => button.label);
if (labels[0] !== "Remove Search: foo") throw new Error(labels.join(" | "));
if (labels[labels.length - 1] !== "Clear all") throw new Error(labels.join(" | "));
if (labels.length !== 2) throw new Error("same filter should be one remove " + labels.join(" | "));

const both = emptyResetPlan(entries, { brand: 11, search: 1 }, filterOrder);
const bothLabels = both.buttons.map(button => button.label);
if (bothLabels[0] !== "Remove last: Search: foo") throw new Error(bothLabels.join(" | "));
if (bothLabels[1] !== "Remove tightest: Baker") throw new Error(bothLabels.join(" | "));
if (bothLabels[2] !== "Clear all") throw new Error(bothLabels.join(" | "));
if (!both.summary.includes("Baker") || !both.summary.includes("Search: foo")) throw new Error(both.summary);
if (both.buttons.filter(button => button.action === "clear").length !== 1) throw new Error("clear");
"""
        result = subprocess.run(["node", "-e", script], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)


if __name__ == "__main__":
    unittest.main()
