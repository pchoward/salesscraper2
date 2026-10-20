import assert from "node:assert/strict";
import { test } from "node:test";
import { internalSignature } from "../src/crypto.js";
import { activeSubscriber, client, fakeNetwork, HMAC_SECRET, makeEnv, outbox, RULE, START, subscribeBody } from "./helpers.js";

// Shared with test_alerts_delivery.py so both sides sign the same way.
export const VECTORS = [
  {
    secret: "vector-secret-".padEnd(40, "x"),
    method: "POST",
    path: "/v1/internal/deliveries",
    timestamp: 1790000000,
    nonce: "nonce_0123456789abcdef",
    body: '{"version":1,"deliveries":[]}',
    signature: "v1=7115ad864013276f5144ac589e5e7f3a8d5019d286630fe9aa2884df9fb398cc",
  },
  {
    secret: "vector-secret-".padEnd(40, "x"),
    method: "GET",
    path: "/v1/internal/routes",
    timestamp: 1790000000,
    nonce: "nonce_0123456789abcdef",
    body: "",
    signature: "v1=d6d386510dbec0accbf2f2fcadb071d9c36006fa266db360b7bb4bf9c6508c0b",
  },
];

const EVENT_A = "a".repeat(64);
const EVENT_B = "b".repeat(64);

function hitFor(eventIds, overrides = {}) {
  return {
    event_ids: eventIds,
    reasons: ["Maximum price reached"],
    note: "Wide Heroin decks",
    item: {
      name: 'Heroin Egg 8.75" Skateboard Deck',
      store: "Zumiez",
      part: "Decks",
      url: "https://www.zumiez.com/heroin-egg-8-75-skateboard-deck.html",
      price_new: "54.99",
      price_old: "79.95",
    },
    ...overrides,
  };
}

async function routeId(api) {
  const routes = await api.signed("GET", "/v1/internal/routes");
  return routes.data.routes[0].route_id;
}

function deliveryBody(route, hits, deliveryId = "d".repeat(64)) {
  return JSON.stringify({ version: 1, deliveries: [{ route_id: route, delivery_id: deliveryId, hits }] });
}

test("signature vectors match the Python client", async () => {
  for (const vector of VECTORS) {
    assert.equal(
      await internalSignature(vector.secret, vector.method, vector.path, vector.timestamp, vector.nonce, vector.body),
      vector.signature,
    );
  }
});

test("internal endpoints reject unsigned, stale, wrong, and replayed requests", async () => {
  const env = makeEnv();
  const api = client(env);
  assert.equal((await api.call("GET", "/v1/internal/routes", { origin: null })).status, 401);
  assert.equal((await api.signed("GET", "/v1/internal/routes", "", { secret: "w".repeat(40) })).status, 401);
  assert.equal((await api.signed("GET", "/v1/internal/routes", "", { timestamp: START - 301 })).status, 401);
  const nonce = "replay_nonce_0123456789";
  assert.equal((await api.signed("GET", "/v1/internal/routes", "", { nonce })).status, 200);
  assert.equal((await api.signed("GET", "/v1/internal/routes", "", { nonce })).status, 401, "a nonce works once");
  // A signature over one body does not authorize another.
  const signature = await internalSignature(HMAC_SECRET, "POST", "/v1/internal/deliveries", START, "nonce_body_swap_0123", "{}");
  const swapped = await api.call("POST", "/v1/internal/deliveries", {
    origin: null,
    raw: JSON.stringify({ version: 1, deliveries: [] }),
    headers: {
      "Content-Type": "application/json",
      "X-SkateDeals-Timestamp": String(START),
      "X-SkateDeals-Nonce": "nonce_body_swap_0123",
      "X-SkateDeals-Signature": signature,
    },
  });
  assert.equal(swapped.status, 401);
});

test("routes list verified subscribers' rules and never an address", async () => {
  const env = makeEnv();
  const api = client(env);
  await activeSubscriber(env, api, "rider@example.com", [RULE, { name: "Antihero Caster" }]);
  await api.call("POST", "/v1/subscribe", { body: subscribeBody("pending@example.com"), headers: { "CF-Connecting-IP": "198.51.100.3" } });
  const response = await api.signed("GET", "/v1/internal/routes");
  assert.equal(response.status, 200);
  assert.equal(response.data.version, 1);
  assert.equal(response.data.routes.length, 1, "pending subscribers are not routed");
  const [route] = response.data.routes;
  assert.match(route.route_id, /^route_[0-9a-f]{24}$/);
  assert.deepEqual(route.rules.map(({ id, ...rule }) => rule), [
    { brand: "Heroin", max_price: 60, min_width: 8.6, note: "Wide Heroin decks", part: "Decks" },
    { name: "Antihero Caster", part: "Decks" },
  ]);
  assert.ok(!JSON.stringify(response.data).includes("@"), "no email addresses");
});

test("deliveries send once per event, even when retried", async () => {
  const env = makeEnv();
  const api = client(env);
  await activeSubscriber(env, api);
  const route = await routeId(api);
  const before = (await outbox(env)).length;

  const first = await api.signed("POST", "/v1/internal/deliveries", deliveryBody(route, [hitFor([EVENT_A])]));
  assert.equal(first.status, 200);
  assert.deepEqual(first.data.results, [{ route_id: route, delivery_id: "d".repeat(64), status: "sent" }]);
  const mail = (await outbox(env)).at(-1);
  assert.equal(mail.subject, 'SkateDeals alert: Heroin Egg 8.75" Skateboard Deck');
  assert.match(mail.text_body, /\$54\.99 \(was \$79\.95\)/);
  assert.match(mail.text_body, /Maximum price reached · Wide Heroin decks/);
  assert.match(JSON.parse(mail.headers)["List-Unsubscribe"], /^<https:\/\/alerts\.example\.test\/v1\/unsubscribe\?token=/);

  const retry = await api.signed("POST", "/v1/internal/deliveries", deliveryBody(route, [hitFor([EVENT_A])], "e".repeat(64)));
  assert.equal(retry.data.results[0].status, "duplicate");
  const mixed = await api.signed("POST", "/v1/internal/deliveries", deliveryBody(route, [hitFor([EVENT_A]), hitFor([EVENT_B])], "f".repeat(64)));
  assert.equal(mixed.data.results[0].status, "sent");
  assert.equal((await outbox(env)).length, before + 2, "the retry sent nothing; the mixed batch sent only the new event");
});

test("provider outcomes map to retry-safe statuses", async () => {
  const outcomes = [
    [() => new Response("{}", { status: 422 }), "failed", 0],
    [() => new Response("{}", { status: 429 }), "failed", 0],
    [() => new Response("{}", { status: 500 }), "uncertain", 1],
    [() => new Error("socket hang up"), "uncertain", 1],
  ];
  for (const [resend, status, kept] of outcomes) {
    const env = makeEnv("production");
    // Make a verified subscriber directly; production signup needs real email.
    await env.DB.prepare(
      "INSERT INTO subscribers (id, route_id, email, email_hash, status, consent_version, created_at, updated_at) VALUES ('s_" +
        "1".repeat(24) +
        "', 'route_prod', 'rider@example.com', 'h', 'active', '2026-10', 1, 1)",
    ).run();
    const failing = client(env, { network: fakeNetwork({ resend }) });
    const response = await failing.signed("POST", "/v1/internal/deliveries", deliveryBody("route_prod", [hitFor([EVENT_A])]));
    assert.equal(response.data.results[0].status, status);
    const rows = await env.DB.prepare("SELECT status FROM deliveries").all();
    assert.equal(rows.results.length, kept, `${status} keeps ${kept} journal rows`);
    if (kept) {
      // An uncertain event is never sent again automatically.
      const again = await client(env, { network: fakeNetwork() }).signed("POST", "/v1/internal/deliveries", deliveryBody("route_prod", [hitFor([EVENT_A])]));
      assert.equal(again.data.results[0].status, "uncertain");
    }
  }
});

test("idempotency key and unsubscribe headers reach Resend", async () => {
  const env = makeEnv("production");
  await env.DB.prepare(
    "INSERT INTO subscribers (id, route_id, email, email_hash, status, consent_version, created_at, updated_at) VALUES ('s_" +
      "2".repeat(24) +
      "', 'route_prod', 'rider@example.com', 'h', 'active', '2026-10', 1, 1)",
  ).run();
  const network = fakeNetwork();
  const api = client(env, { network });
  await api.signed("POST", "/v1/internal/deliveries", deliveryBody("route_prod", [hitFor([EVENT_A])]));
  const call = network.calls.find((entry) => entry.url.startsWith("https://api.resend.com/"));
  assert.equal(call.init.headers["Idempotency-Key"], `skatedeals-s_${"2".repeat(24)}-${"d".repeat(64)}`);
  const payload = JSON.parse(call.init.body);
  assert.equal(payload.headers["List-Unsubscribe-Post"], "List-Unsubscribe=One-Click");
  assert.deepEqual(payload.to, ["rider@example.com"]);
});

test("inactive routes, daily caps, and unsafe content", async () => {
  const env = makeEnv("mock", { DAILY_EMAILS_PER_SUBSCRIBER: "1" });
  const api = client(env);
  await activeSubscriber(env, api);
  const route = await routeId(api);
  const gone = await api.signed("POST", "/v1/internal/deliveries", deliveryBody("route_gone", [hitFor([EVENT_A])]));
  assert.equal(gone.data.results[0].status, "inactive");
  assert.equal((await api.signed("POST", "/v1/internal/deliveries", deliveryBody(route, [hitFor([EVENT_A])]))).data.results[0].status, "sent");
  const capped = await api.signed("POST", "/v1/internal/deliveries", deliveryBody(route, [hitFor([EVENT_B])], "c".repeat(64)));
  assert.equal(capped.data.results[0].status, "deferred");

  const badHits = [
    hitFor([EVENT_A], { item: { ...hitFor([]).item, url: "https://evil.example/phish" } }),
    hitFor([EVENT_A], { item: { ...hitFor([]).item, url: "http://www.zumiez.com/x.html" } }),
    hitFor([EVENT_A], { reasons: ["Click here to win"] }),
    hitFor(["not-hex"]),
    hitFor([EVENT_A], { item: { ...hitFor([]).item, price_new: "free" } }),
  ];
  for (const bad of badHits) {
    const response = await api.signed("POST", "/v1/internal/deliveries", deliveryBody(route, [bad], "9".repeat(64)));
    assert.equal(response.status, 400);
  }
});

test("delivered email escapes every field", async () => {
  const env = makeEnv();
  const api = client(env);
  await activeSubscriber(env, api);
  const route = await routeId(api);
  const hostile = hitFor([EVENT_A], { note: "<script>alert(1)</script>", item: { ...hitFor([]).item, name: '"><img src=x onerror=1>' } });
  await api.signed("POST", "/v1/internal/deliveries", deliveryBody(route, [hostile]));
  const mail = (await outbox(env)).at(-1);
  assert.ok(!mail.html_body.includes("<script>"));
  assert.ok(!mail.html_body.includes("<img src=x"));
  assert.ok(mail.html_body.includes("&lt;script&gt;"));
});
