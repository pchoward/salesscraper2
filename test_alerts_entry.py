"""Subscribe and Alert me entry flows. Unsupported modes must not look saved."""

import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent


class AlertsEntryTests(unittest.TestCase):
    def test_copy_stays_inside_the_supported_contract(self):
        js = (ROOT / "page.js").read_text(encoding="utf-8")
        css = (ROOT / "page.css").read_text(encoding="utf-8")
        mobile = (ROOT / "mobile.css").read_text(encoding="utf-8")
        block = js[js.index("/* ALERTS_UI_START"):js.index("/* ALERTS_UI_END */")]
        self.assertIn('summary.textContent = "Advanced options"', block)
        self.assertIn("Get general SkateDeals deal emails. This is not a watch on one product.", block)
        self.assertIn("General deal emails are coming soon. Nothing was subscribed.", block)
        self.assertIn("An exact watch of this product is coming soon.", block)
        self.assertIn("Watching this exact product is coming soon. Nothing was saved.", block)
        self.assertIn("Alert when below $", block)
        self.assertIn("Any meaningful price drop", block)
        self.assertIn("We'll email you a link to confirm. Nothing is active until you verify that link.", block)
        self.assertIn("Match listings by brand and name (other products can match).", block)
        self.assertIn("Other sizes are coming soon and are not sent.", block)
        self.assertIn("function onAlertsKeydown(", block)
        self.assertIn("function alertsTabStops(", block)
        self.assertIn("appendQuickAlert(actions, card)", js)
        self.assertNotIn("product_url", block)
        self.assertNotIn("alert_on_new", block)
        self.assertNotIn("localStorage", block)
        self.assertIn(".alerts-advanced", css)
        self.assertIn(".alerts-product", css)
        self.assertIn(".alerts-soon", css)
        self.assertIn(".alerts-choice { min-height: 2.75rem; align-items: center; }", mobile)
        phone = mobile[mobile.rindex(".alerts-panel input"):]
        self.assertIn("font-size: 16px", phone)
        self.assertIn("min-height: 2.75rem", phone)

    def test_digest_does_not_subscribe_and_product_watch_is_explicit(self):
        source = (ROOT / "page.js").read_text(encoding="utf-8")
        block = source[source.index("/* ALERTS_UI_START"):source.index("/* ALERTS_UI_END */")]
        script = r'''
const assert = require("node:assert/strict");
class El {
    constructor(tag = "div") {
        this.tag = tag;
        this.children = [];
        this.attrs = {};
        this.className = "";
        this.hidden = false;
        this._text = "";
        this.events = {};
        this.value = "";
        this.checked = false;
        this.disabled = false;
        this.type = "";
        this.id = "";
        this.parent = null;
        this.tabIndex = 0;
        this.noValidate = false;
        this.open = false;
        this.alt = "";
        this.src = "";
    }
    append(...nodes) {
        nodes.forEach(node => {
            if (node) node.parent = this;
            this.children.push(node);
        });
    }
    appendChild(node) { this.append(node); return node; }
    replaceChildren(...nodes) { this.children = []; nodes.forEach(node => this.append(node)); }
    setAttribute(name, value) {
        this.attrs[name] = String(value);
        if (name === "id") this.id = String(value);
        if (name === "class") this.className = String(value);
        if (name === "src") this.src = String(value);
        if (name === "alt") this.alt = String(value);
    }
    getAttribute(name) { return Object.prototype.hasOwnProperty.call(this.attrs, name) ? this.attrs[name] : null; }
    removeAttribute(name) { delete this.attrs[name]; }
    addEventListener(name, fn) { (this.events[name] = this.events[name] || []).push(fn); }
    matches(sel) {
        if (sel === "*") return true;
        if (sel === "[data-action]") return this.getAttribute("data-action") != null;
        if (sel.startsWith("#")) return this.id === sel.slice(1);
        if (sel.startsWith(".")) {
            const have = this.className.split(/\s+/);
            return sel.slice(1).split(".").filter(Boolean).every(name => have.includes(name));
        }
        if (sel.includes("[") || sel.includes(",")) return false;
        return this.tag === sel;
    }
    querySelectorAll(sel) {
        const found = [];
        const visit = node => {
            (node.children || []).forEach(child => {
                if (child && (sel === "*" || child.matches(sel))) found.push(child);
                if (child) visit(child);
            });
        };
        visit(this);
        return found;
    }
    querySelector(sel) { return this.querySelectorAll(sel)[0] || null; }
    contains(node) {
        if (node === this) return true;
        return (this.children || []).some(child => child === node || (child && child.contains && child.contains(node)));
    }
    closest(sel) {
        let node = this;
        while (node) {
            if (node.matches && node.matches(sel)) return node;
            node = node.parent || null;
        }
        return null;
    }
    focus() { document.activeElement = this; }
    get textContent() {
        return this.children.length ? this.children.map(child => child && child.textContent || "").join("") : this._text;
    }
    set textContent(value) { this._text = String(value); this.children = []; }
    get classList() {
        const el = this;
        return {
            contains(name) { return el.className.split(/\s+/).includes(name); },
            add(name) {
                if (!el.className.split(/\s+/).includes(name)) el.className = (el.className + " " + name).trim();
            },
            remove(name) {
                el.className = el.className.split(/\s+/).filter(part => part && part !== name).join(" ");
            }
        };
    }
}
const location = { hostname: "localhost", pathname: "/sale_items_chart.html", search: "", hash: "" };
const history = { replaceState() { location.hash = ""; } };
const memory = {};
globalThis.sessionStorage = {
    getItem(key) { return Object.prototype.hasOwnProperty.call(memory, key) ? memory[key] : null; },
    setItem(key, value) { memory[key] = String(value); },
    removeItem(key) { delete memory[key]; }
};
const window = { SKATEDEALS_ALERTS: { apiBase: "http://127.0.0.1:8787" }, addEventListener() {} };
const document = {
    body: new El("body"),
    activeElement: null,
    events: {},
    createElement(tag) { return new El(tag); },
    addEventListener(name, fn) { (this.events[name] = this.events[name] || []).push(fn); },
    getElementById(id) {
        let found = null;
        const visit = node => {
            if (found || !node) return;
            if (node.id === id) { found = node; return; }
            (node.children || []).forEach(visit);
        };
        visit(this.body);
        return found;
    },
    querySelector(sel) { return this.body ? this.body.querySelector(sel) : null; }
};
function jsonResponse(status, body) {
    return { ok: status >= 200 && status < 300, status, headers: { get() { return ""; } }, json: async () => body };
}
const calls = [];
globalThis.fetch = async (url, options) => {
    calls.push({ url, options });
    const path = new URL(url).pathname;
    if (path === "/v1/health") return jsonResponse(200, { ok: true, api_version: "1", mode: "mock" });
    if (path === "/v1/subscribe") return jsonResponse(202, { status: "check_email" });
    return jsonResponse(500, { error: "internal_error" });
};
function subscribeCalls() { return calls.filter(call => String(call.url).endsWith("/v1/subscribe")); }
function press(key, extras) {
    const event = Object.assign({ key, shiftKey: false, preventDefault() { event.defaultPrevented = true; } }, extras || {});
    (document.events.keydown || []).forEach(fn => fn(event));
    return event;
}
''' + block + r'''
(async () => {
    const nav = new El("div");
    nav.className = "topnav-links";
    document.body.appendChild(nav);
    wireAlerts();
    assert.equal(document.getElementById("navAlerts").textContent, "Subscribe");
    assert.equal(document.getElementById("navAlerts").getAttribute("aria-label"), "Subscribe to SkateDeals deal emails");

    assert.equal(alertsProductImage({ querySelector() { return { getAttribute() { return "javascript:alert(1)"; } }; } }), "");
    assert.equal(alertsProductImage({ querySelector() { return { getAttribute() { return "data:image/png;base64,abc"; } }; } }), "");
    assert.equal(alertsProductImage({ querySelector() { return { getAttribute() { return "https://cdn.example/deck.jpg"; } }; } }), "https://cdn.example/deck.jpg");

    await openAlerts();
    assert.equal(document.getElementById("alertsTitle").textContent, "Subscribe");
    const digest = document.getElementById("alertsBody").textContent;
    assert.match(digest, /Get general SkateDeals deal emails/);
    assert.match(digest, /not a watch on one product/);
    assert.match(digest, /General deal emails are coming soon\. Nothing was subscribed\./);
    assert.match(digest, /We'll email you a link to confirm/);
    assert.match(digest, /Notification preferences for this list are coming soon/);
    assert.equal(document.getElementById("alertsConsent").checked, false);
    assert.equal(document.getElementById("alertsAdvanced").open, false);
    assert.equal(document.getElementById("alertsAdvanced").getAttribute("open"), null);
    assert.equal(document.getElementById("alertsDrop"), null);
    assert.equal(document.getElementById("alertsBroad"), null);
    assert.equal(document.querySelector(".alerts-status"), null);
    assert.equal(document.body.classList.contains("alerts-open"), true);
    document.getElementById("alertsEmail").value = "rider@example.com";
    document.getElementById("alertsConsent").checked = true;
    const beforeDigest = subscribeCalls().length;
    await document.getElementById("alertsForm").events.submit[0]({ preventDefault() {} });
    assert.equal(subscribeCalls().length, beforeDigest);
    assert.match(document.getElementById("alertsBody").textContent, /General deal emails are coming soon\. Nothing was subscribed\./);
    assert.match(document.getElementById("alertsBody").textContent, /No email was sent/);
    assert.equal(document.getElementById("alertsBody").textContent.includes("Check your email to confirm."), false);
    assert.equal(document.querySelector(".alerts-status"), null);
    assert.equal(document.getElementById("alertsTitle").textContent, "Subscribe");

    const draft = alertDraftFromDataset({
        name: "Baker Figgy Deck 8.25", brand: "Baker", part: "Decks", size: "8.25",
        price: "49.99", store: "CCS", shoesize: "9,10"
    });
    draft.image = "https://cdn.example/deck.jpg";
    await openAlerts({ draft });
    assert.equal(document.getElementById("alertsTitle").textContent, "Alert me");
    assert.equal(document.querySelector(".alerts-product-name").textContent, "Baker Figgy Deck 8.25");
    assert.match(document.querySelector(".alerts-product-price").textContent, /Current price \$49\.99/);
    assert.equal(document.querySelector(".alerts-product-photo").getAttribute("src"), "https://cdn.example/deck.jpg");
    assert.equal(document.querySelector(".alerts-product-photo").alt, "Baker Figgy Deck 8.25");
    assert.equal(document.getElementById("alertsTriggerBelow").checked, true);
    assert.equal(document.getElementById("alertsConsent").checked, false);
    assert.equal(document.getElementById("alertsAdvanced").open, false);
    assert.equal(document.getElementById("alertsBrand").disabled, true);
    assert.match(document.getElementById("alertsBody").textContent, /Sizes on this product \(9,10\) are coming soon and are not sent/);
    const closedStops = alertsTabStops(alertsPanel());
    assert.equal(closedStops.some(node => node.id === "alertsBrand"), false);
    assert.equal(closedStops.some(node => node.id === "alertsEmail"), true);
    assert.equal(closedStops.some(node => node.tag === "summary"), true);
    document.getElementById("alertsAdvanced").open = true;
    document.getElementById("alertsBroad").checked = true;
    document.getElementById("alertsBroad").events.change[0]();
    assert.equal(document.getElementById("alertsBrand").disabled, false);
    assert.equal(alertsTabStops(alertsPanel()).some(node => node.id === "alertsBrand"), true);
    const stops = alertsTabStops(alertsPanel());
    document.activeElement = stops[stops.length - 1];
    const forward = press("Tab");
    assert.equal(forward.defaultPrevented, true);
    assert.equal(document.activeElement, stops[0]);
    const backward = press("Tab", { shiftKey: true });
    assert.equal(backward.defaultPrevented, true);
    assert.equal(document.activeElement, stops[stops.length - 1]);

    document.getElementById("alertsEmail").value = "rider@example.com";
    document.getElementById("alertsConsent").checked = true;
    document.getElementById("alertsTriggerDrop").checked = true;
    document.getElementById("alertsTriggerBelow").checked = false;
    document.getElementById("alertsLow").checked = true;
    document.getElementById("alertsStock").checked = true;
    await document.getElementById("alertsForm").events.submit[0]({ preventDefault() {} });
    assert.match(document.getElementById("alertsBody").textContent, /Check your email to confirm/);
    assert.match(document.getElementById("alertsBody").textContent, /not limited to one product/);
    assert.match(document.getElementById("alertsBody").textContent, /not active yet/);
    assert.equal(document.querySelector(".alerts-status"), null);
    const payload = JSON.parse(subscribeCalls()[0].options.body);
    assert.equal(payload.email, "rider@example.com");
    assert.equal(payload.consent, true);
    assert.equal(payload.consent_version, "2026-10");
    assert.equal(payload.turnstile_token, "mock-turnstile-pass");
    const allowed = ["brand", "name", "part", "width", "max_price", "alert_on_drop", "alert_on_low", "alert_on_stock", "back_in_stock_width", "note"];
    Object.keys(payload.rules[0]).forEach(key => assert.ok(allowed.includes(key), key));
    assert.equal(payload.rules[0].brand, "Baker");
    assert.equal(payload.rules[0].name, "Baker Figgy Deck 8.25");
    assert.equal(payload.rules[0].part, "Decks");
    assert.equal(payload.rules[0].width, 8.25);
    assert.equal(payload.rules[0].max_price, undefined);
    assert.equal(payload.rules[0].alert_on_drop, true);
    assert.equal(payload.rules[0].alert_on_low, true);
    assert.equal(payload.rules[0].alert_on_stock, true);
    assert.equal(payload.rules[0].back_in_stock_width, 8.25);
    assert.equal(payload.rules[0].note, undefined);
    assert.equal(JSON.stringify(payload).includes("9,10"), false);
    assert.equal(JSON.stringify(payload).includes("cdn.example"), false);
    assert.equal(JSON.stringify(payload).includes("shoesize"), false);

    press("Escape");
    assert.equal(document.getElementById("alertsRoot").hidden, true);
    assert.equal(document.body.classList.contains("alerts-open"), false);
})().catch(err => { console.error(err); process.exit(1); });
'''
        result = subprocess.run(["node", "-e", script], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
