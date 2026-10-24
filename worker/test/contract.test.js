import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { client, makeEnv, outbox } from "./helpers.js";

const SESSIONS = ["examples.json", "examples-digest-watch.json"];
const load = (name) => JSON.parse(readFileSync(new URL(`../contract/${name}`, import.meta.url), "utf8"));

const SHAPES = {
  "<token>": /^[A-Za-z0-9_-]{43}$/,
  "<rule-id>": /^r_[0-9a-f]{24}$/,
  "<iso-time>": /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/,
};

function substitute(value, captured) {
  if (typeof value === "string") return value.replace(/\{\{(\w+)\}\}/g, (_m, name) => captured[name]);
  if (Array.isArray(value)) return value.map((item) => substitute(item, captured));
  if (value && typeof value === "object") return Object.fromEntries(Object.entries(value).map(([k, v]) => [k, substitute(v, captured)]));
  return value;
}

function matches(actual, expected, path = "body") {
  if (typeof expected === "string" && SHAPES[expected]) {
    assert.match(String(actual), SHAPES[expected], path);
    return;
  }
  if (Array.isArray(expected)) {
    assert.ok(Array.isArray(actual), `${path} is a list`);
    assert.equal(actual.length, expected.length, `${path} length`);
    expected.forEach((item, index) => matches(actual[index], item, `${path}[${index}]`));
    return;
  }
  if (expected && typeof expected === "object") {
    assert.deepEqual(Object.keys(actual).sort(), Object.keys(expected).sort(), `${path} keys`);
    for (const key of Object.keys(expected)) matches(actual[key], expected[key], `${path}.${key}`);
    return;
  }
  assert.deepEqual(actual, expected, path);
}

for (const name of SESSIONS) test(`contract/${name} is exactly what the API does`, async () => {
  const contract = load(name);
  const env = makeEnv("mock");
  const api = client(env);
  const captured = {};
  let ip = 0;
  for (const step of contract.steps) {
    const request = substitute(step.request, captured);
    const response = await api.call(request.method, request.path, {
      body: request.body,
      headers: { ...(request.headers || {}), "CF-Connecting-IP": `192.0.2.${(ip += 1)}` },
    });
    assert.equal(response.status, step.response.status, step.name);
    matches(response.data, step.response.body, step.name);
    for (const [name, field] of Object.entries(step.capture || {})) captured[name] = response.data[field];
    for (const [name, marker] of Object.entries(step.capture_from_email || {})) {
      const mail = (await outbox(env)).at(-1);
      const match = new RegExp(`${marker}([A-Za-z0-9_-]+)`).exec(mail.text_body);
      assert.ok(match, `${step.name}: email carries ${marker}`);
      captured[name] = match[1];
    }
  }
});
