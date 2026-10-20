"""UI client requests and responses against the v1 examples and mock server."""

import json
import os
import socket
import subprocess
import tempfile
import time
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent
EXAMPLES = ROOT / "tests" / "fixtures" / "alerts-api-examples.json"


def _alerts_block():
    source = (ROOT / "page.js").read_text(encoding="utf-8")
    return source[source.index("/* ALERTS_UI_START"):source.index("/* ALERTS_UI_END */")]


class AlertsContractTests(unittest.TestCase):
    def test_client_matches_examples(self):
        examples = json.loads(EXAMPLES.read_text(encoding="utf-8"))
        script = r'''
const assert = require("node:assert/strict");
const examples = JSON.parse(process.argv[1]);
const seen = [];
function jsonResponse(step) {
    return {
        ok: step.response.status >= 200 && step.response.status < 300,
        status: step.response.status,
        headers: { get() { return ""; } },
        json: async () => step.response.body
    };
}
const fetchImpl = async (url, options) => {
    seen.push({ url, options });
    return jsonResponse(examples.steps[seen.length - 1]);
};
''' + _alerts_block() + r'''
(async () => {
    const client = createAlertsClient({ mode: "live", apiBase: "http://127.0.0.1:8787" }, fetchImpl);
    const bearer = header => {
        const value = header && header.Authorization ? header.Authorization : "";
        return value.startsWith("Bearer ") ? value.slice(7) : "";
    };
    for (const step of examples.steps) {
        const request = step.request;
        const token = bearer(request.headers);
        if (step.name === "health") await client.health();
        else if (step.name === "subscribe") await client.subscribe(request.body);
        else if (step.name.startsWith("verify")) await client.verify(request.body.token);
        else if (request.method === "GET" && request.path === "/v1/preferences") await client.getPreferences(token);
        else if (request.method === "PUT") await client.putPreferences(token, request.body.rules);
        else if (request.path === "/v1/link") await client.link(request.body);
        else if (request.path === "/v1/unsubscribe") await client.unsubscribe(token);
        else throw new Error("unmapped step " + step.name);
    }
    examples.steps.forEach((step, index) => {
        const hit = seen[index];
        const url = new URL(hit.url);
        assert.equal(hit.options.method, step.request.method, step.name);
        assert.equal(url.pathname, step.request.path, step.name);
        assert.equal(hit.options.credentials, "omit", step.name);
        assert.equal(url.search, "");
        assert.equal(url.hash, "");
        const auth = (step.request.headers && step.request.headers.Authorization) || "";
        assert.equal(hit.options.headers.Authorization || "", auth, step.name);
        if (step.request.body) {
            assert.equal(hit.options.headers["Content-Type"], "application/json", step.name);
            assert.deepEqual(JSON.parse(hit.options.body), step.request.body, step.name);
        } else {
            assert.equal(hit.options.body, undefined, step.name);
        }
        const applied = alertsApplyResult({}, step.name.startsWith("verify") ? "verify" : (
            step.name === "subscribe" || step.name === "request a manage link" ? (step.request.path === "/v1/link" ? "link" : "subscribe") :
            step.request.path === "/v1/preferences" ? "preferences" :
            step.request.path === "/v1/unsubscribe" ? "unsubscribe" :
            step.name === "health" ? "health" : "preferences"
        ), { status: step.response.status, body: step.response.body });
        if (step.name === "subscribe" || step.name === "request a manage link") {
            assert.equal(applied.active, false, step.name);
            assert.equal(applied.view, "check", step.name);
        }
        if (step.name === "verify") {
            assert.equal(applied.active, true, step.name);
            assert.equal(applied.prefs.status, "active", step.name);
            assert.equal(applied.prefs.max_rules, 10, step.name);
        }
        if (step.name === "verify again (single use)" || step.name === "the manage token stops working") {
            assert.equal(applied.active, false, step.name);
            assert.equal(applied.view, "relink", step.name);
        }
        if (step.name === "invalid preferences") {
            assert.equal(applied.active, false, step.name);
            assert.match(applied.error, /decks_only/);
            assert.match(applied.error, /price_out_of_range/);
        }
        if (step.name === "replace preferences" || step.name === "read preferences") {
            assert.equal(applied.active, true, step.name);
            assert.equal(applied.prefs.status, "active", step.name);
        }
        if (step.name === "unsubscribe with the manage token") {
            assert.equal(applied.active, false, step.name);
            assert.equal(applied.token, "");
        }
        if (step.name === "bad captcha") assert.match(applied.error, /captcha/);
    });
})().catch(err => { console.error(err); process.exit(1); });
'''
        result = subprocess.run(
            ["node", "-e", script, json.dumps(examples)],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_mock_server_session(self):
        probe = subprocess.run(
            ["git", "rev-parse", "--verify", "origin/claude/alerts-backend"],
            capture_output=True,
            text=True,
        )
        if probe.returncode != 0:
            self.skipTest("origin/claude/alerts-backend is not available")
        with tempfile.TemporaryDirectory() as tmp:
            archive = subprocess.check_output(["git", "archive", "origin/claude/alerts-backend", "worker"])
            subprocess.run(["tar", "-x"], input=archive, cwd=tmp, check=True)
            sock = socket.socket()
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
            sock.close()
            env = os.environ.copy()
            env["PORT"] = str(port)
            env["MANAGE_PAGE_URL"] = "http://127.0.0.1:8000/index.html"
            proc = subprocess.Popen(
                ["node", "dev/mock-server.js"],
                cwd=str(Path(tmp) / "worker"),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            try:
                self._wait_for_server(proc, port)
                script = r'''
const assert = require("node:assert/strict");
const base = process.argv[1];
''' + _alerts_block() + r'''
(async () => {
    const client = createAlertsClient({ mode: "live", apiBase: base, consentVersion: "2026-10" });
    const health = await client.health();
    assert.equal(health.status, 200);
    assert.deepEqual(health.body, { ok: true, api_version: "1", mode: "mock" });
    const subscribed = await client.subscribe({
        email: "rider@example.com",
        rules: [
            { brand: "Heroin", part: "Decks", min_width: 8.6, max_price: 60, note: "Wide Heroin decks" },
            { name: "Antihero Caster", alert_on_low: true }
        ],
        consent: true,
        consent_version: "2026-10",
        turnstile_token: "mock-turnstile-pass"
    });
    assert.equal(subscribed.status, 202);
    assert.deepEqual(subscribed.body, { status: "check_email" });
    const pending = alertsApplyResult({}, "subscribe", subscribed);
    assert.equal(pending.active, false);
    const outbox = await fetch(base + "/v1/mock/outbox");
    const mail = await outbox.json();
    assert.ok(mail.messages.length >= 1);
    const link = (mail.messages[0].links || []).find(item => item.includes("#verify=")) || mail.messages[0].text;
    const token = decodeURIComponent(link.split("#verify=")[1].split(/[\s#]/)[0]);
    const verified = await client.verify(token);
    assert.equal(verified.status, 200);
    assert.equal(verified.body.status, "active");
    assert.equal(verified.body.preferences.status, "active");
    assert.equal(verified.body.preferences.max_rules, 10);
    assert.equal(verified.body.preferences.rules.length, 2);
    const active = alertsApplyResult({}, "verify", verified);
    assert.equal(active.active, true);
    const manage = verified.body.manage_token;
    const again = await client.verify(token);
    assert.equal(again.status, 400);
    assert.deepEqual(again.body, { error: "invalid_token" });
    const prefs = await client.getPreferences(manage);
    assert.equal(prefs.status, 200);
    assert.equal(prefs.body.status, "active");
    const edited = await client.putPreferences(manage, [{
        id: prefs.body.rules[0].id,
        brand: "Powell Peralta",
        part: "Decks",
        width: 9,
        alert_on_drop: true,
        paused: true
    }]);
    assert.equal(edited.status, 200, JSON.stringify(edited.body));
    assert.equal(edited.body.rules.length, 1);
    assert.equal(edited.body.rules[0].brand, "Powell Peralta");
    assert.equal(edited.body.rules[0].width, 9);
    assert.equal(edited.body.status, "active");
    const bad = await client.putPreferences(manage, [{ brand: "Bones", part: "Wheels", max_price: -5, width: 8.5 }]);
    assert.equal(bad.status, 400);
    assert.equal(bad.body.error, "invalid_rules");
    assert.equal(bad.body.fields["rules[0].width"], "decks_only");
    assert.equal(bad.body.fields["rules[0].max_price"], "price_out_of_range");
    const linked = await client.link({ email: "rider@example.com", turnstile_token: "mock-turnstile-pass" });
    assert.equal(linked.status, 202);
    assert.deepEqual(linked.body, { status: "check_email" });
    const captcha = await client.link({ email: "rider@example.com", turnstile_token: "wrong" });
    assert.equal(captcha.status, 400);
    assert.deepEqual(captcha.body, { error: "captcha_failed" });
    const gone = await client.unsubscribe(manage);
    assert.equal(gone.status, 200);
    assert.deepEqual(gone.body, { status: "unsubscribed" });
    const dead = await client.getPreferences(manage);
    assert.equal(dead.status, 401);
    assert.deepEqual(dead.body, { error: "invalid_token" });
})().catch(err => { console.error(err); process.exit(1); });
'''
                result = subprocess.run(
                    ["node", "-e", script, f"http://127.0.0.1:{port}"],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
            finally:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                if proc.stdout:
                    proc.stdout.close()

    def _wait_for_server(self, proc, port):
        import urllib.request

        deadline = time.time() + 10
        last = ""
        while time.time() < deadline:
            if proc.poll() is not None:
                output = proc.stdout.read() if proc.stdout else ""
                self.fail(f"mock server exited {proc.returncode}: {output}")
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/v1/health", timeout=0.5) as response:
                    if response.status == 200:
                        return
            except Exception as err:
                last = str(err)
            time.sleep(0.1)
        output = ""
        if proc.stdout:
            proc.terminate()
        self.fail(f"mock server did not start: {last}")
