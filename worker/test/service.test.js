import assert from "node:assert/strict";
import { test } from "node:test";
import { loadConfig } from "../src/config.js";
import { emailHash, hmacBase64 } from "../src/crypto.js";
import { runMaintenance } from "../src/maintenance.js";
import { activeSubscriber, client, makeEnv, outbox, START, subscribeBody } from "./helpers.js";

test("misconfiguration fails closed and /v1/health names only the settings", async () => {
  const cases = [
    [{ MODE: undefined }, "MODE"],
    [{ MODE: "dev" }, "MODE"],
    [{ HMAC_SECRET: "short" }, "HMAC_SECRET"],
    [{ TOKEN_PEPPER: "" }, "TOKEN_PEPPER"],
    [{ PUBLIC_ORIGIN: "http://pchoward.github.io" }, "PUBLIC_ORIGIN"],
    [{ PUBLIC_ORIGIN: "https://pchoward.github.io/salesscraper2" }, "PUBLIC_ORIGIN"],
    [{ CONSENT_VERSION: "" }, "CONSENT_VERSION"],
  ];
  for (const [override, problem] of cases) {
    const env = makeEnv("mock", override);
    const api = client(env);
    const health = await api.call("GET", "/v1/health");
    assert.equal(health.status, 503);
    assert.ok(health.data.problems.includes(problem), problem);
    const blocked = await api.call("POST", "/v1/subscribe", { body: subscribeBody() });
    assert.deepEqual([blocked.status, blocked.data], [503, { error: "service_unavailable" }]);
    assert.ok(!JSON.stringify(health.data).includes("p".repeat(40)), "values are never echoed");
  }
});

test("production refuses Resend's test sender and missing provider keys", () => {
  const sender = loadConfig(makeEnv("production", { EMAIL_FROM: "SkateDeals <onboarding@resend.dev>" }));
  assert.deepEqual(sender.problems, ["EMAIL_FROM"]);
  const keys = loadConfig(makeEnv("production", { RESEND_API_KEY: "", TURNSTILE_SECRET: "" }));
  assert.deepEqual(keys.problems.sort(), ["RESEND_API_KEY", "TURNSTILE_SECRET"]);
  assert.ok(loadConfig(makeEnv("staging")).ok, "staging may use onboarding@resend.dev for the owner");
  assert.deepEqual(loadConfig(makeEnv("staging", { STAGING_ALLOWED_EMAILS: "" })).problems, ["STAGING_ALLOWED_EMAILS"]);
  assert.ok(loadConfig(makeEnv("production")).ok);
});

test("mock outbox exists only in mock mode", async () => {
  const mock = client(makeEnv("mock"));
  assert.equal((await mock.call("GET", "/v1/mock/outbox")).status, 200);
  const prod = client(makeEnv("production"));
  assert.equal((await prod.call("GET", "/v1/mock/outbox")).status, 404);
});

test("unknown paths and methods", async () => {
  const api = client(makeEnv());
  assert.equal((await api.call("GET", "/v1/nope")).status, 404);
  assert.equal((await api.call("DELETE", "/v1/subscribe")).status, 405);
});

async function svixHeaders(secret, body, timestamp, id = "msg_1") {
  const key = Uint8Array.from(atob(secret.slice(6)), (char) => char.charCodeAt(0));
  return {
    "svix-id": id,
    "svix-timestamp": String(timestamp),
    "svix-signature": `v1,${await hmacBase64(key, `${id}.${timestamp}.${body}`)}`,
    "Content-Type": "application/json",
  };
}

test("complaints and permanent bounces delete the subscriber and suppress the address", async () => {
  const secret = `whsec_${btoa("w".repeat(32))}`;
  const env = makeEnv("mock", { RESEND_WEBHOOK_SECRET: secret });
  const api = client(env);
  await activeSubscriber(env, api);
  const transient = JSON.stringify({ type: "email.bounced", data: { to: ["rider@example.com"], bounce: { type: "Transient" } } });
  assert.equal((await api.call("POST", "/v1/webhooks/resend", { raw: transient, origin: null, headers: await svixHeaders(secret, transient, START) })).status, 200);
  assert.equal((await env.DB.prepare("SELECT COUNT(*) AS n FROM subscribers").first()).n, 1, "a transient bounce keeps them");

  const forged = JSON.stringify({ type: "email.complained", data: { to: ["rider@example.com"] } });
  const bad = await api.call("POST", "/v1/webhooks/resend", {
    raw: forged,
    origin: null,
    headers: { ...(await svixHeaders(secret, "different body", START)) },
  });
  assert.equal(bad.status, 401);
  const stale = await api.call("POST", "/v1/webhooks/resend", { raw: forged, origin: null, headers: await svixHeaders(secret, forged, START - 600) });
  assert.equal(stale.status, 401);

  const ok = await api.call("POST", "/v1/webhooks/resend", { raw: forged, origin: null, headers: await svixHeaders(secret, forged, START, "msg_2") });
  assert.equal(ok.status, 200);
  assert.equal((await env.DB.prepare("SELECT COUNT(*) AS n FROM subscribers").first()).n, 0);
  const suppression = await env.DB.prepare("SELECT reason, email_hash FROM suppressions").first();
  assert.equal(suppression.reason, "complaint");
  assert.equal(suppression.email_hash, await emailHash("p".repeat(40), "rider@example.com"));

  // A new signup for a suppressed address is accepted quietly and sends nothing.
  const sent = (await outbox(env)).length;
  const again = await api.call("POST", "/v1/subscribe", { body: subscribeBody(), headers: { "CF-Connecting-IP": "198.51.100.77" } });
  assert.equal(again.status, 202);
  assert.equal((await outbox(env)).length, sent);
});

test("webhook is disabled until its secret is set", async () => {
  const api = client(makeEnv());
  const response = await api.call("POST", "/v1/webhooks/resend", { raw: "{}", origin: null, headers: { "Content-Type": "application/json" } });
  assert.deepEqual([response.status, response.data.error], [503, "webhook_disabled"]);
});

test("retention removes stale pending signups, tokens, deliveries, and counters", async () => {
  const env = makeEnv();
  const api = client(env);
  await api.call("POST", "/v1/subscribe", { body: subscribeBody("pending@example.com") });
  await activeSubscriber(env, api, "active@example.com");
  const removed = await runMaintenance(env.DB, START + 8 * 86400);
  assert.equal(removed.pending, 1);
  const statuses = await env.DB.prepare("SELECT status FROM subscribers").all();
  assert.deepEqual(statuses.results.map((row) => row.status), ["active"]);
  assert.ok(removed.tokens >= 1);
  assert.ok(removed.rate_limits >= 1);
});
