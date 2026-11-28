// Store newsletters -> promo strip (owner, 2026-11-27).
import assert from "node:assert/strict";
import { test } from "node:test";
import { API, client, HMAC_SECRET, makeEnv, START } from "./helpers.js";
import { dmarcPassed, fromDomain, mailText, pruneNewsletters, receiveEmail, storeFor } from "../src/newsletters.js";

const INBOX = "deals@shreddeals.example";

function env(overrides = {}) {
  return makeEnv("mock", { NEWSLETTER_INBOX: INBOX, ...overrides });
}

function mail({ from = "Jenson USA <deals@email.jensonusa.com>", auth = "mx.cloudflare.net; dkim=pass; dmarc=pass header.from=email.jensonusa.com", id = "<a1@jensonusa.com>", body } = {}) {
  const text = body || [
    "--b1",
    "Content-Type: text/plain; charset=utf-8",
    "Content-Transfer-Encoding: quoted-printable",
    "",
    "Black Friday: take 20% off everything with code BLACKFRI=",
    "DAY20 at checkout. Ends 12/2.",
    "--b1",
    "Content-Type: text/html; charset=utf-8",
    "",
    "<p>ignored when there is plain text</p>",
    "--b1--",
  ].join("\r\n");
  const raw = [
    `From: ${from}`,
    `To: ${INBOX}`,
    "Subject: =?utf-8?Q?20%_Off_Everything?=",
    `Message-ID: ${id}`,
    'Content-Type: multipart/alternative; boundary="b1"',
    "",
    text,
  ].join("\r\n");
  return {
    from: "bounce@email.jensonusa.com",
    to: INBOX,
    rawSize: raw.length,
    raw: new Response(raw).body,
    headers: new Headers({ "Authentication-Results": auth }),
  };
}

test("parts of a mail", () => {
  assert.equal(fromDomain("Jenson USA <deals@email.jensonusa.com>"), "email.jensonusa.com");
  assert.deepEqual(storeFor("email.jensonusa.com"), { domain: "jensonusa.com", store: "Jenson USA" });
  assert.equal(storeFor("jensonusa.com.evil.example"), null);
  assert.equal(dmarcPassed("x; dmarc=pass (p=reject) header.from=jensonusa.com", "jensonusa.com"), true);
  assert.equal(dmarcPassed("x; dmarc=fail header.from=jensonusa.com", "jensonusa.com"), false);
  const html = mailText('Content-Type: text/html\r\n\r\n<style>.x{}</style><p>Save 15% &amp; more</p>');
  assert.equal(html.text, "Save 15% & more");
});

test("a store's authenticated mail is stored once and listed with a signed request", async () => {
  const e = env();
  assert.equal(await receiveEmail(mail(), e, START), "stored");
  assert.equal(await receiveEmail(mail(), e, START), "duplicate");
  const api = client(e);
  const listed = await api.signed("GET", "/v1/internal/newsletters?since=0");
  assert.equal(listed.status, 200);
  const [entry] = listed.data.newsletters;
  assert.equal(entry.store, "Jenson USA");
  assert.equal(entry.subject, "20% Off Everything");
  assert.match(entry.text, /code BLACKFRIDAY20 at checkout\. Ends 12\/2\./);
  assert.doesNotMatch(entry.text, /ignored/);
});

test("forged, unknown, misaddressed or oversized mail is dropped", async () => {
  const e = env();
  assert.equal(await receiveEmail(mail({ auth: "dmarc=fail header.from=jensonusa.com" }), e, START), "not_authenticated");
  assert.equal(await receiveEmail(mail({ auth: "dmarc=pass header.from=evil.example" }), e, START), "not_authenticated");
  assert.equal(await receiveEmail(mail({ from: "Deals <x@coupons.example>" }), e, START), "unknown_sender");
  assert.equal(await receiveEmail({ ...mail(), to: "other@shreddeals.example" }, e, START), "not_inbox");
  assert.equal(await receiveEmail({ ...mail(), rawSize: 2_000_000 }, e, START), "too_big");
  assert.equal(await receiveEmail(mail(), makeEnv("mock"), START), "disabled"); // no NEWSLETTER_INBOX
  const listed = await client(e).signed("GET", "/v1/internal/newsletters?since=0");
  assert.deepEqual(listed.data.newsletters, []);
});

test("the list needs a valid signature and works without the alert settings", async () => {
  const e = { DB: env().DB, HMAC_SECRET, NEWSLETTER_INBOX: INBOX }; // no MODE, PUBLIC_ORIGIN, RESEND...
  assert.equal(await receiveEmail(mail(), e, START), "stored");
  const api = client(e);
  assert.equal((await api.signed("GET", "/v1/internal/newsletters?since=0", "", { secret: "x".repeat(40) })).status, 401);
  assert.equal((await api.call("GET", "/v1/internal/newsletters?since=0", { origin: null })).status, 401);
  assert.equal((await api.signed("GET", "/v1/internal/newsletters?since=0")).status, 200);
  assert.equal((await api.signed("GET", `/v1/internal/newsletters?since=${START + 1}`)).data.newsletters.length, 0);
});

test("old mail is forgotten", async () => {
  const e = env();
  await receiveEmail(mail(), e, START);
  assert.equal(await pruneNewsletters(e.DB, START + 46 * 86400), 1);
});
