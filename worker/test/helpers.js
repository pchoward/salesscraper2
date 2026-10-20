import { fileURLToPath } from "node:url";
import { D1Sqlite } from "../dev/d1-sqlite.js";
import { internalSignature, randomToken } from "../src/crypto.js";
import { handle } from "../src/index.js";

export const MIGRATIONS = fileURLToPath(new URL("../migrations/", import.meta.url));
export const ORIGIN = "https://pchoward.github.io";
export const API = "https://alerts.example.test";
export const HMAC_SECRET = "h".repeat(40);
export const START = 1_790_000_000; // a fixed "now" for every test

export function makeEnv(mode = "mock", overrides = {}) {
  return {
    DB: new D1Sqlite().applyMigrations(MIGRATIONS),
    MODE: mode,
    HMAC_SECRET,
    TOKEN_PEPPER: "p".repeat(40),
    PUBLIC_ORIGIN: ORIGIN,
    PUBLIC_API_URL: API,
    MANAGE_PAGE_URL: `${ORIGIN}/salesscraper2/alerts.html`,
    CONSENT_VERSION: "2026-10",
    EMAIL_FROM: mode === "production" ? "SkateDeals <alerts@skatedeals.example>" : "onboarding@resend.dev",
    ...(mode === "mock" ? {} : { RESEND_API_KEY: "re_test_key", TURNSTILE_SECRET: "turnstile-secret" }),
    ...(mode === "staging" ? { STAGING_ALLOWED_EMAILS: "owner@example.com" } : {}),
    ...overrides,
  };
}

/** Records outbound calls. `resend` and `turnstile` decide the fake replies. */
export function fakeNetwork({ resend = () => new Response("{}", { status: 200 }), turnstile = () => ({ success: true }) } = {}) {
  const calls = [];
  const fetcher = async (url, init = {}) => {
    calls.push({ url: String(url), init });
    if (String(url).startsWith("https://api.resend.com/")) {
      const reply = resend(JSON.parse(init.body), init);
      if (reply instanceof Error) throw reply;
      return reply;
    }
    if (String(url).startsWith("https://challenges.cloudflare.com/")) {
      return new Response(JSON.stringify(turnstile(init)), { status: 200 });
    }
    throw new Error(`unexpected fetch ${url}`);
  };
  return { calls, fetcher };
}

export function client(env, { network = fakeNetwork(), clock = { now: START } } = {}) {
  const deps = { fetch: network.fetcher, now: () => clock.now };
  async function call(method, path, { body, headers = {}, origin = ORIGIN, raw } = {}) {
    const init = { method, headers: { "CF-Connecting-IP": "203.0.113.7", ...headers } };
    if (origin) init.headers.Origin = origin;
    if (raw !== undefined) init.body = raw;
    else if (body !== undefined) {
      init.body = JSON.stringify(body);
      init.headers["Content-Type"] = "application/json";
    }
    const response = await handle(new Request(`${API}${path}`, init), env, deps);
    const text = await response.text();
    let data = null;
    try {
      data = JSON.parse(text);
    } catch {
      data = text;
    }
    return { status: response.status, data, headers: response.headers };
  }
  async function signed(method, path, body = "", { secret = HMAC_SECRET, nonce = randomToken(16), timestamp } = {}) {
    const ts = timestamp ?? clock.now;
    const signature = await internalSignature(secret, method, path, ts, nonce, body);
    return call(method, path, {
      raw: method === "GET" ? undefined : body,
      origin: null,
      headers: {
        "X-SkateDeals-Timestamp": String(ts),
        "X-SkateDeals-Nonce": nonce,
        "X-SkateDeals-Signature": signature,
        ...(method === "GET" ? {} : { "Content-Type": "application/json" }),
      },
    });
  }
  return { call, signed, network, clock };
}

export const RULE = { brand: "Heroin", part: "Decks", min_width: 8.6, max_price: 60, note: "Wide Heroin decks" };

export function subscribeBody(email = "rider@example.com", extra = {}) {
  return {
    email,
    rules: [RULE],
    consent: true,
    consent_version: "2026-10",
    turnstile_token: "mock-turnstile-pass",
    ...extra,
  };
}

export async function outbox(env) {
  const { results } = await env.DB.prepare("SELECT * FROM outbox ORDER BY id").all();
  return results;
}

export function tokenFrom(text, key) {
  const match = new RegExp(`#${key}=([A-Za-z0-9_-]+)`).exec(text);
  return match ? match[1] : null;
}

/** Subscribe and verify in mock mode; returns the manage token. */
export async function activeSubscriber(env, api, email = "rider@example.com", rules = [RULE]) {
  const subscribed = await api.call("POST", "/v1/subscribe", { body: subscribeBody(email, { rules }) });
  if (subscribed.status !== 202) throw new Error(`subscribe failed ${subscribed.status}`);
  const mail = (await outbox(env)).filter((row) => row.to_addr === email).pop();
  const verified = await api.call("POST", "/v1/verify", { body: { token: tokenFrom(mail.text_body, "verify") } });
  if (verified.status !== 200) throw new Error(`verify failed ${verified.status}`);
  return verified.data.manage_token;
}
