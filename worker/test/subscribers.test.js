import assert from "node:assert/strict";
import { test } from "node:test";
import { unsubscribeToken } from "../src/crypto.js";
import {
  activeSubscriber,
  API,
  client,
  fakeNetwork,
  makeEnv,
  outbox,
  RULE,
  START,
  subscribeBody,
  tokenFrom,
} from "./helpers.js";

test("signup is double opt-in: pending until the emailed link is used", async () => {
  const env = makeEnv();
  const api = client(env);
  const response = await api.call("POST", "/v1/subscribe", { body: subscribeBody() });
  assert.equal(response.status, 202);
  assert.deepEqual(response.data, { status: "check_email" });
  const row = await env.DB.prepare("SELECT status, email FROM subscribers").first();
  assert.equal(row.status, "pending");
  const [mail] = await outbox(env);
  assert.equal(mail.to_addr, "rider@example.com");
  assert.match(mail.subject, /Confirm/);
  const token = tokenFrom(mail.text_body, "verify");
  assert.ok(token, "verification link uses a URL fragment");
  assert.ok(mail.text_body.includes("https://pchoward.github.io/salesscraper2/alerts.html#verify="));

  // Pending subscribers are invisible to the delivery job.
  const before = await api.signed("GET", "/v1/internal/routes");
  assert.deepEqual(before.data.routes, []);

  const verified = await api.call("POST", "/v1/verify", { body: { token } });
  assert.equal(verified.status, 200);
  assert.equal(verified.data.status, "active");
  assert.match(verified.data.manage_token, /^[A-Za-z0-9_-]{43}$/);
  assert.equal(verified.data.preferences.email_masked, "r***@example.com");
  assert.equal(verified.data.preferences.rules.length, 1);

  const again = await api.call("POST", "/v1/verify", { body: { token } });
  assert.equal(again.status, 400, "verify tokens are single use");
  const after = await api.signed("GET", "/v1/internal/routes");
  assert.equal(after.data.routes.length, 1);
});

test("verify links expire after 48 hours", async () => {
  const env = makeEnv();
  const api = client(env);
  await api.call("POST", "/v1/subscribe", { body: subscribeBody() });
  const token = tokenFrom((await outbox(env))[0].text_body, "verify");
  api.clock.now = START + 48 * 3600 + 1;
  const late = await api.call("POST", "/v1/verify", { body: { token } });
  assert.equal(late.status, 400);
  assert.equal(late.data.error, "invalid_token");
});

test("responses never reveal whether an address is subscribed", async () => {
  const env = makeEnv();
  const api = client(env);
  await activeSubscriber(env, api);
  const before = await outbox(env);
  const known = await api.call("POST", "/v1/subscribe", { body: subscribeBody("rider@example.com", { rules: [{ brand: "Baker" }] }) });
  const unknown = await api.call("POST", "/v1/subscribe", { body: subscribeBody("someone@example.com") });
  assert.equal(known.status, unknown.status);
  assert.deepEqual(known.data, unknown.data);

  // The active subscriber's rules did not change, and they got a manage link instead.
  const rules = await env.DB.prepare(
    "SELECT r.fields FROM rules r JOIN subscribers s ON s.id = r.subscriber_id WHERE s.email = 'rider@example.com'",
  ).all();
  assert.deepEqual(JSON.parse(rules.results[0].fields).brand, "Heroin");
  const sent = (await outbox(env)).slice(before.length);
  assert.equal(sent.find((row) => row.to_addr === "rider@example.com").subject, "Your SkateDeals alerts link");

  const linkKnown = await api.call("POST", "/v1/link", { body: { email: "rider@example.com", turnstile_token: "mock-turnstile-pass" } });
  const linkUnknown = await api.call("POST", "/v1/link", { body: { email: "nobody@example.com", turnstile_token: "mock-turnstile-pass" } });
  assert.deepEqual([linkKnown.status, linkKnown.data], [linkUnknown.status, linkUnknown.data]);
});

test("signup input is validated with field-level errors", async () => {
  const base = client(makeEnv());
  let ip = 0;
  const api = {
    call: (method, path, options = {}) =>
      base.call(method, path, { ...options, headers: { ...(options.headers || {}), "CF-Connecting-IP": `192.0.2.${(ip += 1)}` } }),
  };
  const cases = [
    [{ email: "not-an-email" }, 400, "invalid_email"],
    [{ consent: false }, 400, "consent_required"],
    [{ consent_version: "2020-01" }, 400, "consent_outdated"],
    [{ turnstile_token: "wrong" }, 400, "captcha_failed"],
    [{ rules: [] }, 400, "invalid_rules"],
  ];
  for (const [override, status, error] of cases) {
    const response = await api.call("POST", "/v1/subscribe", { body: subscribeBody(override.email || "rider@example.com", override) });
    assert.equal(response.status, status, error);
    assert.equal(response.data.error, error);
  }
  const bad = await api.call("POST", "/v1/subscribe", {
    body: subscribeBody("rider@example.com", {
      rules: [{ brand: "", part: "Skis" }, { brand: "Baker", part: "Wheels", min_width: 8 }, { brand: "x", color: "red" }, { name: "<b>" }],
    }),
  });
  assert.equal(bad.status, 400);
  assert.deepEqual(bad.data.fields, {
    "rules[0].part": "invalid",
    "rules[0].brand": "brand_or_name_required",
    "rules[1].min_width": "decks_only",
    "rules[2].color": "unknown_field",
    "rules[3].name": "invalid_characters",
  });
  const tooMany = await api.call("POST", "/v1/subscribe", {
    body: subscribeBody("rider@example.com", { rules: Array.from({ length: 11 }, (_v, i) => ({ brand: `Brand ${i}` })) }),
  });
  assert.deepEqual(tooMany.data.fields, { rules: "too_many" });
  const notJson = await api.call("POST", "/v1/subscribe", { raw: "email=a", headers: { "Content-Type": "text/plain" } });
  assert.equal(notJson.status, 415);
});

test("manage token reads and replaces rules; edits keep stable rule ids", async () => {
  const env = makeEnv();
  const api = client(env);
  const token = await activeSubscriber(env, api);
  const auth = { Authorization: `Bearer ${token}` };
  const got = await api.call("GET", "/v1/preferences", { headers: auth });
  assert.equal(got.status, 200);
  const firstId = got.data.rules[0].id;
  assert.match(firstId, /^r_[0-9a-f]{24}$/);

  const put = await api.call("PUT", "/v1/preferences", {
    headers: auth,
    body: { rules: [{ ...RULE, note: "edited note only" }, { name: "Antihero Caster", part: "Decks", alert_on_low: true }] },
  });
  assert.equal(put.status, 200);
  assert.equal(put.data.rules.length, 2);
  assert.equal(put.data.rules[0].id, firstId, "a note edit does not change the rule id");
  assert.equal(put.data.rules[0].note, "edited note only");

  const unauthorized = await api.call("GET", "/v1/preferences", { headers: { Authorization: "Bearer nope" } });
  assert.equal(unauthorized.status, 401);
  api.clock.now = START + 31 * 86400;
  const expired = await api.call("GET", "/v1/preferences", { headers: auth });
  assert.equal(expired.status, 401, "manage tokens expire after 30 days");
});

test("one-click unsubscribe (RFC 8058) deletes the subscriber and their data", async () => {
  const env = makeEnv();
  const api = client(env);
  await activeSubscriber(env, api);
  const subscriber = await env.DB.prepare("SELECT id FROM subscribers").first();
  const token = await unsubscribeToken("p".repeat(40), subscriber.id);

  const page = await api.call("GET", `/v1/unsubscribe?token=${token}`);
  assert.equal(page.status, 200);
  assert.match(page.data, /<form method="post"/);
  assert.ok(await env.DB.prepare("SELECT id FROM subscribers").first(), "GET never unsubscribes");

  const oneClick = await api.call("POST", `/v1/unsubscribe?token=${token}`, {
    raw: "List-Unsubscribe=One-Click",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    origin: null,
  });
  assert.equal(oneClick.status, 200);
  for (const table of ["subscribers", "rules", "tokens", "deliveries"]) {
    const row = await env.DB.prepare(`SELECT COUNT(*) AS n FROM ${table}`).first();
    assert.equal(row.n, 0, `${table} emptied`);
  }
  const forged = await api.call("POST", `/v1/unsubscribe?token=${subscriber.id}.${"0".repeat(40)}`, { raw: "" });
  assert.equal(forged.status, 400);
});

test("delete with the manage token removes everything", async () => {
  const env = makeEnv();
  const api = client(env);
  const token = await activeSubscriber(env, api);
  const deleted = await api.call("DELETE", "/v1/subscriber", { headers: { Authorization: `Bearer ${token}` } });
  assert.deepEqual([deleted.status, deleted.data], [200, { status: "deleted" }]);
  assert.equal((await env.DB.prepare("SELECT COUNT(*) AS n FROM subscribers").first()).n, 0);
});

test("rate limits: per IP returns 429, per address is silent", async () => {
  const env = makeEnv();
  const api = client(env);
  for (let index = 0; index < 5; index += 1) {
    const response = await api.call("POST", "/v1/subscribe", { body: subscribeBody(`r${index}@example.com`) });
    assert.equal(response.status, 202);
  }
  const blocked = await api.call("POST", "/v1/subscribe", { body: subscribeBody("r9@example.com") });
  assert.equal(blocked.status, 429);
  assert.equal(blocked.data.error, "rate_limited");
  assert.ok(Number(blocked.headers.get("Retry-After")) > 0);
});

test("per-address limit stops extra verification emails without telling the caller", async () => {
  const env = makeEnv();
  const api = client(env);
  let ip = 0;
  for (let index = 0; index < 5; index += 1) {
    const response = await api.call("POST", "/v1/subscribe", {
      body: subscribeBody("same@example.com"),
      headers: { "CF-Connecting-IP": `198.51.100.${(ip += 1)}` },
    });
    assert.equal(response.status, 202);
  }
  assert.equal((await outbox(env)).length, 3, "3 verification emails per address per day");
});

test("subscriber cap closes signups", async () => {
  const env = makeEnv("mock", { MAX_ACTIVE_SUBSCRIBERS: "1" });
  const api = client(env);
  await activeSubscriber(env, api, "first@example.com");
  const second = await api.call("POST", "/v1/subscribe", {
    body: subscribeBody("second@example.com"),
    headers: { "CF-Connecting-IP": "198.51.100.200" },
  });
  assert.equal(second.status, 503);
  assert.equal(second.data.error, "signups_closed");

  const closed = client(makeEnv("mock", { MAX_ACTIVE_SUBSCRIBERS: "0" }));
  const none = await closed.call("POST", "/v1/subscribe", { body: subscribeBody() });
  assert.deepEqual([none.status, none.data.error], [503, "signups_closed"], '"0" closes signups');
});

test("CORS allows only the site origin (plus localhost in mock mode)", async () => {
  const prod = client(makeEnv("production"), { network: fakeNetwork() });
  const preflight = await prod.call("OPTIONS", "/v1/subscribe", {});
  assert.equal(preflight.status, 204);
  assert.equal(preflight.headers.get("Access-Control-Allow-Origin"), "https://pchoward.github.io");
  const evil = await prod.call("OPTIONS", "/v1/subscribe", { origin: "https://evil.example" });
  assert.equal(evil.status, 403);
  const local = await prod.call("OPTIONS", "/v1/subscribe", { origin: "http://localhost:8000" });
  assert.equal(local.status, 403, "no localhost outside mock mode");
  const mock = client(makeEnv("mock"));
  const mockLocal = await mock.call("OPTIONS", "/v1/subscribe", { origin: "http://localhost:8000" });
  assert.equal(mockLocal.status, 204);
});

test("production sends through Resend with a verified Turnstile token", async () => {
  const network = fakeNetwork();
  const env = makeEnv("production");
  const api = client(env, { network });
  const response = await api.call("POST", "/v1/subscribe", { body: subscribeBody("rider@example.com", { turnstile_token: "real-token" }) });
  assert.equal(response.status, 202);
  const turnstile = network.calls.find((call) => call.url.includes("turnstile"));
  assert.equal(turnstile.init.body.get("secret"), "turnstile-secret");
  const resend = network.calls.find((call) => call.url.startsWith("https://api.resend.com/"));
  const payload = JSON.parse(resend.init.body);
  assert.equal(payload.from, "SkateDeals <alerts@skatedeals.example>");
  assert.deepEqual(payload.to, ["rider@example.com"]);
  assert.equal(resend.init.headers.Authorization, "Bearer re_test_key");
  assert.equal((await outbox(env)).length, 0, "the outbox is mock-only");

  const failedCaptcha = client(makeEnv("production"), { network: fakeNetwork({ turnstile: () => ({ success: false }) }) });
  assert.equal((await failedCaptcha.call("POST", "/v1/subscribe", { body: subscribeBody() })).data.error, "captcha_failed");
  const downCaptcha = client(makeEnv("production"), {
    network: fakeNetwork({ turnstile: () => { throw new Error("down"); } }),
  });
  assert.equal((await downCaptcha.call("POST", "/v1/subscribe", { body: subscribeBody() })).data.error, "captcha_failed");
  const downMail = client(makeEnv("production"), { network: fakeNetwork({ resend: () => new Response("{}", { status: 500 }) }) });
  assert.equal((await downMail.call("POST", "/v1/subscribe", { body: subscribeBody() })).data.error, "email_unavailable");
});

test("staging only emails STAGING_ALLOWED_EMAILS", async () => {
  const network = fakeNetwork();
  const api = client(makeEnv("staging"), { network });
  const other = await api.call("POST", "/v1/subscribe", { body: subscribeBody("stranger@example.com") });
  assert.equal(other.status, 403);
  assert.equal(network.calls.filter((call) => call.url.includes("resend")).length, 0);
  const owner = await api.call("POST", "/v1/subscribe", { body: subscribeBody("owner@example.com"), headers: { "CF-Connecting-IP": "198.51.100.9" } });
  assert.equal(owner.status, 202);
  assert.equal(network.calls.filter((call) => call.url.includes("resend")).length, 1);
});

test("public API URL in links", async () => {
  const env = makeEnv();
  const api = client(env);
  await activeSubscriber(env, api);
  await api.call("POST", "/v1/link", { body: { email: "rider@example.com", turnstile_token: "mock-turnstile-pass" } });
  const mail = (await outbox(env)).pop();
  const headers = JSON.parse(mail.headers);
  assert.match(headers["List-Unsubscribe"], new RegExp(`^<${API}/v1/unsubscribe\\?token=s_[0-9a-f]{24}\\.[0-9a-f]{40}>$`));
  assert.equal(headers["List-Unsubscribe-Post"], "List-Unsubscribe=One-Click");
});
