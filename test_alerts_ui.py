"""Alerts panel behavior against the v1 contract. Node runs the page script."""

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
        block = js[js.index("/* ALERTS_UI_START"):js.index("/* ALERTS_UI_END */")]
        self.assertIn('const ALERTS_API_BASE = "";', js)
        self.assertIn("function appendQuickAlert(", js)
        self.assertIn("appendQuickAlert(actions, card)", js)
        self.assertIn('summary.textContent = "More details"', js)
        self.assertIn("/v1/subscribe", block)
        self.assertIn("/v1/verify", block)
        self.assertIn("/v1/preferences", block)
        self.assertIn("/v1/unsubscribe", block)
        self.assertIn('const ALERTS_CONSENT_VERSION = "2026-10"', block)
        self.assertIn("skatedeals.alerts.manage", block)
        self.assertNotIn("2026-10-20", block)
        self.assertNotIn("localStorage", block)
        self.assertNotIn("/v1/mock/outbox", block)
        self.assertNotIn("/v1/internal", block)
        self.assertNotIn("alert_on_new", block)
        self.assertNotIn("product_url", block)
        self.assertNotIn("paused", block)
        self.assertNotIn("Open preview confirmation", block)
        self.assertNotIn("RESEND_API_KEY", js)
        self.assertNotIn("SMTP_PASSWORD", js)
        self.assertNotIn("sk_live", js)
        self.assertNotIn("whsec_", js)
        self.assertNotIn("location.hash =", block)
        self.assertIn(".quick-alert", css)
        self.assertIn("#alertsRoot", css)
        self.assertIn(".alerts-status.is-active", css)
        phone = mobile[mobile.rindex(".alerts-panel input"):]
        self.assertIn("font-size: 16px", phone)
        self.assertIn("min-height: 2.75rem", phone)
        self.assertIn("Email alerts coming soon", contract)
        self.assertIn("docs/alerts-api.md", contract)
        self.assertNotIn("POST /subscribe", contract)

    def test_report_points_the_panel_at_the_staging_worker(self):
        import page
        from report import build_report_html

        html = build_report_html({}, {}, generated_at="2026-10-24T12:00:00+00:00")
        config = '<script>window.SKATEDEALS_ALERTS = {"apiBase": "https://skatedeals-alerts.pchoward.workers.dev"'
        self.assertEqual(html.count("window.SKATEDEALS_ALERTS ="), 1)
        self.assertLess(html.index(config), html.index("const ALERTS_API_BASE"), "config must load before page.js")
        # Public values only, and markup in a value cannot close the script.
        self.assertEqual(set(page.ALERTS_UI_CONFIG), {"apiBase", "turnstileSiteKey"})
        self.assertTrue(page.ALERTS_UI_CONFIG["apiBase"].startswith("https://"))
        self.assertEqual(page._alerts_config_script({"apiBase": " "}), "")
        hostile = page._alerts_config_script({"apiBase": "https://x.example", "turnstileSiteKey": "</script>"})
        self.assertEqual(hostile.count("</script>"), 1)

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
        this.parent = null;
        this.tabIndex = 0;
        this.noValidate = false;
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
const location = { hostname: "localhost", pathname: "/sale_items_chart.html", search: "?token=should-stay-out", hash: "" };
const history = {
    replaceState(state, title, url) {
        const text = String(url || "");
        location.hash = text.includes("#") ? "#" + text.split("#").slice(1).join("#") : "";
    }
};
const memory = {};
globalThis.sessionStorage = {
    getItem(key) { return Object.prototype.hasOwnProperty.call(memory, key) ? memory[key] : null; },
    setItem(key, value) { memory[key] = String(value); },
    removeItem(key) { delete memory[key]; }
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
    const buttons = document.body.querySelectorAll("button");
    for (const button of buttons) if (button.textContent === text) return button;
    return null;
}
async function clickButton(text) {
    const button = findButton(text);
    assert.ok(button, text);
    const body = document.getElementById("alertsBody");
    const handler = body.events.click[0];
    return handler({ target: button, preventDefault() {} });
}
function jsonResponse(status, body, headers) {
    return {
        ok: status >= 200 && status < 300,
        status,
        headers: { get(name) { return (headers && headers[name]) || ""; } },
        json: async () => body
    };
}
''' + block + r'''
(async () => {
    assert.equal(alertsResolveConfig({ config: { mock: true }, host: "pchoward.github.io" }).mode, "soon");
    assert.equal(alertsResolveConfig({ config: { mock: true }, host: "localhost" }).mode, "soon");
    const liveConfig = alertsResolveConfig({ config: { apiBase: "https://alerts.example.com/" }, host: "pchoward.github.io" });
    assert.equal(liveConfig.mode, "live");
    assert.equal(liveConfig.apiBase, "https://alerts.example.com");
    assert.equal(liveConfig.consentVersion, "2026-10");
    assert.equal(alertsResolveConfig({ config: { apiBase: "http://alerts.example.com" }, host: "pchoward.github.io" }).mode, "soon");
    assert.equal(alertsResolveConfig({ config: { apiBase: "http://127.0.0.1:8787" }, host: "localhost" }).mode, "live");
    assert.equal(alertsResolveConfig({ config: { apiBase: "https://user:pass@alerts.example.com" }, host: "localhost" }).mode, "soon");
    assert.equal(alertsResolveConfig({ config: {}, host: "sale.github.io" }).mode, "soon");

    assert.deepEqual(readAlertsFragment("#verify=abc"), { purpose: "verify", token: "abc" });
    assert.deepEqual(readAlertsFragment("#manage=abc%3D"), { purpose: "manage", token: "abc=" });
    assert.equal(readAlertsFragment("#token=abc&purpose=manage"), null);
    assert.equal(readAlertsFragment(location.search), null);
    assert.equal(manageTokenFromVerify({ manage_link: "https://pages.example/?token=nope" }), "");
    assert.equal(manageTokenFromVerify({ manage_link: "https://pages.example/#manage=yes" }), "yes");
    assert.equal(manageTokenFromVerify({ manage_token: "abc" }), "abc");

    const named = ruleFromDraft({
        brand: "Baker", name: "Baker Figgy Deck 8.25", part: "Decks", width: "8.25",
        max_price: "49.99", alert_on_drop: true, alert_on_low: true, alert_on_stock: true
    });
    assert.equal(named.name, "Baker Figgy Deck 8.25");
    assert.equal(named.brand, "Baker");
    assert.equal(named.part, "Decks");
    assert.equal(named.width, 8.25);
    assert.equal(named.max_price, 49.99);
    assert.equal(named.back_in_stock_width, 8.25);
    assert.equal(named.alert_on_low, true);
    assert.equal(named.alert_on_stock, true);
    assert.equal(named.id, undefined);
    assert.equal(named.product_url, undefined);
    assert.equal(named.size, undefined);
    assert.equal(named.alert_on_new, undefined);
    assert.equal(named.paused, undefined);
    assert.equal(buildRule({ name: "Shoe", part: "Sneakers" }).ok, false);
    assert.equal(buildRule({ name: "Wheel", part: "Wheels", width: "8.5", max_price: "20" }).rule.width, undefined);
    const checked = alertsApplyResult({}, "subscribe", { status: 202, body: { status: "check_email" } });
    assert.equal(checked.active, false);
    assert.equal(checked.view, "check");
    const confirmed = alertsApplyResult({}, "verify", {
        status: 200,
        body: { status: "active", manage_token: "m1", preferences: { status: "active", rules: [] } }
    });
    assert.equal(confirmed.active, true);
    assert.equal(confirmed.prefs.status, "active");
    const missing = alertsApplyResult({}, "preferences", { status: 200, body: { rules: [{ brand: "Baker" }] } });
    assert.equal(missing.active, false);
    const rejected = alertsApplyResult({}, "verify", { status: 400, body: { error: "invalid_token" } });
    assert.equal(rejected.view, "relink");
    assert.equal(rejected.active, false);
    const invalid = alertsApplyResult({}, "preferences", {
        status: 400,
        body: { error: "invalid_rules", fields: { "rules[0].width": "decks_only" } }
    });
    assert.match(invalid.error, /decks_only/);
    assert.equal(invalid.active, false);
    assert.match(alertsFailureMessage({ status: 429, error: "rate_limited", body: { error: "rate_limited", retry_after: 9 } }), /Nothing was changed/);
    assert.equal(alertsFailureMessage({ status: 503, body: { error: "service_unavailable" } }), "Alerts are unavailable right now.");

    let calls = 0;
    const soon = createAlertsClient({ mode: "soon" }, () => { calls += 1; return {}; });
    const denied = await soon.subscribe({ email: "a@b.co", consent: true, rules: [{ brand: "Baker", part: "Decks" }] });
    assert.equal(calls, 0);
    assert.equal(denied.error, "unavailable");

    const seen = [];
    const fetchImpl = async (url, options) => {
        seen.push({ url, options });
        if (url.endsWith("/v1/preferences") && options.method === "PUT") {
            return jsonResponse(400, { error: "invalid_rules", fields: { "rules[0].width": "decks_only", "rules[0].max_price": "price_out_of_range" } });
        }
        return jsonResponse(200, { status: "active", rules: [] });
    };
    const live = createAlertsClient({ mode: "live", apiBase: "https://alerts.example.com" }, fetchImpl);
    await live.subscribe({
        email: "rider@example.com",
        rules: [{ brand: "Heroin", part: "Decks", min_width: 8.6, max_price: 60, note: "Wide Heroin decks" }],
        consent: true,
        consent_version: "2026-10",
        turnstile_token: "mock-turnstile-pass"
    });
    assert.equal(seen[0].url, "https://alerts.example.com/v1/subscribe");
    assert.equal(seen[0].options.credentials, "omit");
    assert.equal(seen[0].options.headers["Content-Type"], "application/json");
    assert.equal(seen[0].url.includes("rider@example.com"), false);
    await live.verify("verify-secret");
    assert.equal(seen[1].url, "https://alerts.example.com/v1/verify");
    assert.deepEqual(JSON.parse(seen[1].options.body), { token: "verify-secret" });
    assert.equal(seen[1].url.includes("verify-secret"), false);
    await live.getPreferences("manage-secret");
    assert.equal(seen[2].options.method, "GET");
    assert.equal(seen[2].options.headers.Authorization, "Bearer manage-secret");
    assert.equal(seen[2].options.body, undefined);
    const limited = await live.putPreferences("manage-secret", [
        { id: "r_aaaaaaaaaaaaaaaaaaaaaaaa", brand: "Bones", part: "Wheels", width: 8.5, max_price: -5, paused: true }
    ]);
    assert.equal(limited.status, 400);
    const sent = JSON.parse(seen[3].options.body);
    assert.equal(sent.rules[0].id, undefined);
    assert.equal(sent.rules[0].paused, undefined);
    assert.equal(sent.rules[0].width, 8.5);
    assert.equal(sent.rules[0].max_price, -5);
    assert.match(alertsFailureMessage(limited), /decks_only/);
    const gone = await live.unsubscribe("manage-secret");
    assert.equal(seen[4].options.method, "POST");
    assert.equal(seen[4].options.body, undefined);
    assert.equal(seen[4].options.headers.Authorization, "Bearer manage-secret");
    assert.equal(gone.status, 200);

    const nav = new El("div");
    nav.className = "topnav-links";
    document.body.appendChild(nav);
    wireAlerts();
    assert.equal(document.getElementById("navAlerts").textContent, "Subscribe");
    const parent = new El("div");
    appendQuickAlert(parent, { dataset: { name: "Deck", brand: "Baker", part: "Decks", size: "8.5", price: "40", url: "https://example.com/d", store: "Tactics" } });
    assert.equal(parent.querySelector("button").textContent, "Alert me");

    window.SKATEDEALS_ALERTS = { mock: true };
    location.hostname = "pchoward.github.io";
    await openAlerts({ draft: alertDraftFromDataset({ name: "Baker Figgy Deck 8.25", brand: "Baker", part: "Decks", size: "8.25", price: "49.99" }) });
    assert.equal(document.getElementById("alertsLive").textContent, "");
    assert.match(document.getElementById("alertsBody").textContent, /Email alerts coming soon/);
    assert.equal(document.getElementById("alertsEmail"), null);
    assert.equal(document.getElementById("alertsSubmit"), null);
    assert.match(document.getElementById("alertsBody").textContent, /Nothing here subscribes you/);
    assert.match(document.getElementById("alertsBody").textContent, /You'd be able to watch/);
    assert.equal(document.querySelector(".alerts-status"), null);

    const callsLive = [];
    globalThis.fetch = async (url, options) => {
        callsLive.push({ url, options });
        const path = new URL(url).pathname;
        if (path === "/v1/health") return jsonResponse(200, { ok: true, api_version: "1", mode: "mock" });
        if (path === "/v1/subscribe") return jsonResponse(202, { status: "check_email" });
        if (path === "/v1/verify") {
            return jsonResponse(200, {
                status: "active",
                manage_token: "manage-secret",
                preferences: {
                    status: "active",
                    email_masked: "s***@example.com",
                    consent_version: "2026-10",
                    verified_at: "2026-10-20T00:00:00Z",
                    max_rules: 10,
                    rules: [{ id: "r_aaaaaaaaaaaaaaaaaaaaaaaa", brand: "Baker", name: "Baker Figgy Deck 8.25", part: "Decks", width: 8.25, max_price: 49.99 }]
                }
            });
        }
        if (path === "/v1/preferences" && options.method === "PUT") {
            const body = JSON.parse(options.body);
            return jsonResponse(200, {
                status: "active",
                email_masked: "s***@example.com",
                consent_version: "2026-10",
                verified_at: "2026-10-20T00:00:00Z",
                max_rules: 10,
                rules: body.rules.map(rule => Object.assign({ id: "r_bbbbbbbbbbbbbbbbbbbbbbbb" }, rule))
            });
        }
        if (path === "/v1/unsubscribe") return jsonResponse(200, { status: "unsubscribed" });
        return jsonResponse(500, { error: "internal_error" });
    };
    window.SKATEDEALS_ALERTS = { apiBase: "http://127.0.0.1:8787" };
    location.hostname = "localhost";
    await openAlerts({ draft: alertDraftFromDataset({
        part: "Decks", size: "8.25", brand: "Baker", name: "Baker Figgy Deck 8.25",
        price: "49.99", url: "https://example.com/baker", store: "CCS"
    }) });
    assert.equal(document.getElementById("alertsTitle").textContent, "Alert me");
    assert.match(document.getElementById("alertsBody").textContent, /Baker Figgy Deck 8.25/);
    assert.match(document.getElementById("alertsBody").textContent, /Current price \$49\.99/);
    assert.match(document.getElementById("alertsBody").textContent, /This is a local mock\. No email is sent/);
    assert.match(document.getElementById("alertsBody").textContent, /Any meaningful price drop/);
    assert.match(document.getElementById("alertsBody").textContent, /Verified historical low/);
    assert.match(document.getElementById("alertsBody").textContent, /Verified restock/);
    assert.equal(document.getElementById("alertsAdvanced").open, false);
    assert.equal(document.getElementById("alertsConsent").checked, false);
    assert.equal(document.getElementById("alertsPrice").value, "49.99");
    assert.equal(document.getElementById("alertsWidth").value, "8.25");
    assert.equal(document.getElementById("alertsPart").value, "Decks");
    assert.equal(findButton("Pause"), null);
    assert.equal(findButton("Open preview confirmation"), null);
    await document.getElementById("alertsForm").events.submit[0]({ preventDefault() {} });
    assert.match(document.getElementById("alertsError").textContent, /email address/i);
    assert.equal(document.querySelector(".alerts-status"), null);

    document.getElementById("alertsEmail").value = "skater@example.com";
    await document.getElementById("alertsForm").events.submit[0]({ preventDefault() {} });
    assert.match(document.getElementById("alertsError").textContent, /check the box/i);
    assert.equal(callsLive.filter(call => call.url.endsWith("/v1/subscribe")).length, 0);
    assert.equal(document.querySelector(".alerts-status"), null);

    document.getElementById("alertsConsent").checked = true;
    await document.getElementById("alertsForm").events.submit[0]({ preventDefault() {} });
    assert.match(document.getElementById("alertsBody").textContent, /Watching this exact product is coming soon/);
    assert.match(document.getElementById("alertsBody").textContent, /Nothing was saved/);
    assert.equal(document.getElementById("alertsBody").textContent.includes("Check your email to confirm."), false);
    assert.equal(callsLive.filter(call => call.url.endsWith("/v1/subscribe")).length, 0);
    assert.equal(document.querySelector(".alerts-status"), null);
    await clickButton("Back");
    document.getElementById("alertsEmail").value = "skater@example.com";
    document.getElementById("alertsConsent").checked = true;
    document.getElementById("alertsBroad").checked = true;
    await document.getElementById("alertsForm").events.submit[0]({ preventDefault() {} });
    assert.match(document.getElementById("alertsBody").textContent, /Check your email to confirm/);
    assert.match(document.getElementById("alertsBody").textContent, /were not saved/);
    assert.match(document.getElementById("alertsBody").textContent, /not limited to one product/);
    assert.equal(document.querySelector(".alerts-status"), null);
    const posted = callsLive.find(call => call.url.endsWith("/v1/subscribe"));
    const payload = JSON.parse(posted.options.body);
    assert.equal(payload.email, "skater@example.com");
    assert.equal(payload.consent, true);
    assert.equal(payload.consent_version, "2026-10");
    assert.equal(payload.turnstile_token, "mock-turnstile-pass");
    assert.equal(payload.rules[0].brand, "Baker");
    assert.equal(payload.rules[0].name, "Baker Figgy Deck 8.25");
    assert.equal(payload.rules[0].part, "Decks");
    assert.equal(payload.rules[0].width, 8.25);
    assert.equal(payload.rules[0].max_price, 49.99);
    assert.equal(payload.rules[0].id, undefined);
    assert.equal(payload.rules[0].product_url, undefined);
    assert.equal(payload.rules[0].alert_on_drop, undefined);
    assert.equal(location.hash, "");
    assert.equal(location.search, "?token=should-stay-out");

    await openAlerts({ fragment: { purpose: "verify", token: "verify-secret" } });
    assert.equal(document.getElementById("alertsTitle").textContent, "Manage alerts");
    assert.equal(document.querySelector(".alerts-status").textContent, "Active");
    assert.equal(sessionStorage.getItem("skatedeals.alerts.manage"), "manage-secret");
    assert.equal(location.hash, "");
    assert.equal(location.hash.includes("manage-secret"), false);
    const beforeRemove = callsLive.length;
    await clickButton("Remove");
    assert.equal(callsLive.length, beforeRemove);
    assert.match(document.getElementById("alertsError").textContent, /Unsubscribe to remove the last alert/);
    assert.equal(document.querySelector(".alerts-status").textContent, "Active");

    await clickButton("Edit");
    document.getElementById("alertsBrand").value = "Powell Peralta";
    document.getElementById("alertsName").value = "";
    document.getElementById("alertsWidth").value = "9";
    document.getElementById("alertsDrop").checked = true;
    await document.getElementById("alertsEditForm").events.submit[0]({ preventDefault() {} });
    const put = callsLive.find(call => call.options && call.options.method === "PUT");
    const saved = JSON.parse(put.options.body);
    assert.equal(saved.rules[0].id, undefined);
    assert.equal(saved.rules[0].brand, "Powell Peralta");
    assert.equal(saved.rules[0].width, 9);
    assert.equal(saved.rules[0].alert_on_drop, true);
    assert.equal(saved.rules[0].name, undefined);
    assert.equal(document.querySelector(".alerts-status").textContent, "Active");

    await clickButton("Unsubscribe");
    await clickButton("Confirm unsubscribe");
    assert.match(document.getElementById("alertsBody").textContent, /unsubscribed/i);
    assert.equal(document.querySelector(".alerts-status"), null);
    assert.equal(sessionStorage.getItem("skatedeals.alerts.manage"), null);
    assert.equal(location.hash, "");

    window.SKATEDEALS_ALERTS = { apiBase: "http://127.0.0.1:8787" };
    await openAlerts({ draft: alertDraftFromDataset({ name: "Shoe", brand: "Nike", part: "Sneakers", size: "9", price: "40", shoesize: "9,10" }) });
    document.getElementById("alertsEmail").value = "skater@example.com";
    document.getElementById("alertsConsent").checked = true;
    const beforeShoe = callsLive.filter(call => call.url.endsWith("/v1/subscribe")).length;
    await document.getElementById("alertsForm").events.submit[0]({ preventDefault() {} });
    assert.match(document.getElementById("alertsBody").textContent, /exact product is coming soon/);
    assert.equal(callsLive.filter(call => call.url.endsWith("/v1/subscribe")).length, beforeShoe);
    assert.equal(document.querySelector(".alerts-status"), null);
    await clickButton("Back");
    document.getElementById("alertsEmail").value = "skater@example.com";
    document.getElementById("alertsConsent").checked = true;
    document.getElementById("alertsBroad").checked = true;
    await document.getElementById("alertsForm").events.submit[0]({ preventDefault() {} });
    assert.match(document.getElementById("alertsError").textContent, /Decks, Wheels, Trucks, or Bearings/);
    assert.match(document.getElementById("alertsBody").textContent, /coming soon and are not sent/);
    assert.equal(callsLive.filter(call => call.url.endsWith("/v1/subscribe")).length, beforeShoe);
    assert.equal(document.querySelector(".alerts-status"), null);

    globalThis.fetch = async () => { throw new Error("Failed to fetch"); };
    window.SKATEDEALS_ALERTS = { apiBase: "http://127.0.0.1:9" };
    await openAlerts({ draft: blankAlertDraft() });
    assert.equal(document.querySelector(".alerts-status"), null);
    assert.ok(document.getElementById("alertsEmail"));
    assert.match(document.getElementById("alertsBody").textContent, /could not be read/);
    assert.equal(document.getElementById("alertsTitle").textContent, "Subscribe");
    assert.match(document.getElementById("alertsBody").textContent, /not a watch on one product/);
    assert.equal(document.getElementById("alertsAdvanced").open, false);
    assert.equal(document.getElementById("alertsConsent").checked, false);
})().catch(err => { console.error(err); process.exit(1); });
'''
        result = subprocess.run(["node", "-e", script], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
