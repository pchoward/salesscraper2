"""Alert and watch controls stay on Skate and disappear where alerts are off.

Skate's page has no SPORT_SETTINGS. Another sport sends alerts: false until
delivery is turned on, and that page must not offer Alert me, Subscribe, or
the card and Quick View watch prompts.
"""

import subprocess
import unittest
from pathlib import Path

import sports
from report import build_report_html

from page import _removed_card_html


def _deck():
    return {
        "name": "Baker Brand Logo 8.25 Skateboard Deck",
        "url": "https://example.com/baker",
        "price_new": "39.99",
        "price_old": "64.95",
        "part": "Decks",
        "store": "Zumiez",
        "image": "https://example.com/deck.jpg",
    }


def _bmx():
    return {
        "name": "Cult Gateway Frame 20.75\"",
        "url": "https://bmx.example/cult-gateway",
        "price_new": "199.99",
        "price_old": "299.99",
        "availability": "In stock",
        "part": "Frames & Forks",
        "store": "Albe's BMX",
        "image": "https://example.com/frame.jpg",
    }


def _cards(html):
    return [
        part.split("</article>", 1)[0]
        for part in html.split('<article class="deal-card')[1:]
    ]


def _page(data, sport=None):
    kwargs = {"generated_at": "2026-11-01T12:00:00+00:00"}
    if sport is not None:
        kwargs["sport"] = sport
    return build_report_html(data, {}, {}, **kwargs)


class SportAlertMarkupTests(unittest.TestCase):
    def test_skate_cards_keep_alert_and_watch_controls(self):
        html = _page({"Zumiez_Decks": [_deck()]})
        self.assertNotIn("const SPORT_SETTINGS =", html)
        cards = _cards(html)
        self.assertTrue(cards)
        for card in cards:
            self.assertIn(">Alert me</button>", card)
            self.assertIn('aria-label="Watch this item"', card)
        self.assertIn('id="watchingToggle"', html)
        self.assertIn('data-kind="watch"', html)
        self.assertIn('id="navTrack"', html)

    def test_bmx_cards_and_quick_view_have_no_alert_or_watch_prompt(self):
        item = _bmx()
        html = _page({"Albes_Frames": [item]}, sport=sports.BMX)
        self.assertIn('"alerts": false', html)
        cards = [card for card in _cards(html) if "cult-gateway" in card]
        self.assertEqual(len(cards), 1)
        card = cards[0]
        self.assertNotIn("Alert me", card)
        self.assertNotIn('class="star"', card)
        self.assertNotIn('class="card-alert"', card)
        self.assertIn("Quick view", card)
        self.assertNotIn('id="watchingToggle"', html)
        self.assertNotIn('data-kind="watch"', html)
        # The header Track link is the shared nav, left for the header owner.
        self.assertIn('id="navTrack"', html)
        row = {
            "url": item["url"],
            "name": item["name"],
            "store": item["store"],
            "part": item["part"],
            "brand": "Cult",
            "width_key": "",
            "price": item["price_new"],
            "price_old": item["price_old"],
            "currency": "USD",
            "last_seen": "2026-11-01",
            "image": item["image"],
        }
        gone = _removed_card_html(row, "g0", alerts=False)
        self.assertNotIn("Alert me", gone)
        self.assertNotIn('class="star"', gone)
        kept = _removed_card_html(row, "g0", alerts=True)
        self.assertIn(">Alert me</button>", kept)
        self.assertIn('aria-label="Watch this item"', kept)

    def test_client_hides_quick_view_prompts_and_does_not_open_alerts(self):
        source = Path("page.js").read_text(encoding="utf-8")
        fill = source[source.index("function fillQuickView("):source.index("function quickKicker(")]
        alerts_on = source[source.index("function sportAlertsOn("):source.index("async function openAlerts(")]
        open_alerts = source[source.index("async function openAlerts("):source.index("function appendQuickAlert(")]
        wire = source[source.index("function wireAlerts("):source.index('if (typeof document !== "undefined") document.addEventListener("DOMContentLoaded"')]
        script = r"""
const assert = require("node:assert/strict");
class Element {
    constructor(tag) {
        this.tag = tag || "div";
        this.children = [];
        this.className = "";
        this.dataset = {};
        this.attrs = {};
        this.hidden = false;
        this.textContent = "";
        this.id = "";
        this.classList = { add() {}, remove() {}, toggle() {}, contains() { return false; } };
    }
    append(...nodes) { this.children.push(...nodes); }
    appendChild(node) { this.append(node); }
    replaceChildren() { this.children = []; }
    setAttribute(name, value) { this.attrs[name] = String(value); if (name === "class") this.className = String(value); }
    getAttribute(name) { return this.attrs[name] || null; }
    addEventListener() {}
    querySelectorAll(selector) {
        const nested = this.children.flatMap(child => [child, ...child.querySelectorAll("*")]);
        if (!selector || selector === "*") return nested;
        const name = String(selector).replace(/^\./, "");
        return nested.filter(node => String(node.className || "").split(/\s+/).includes(name));
    }
    querySelector(selector) { return this.querySelectorAll(selector)[0] || null; }
}
const panel = new Element("div");
panel.append(new Element("div"));
const body = new Element("div");
const document = {
    getElementById: id => ({ quickView: panel, quickBody: body }[id] || null),
    createElement: tag => new Element(tag),
    addEventListener() {},
    body: new Element("body"),
};
const window = { addEventListener() {} };
function historyReady() { return true; }
function whenHistory() {}
function catalog() { return { items: { a: { name: "Frame", store: "Albe's BMX" } }, generated: "2026-11-01" }; }
function quickFacts() { return { symbol: "$", viewUrl: "https://bmx.example/cult", viewLabel: "View at Albe's BMX", specs: [] }; }
function quickMoney(symbol, amount) { return symbol + Number(amount).toFixed(2); }
function quickKicker() { return "Albe's BMX"; }
function quickDealBadge() { return ""; }
function appendQuickListLine() {}
function appendQuickSpecTable() {}
function appendQuickGallery() {}
function syncQuickStar() {}
function appendQuickMore() {}
let alertsAppended = 0;
function appendQuickAlert(parent) {
    alertsAppended += 1;
    const button = new Element("button");
    button.className = "quick-alert";
    button.textContent = "Alert me";
    parent.appendChild(button);
}
""" + fill + alerts_on + open_alerts + wire + r"""
const card = new Element("article");
card.dataset = { id: "a", price: "199.99", original: "299.99", store: "Albe's BMX" };
let SPORT_SETTINGS = { id: "bmx", label: "BMX", alerts: false };
fillQuickView(card);
assert.equal(alertsAppended, 0, "Quick View does not offer Alert me");
assert.equal(body.querySelector(".quick-star"), null, "Quick View has no watch star");
assert.equal(body.querySelector(".quick-view-link").textContent, "View Deal");

body.replaceChildren();
alertsAppended = 0;
SPORT_SETTINGS = undefined;
fillQuickView(card);
assert.equal(alertsAppended, 1, "Skate Quick View still offers Alert me");
assert.ok(body.querySelector(".quick-star"), "Skate Quick View still has the watch star");
""" + r"""
const alertsUi = { wired: false, open: false };
let mounted = 0;
let shell = 0;
mountAlertsNav = function() { mounted += 1; };
ensureAlertsShell = function() { shell += 1; };
onAlertsKeydown = function() {};
consumeAlertsFragment = function() { return null; };
setHidden = function() {};
SPORT_SETTINGS = { id: "bmx", label: "BMX", alerts: false };
wireAlerts();
assert.equal(mounted, 0, "Subscribe is not added");
assert.equal(shell, 0, "the alerts panel is not built");
openAlerts({});
assert.equal(alertsUi.open, false, "alerts cannot be opened");

SPORT_SETTINGS = undefined;
alertsUi.wired = false;
wireAlerts();
assert.equal(mounted, 1, "Skate still gets Subscribe");
assert.equal(shell, 1);
"""
        result = subprocess.run(["node", "-e", script], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)


if __name__ == "__main__":
    unittest.main()
