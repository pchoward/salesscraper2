// Issue #70: the general digest and product watches, next to the original
// brand/name ("search") rules.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { sha256Hex } from "../src/crypto.js";
import { productKey, ruleId, validateRule, validateRules } from "../src/rules.js";
import { activeSubscriber, client, makeEnv, outbox, RULE } from "./helpers.js";

const KEYS = JSON.parse(readFileSync(new URL("../contract/product-keys.json", import.meta.url), "utf8"));
const CCS = "https://shop.ccs.com/collections/sale/products/baker-brand-logo-deck-8-25";
const ZUMIEZ = "https://www.zumiez.com/heroin-egg-8-75-skateboard-deck.html";
const WATCH = { kind: "watch", product_url: ZUMIEZ, label: 'Heroin Egg 8.75" Skateboard Deck', max_price: 50 };
const DIGEST = { kind: "digest" };

function errorsOf(input) {
  return validateRule(input).errors;
}

test("product keys match the Python side for every shared vector", () => {
  for (const row of KEYS.keys) assert.equal(productKey(row.url), row.key, row.why);
});

test("a watch names one store listing by its canonical URL", () => {
  const { rule } = validateRule(WATCH);
  assert.deepEqual(rule, {
    kind: "watch",
    label: 'Heroin Egg 8.75" Skateboard Deck',
    max_price: 50,
    product_key: ZUMIEZ,
    product_url: ZUMIEZ,
  });
  // No trigger means "any meaningful price drop", stored explicitly.
  assert.equal(validateRule({ kind: "watch", product_url: ZUMIEZ }).rule.alert_on_drop, true);
  assert.equal(validateRule({ kind: "watch", product_url: CCS }).rule.product_key, "shopify:shop.ccs.com:baker-brand-logo-deck-8-25");

  assert.deepEqual(errorsOf({ kind: "watch" }), { product_url: "required" });
  for (const url of [
    "http://www.zumiez.com/x.html",
    "https://WWW.zumiez.com/x.html", // not the canonical spelling
    "https://www.zumiez.com/x.html#reviews",
    "https://user:pw@www.zumiez.com/x.html",
    " https://www.zumiez.com/x.html",
    "not a url",
    `https://www.zumiez.com/${"x".repeat(500)}`,
    42,
  ]) {
    assert.deepEqual(errorsOf({ kind: "watch", product_url: url }), { product_url: "invalid_url" }, String(url));
  }
  assert.deepEqual(errorsOf({ kind: "watch", product_url: "https://example.com/deck" }), { product_url: "store_not_tracked" });
  // Search fields on a watch are a kind mix-up, not a typo, and are never silently ignored.
  assert.deepEqual(errorsOf({ ...WATCH, brand: "Heroin", width: 8.75 }), { brand: "not_for_kind", width: "not_for_kind" });
  assert.deepEqual(errorsOf({ ...WATCH, product_key: "x" }), { product_key: "unknown_field" }, "the key is response-only");
  assert.deepEqual(errorsOf({ kind: "everything" }), { kind: "invalid" });
});

test("the digest is simple by default and filterable when asked", () => {
  assert.deepEqual(validateRule(DIGEST).rule, { kind: "digest" });
  const advanced = validateRule({ kind: "digest", parts: ["Wheels", "Decks"], events: ["low", "drop"], min_width: 8.5, max_price: 80 });
  assert.deepEqual(advanced.rule, {
    events: ["drop", "low"],
    kind: "digest",
    max_price: 80,
    min_width: 8.5,
    parts: ["Decks", "Wheels"],
  });
  assert.deepEqual(errorsOf({ kind: "digest", parts: [] }), { parts: "at_least_one" });
  assert.deepEqual(errorsOf({ kind: "digest", parts: ["Skis"] }), { parts: "invalid" });
  assert.deepEqual(errorsOf({ kind: "digest", parts: "Decks" }), { parts: "must_be_list" });
  assert.deepEqual(errorsOf({ kind: "digest", events: ["new", "new"] }), { events: "duplicate" });
  assert.deepEqual(errorsOf({ kind: "digest", parts: ["Wheels"], min_width: 8.5 }), { min_width: "decks_only" });
  assert.deepEqual(errorsOf({ kind: "digest", min_width: 9, max_width: 8 }), { max_width: "below_min_width" });
  assert.deepEqual(errorsOf({ kind: "digest", brand: "Baker" }), { brand: "not_for_kind" });
  // Sneakers and the other catalog parts are fine in a digest.
  assert.ok(validateRule({ kind: "digest", parts: ["Sneakers", "Completes"] }).rule);
});

test("rule lists: one digest, and the same watch twice is a duplicate however it is spelled", () => {
  assert.deepEqual(validateRules([DIGEST, { kind: "digest", events: ["new"] }], 10).errors, { "rules[1]": "one_digest_only" });
  const twin = { kind: "watch", product_url: "https://shop.ccs.com/products/baker-brand-logo-deck-8-25" };
  assert.deepEqual(validateRules([{ kind: "watch", product_url: CCS }, twin], 10).errors, { "rules[1]": "duplicate" });
  assert.deepEqual(validateRules([WATCH, { ...WATCH, label: "Other words", note: "x" }], 10).errors, { "rules[1]": "duplicate" });
  const mixed = validateRules([RULE, WATCH, DIGEST], 10);
  assert.equal(mixed.rules.length, 3);
});

test("search rules are unchanged: same normalized form, same ids as before kinds existed", async () => {
  const { rule } = validateRule({ ...RULE, kind: "search" });
  assert.equal(rule.kind, undefined, "search rules keep their original stored form");
  const { note, ...identity } = rule;
  const before = `r_${(await sha256Hex(`s_1:${JSON.stringify(identity)}`)).slice(0, 24)}`;
  assert.equal(await ruleId("s_1", rule), before);
  // Display text never changes a watch's id.
  const watch = validateRule(WATCH).rule;
  assert.equal(await ruleId("s_1", watch), await ruleId("s_1", { ...watch, label: "Renamed", note: "n" }));
});

const DAY_EVENT = "c".repeat(64);
const ITEM = {
  name: 'Heroin Egg 8.75" Skateboard Deck',
  store: "Zumiez",
  part: "Decks",
  url: ZUMIEZ,
  price_new: "44.99",
  price_old: "79.95",
};

function digestSection(overrides = {}) {
  return {
    event_id: DAY_EVENT,
    total: 3,
    items: [
      { kind: "drop", item: ITEM, price_before: "54.99" },
      { kind: "new", item: { ...ITEM, name: "Baker Brand Logo Deck 8.25", url: "https://www.zumiez.com/baker.html", price_new: "49.99" } },
    ],
    ...overrides,
  };
}

async function deliver(api, deliveries) {
  return api.signed("POST", "/v1/internal/deliveries", JSON.stringify({ version: 1, deliveries }));
}

test("routes carry watches and the digest; one email holds alerts and today's deals", async () => {
  const env = makeEnv();
  const api = client(env);
  await activeSubscriber(env, api, "rider@example.com", [WATCH, DIGEST]);
  const routes = await api.signed("GET", "/v1/internal/routes");
  const [route] = routes.data.routes;
  assert.deepEqual(
    route.rules.map(({ id, ...rule }) => rule),
    [validateRule(WATCH).rule, { kind: "digest" }],
  );
  const before = (await outbox(env)).length;

  const hit = { event_ids: ["e".repeat(64)], reasons: ["Maximum price reached"], note: "", item: ITEM };
  const both = await deliver(api, [{ route_id: route.route_id, delivery_id: "1".repeat(64), hits: [hit], digest: digestSection() }]);
  assert.equal(both.status, 200);
  assert.equal(both.data.results[0].status, "sent");
  const [mail] = (await outbox(env)).slice(before);
  assert.equal(mail.subject, "SkateDeals: 1 alert and 3 deals today");
  assert.match(mail.text_body, /Your SkateDeals alerts matched[\s\S]*Today's deals/);
  assert.match(mail.text_body, /Price drop/);
  assert.match(mail.text_body, /\(was \$54\.99\)/);
  assert.match(mail.text_body, /1 more today: https:\/\/pchoward\.github\.io\//);
  assert.match(mail.html_body, /See 1 more on SkateDeals/);

  // The same day's digest never goes out twice, even in a new delivery.
  const again = await deliver(api, [{ route_id: route.route_id, delivery_id: "2".repeat(64), digest: digestSection() }]);
  assert.equal(again.data.results[0].status, "duplicate");
  // A digest-only delivery for a new day is its own email.
  const next = await deliver(api, [
    { route_id: route.route_id, delivery_id: "3".repeat(64), digest: digestSection({ event_id: "f".repeat(64), total: 2 }) },
  ]);
  assert.equal(next.data.results[0].status, "sent");
  const last = (await outbox(env)).at(-1);
  assert.equal(last.subject, "SkateDeals daily deals: 2 today");
  assert.doesNotMatch(last.text_body, /more today/);
  assert.match(last.text_body, /Unsubscribe: /);
});

test("malformed digest sections are refused", async () => {
  const env = makeEnv();
  const api = client(env);
  await activeSubscriber(env, api, "rider@example.com", [DIGEST]);
  const route = (await api.signed("GET", "/v1/internal/routes")).data.routes[0].route_id;
  const many = Array.from({ length: 31 }, () => ({ kind: "new", item: ITEM }));
  for (const digest of [
    digestSection({ event_id: "nope" }),
    digestSection({ total: 1 }),
    digestSection({ items: [] }),
    digestSection({ items: many, total: 31 }),
    digestSection({ items: [{ kind: "restock", item: ITEM }] }),
    digestSection({ items: [{ kind: "drop", item: ITEM }] }), // a drop needs its earlier price
    digestSection({ items: [{ kind: "new", item: { ...ITEM, url: "https://evil.example/deck" } }] }),
  ]) {
    const response = await deliver(api, [{ route_id: route, delivery_id: "4".repeat(64), digest }]);
    assert.equal(response.status, 400, JSON.stringify(digest).slice(0, 80));
  }
  // Neither hits nor a digest: nothing to send.
  assert.equal((await deliver(api, [{ route_id: route, delivery_id: "5".repeat(64), hits: [] }])).status, 400);
});
