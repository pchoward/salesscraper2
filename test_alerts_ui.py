"""Alerts panel, API client, and coming-soon behavior. Node runs the page script."""

import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent


class AlertsUiTests(unittest.TestCase):
    def test_styles_and_source_guardrails(self):
        js = (ROOT / "page.js").read_text(encoding="utf-8")
        css = (ROOT / "page.css").read_text(encoding="utf-8")
        mobile = (ROOT / "mobile.css").read_text(encoding="utf-8")
        contract = (ROOT / "docs" / "alerts-api-contract.md").read_text(encoding="utf-8")
        self.assertIn("const ALERTS_API_BASE = \"\";", js)
        self.assertIn("function appendQuickAlert(", js)
        self.assertIn("appendQuickAlert(actions, card)", js)
        self.assertIn('summary.textContent = "More details"', js)
        self.assertIn("#manage=", js)
        self.assertNotIn("RESEND_API_KEY", js)
        self.assertNotIn("SMTP_PASSWORD", js)
        self.assertNotIn("sk_live", js)
        self.assertNotIn("whsec_", js)
        self.assertIn(".quick-alert", css)
        self.assertIn("#alertsRoot", css)
        self.assertIn(".alerts-status.is-active", css)
        self.assertIn(".alerts-status.is-pending", css)
        phone = mobile[mobile.rindex(".alerts-panel input"):]
        self.assertIn("font-size: 16px", phone)
        self.assertIn("min-height: 2.75rem", phone)
        self.assertIn("Email alerts coming soon", contract)
        self.assertIn("manage_token", contract)

    def test_client_fragment_and_panel(self):
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
        this.tabIndex = 0;
        this.noValidate = false;
    }
    append(...nodes) { nodes.forEach(node => this.children.push(node)); }
    appendChild(node) { this.append(node); return node; }
    replaceChildren(...nodes) { this.children = [...nodes]; }
    setAttribute(name, value) {
        this.attrs[name] = String(value);
        if (name === "id") this.id = String(value);
        if (name === "class") this.className = String(value);
    }
    getAttribute(name) { return Object.prototype.hasOwnProperty.call(this.attrs, name) ? this.attrs[name] : null; }
    removeAttribute(name) { delete this.attrs[name]; }
    addEventListener(name, fn) { (this.events[name] = this.events[name] || []).push(fn); }
    matches(sel) {
        if (sel === "*") return true;
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
                if (sel === "*" || child.matches(sel)) found.push(child);
                visit(child);
            });
        };
        visit(this);
        return found;
    }
    querySelector(sel) { return this.querySelectorAll(sel)[0] || null; }
    contains(node) {
        if (node === this) return true;
        return (this.children || []).some(child => child === node || (child.contains && child.contains(node)));
    }
    closest(sel) { return this.matches(sel) ? this : null; }
    focus() { document.activeElement = this; }
    get textContent() {
        return this.children.length ? this.children.map(child => child.textContent).join("") : this._text;
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
            },
            toggle(name, force) {
                const has = el.className.split(/\s+/).includes(name);
                const next = force == null ? !has : !!force;
                if (next) this.add(name); else this.remove(name);
            }
        };
    }
}
const location = { hostname: "localhost", pathname: "/sale_items_chart.html", search: "?token=should-stay-out", hash: "" };
const history = {
    replaceState(state, title, url) {
        const text = String(url || "");
        location.hash = text.includes("#") ? "#" + text.split("#").slice(1).join("#") : "";
    }
};
const window = { SKATEDEALS_ALERTS: { mock: true }, addEventListener() {} };
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
function findButton(text) {
    const body = document.getElementById("alertsBody");
    const buttons = body ? body.querySelectorAll("button") : [];
    for (const button of buttons) if (button.textContent === text) return button;
    return null;
}
''' + block + r'''
(async () => {
    assert.equal(alertsResolveConfig({ config: { mock: true }, host: "pchoward.github.io" }).mode, "soon");
    assert.equal(alertsResolveConfig({ config: { mock: true }, host: "localhost" }).mode, "mock");
    const liveConfig = alertsResolveConfig({ config: { apiBase: "https://alerts.example.com/" }, host: "pchoward.github.io" });
    assert.equal(liveConfig.mode, "live");
    assert.equal(liveConfig.apiBase, "https://alerts.example.com");
    assert.equal(alertsResolveConfig({ config: { apiBase: "http://alerts.example.com" }, host: "pchoward.github.io" }).mode, "soon");
    assert.equal(alertsResolveConfig({ config: { apiBase: "http://127.0.0.1:8787" }, host: "localhost" }).mode, "live");
    assert.equal(alertsResolveConfig({ config: { apiBase: "https://user:pass@alerts.example.com" }, host: "localhost" }).mode, "soon");
    assert.equal(alertsResolveConfig({ config: {}, host: "sale.github.io" }).mode, "soon");

    assert.deepEqual(readAlertsFragment("#verify=abc"), { purpose: "verify", token: "abc" });
    assert.deepEqual(readAlertsFragment("#manage=abc%3D"), { purpose: "manage", token: "abc=" });
    assert.deepEqual(readAlertsFragment("#token=abc&purpose=manage"), { purpose: "manage", token: "abc" });
    assert.equal(readAlertsFragment("#token=abc").purpose, "auto");
    assert.equal(readAlertsFragment("#token=abc").token, "abc");
    assert.equal(readAlertsFragment(location.search), null);
    assert.equal(manageTokenFromVerify({ manage_link: "https://pages.example/?token=nope" }), "");
    assert.equal(manageTokenFromVerify({ manage_link: "https://pages.example/#manage=yes" }), "yes");
    assert.equal(manageTokenFromVerify({ manage_token: "abc" }), "abc");

    const named = ruleFromDraft({
        match: "name", brand: "Baker", name: "Baker Figgy Deck 8.25", part: "Decks", size: "8.25",
        product_url: "https://example.com/p", max_price: "49.99",
        alert_on_drop: true, alert_on_low: true, alert_on_stock: true, status: "active"
    });
    assert.equal(named.name, "Baker Figgy Deck 8.25");
    assert.equal(named.brand, "Baker");
    assert.equal(named.width, 8.25);
    assert.equal(named.back_in_stock_width, 8.25);
    assert.equal(named.alert_on_low, true);
    assert.equal(named.status, undefined);
    const brandOnly = ruleFromDraft({ match: "brand", brand: "Baker", name: "Secret name", product_url: "https://example.com/p" });
    assert.equal(brandOnly.brand, "Baker");
    assert.equal(brandOnly.name, undefined);
    assert.equal(brandOnly.product_url, undefined);
    assert.equal(ruleFromDraft({ name: "X", product_url: "javascript:alert(1)" }).product_url, undefined);
    assert.equal(ruleBadge("pending", { status: "active" }).label, "Pending verification");
    assert.equal(ruleBadge("active", { status: "active" }).key, "active");
    assert.equal(ruleBadge("active", { status: "active", paused: true }).label, "Paused");
    assert.equal(ruleBadge("active", { brand: "Baker" }).label, "Pending verification");
    assert.equal(cleanRule({ brand: "Baker", status: "active" }).status, undefined);

    let calls = 0;
    const soon = createAlertsClient({ mode: "soon" }, () => { calls += 1; return {}; });
    const denied = await soon.subscribe({ email: "a@b.co", consent: true, rules: [{ brand: "Baker" }] });
    assert.equal(calls, 0);
    assert.equal(denied.error, "unavailable");
    assert.equal(soon.peek("a@b.co"), null);

    const seen = [];
    const fetchImpl = async (url, options) => {
        seen.push({ url, options });
        if (url.endsWith("/verify")) {
            return { ok: true, status: 200, json: async () => ({ status: "active", manage_token: "m1", email_masked: "a***@b.co" }) };
        }
        if (url.endsWith("/preferences") && options.method === "PUT") {
            return { ok: false, status: 429, json: async () => ({ error: "rate_limited", message: "slow down" }) };
        }
        if (url.endsWith("/preferences")) {
            return { ok: true, status: 200, json: async () => ({ status: "active", email_masked: "a***@b.co", rules: [{ rule_id: "r1", brand: "Baker", status: "active" }] }) };
        }
        return { ok: true, status: 202, json: async () => ({}) };
    };
    const live = createAlertsClient({ mode: "live", apiBase: "https://alerts.example.com/v1" }, fetchImpl);
    await live.subscribe({ email: "a@b.co", consent: true, rules: [{ brand: "Baker" }], consent_version: "2026-10-20" });
    assert.equal(seen[0].url, "https://alerts.example.com/v1/subscribe");
    assert.equal(seen[0].options.credentials, "omit");
    assert.equal(seen[0].url.includes("a@b.co"), false);
    await live.verify("verify-secret");
    assert.equal(seen[1].url, "https://alerts.example.com/v1/verify");
    assert.deepEqual(JSON.parse(seen[1].options.body), { token: "verify-secret" });
    assert.equal(seen[1].url.includes("verify-secret"), false);
    await live.getPreferences("manage-secret");
    assert.equal(seen[2].options.headers.Authorization, "Bearer manage-secret");
    assert.equal(seen[2].url.includes("manage-secret"), false);
    const limited = await live.putPreferences("manage-secret", [{ brand: "Baker", status: "active" }]);
    assert.equal(limited.status, 429);
    assert.match(alertsFailureMessage(limited), /Nothing was changed/);
    assert.equal(JSON.parse(seen[3].options.body).rules[0].status, undefined);

    const client = createAlertsClient({ mode: "mock", consentVersion: "2026-10-20" });
    const rules = [ruleFromDraft({ match: "brand", brand: "Baker", part: "Decks", alert_on_drop: true })];
    const first = await client.subscribe({ email: "one@example.com", rules, consent: true, consent_version: "2026-10-20" });
    const second = await client.subscribe({ email: "two@example.com", rules, consent: true, consent_version: "2026-10-20" });
    assert.equal(first.status, 202);
    assert.deepEqual(first.body, second.body);
    assert.match(first.body.message, /Alerts stay off/);
    assert.equal(client.peek("one@example.com").status, "pending");
    assert.equal(client.peek("one@example.com").rules[0].status, "pending");
    const rejected = await client.subscribe({ email: "one@example.com", rules, consent: false, consent_version: "2026-10-20" });
    assert.equal(rejected.status, 400);
    assert.equal(client.peek("nope@example.com"), null);
    const verified = await client.verify(client.peek("one@example.com").verifyToken);
    assert.equal(verified.body.status, "active");
    assert.ok(verified.body.manage_token);
    assert.equal(await client.verify(client.peek("one@example.com").verifyToken).then(item => item.ok), false);
    const prefs = await client.getPreferences(verified.body.manage_token);
    assert.equal(prefs.body.rules[0].status, "active");
    const paused = await client.putPreferences(verified.body.manage_token, prefs.body.rules.map(rule => Object.assign({}, rule, { paused: true })));
    assert.equal(paused.body.rules[0].status, "paused");
    const removed = await client.putPreferences(verified.body.manage_token, []);
    assert.deepEqual(removed.body.rules, []);
    const gone = await client.unsubscribe(verified.body.manage_token);
    assert.equal(gone.status, 200);
    assert.equal(client.peek("one@example.com"), null);
    const again = await client.subscribe({ email: "one@example.com", rules, consent: true, consent_version: "2026-10-20" });
    assert.deepEqual(again.body, first.body);

    const nav = new El("div");
    nav.className = "topnav-links";
    document.body.appendChild(nav);
    wireAlerts();
    assert.equal(document.getElementById("navAlerts").textContent, "Alerts");
    const parent = new El("div");
    appendQuickAlert(parent, { dataset: { name: "Deck", brand: "Baker", part: "Decks", size: "8.5", price: "40", url: "https://example.com/d", store: "Tactics" } });
    assert.equal(parent.querySelector("button").textContent, "Alert me");

    await openAlerts({ draft: alertDraftFromDataset({
        part: "Decks", size: "8.25", brand: "Baker", name: "Baker Figgy Deck 8.25",
        price: "49.99", url: "https://example.com/baker", store: "CCS"
    }) });
    assert.match(document.getElementById("alertsBody").textContent, /Baker Figgy Deck 8.25/);
    assert.match(document.getElementById("alertsBody").textContent, /Preview mode\. No email is sent/);
    assert.match(document.getElementById("alertsBody").textContent, /Meaningful drop/);
    assert.match(document.getElementById("alertsBody").textContent, /Historical low/);
    assert.match(document.getElementById("alertsBody").textContent, /Verified restock/);
    assert.equal(document.getElementById("alertsPrice").value, "49.99");
    assert.equal(document.getElementById("alertsSize").value, "8.25");
    assert.equal(document.getElementById("alertsPart").value, "Decks");
    await document.getElementById("alertsForm").events.submit[0]({ preventDefault() {} });
    assert.match(document.getElementById("alertsError").textContent, /email address/i);
    assert.equal(document.querySelector(".alerts-status"), null);

    document.getElementById("alertsEmail").value = "skater@example.com";
    await document.getElementById("alertsForm").events.submit[0]({ preventDefault() {} });
    assert.match(document.getElementById("alertsError").textContent, /consent|check the box/i);
    assert.equal(alertsUi.client.peek("skater@example.com"), null);
    assert.equal(document.querySelector(".alerts-status"), null);

    document.getElementById("alertsConsent").checked = true;
    await document.getElementById("alertsForm").events.submit[0]({ preventDefault() {} });
    assert.match(document.getElementById("alertsLive").textContent, /Alerts stay off/);
    assert.equal(document.querySelector(".alerts-status"), null);
    const pending = alertsUi.client.peek("skater@example.com");
    assert.equal(pending.status, "pending");
    assert.equal(pending.rules[0].status, "pending");
    assert.equal(pending.rules[0].name, "Baker Figgy Deck 8.25");
    assert.equal(pending.rules[0].max_price, 49.99);
    assert.equal(findButton("Open preview confirmation").textContent, "Open preview confirmation");
    await confirmPreview();
    assert.match(location.hash, /^#manage=/);
    assert.equal(location.search, "?token=should-stay-out");
    assert.equal(location.hash.includes("skater@example.com"), false);
    assert.equal(document.getElementById("alertsTitle").textContent, "Manage alerts");
    assert.equal(document.querySelector(".alerts-status").textContent, "Active");
    const ruleId = findButton("Pause").getAttribute("data-rule-id");
    await togglePause(ruleId);
    assert.equal(document.querySelector(".alerts-status").textContent, "Paused");
    assert.equal(alertsUi.client.peek("skater@example.com").rules[0].status, "paused");
    await togglePause(ruleId);
    assert.equal(document.querySelector(".alerts-status").textContent, "Active");
    await unsubscribeAlerts();
    assert.match(document.getElementById("alertsLive").textContent, /unsubscribed/i);
    assert.equal(document.querySelector(".alerts-status"), null);
    assert.equal(alertsUi.client.peek("skater@example.com"), null);
    assert.equal(location.hash, "");

    window.SKATEDEALS_ALERTS = { mock: true };
    location.hostname = "pchoward.github.io";
    await openAlerts({ draft: alertDraftFromDataset({ name: "Baker Figgy Deck 8.25", brand: "Baker", part: "Decks", size: "8.25", price: "49.99" }) });
    assert.equal(document.getElementById("alertsLive").textContent, "Email alerts coming soon.");
    assert.equal(document.getElementById("alertsEmail"), null);
    assert.equal(document.getElementById("alertsSubmit"), null);
    assert.match(document.getElementById("alertsBody").textContent, /Nothing here subscribes you/);
    assert.match(document.getElementById("alertsBody").textContent, /You'd be able to watch/);
    assert.equal(document.querySelector(".alerts-status"), null);
    assert.equal(findButton("Open preview confirmation"), null);
})().catch(err => { console.error(err); process.exit(1); });
'''
        result = subprocess.run(["node", "-e", script], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
