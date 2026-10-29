"""Disappeared, New, price drops, and hit lowest filter the grid."""

import subprocess
import unittest
from pathlib import Path

from report import Digest, build_report_html


def _deck(price="44.99", url="https://example.com/live", store="Zumiez", name=None, part="Decks"):
    return {
        "name": name or "Welcome Mock Cupid Deck 8.65",
        "url": url,
        "price_new": price,
        "price_old": "64.95",
        "part": part,
        "store": store,
    }


class DisappearedFeedTests(unittest.TestCase):
    def test_missing_listings_render_from_the_previous_scrape(self):
        live = _deck()
        gone = {
            "name": "Plan B Joslin Lew Holographic 8.375 Skateboard Deck",
            "url": "https://www.tactics.com/plan-b/joslin",
            "price_new": "55.95",
            "price_old": "69.07",
            "part": "Decks",
            "store": "Tactics",
        }
        pad = {
            "name": "Triple Eight Saver Series Pads",
            "url": "https://shop.ccs.com/products/pads-black",
            "price_new": "49.95",
            "price_old": "62.00",
            "part": "Protection",
            "store": "CCS",
        }
        history = {
            gone["url"]: {
                "name": gone["name"],
                "store": "Tactics",
                "part": "Decks",
                "last_seen": "2026-10-20",
                "prices": {"2026-10-20": 55.95},
            },
            pad["url"]: {
                "name": pad["name"],
                "store": "CCS",
                "part": "Protection",
                "last_seen": "2026-10-18",
                "prices": {"2026-10-18": 49.95},
            },
        }
        digest = Digest(removed=[
            ("Tactics_Decks", gone),
            ("CCS_Protection", pad),
            ("Zumiez_Decks", live),
        ])
        html = build_report_html(
            {"Zumiez_Decks": [live]},
            {},
            price_history=history,
            generated_at="2026-10-28T15:23:36+00:00",
            digest=digest,
        )
        grid = html.split('id="cardGrid"', 1)[1].split('id="cardPool"', 1)[0]
        pool = html.split('id="cardPool"', 1)[1].split("</template>", 1)[0]
        self.assertIn(live["url"], grid)
        self.assertNotIn('data-removed="1"', grid)
        self.assertEqual(pool.count('data-removed="1"'), 2)
        self.assertNotIn(live["url"], pool)
        card = pool.split('<article class="deal-card filtered-out"', 1)[1]
        card = card[: card.find("</article>")]
        self.assertIn("No longer in sale feed", card)
        self.assertIn("Last $55.95", card)
        self.assertIn("Last seen Oct 20 · Tactics", card)
        self.assertIn('href="https://www.tactics.com/plan-b/joslin"', card)
        self.assertIn("Plan B Joslin Lew Holographic 8.375 Skateboard Deck", card)
        self.assertIn('data-part="Decks"', card)
        self.assertIn('data-store="Tactics"', card)
        self.assertIn('data-removed="1"', card)
        pad_card = pool.split('data-url="https://shop.ccs.com/products/pads-black"', 1)[1]
        pad_card = pad_card[: pad_card.find("</article>")]
        self.assertIn('data-part="Protection"', pad_card)
        self.assertIn("Last seen Oct 18 · CCS", pad_card)
        self.assertIn('data-drops="0"', html)

    def test_change_chips_filter_the_grid_and_match_its_count(self):
        source = Path(__file__).with_name("page.js").read_text(encoding="utf-8")
        script = r"""
const rows = [];
const buttons = {};
["btnNew", "btnDrop", "btnLow", "btnGone"].forEach(id => { buttons[id] = { textContent: "" }; });
buttons.changePrefix = { textContent: "" };
const document = {
  addEventListener() {},
  getElementById(id) {
    if (buttons[id]) return buttons[id];
    if (id === "changeLine") return { dataset: { new: "9", drops: "9", lows: "9", gone: "9" } };
    return null;
  },
  querySelector() { return null; },
  querySelectorAll(selector) {
    if (selector === "#mainTable .deal-row") return rows.slice();
    return [];
  },
  createElement() { return { style: {}, append() {}, setAttribute() {}, classList: { add() {}, remove() {} } }; },
  body: { classList: { add() {}, remove() {}, toggle() {} } }
};
const window = { addEventListener() {}, matchMedia() { return { matches: false }; }, innerWidth: 1200, scrollTo() {} };
const localStorage = { getItem() { return null; }, setItem() {}, removeItem() {} };
const location = { search: "", pathname: "/", hash: "" };
const history = { replaceState() {} };
function makeRow(dataset) {
  const row = { className: "deal-row", dataset: dataset };
  row.classList = {
    contains(name) { return row.className.split(/\s+/).includes(name); },
    toggle(name, force) {
      const on = row.classList.contains(name);
      const next = force === undefined ? !on : !!force;
      const parts = row.className.split(/\s+/).filter(part => part && part !== name);
      if (next) parts.push(name);
      row.className = parts.join(" ");
      return next;
    }
  };
  return row;
}
rows.push(makeRow({
  id: "live", store: "Zumiez", part: "Decks", search: "welcome live", price: "44.99",
  discount: "30", added: "0", drop: "0", hitlow: "0", score: "10", brand: "Welcome", name: "Live"
}));
rows.push(makeRow({
  id: "fresh", store: "Zumiez", part: "Decks", search: "fresh deck", price: "30",
  discount: "10", added: "1", drop: "0", hitlow: "0", score: "10", brand: "Baker", name: "Fresh"
}));
rows.push(makeRow({
  id: "g0", store: "Tactics", part: "Decks", search: "plan b gone", price: "55.95",
  discount: "19", added: "0", drop: "0", hitlow: "0", removed: "1", score: "", brand: "Plan B", name: "Gone deck"
}));
rows.push(makeRow({
  id: "g1", store: "CCS", part: "Protection", search: "triple eight pad", price: "49.95",
  discount: "20", added: "0", drop: "0", hitlow: "0", removed: "1", score: "", brand: "Triple Eight", name: "Gone pad"
}));
function visibleIds() {
  return rows.filter(row => !row.classList.contains("filtered-out")).map(row => row.dataset.id);
}
function applyChange(kind) {
  state.change = kind;
  rows.forEach(row => row.classList.toggle("filtered-out", !rowMatches(row)));
  updateChangeLine();
}
"""
        script += source + r"""
state.part = "Decks";
state.store = "all";
state.change = "all";
applyChange("all");
if (visibleIds().join(",") !== "live,fresh") throw new Error("all deals " + visibleIds());
if (buttons.btnGone.textContent !== "Disappeared 1") throw new Error(buttons.btnGone.textContent);
if (buttons.btnNew.textContent !== "New 1") throw new Error(buttons.btnNew.textContent);
if (buttons.btnDrop.textContent !== "Price drops 0") throw new Error(buttons.btnDrop.textContent);
if (buttons.btnLow.textContent !== "Hit lowest 0") throw new Error(buttons.btnLow.textContent);

applyChange("removed");
if (visibleIds().join(",") !== "g0") throw new Error("removed decks " + visibleIds());
if (buttons.btnGone.textContent !== "Disappeared 1") throw new Error("chip " + buttons.btnGone.textContent);
if (visibleIds().length !== 1) throw new Error("grid count");

state.part = "all";
applyChange("removed");
if (visibleIds().slice().sort().join(",") !== "g0,g1") throw new Error("both gone " + visibleIds());
if (buttons.btnGone.textContent !== "Disappeared " + visibleIds().length) throw new Error(buttons.btnGone.textContent);

state.store = "Zumiez";
applyChange("removed");
if (visibleIds().length !== 0) throw new Error("zumiez disappeared " + visibleIds());
if (buttons.btnGone.textContent !== "Disappeared 0") throw new Error(buttons.btnGone.textContent);
rows.forEach(row => {
  if (!row.classList.contains("filtered-out")) throw new Error("live catalog leaked");
});

state.store = "all";
state.part = "Decks";
applyChange("drop");
if (visibleIds().length !== 0) throw new Error("price drops showed " + visibleIds());
if (buttons.btnDrop.textContent !== "Price drops 0") throw new Error(buttons.btnDrop.textContent);
const dropEntries = collectFilterActions();
if (!dropEntries.some(entry => entry.key === "change")) throw new Error("drop chip is not a resettable filter");
const dropPlan = emptyResetPlan(dropEntries, {}, filterOrder);
if (!dropPlan.buttons.some(button => button.action === "clear")) throw new Error("no reset " + dropPlan.buttons.map(button => button.label));

applyChange("new");
if (visibleIds().join(",") !== "fresh") throw new Error("new " + visibleIds());
if (buttons.btnNew.textContent !== "New 1") throw new Error(buttons.btnNew.textContent);

applyChange("lowest");
if (visibleIds().length !== 0) throw new Error("hit lowest showed " + visibleIds());
if (buttons.btnLow.textContent !== "Hit lowest 0") throw new Error(buttons.btnLow.textContent);

state.part = "Protection";
applyChange("removed");
if (visibleIds().join(",") !== "g1") throw new Error("pads " + visibleIds());
if (buttons.btnGone.textContent !== "Disappeared 1") throw new Error(buttons.btnGone.textContent);
"""
        path = Path("/tmp/disappeared-filter-test.js")
        path.write_text(script, encoding="utf-8")
        result = subprocess.run(["node", str(path)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)


if __name__ == "__main__":
    unittest.main()
