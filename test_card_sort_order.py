"""The card grid follows the chosen sort on every batch, from the first visit on.

The bug: a fresh visit (no ?sort=) opened with "% off" selected, but nothing
sorted the deal rows, so cards mounted in the page's rank order. Cards past
the first page come from #cardPool in table-body order, so every batch was
wrong too.
"""

import re
import subprocess
import unittest
from pathlib import Path

from query_state import DEFAULT_SORT
from report import build_report_html

ROOT = Path(__file__).resolve().parent

DOM = r"""
function el(tag, opts) {
  opts = opts || {};
  const node = { tag, id: opts.id || "", className: opts.className || "", dataset: Object.assign({}, opts.dataset),
                 attrs: Object.assign({}, opts.attrs), children: [], parent: null, hidden: false };
  node.classList = {
    contains(name) { return node.className.split(/\s+/).indexOf(name) >= 0; },
    add(name) { if (!node.classList.contains(name)) node.className = (node.className + " " + name).trim(); },
    remove(name) { node.className = node.className.split(/\s+/).filter(part => part && part !== name).join(" "); },
    toggle(name, on) { if (on === undefined) on = !node.classList.contains(name); on ? node.classList.add(name) : node.classList.remove(name); }
  };
  node.appendChild = child => {
    if (child.parent) child.parent.children = child.parent.children.filter(item => item !== child);
    child.parent = node;
    node.children.push(child);
    return child;
  };
  node.setAttribute = (name, value) => { node.attrs[name] = String(value); };
  node.removeAttribute = name => { delete node.attrs[name]; };
  node.getAttribute = name => (name in node.attrs ? node.attrs[name] : null);
  node.querySelectorAll = selector => queryAll(node, selector);
  node.querySelector = selector => queryAll(node, selector)[0] || null;
  return node;
}
function matches(node, part) {
  const tokens = part.match(/#[\w-]+|\.[\w-]+|\[[^\]]+\]|^[\w-]+/g) || [];
  return tokens.every(token => {
    if (token[0] === "#") return node.id === token.slice(1);
    if (token[0] === ".") return node.classList.contains(token.slice(1));
    if (token[0] === "[") {
      const eq = /^\[([\w-]+)="([^"]*)"\]$/.exec(token);
      if (eq) {
        const data = eq[1].startsWith("data-") ? node.dataset[eq[1].slice(5)] : undefined;
        return (node.attrs[eq[1]] !== undefined ? node.attrs[eq[1]] : data) === eq[2];
      }
      return token.slice(1, -1) in node.attrs;
    }
    return node.tag === token;
  });
}
function queryAll(root, selector) {
  return selector.split(",").flatMap(one => {
    let nodes = [root];
    one.trim().split(/\s+/).forEach(part => {
      const next = [];
      nodes.forEach(start => {
        const walk = node => node.children.forEach(child => { if (matches(child, part)) next.push(child); walk(child); });
        walk(start);
      });
      nodes = next;
    });
    return nodes;
  });
}
const doc = el("doc");
doc.getElementById = id => queryAll(doc, "#" + id)[0] || null;
doc.querySelector = selector => queryAll(doc, selector)[0] || null;
doc.querySelectorAll = selector => queryAll(doc, selector);
global.document = doc;
"""


def _slice(source, start, end):
    return source[source.index(start):source.index(end)]


class CardSortOrderTests(unittest.TestCase):
    def test_every_batch_follows_the_sort_from_a_fresh_visit_on(self):
        source = (ROOT / "page.js").read_text(encoding="utf-8")
        script = (
            "const DEFAULT_SORT = " + repr(DEFAULT_SORT).replace("'", '"') + ";\n"
            "const CARD_PAGE_SIZE = 24;\n"
            "let state = { sortKey: DEFAULT_SORT, sortDir: \"desc\" };\n"
            "let rowList = null, rowById = null, cardById = null, detailById = null, chartObserver = null;\n"
            "function mirrorSort() {}\nfunction syncUrl() {}\nfunction paintOfferPrices() {}\nfunction fitCardPhotos() {}\n"
            + DOM
            + _slice(source, "function indexDeals(", "function readJson(")
            + _slice(source, "function cardPageSize(", "function applyFilters(")
            + _slice(source, "const SORT_NUMERIC", "function sortTable(")
            + r"""
const tbody = el("tbody");
const table = el("table", { id: "mainTable" });
table.appendChild(tbody);
const grid = el("div", { id: "cardGrid" });
const pool = el("div", { id: "cardPool" });
const more = el("button", { id: "showMoreCards" });
[table, grid, more, pool].forEach(node => doc.appendChild(node));

// 70 decks in the page's rank order (drops and new first), the way the old
// build emitted them: % off is unrelated to rank, with ties, a few sold out
// and two without a % off.
const deals = [];
for (let rank = 0; rank < 70; rank++) {
  const discount = rank === 5 || rank === 50 ? "" : String(((rank * 37) % 23) * 2.5 + 10);
  const data = { id: String(rank), rank: String(rank), discount, price: String(100 - ((rank * 13) % 61)),
                 soldout: rank % 17 === 3 ? "1" : "0", store: ["CCS", "Zumiez", "Tactics"][rank % 3] };
  deals.push(data);
  tbody.appendChild(el("tr", { className: "deal-row", dataset: data }));
  (rank < 24 ? grid : pool).appendChild(el("article", { className: "deal-card", dataset: Object.assign({}, data) }));
}

function expected(key, dir, keep) {
  const num = value => parseFloat(value);
  return deals.filter(keep || (() => true)).slice().sort((a, b) => {
    if ((a.soldout === "1") !== (b.soldout === "1")) return a.soldout === "1" ? 1 : -1;
    const am = a[key] === "", bm = b[key] === "";
    if (am !== bm) return am ? 1 : -1;
    const diff = am ? 0 : (key === "store" ? a[key].localeCompare(b[key]) : num(a[key]) - num(b[key])) * (dir === "asc" ? 1 : -1);
    return diff || num(a.rank) - num(b.rank);
  }).map(deal => deal.id);
}
const live = node => !node.classList.contains("filtered-out") && !node.classList.contains("grouped-hide");
const shown = () => grid.querySelectorAll(".deal-card").filter(live).map(card => card.dataset.id);
function revealAll() {
  for (let i = 0; i < 20 && !more.hidden; i++) revealMoreCards();
  return shown();
}
function same(label, got, want) {
  if (got.join(",") !== want.join(",")) throw new Error(label + "\n got  " + got.join(",") + "\n want " + want.join(","));
}

// Fresh visit: no sortBy call. applyFilters orders the rows, then cards mount.
dealRows();
if (orderRows()) syncCardOrder();
same("first page", shown(), expected("discount", "desc").slice(0, 24));
same("every batch", revealAll(), expected("discount", "desc"));

// A filter: the whole filtered list stays sorted, not just the batch.
cardShown = cardPageSize();
dealRows().forEach(row => row.classList.toggle("filtered-out", row.dataset.store === "Zumiez"));
if (orderRows()) syncCardOrder();
syncMountedCards();
const notZumiez = deal => deal.store !== "Zumiez";
same("filtered first page", shown(), expected("discount", "desc", notZumiez).slice(0, 24));
same("filtered batches", revealAll(), expected("discount", "desc", notZumiez));
dealRows().forEach(row => row.classList.remove("filtered-out"));

// Other sorts, and back: ties fall back to rank, whatever sort came before.
[["price", "asc"], ["price", "desc"], ["store", "asc"], ["discount", "desc"]].forEach(([key, dir]) => {
  cardShown = cardPageSize();
  sortBy(key, dir);
  same(key + " " + dir, revealAll(), expected(key, dir));
});

// Shoe-size offers rewrite % off on the rows: the next pass re-sorts.
cardShown = cardPageSize();
dealRows().forEach(row => {
  if (row.dataset.id === "69") row.dataset.discount = "99";
});
deals[69].discount = "99";
if (orderRows()) syncCardOrder();
syncMountedCards();
same("after an offer changed % off", shown().slice(0, 1), ["69"]);
"""
        )
        result = subprocess.run(["node", "-e", script], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_apply_filters_sorts_before_cards_mount(self):
        source = (ROOT / "page.js").read_text(encoding="utf-8")
        body = _slice(source, "function applyFilters(", "function paintKeepaCounts(")
        self.assertIn("if (orderRows()) syncCardOrder();", body)
        self.assertLess(body.index("orderRows()"), body.index("applyGroupVisibility()"), "cards mount in applyGroupVisibility")
        self.assertIn("orderRows();", _slice(source, "function sortBy(", "function orderRows("))

    def test_the_page_is_built_in_the_default_sort_and_keeps_rank(self):
        self.assertEqual(DEFAULT_SORT, "discount", "the build order below assumes % off")

        def deck(n, price, old, stock=None):
            item = {
                "name": f"Baker Team Deck {n} 8.25",
                "url": f"https://www.zumiez.com/baker-{n}.html",
                "price_new": price,
                "price_old": old,
                "part": "Decks",
                "store": "Zumiez",
            }
            if stock:
                item["stock"] = stock
            return item

        decks = [deck(n, f"{60 - n:.2f}", "80.00") for n in range(30)]
        decks.append(deck(99, "10.00", "80.00", stock="out_of_stock"))
        html = build_report_html({"Zumiez_Decks": decks}, {}, generated_at="2026-10-29T12:00:00+00:00")
        cards = re.findall(r'<article class="deal-card[^"]*"[^>]*data-discount="([^"]*)"', html)
        sold = re.findall(r'<article class="deal-card[^"]*"[^>]*data-soldout="1"', html)
        self.assertEqual(len(cards), 31)
        self.assertEqual(len(sold), 1)
        values = [float(value) for value in cards]
        self.assertEqual(values[:-1], sorted(values[:-1], reverse=True), "highest % off first, in the grid and the pool")
        self.assertEqual(values[-1], 87.5, "sold out goes last even at the top % off")
        body = html.split('<table id="mainTable">', 1)[1].split("</table>", 1)[0]
        rows = re.findall(r'<tr class="deal-row[^"]*"[^>]*data-discount="([^"]*)"', body)
        self.assertEqual(rows, cards, "table body and cards share one order")
        # data-rank still carries the drops-and-new-first order for that option.
        ranks = sorted(int(rank) for rank in re.findall(r'<tr class="deal-row[^"]*"[^>]*data-rank="(\d+)"', body))
        self.assertEqual(ranks, list(range(31)))


if __name__ == "__main__":
    unittest.main()
