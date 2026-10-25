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
        self.assertIn("Alert when below $", block)
        self.assertIn("Any meaningful price drop", block)
        self.assertIn("We'll email you a link to confirm. Nothing is active until you verify that link.", block)
        self.assertIn("Specific sneaker sizes are coming soon and are not sent.", block)
        self.assertIn("render=explicit", block)
        self.assertIn("Complete the verification check. Nothing was sent.", block)
        self.assertIn("Couldn't reach the alerts service. Nothing was sent.", block)
        self.assertIn("not on the staging allowlist", block)
        self.assertIn("If this address is already confirmed, we'll email a link to manage its alerts.", block)
        self.assertIn("function buildDigestRule(", block)
        self.assertIn("function buildWatchRule(", block)
        self.assertIn("function onAlertsKeydown(", block)
        self.assertIn("function alertsTabStops(", block)
        self.assertIn("appendQuickAlert(actions, card)", js)
        self.assertIn("product_url", block)
        self.assertNotIn("product_key", block)
        self.assertNotIn("alert_on_new", block)
        self.assertNotIn("localStorage", block)
        self.assertNotIn("General deal emails are coming soon", block)
        self.assertNotIn("exact watch of this product is coming soon", block)
        self.assertNotIn("Match listings by brand and name", block)
        self.assertIn(".alerts-turnstile { min-height: 65px; margin: 0.35rem 0 0.15rem; }", css)
        self.assertIn(".alerts-advanced", css)
        self.assertIn(".alerts-product", css)
        self.assertIn(".alerts-soon", css)
        self.assertIn(".alerts-choice { min-height: 2.75rem; align-items: center; }", mobile)
        phone = mobile[mobile.rindex(".alerts-panel input"):]
        self.assertIn("font-size: 16px", phone)
        self.assertIn("min-height: 2.75rem", phone)

    def test_digest_and_watch_payloads(self):
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
    if (path === "/v1/preferences" && options && options.method === "GET") {
        if (options.headers && options.headers.Authorization === "Bearer dead-token") {
            return jsonResponse(401, { error: "invalid_token" });
        }
        return jsonResponse(200, {
            status: "active",
            max_rules: 10,
            rules: [
                { id: "r_digest", kind: "digest", note: "old", product_key: "not-a-watch" },
                { id: "r_search", brand: "Baker", part: "Decks", name: "Baker Figgy" }
            ]
        });
    }
    if (path === "/v1/preferences" && options && options.method === "PUT") {
        const body = JSON.parse(options.body);
        return jsonResponse(200, { status: "active", max_rules: 10, email_masked: "r***@example.com", rules: body.rules });
    }
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

    const cleanedWatch = cleanRule({
        id: "r_watch", kind: "watch", product_url: "https://shop.ccs.com/products/baker",
        product_key: "shopify:ccs.com:baker", label: "Baker", alert_on_drop: false, brand: "Baker"
    });
    assert.equal(cleanedWatch.kind, "watch");
    assert.equal(cleanedWatch.product_url, "https://shop.ccs.com/products/baker");
    assert.equal(cleanedWatch.label, "Baker");
    assert.equal(cleanedWatch.id, undefined);
    assert.equal(cleanedWatch.product_key, undefined);
    assert.equal(cleanedWatch.brand, undefined);
    assert.equal(cleanedWatch.alert_on_drop, undefined);
    const cleanedDigest = cleanRule({ id: "r_digest", kind: "digest", parts: ["Wheels", "Decks"], events: ["low", "new"], product_key: "nope" });
    assert.deepEqual(cleanedDigest.parts, ["Decks", "Wheels"]);
    assert.deepEqual(cleanedDigest.events, ["new", "low"]);
    assert.equal(cleanedDigest.id, undefined);
    assert.equal(cleanedDigest.product_key, undefined);

    await openAlerts();
    assert.equal(document.getElementById("alertsTitle").textContent, "Subscribe");
    const digest = document.getElementById("alertsBody").textContent;
    assert.match(digest, /Get general SkateDeals deal emails/);
    assert.match(digest, /not a watch on one product/);
    assert.match(digest, /We'll email you a link to confirm/);
    assert.equal(document.getElementById("alertsEventnew").checked, true);
    assert.equal(document.getElementById("alertsEventdrop").checked, true);
    assert.equal(document.getElementById("alertsEventlow").checked, true);
    assert.equal(document.getElementById("alertsDigestPartDecks").checked, false);
    assert.equal(document.getElementById("alertsConsent").checked, false);
    assert.equal(document.getElementById("alertsAdvanced").open, false);
    assert.equal(document.getElementById("alertsAdvanced").getAttribute("open"), null);
    assert.equal(document.getElementById("alertsDrop"), null);
    assert.equal(document.getElementById("alertsBroad"), null);
    assert.equal(document.querySelector(".alerts-status"), null);
    assert.equal(document.body.classList.contains("alerts-open"), true);
    document.getElementById("alertsEmail").value = "rider@example.com";
    document.getElementById("alertsConsent").checked = true;
    await document.getElementById("alertsForm").events.submit[0]({ preventDefault() {} });
    assert.equal(subscribeCalls().length, 1);
    assert.match(document.getElementById("alertsBody").textContent, /Check your email to confirm/);
    assert.equal(document.getElementById("alertsBody").textContent.includes("Nothing was subscribed."), false);
    assert.equal(document.querySelector(".alerts-status"), null);
    assert.equal(document.getElementById("alertsTitle").textContent, "Check your email");
    const simple = JSON.parse(subscribeCalls()[0].options.body);
    assert.equal(simple.email, "rider@example.com");
    assert.equal(simple.consent, true);
    assert.equal(simple.consent_version, "2026-10");
    assert.equal(simple.turnstile_token, "mock-turnstile-pass");
    assert.deepEqual(simple.rules, [{ kind: "digest" }]);

    await openAlerts();
    document.getElementById("alertsEmail").value = "rider@example.com";
    document.getElementById("alertsConsent").checked = true;
    document.getElementById("alertsEventnew").checked = false;
    document.getElementById("alertsDigestPartWheels").checked = true;
    document.getElementById("alertsDigestPartDecks").checked = true;
    document.getElementById("alertsMinWidth").value = "8.5";
    document.getElementById("alertsDigestPrice").value = "80";
    await document.getElementById("alertsForm").events.submit[0]({ preventDefault() {} });
    const advanced = JSON.parse(subscribeCalls()[1].options.body);
    assert.equal(advanced.rules[0].kind, "digest");
    assert.deepEqual(advanced.rules[0].parts, ["Decks", "Wheels"]);
    assert.deepEqual(advanced.rules[0].events, ["drop", "low"]);
    assert.equal(advanced.rules[0].min_width, 8.5);
    assert.equal(advanced.rules[0].max_price, 80);
    assert.equal(document.querySelector(".alerts-status"), null);

    await openAlerts();
    document.getElementById("alertsEmail").value = "rider@example.com";
    document.getElementById("alertsConsent").checked = true;
    document.getElementById("alertsEventnew").checked = false;
    document.getElementById("alertsEventdrop").checked = false;
    document.getElementById("alertsEventlow").checked = false;
    const beforeEmpty = subscribeCalls().length;
    await document.getElementById("alertsForm").events.submit[0]({ preventDefault() {} });
    assert.equal(subscribeCalls().length, beforeEmpty);
    assert.match(document.getElementById("alertsError").textContent, /at least one/);
    assert.match(document.getElementById("alertsError").textContent, /Nothing was saved/);
    assert.equal(document.querySelector(".alerts-status"), null);
    assert.equal(document.getElementById("alertsTitle").textContent, "Subscribe");

    const draft = alertDraftFromDataset({
        name: "Heroin Egg 8.75 Skateboard Deck", brand: "Heroin", part: "Decks", size: "8.75",
        price: "49.99", store: "Zumiez", shoesize: "9,10",
        url: "https://www.zumiez.com/heroin-egg-8-75-skateboard-deck.html"
    });
    draft.image = "https://cdn.example/deck.jpg";
    await openAlerts({ draft });
    assert.equal(document.getElementById("alertsTitle").textContent, "Alert me");
    assert.equal(document.querySelector(".alerts-product-name").textContent, "Heroin Egg 8.75 Skateboard Deck");
    assert.match(document.querySelector(".alerts-product-price").textContent, /Current price \$49\.99/);
    assert.equal(document.querySelector(".alerts-product-photo").getAttribute("src"), "https://cdn.example/deck.jpg");
    assert.equal(document.getElementById("alertsTriggerBelow").checked, true);
    assert.equal(document.getElementById("alertsConsent").checked, false);
    assert.equal(document.getElementById("alertsAdvanced").open, false);
    assert.equal(document.getElementById("alertsBrand"), null);
    assert.equal(document.getElementById("alertsPart"), null);
    assert.equal(document.getElementById("alertsWidth"), null);
    assert.match(document.getElementById("alertsBody").textContent, /Specific sneaker sizes are coming soon and are not sent/);
    assert.match(document.getElementById("alertsBody").textContent, /Sizes on this product \(9,10\) are coming soon and are not sent/);
    const closedStops = alertsTabStops(alertsPanel());
    assert.equal(closedStops.some(node => node.id === "alertsLow"), false);
    assert.equal(closedStops.some(node => node.id === "alertsEmail"), true);
    assert.equal(closedStops.some(node => node.tag === "summary"), true);
    document.getElementById("alertsAdvanced").open = true;
    assert.equal(alertsTabStops(alertsPanel()).some(node => node.id === "alertsLow"), true);
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
    assert.match(document.getElementById("alertsBody").textContent, /follows that one listing/);
    assert.match(document.getElementById("alertsBody").textContent, /not active until/);
    assert.equal(document.querySelector(".alerts-status"), null);
    const payload = JSON.parse(subscribeCalls()[subscribeCalls().length - 1].options.body);
    assert.equal(payload.email, "rider@example.com");
    assert.equal(payload.consent, true);
    assert.equal(payload.consent_version, "2026-10");
    assert.equal(payload.turnstile_token, "mock-turnstile-pass");
    const allowed = ["kind", "product_url", "label", "max_price", "alert_on_drop", "alert_on_low", "alert_on_stock", "note"];
    Object.keys(payload.rules[0]).forEach(key => assert.ok(allowed.includes(key), key));
    assert.equal(payload.rules[0].kind, "watch");
    assert.equal(payload.rules[0].product_url, "https://www.zumiez.com/heroin-egg-8-75-skateboard-deck.html");
    assert.equal(payload.rules[0].label, "Heroin Egg 8.75 Skateboard Deck");
    assert.equal(payload.rules[0].max_price, undefined);
    assert.equal(payload.rules[0].alert_on_drop, true);
    assert.equal(payload.rules[0].alert_on_low, true);
    assert.equal(payload.rules[0].alert_on_stock, true);
    assert.equal(payload.rules[0].brand, undefined);
    assert.equal(payload.rules[0].name, undefined);
    assert.equal(payload.rules[0].part, undefined);
    assert.equal(payload.rules[0].width, undefined);
    assert.equal(payload.rules[0].product_key, undefined);
    assert.equal(JSON.stringify(payload).includes("9,10"), false);
    assert.equal(JSON.stringify(payload).includes("cdn.example"), false);
    assert.equal(JSON.stringify(payload).includes("shoesize"), false);

    const dropOnly = alertDraftFromDataset({
        name: "Heroin Egg 8.75 Skateboard Deck",
        price: "49.99",
        url: "https://www.zumiez.com/heroin-egg-8-75-skateboard-deck.html"
    });
    await openAlerts({ draft: dropOnly });
    document.getElementById("alertsEmail").value = "rider@example.com";
    document.getElementById("alertsConsent").checked = true;
    document.getElementById("alertsTriggerDrop").checked = true;
    document.getElementById("alertsTriggerBelow").checked = false;
    await document.getElementById("alertsForm").events.submit[0]({ preventDefault() {} });
    const dropPayload = JSON.parse(subscribeCalls()[subscribeCalls().length - 1].options.body);
    assert.deepEqual(dropPayload.rules[0], {
        kind: "watch",
        product_url: "https://www.zumiez.com/heroin-egg-8-75-skateboard-deck.html",
        label: "Heroin Egg 8.75 Skateboard Deck"
    });
    assert.equal(document.querySelector(".alerts-status"), null);

    await openAlerts({ draft: alertDraftFromDataset({ name: "Other", price: "10", url: "https://example.com/baker" }) });
    document.getElementById("alertsEmail").value = "rider@example.com";
    document.getElementById("alertsConsent").checked = true;
    const beforeBad = subscribeCalls().length;
    await document.getElementById("alertsForm").events.submit[0]({ preventDefault() {} });
    assert.equal(subscribeCalls().length, beforeBad);
    assert.match(document.getElementById("alertsError").textContent, /not tracked/);
    assert.match(document.getElementById("alertsError").textContent, /Nothing was saved/);
    assert.equal(document.getElementById("alertsBody").textContent.includes("Check your email to confirm."), false);
    assert.equal(document.querySelector(".alerts-status"), null);

    await openAlerts({ draft: alertDraftFromDataset({ name: "No link", price: "10" }) });
    document.getElementById("alertsEmail").value = "rider@example.com";
    document.getElementById("alertsConsent").checked = true;
    await document.getElementById("alertsForm").events.submit[0]({ preventDefault() {} });
    assert.equal(subscribeCalls().length, beforeBad);
    assert.match(document.getElementById("alertsError").textContent, /listing link/);
    assert.equal(document.querySelector(".alerts-status"), null);

    sessionStorage.setItem("skatedeals.alerts.manage", "manage-secret");
    await openAlerts();
    document.getElementById("alertsEmail").value = "rider@example.com";
    document.getElementById("alertsConsent").checked = true;
    const beforeSaved = subscribeCalls().length;
    await document.getElementById("alertsForm").events.submit[0]({ preventDefault() {} });
    assert.equal(subscribeCalls().length, beforeSaved);
    const put = calls.filter(call => String(call.url).endsWith("/v1/preferences") && call.options.method === "PUT").pop();
    const saved = JSON.parse(put.options.body);
    assert.deepEqual(saved.rules[0], { kind: "digest" });
    assert.equal(saved.rules[0].id, undefined);
    assert.equal(saved.rules[0].product_key, undefined);
    assert.equal(saved.rules[1].brand, "Baker");
    assert.equal(saved.rules[1].id, undefined);
    assert.equal(document.querySelector(".alerts-status").textContent, "Active");
    assert.equal(document.getElementById("alertsTitle").textContent, "Manage alerts");

    sessionStorage.setItem("skatedeals.alerts.manage", "dead-token");
    await openAlerts();
    document.getElementById("alertsEmail").value = "rider@example.com";
    document.getElementById("alertsConsent").checked = true;
    await document.getElementById("alertsForm").events.submit[0]({ preventDefault() {} });
    assert.equal(subscribeCalls().length, beforeSaved + 1);
    assert.deepEqual(JSON.parse(subscribeCalls().pop().options.body).rules, [{ kind: "digest" }]);
    assert.equal(document.querySelector(".alerts-status"), null);
    assert.equal(sessionStorage.getItem("skatedeals.alerts.manage"), null);

    press("Escape");
    assert.equal(document.getElementById("alertsRoot").hidden, true);
    assert.equal(document.body.classList.contains("alerts-open"), false);

    let nextToken = "";
    let explodeGet = false;
    const rendered = [];
    const removed = [];
    globalThis.turnstile = {
        render(el, options) {
            // Like Cloudflare's: nothing renders into an element outside the page.
            if (!el.id || document.getElementById(el.id) !== el) return undefined;
            const id = "w" + (rendered.length + 1);
            rendered.push({ id, options });
            el.setAttribute("data-rendered", id);
            return id;
        },
        remove(id) { removed.push(id); },
        getResponse(id) {
            if (explodeGet) throw new Error("Nothing to get response for");
            return rendered.some(item => item.id === id) ? nextToken : "";
        }
    };
    const staged = [];
    let stagedMode = "ok";
    let hold = null;
    globalThis.fetch = async (url, options) => {
        const path = new URL(url).pathname;
        if (path !== "/v1/health" && hold) {
            const waiting = hold;
            hold = null;
            await waiting;
        }
        staged.push({ url, options, path });
        if (path === "/v1/health") return jsonResponse(200, { ok: true, api_version: "1", mode: "staging" });
        if (stagedMode === "throw") throw new Error("Failed to fetch");
        if (stagedMode === "staging") return jsonResponse(403, { error: "staging_recipient_not_allowed" });
        if (stagedMode === "captcha") return jsonResponse(400, { error: "captcha_failed" });
        if (stagedMode === "bad-token") return jsonResponse(400, { error: "invalid_token" });
        if (path === "/v1/subscribe" || path === "/v1/link") return jsonResponse(202, { status: "check_email" });
        return jsonResponse(500, { error: "internal_error" });
    };
    function stagedPosts(path) {
        return staged.filter(call => call.path === path && call.options && call.options.method === "POST");
    }
    async function clickLabel(label) {
        const buttons = document.body.querySelectorAll("button");
        let button = null;
        for (const item of buttons) if (item.textContent === label) button = item;
        assert.ok(button, label);
        const body = document.getElementById("alertsBody");
        return body.events.click[0]({ target: button, preventDefault() {} });
    }
    window.SKATEDEALS_ALERTS = { apiBase: "http://127.0.0.1:8787", turnstileSiteKey: "0x4AAAAAAFjwOIPFNNUHi29X" };
    clearManageToken();
    await openAlerts();
    assert.equal(document.getElementById("alertsTitle").textContent, "Subscribe");
    const slot = document.getElementById("alertsTurnstile");
    assert.ok(slot);
    assert.equal(document.getElementById("alertsForm").contains(slot), true);
    assert.equal(rendered.length, 1);
    assert.equal(rendered[0].options.sitekey, "0x4AAAAAAFjwOIPFNNUHi29X");
    assert.equal(document.getElementById("alertsTurnstileScript"), null);
    assert.equal(document.getElementById("alertsBody").textContent.includes("This is a local mock"), false);
    document.getElementById("alertsEmail").value = "rider@example.com";
    document.getElementById("alertsConsent").checked = true;
    await document.getElementById("alertsForm").events.submit[0]({ preventDefault() {} });
    assert.equal(stagedPosts("/v1/subscribe").length, 0);
    assert.match(document.getElementById("alertsError").textContent, /Complete the verification check/);
    assert.match(document.getElementById("alertsError").textContent, /Nothing was sent/);
    assert.equal(document.querySelector(".alerts-status"), null);
    assert.equal(alertsUi.busy, false);

    explodeGet = true;
    document.getElementById("alertsEmail").value = "rider@example.com";
    document.getElementById("alertsConsent").checked = true;
    await document.getElementById("alertsForm").events.submit[0]({ preventDefault() {} });
    assert.equal(stagedPosts("/v1/subscribe").length, 0);
    assert.match(document.getElementById("alertsError").textContent, /Complete the verification check/);
    assert.equal(alertsUi.busy, false);
    explodeGet = false;

    nextToken = "token-ok";
    document.getElementById("alertsEmail").value = "rider@example.com";
    document.getElementById("alertsConsent").checked = true;
    let releaseHold = null;
    hold = new Promise(resolve => { releaseHold = resolve; });
    const pendingSend = document.getElementById("alertsForm").events.submit[0]({ preventDefault() {} });
    await new Promise(resolve => setTimeout(resolve, 0));
    assert.equal(document.getElementById("alertsSubmit").disabled, true);
    assert.match(document.getElementById("alertsLive").textContent, /Sending/);
    releaseHold();
    await pendingSend;
    const posted = stagedPosts("/v1/subscribe");
    assert.equal(posted.length, 1);
    const digestBody = JSON.parse(posted[0].options.body);
    assert.equal(digestBody.turnstile_token, "token-ok");
    assert.deepEqual(digestBody.rules, [{ kind: "digest" }]);
    assert.match(document.getElementById("alertsBody").textContent, /Check your email to confirm/);
    assert.equal(document.querySelector(".alerts-status"), null);
    assert.equal(alertsUi.busy, false);

    nextToken = "";
    await openAlerts();
    document.getElementById("alertsEmail").value = "rider@example.com";
    document.getElementById("alertsConsent").checked = true;
    stagedMode = "staging";
    nextToken = "token-ok";
    const beforeStaging = stagedPosts("/v1/subscribe").length;
    await document.getElementById("alertsForm").events.submit[0]({ preventDefault() {} });
    assert.equal(stagedPosts("/v1/subscribe").length, beforeStaging + 1);
    assert.match(document.getElementById("alertsError").textContent, /staging allowlist/);
    assert.equal(document.querySelector(".alerts-status"), null);
    assert.equal(document.getElementById("alertsTitle").textContent, "Subscribe");

    stagedMode = "captcha";
    document.getElementById("alertsEmail").value = "rider@example.com";
    document.getElementById("alertsConsent").checked = true;
    await document.getElementById("alertsForm").events.submit[0]({ preventDefault() {} });
    assert.match(document.getElementById("alertsError").textContent, /captcha check failed/);
    assert.equal(document.querySelector(".alerts-status"), null);

    stagedMode = "throw";
    document.getElementById("alertsEmail").value = "rider@example.com";
    document.getElementById("alertsConsent").checked = true;
    await document.getElementById("alertsForm").events.submit[0]({ preventDefault() {} });
    assert.match(document.getElementById("alertsError").textContent, /Couldn't reach the alerts service/);
    assert.match(document.getElementById("alertsError").textContent, /Nothing was sent/);
    assert.equal(alertsUi.busy, false);

    stagedMode = "ok";
    nextToken = "";
    const watch = alertDraftFromDataset({
        name: "Powell Peralta Wheels",
        price: "40.95",
        url: "https://www.tactics.com/powell-peralta-wheels"
    });
    await openAlerts({ draft: watch });
    assert.equal(document.getElementById("alertsTitle").textContent, "Alert me");
    assert.ok(document.getElementById("alertsTurnstile"));
    document.getElementById("alertsEmail").value = "pchoward@yahoo.com";
    document.getElementById("alertsConsent").checked = true;
    const beforeWatch = stagedPosts("/v1/subscribe").length;
    await document.getElementById("alertsForm").events.submit[0]({ preventDefault() {} });
    assert.equal(stagedPosts("/v1/subscribe").length, beforeWatch);
    assert.match(document.getElementById("alertsError").textContent, /Complete the verification check/);
    assert.equal(document.querySelector(".alerts-status"), null);

    nextToken = "watch-token";
    document.getElementById("alertsEmail").value = "pchoward@yahoo.com";
    document.getElementById("alertsConsent").checked = true;
    await document.getElementById("alertsForm").events.submit[0]({ preventDefault() {} });
    const watchPost = stagedPosts("/v1/subscribe").pop();
    const watchBody = JSON.parse(watchPost.options.body);
    assert.equal(watchBody.turnstile_token, "watch-token");
    assert.equal(watchBody.rules[0].kind, "watch");
    assert.equal(watchBody.rules[0].product_url, "https://www.tactics.com/powell-peralta-wheels");
    assert.equal(watchBody.rules[0].max_price, 40.95);
    assert.equal(document.querySelector(".alerts-status"), null);

    nextToken = "";
    await openAlerts({ draft: watch });
    const beforeRelink = rendered.length;
    await clickLabel("I already confirmed");
    assert.equal(document.getElementById("alertsTitle").textContent, "Email me a link");
    assert.equal(document.querySelector(".alerts-copy").textContent, "If this address is already confirmed, we'll email a link to manage its alerts.");
    assert.ok(rendered.length > beforeRelink);
    assert.ok(removed.length >= 1);
    assert.ok(document.getElementById("alertsTurnstile"));
    document.getElementById("alertsLinkEmail").value = "pchoward@yahoo.com";
    const beforeLink = stagedPosts("/v1/link").length;
    await document.getElementById("alertsLinkForm").events.submit[0]({ preventDefault() {} });
    assert.equal(stagedPosts("/v1/link").length, beforeLink);
    assert.match(document.getElementById("alertsError").textContent, /Complete the verification check/);
    assert.equal(alertsUi.busy, false);

    nextToken = "link-token";
    document.getElementById("alertsLinkEmail").value = "pchoward@yahoo.com";
    await document.getElementById("alertsLinkForm").events.submit[0]({ preventDefault() {} });
    const linkPost = stagedPosts("/v1/link").pop();
    assert.deepEqual(JSON.parse(linkPost.options.body), { email: "pchoward@yahoo.com", turnstile_token: "link-token" });
    assert.match(document.getElementById("alertsBody").textContent, /Check your email to confirm/);
    assert.equal(document.querySelector(".alerts-status"), null);

    await clickLabel("Email me a link");
    document.getElementById("alertsLinkEmail").value = "pchoward@yahoo.com";
    stagedMode = "bad-token";
    nextToken = "link-token";
    await document.getElementById("alertsLinkForm").events.submit[0]({ preventDefault() {} });
    assert.match(document.getElementById("alertsError").textContent, /invalid or already used/);
    assert.equal(document.querySelector(".alerts-status"), null);
    assert.equal(alertsUi.busy, false);
})().catch(err => { console.error(err); process.exit(1); });
'''
        result = subprocess.run(["node", "-e", script], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
