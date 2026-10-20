// Public endpoints: subscribe, verify, request a manage link, preferences,
// unsubscribe, and delete. Responses never reveal whether an address is
// subscribed.

import {
  emailHash,
  normalizeEmail,
  randomId,
  randomToken,
  readUnsubscribeToken,
  tokenHash,
  unsubscribeToken,
} from "./crypto.js";
import { manageLinkEmail, sendEmail, verificationEmail } from "./email.js";
import { checkTurnstile, enforce, hit } from "./guards.js";
import { bearerToken, clientIp, html, HttpError, json, readBody, readJson } from "./http.js";
import { ruleId, validateRules } from "./rules.js";

const VERIFY_TTL = 48 * 3600;
const MANAGE_TTL = 30 * 86400;
const EMAIL_RE = /^[^\s@<>()[\]\\,;:"]{1,64}@[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+$/;
const TOKEN_RE = /^[A-Za-z0-9_-]{20,100}$/;

const ACCEPTED = () => json(202, { status: "check_email" });

export function validEmail(email) {
  return email.length <= 254 && EMAIL_RE.test(email);
}

function maskEmail(email) {
  const [local, domain] = email.split("@");
  return `${local.slice(0, 1)}***@${domain}`;
}

function fragmentLink(base, key, token) {
  const url = new URL(base);
  url.hash = `${key}=${token}`;
  return url.href;
}

async function links(ctx, subscriberId) {
  const unsubscribe = `${ctx.settings.apiUrl}/v1/unsubscribe?token=${await unsubscribeToken(ctx.settings.pepper, subscriberId)}`;
  return { manage: ctx.settings.manageUrl, unsubscribe };
}

async function issueToken(ctx, subscriberId, purpose, ttl) {
  const token = randomToken();
  await ctx.db
    .prepare("INSERT INTO tokens (token_hash, subscriber_id, purpose, expires_at) VALUES (?, ?, ?, ?)")
    .bind(await tokenHash(ctx.settings.pepper, token), subscriberId, purpose, ctx.now + ttl)
    .run();
  return token;
}

async function send(ctx, subscriber, message, headers = {}) {
  return sendEmail(ctx.env, ctx.settings, { to: subscriber.email, headers, ...message }, ctx.fetch);
}

async function sendVerification(ctx, subscriber) {
  await ctx.db.prepare("DELETE FROM tokens WHERE subscriber_id = ? AND purpose = 'verify'").bind(subscriber.id).run();
  const token = await issueToken(ctx, subscriber.id, "verify", VERIFY_TTL);
  return send(ctx, subscriber, verificationEmail({ verify: fragmentLink(ctx.settings.manageUrl, "verify", token) }));
}

async function sendManageLink(ctx, subscriber) {
  const token = await issueToken(ctx, subscriber.id, "manage", MANAGE_TTL);
  const unsubscribe = (await links(ctx, subscriber.id)).unsubscribe;
  return send(
    ctx,
    subscriber,
    manageLinkEmail({ manage: fragmentLink(ctx.settings.manageUrl, "manage", token) }),
    { "List-Unsubscribe": `<${unsubscribe}>`, "List-Unsubscribe-Post": "List-Unsubscribe=One-Click" },
  );
}

async function replaceRules(ctx, subscriberId, rules) {
  const statements = [ctx.db.prepare("DELETE FROM rules WHERE subscriber_id = ?").bind(subscriberId)];
  for (const [position, rule] of rules.entries()) {
    statements.push(
      ctx.db
        .prepare("INSERT INTO rules (id, subscriber_id, position, fields, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)")
        .bind(await ruleId(subscriberId, rule), subscriberId, position, JSON.stringify(rule), ctx.now, ctx.now),
    );
  }
  await ctx.db.batch(statements);
}

async function activeCount(ctx) {
  const row = await ctx.db.prepare("SELECT COUNT(*) AS n FROM subscribers WHERE status = 'active'").first();
  return row ? Number(row.n) : 0;
}

async function preferences(ctx, subscriber) {
  const { results } = await ctx.db
    .prepare("SELECT id, fields FROM rules WHERE subscriber_id = ? ORDER BY position")
    .bind(subscriber.id)
    .all();
  return {
    status: subscriber.status,
    email_masked: maskEmail(subscriber.email),
    consent_version: subscriber.consent_version,
    verified_at: subscriber.verified_at ? new Date(subscriber.verified_at * 1000).toISOString() : null,
    max_rules: ctx.settings.maxRules,
    rules: results.map((row) => ({ id: row.id, ...JSON.parse(row.fields) })),
  };
}

function parseEmail(ctx, body) {
  const email = normalizeEmail(body.email);
  if (!validEmail(email)) throw new HttpError(400, "invalid_email");
  return email;
}

export async function subscribe(ctx, request) {
  const ip = clientIp(request);
  await enforce(ctx.db, ctx.settings.pepper, "subscribeIp", ip, ctx.now);
  const body = await readJson(request);
  const email = parseEmail(ctx, body);
  if (body.consent !== true) throw new HttpError(400, "consent_required");
  if (body.consent_version !== ctx.settings.consentVersion) throw new HttpError(400, "consent_outdated");
  const { rules, errors } = validateRules(body.rules, ctx.settings.maxRules);
  if (!rules) throw new HttpError(400, "invalid_rules", { fields: errors });
  await checkTurnstile(ctx.settings, body.turnstile_token, ip, ctx.fetch);
  if (ctx.settings.mode === "staging" && !ctx.settings.stagingAllowed.includes(email)) {
    throw new HttpError(403, "staging_recipient_not_allowed");
  }

  const hash = await emailHash(ctx.settings.pepper, email);
  // Per-address limit is silent so it cannot be used to probe addresses.
  if (!(await hit(ctx.db, ctx.settings.pepper, "subscribeEmail", hash, ctx.now)).allowed) return ACCEPTED();
  if (await ctx.db.prepare("SELECT 1 AS x FROM suppressions WHERE email_hash = ?").bind(hash).first()) return ACCEPTED();

  let subscriber = await ctx.db.prepare("SELECT * FROM subscribers WHERE email_hash = ?").bind(hash).first();
  let outcome;
  if (subscriber && subscriber.status === "active") {
    // Never change an active subscriber's rules from an unauthenticated form.
    outcome = await sendManageLink(ctx, subscriber);
  } else {
    if (!subscriber) {
      if ((await activeCount(ctx)) >= ctx.settings.maxActiveSubscribers) throw new HttpError(503, "signups_closed");
      await enforce(ctx.db, ctx.settings.pepper, "signupsGlobal", "all", ctx.now);
      subscriber = {
        id: randomId("s_"),
        route_id: randomId("route_", 12),
        email,
        email_hash: hash,
        status: "pending",
        consent_version: ctx.settings.consentVersion,
      };
      await ctx.db
        .prepare(
          `INSERT INTO subscribers (id, route_id, email, email_hash, status, consent_version, created_at, updated_at)
           VALUES (?, ?, ?, ?, 'pending', ?, ?, ?)`,
        )
        .bind(subscriber.id, subscriber.route_id, email, hash, subscriber.consent_version, ctx.now, ctx.now)
        .run();
    } else {
      await ctx.db
        .prepare("UPDATE subscribers SET consent_version = ?, updated_at = ? WHERE id = ?")
        .bind(ctx.settings.consentVersion, ctx.now, subscriber.id)
        .run();
    }
    await replaceRules(ctx, subscriber.id, rules);
    outcome = await sendVerification(ctx, subscriber);
  }
  if (outcome !== "sent") throw new HttpError(503, "email_unavailable");
  return ACCEPTED();
}

async function tokenRow(ctx, token, purpose) {
  if (!TOKEN_RE.test(String(token || ""))) return null;
  const row = await ctx.db
    .prepare(
      `SELECT t.token_hash, t.expires_at, t.used_at, s.*
       FROM tokens t JOIN subscribers s ON s.id = t.subscriber_id
       WHERE t.token_hash = ? AND t.purpose = ?`,
    )
    .bind(await tokenHash(ctx.settings.pepper, token), purpose)
    .first();
  if (!row || row.expires_at <= ctx.now || row.used_at) return null;
  return row;
}

export async function verify(ctx, request) {
  await enforce(ctx.db, ctx.settings.pepper, "verifyIp", clientIp(request), ctx.now);
  const body = await readJson(request);
  const row = await tokenRow(ctx, body.token, "verify");
  if (!row) throw new HttpError(400, "invalid_token");
  if (row.status !== "active" && (await activeCount(ctx)) >= ctx.settings.maxActiveSubscribers) {
    throw new HttpError(503, "signups_closed");
  }
  await ctx.db.batch([
    ctx.db.prepare("UPDATE tokens SET used_at = ? WHERE token_hash = ?").bind(ctx.now, row.token_hash),
    ctx.db
      .prepare("UPDATE subscribers SET status = 'active', verified_at = COALESCE(verified_at, ?), updated_at = ? WHERE id = ?")
      .bind(ctx.now, ctx.now, row.id),
    ctx.db.prepare("DELETE FROM tokens WHERE subscriber_id = ? AND purpose = 'verify' AND token_hash != ?").bind(row.id, row.token_hash),
  ]);
  const subscriber = await ctx.db.prepare("SELECT * FROM subscribers WHERE id = ?").bind(row.id).first();
  const manageToken = await issueToken(ctx, row.id, "manage", MANAGE_TTL);
  return json(200, { status: "active", manage_token: manageToken, preferences: await preferences(ctx, subscriber) });
}

export async function requestLink(ctx, request) {
  const ip = clientIp(request);
  await enforce(ctx.db, ctx.settings.pepper, "linkIp", ip, ctx.now);
  const body = await readJson(request);
  const email = parseEmail(ctx, body);
  await checkTurnstile(ctx.settings, body.turnstile_token, ip, ctx.fetch);
  const hash = await emailHash(ctx.settings.pepper, email);
  if (!(await hit(ctx.db, ctx.settings.pepper, "linkEmail", hash, ctx.now)).allowed) return ACCEPTED();
  const subscriber = await ctx.db
    .prepare("SELECT * FROM subscribers WHERE email_hash = ? AND status = 'active'")
    .bind(hash)
    .first();
  if (subscriber) await sendManageLink(ctx, subscriber); // outcome hidden on purpose
  return ACCEPTED();
}

async function manageSubscriber(ctx, request) {
  await enforce(ctx.db, ctx.settings.pepper, "manageIp", clientIp(request), ctx.now);
  const row = await tokenRow(ctx, bearerToken(request), "manage");
  if (!row || row.status !== "active") throw new HttpError(401, "invalid_token");
  return row;
}

export async function getPreferences(ctx, request) {
  return json(200, await preferences(ctx, await manageSubscriber(ctx, request)));
}

export async function putPreferences(ctx, request) {
  const subscriber = await manageSubscriber(ctx, request);
  const body = await readJson(request);
  const { rules, errors } = validateRules(body.rules, ctx.settings.maxRules);
  if (!rules) throw new HttpError(400, "invalid_rules", { fields: errors });
  await replaceRules(ctx, subscriber.id, rules);
  await ctx.db.prepare("UPDATE subscribers SET updated_at = ? WHERE id = ?").bind(ctx.now, subscriber.id).run();
  return json(200, await preferences(ctx, subscriber));
}

async function deleteSubscriber(ctx, subscriberId) {
  await ctx.db.batch([
    ctx.db.prepare("DELETE FROM deliveries WHERE subscriber_id = ?").bind(subscriberId),
    ctx.db.prepare("DELETE FROM tokens WHERE subscriber_id = ?").bind(subscriberId),
    ctx.db.prepare("DELETE FROM rules WHERE subscriber_id = ?").bind(subscriberId),
    ctx.db.prepare("DELETE FROM subscribers WHERE id = ?").bind(subscriberId),
  ]);
}

export async function deleteBySubscriberHash(ctx, hash) {
  const subscriber = await ctx.db.prepare("SELECT id FROM subscribers WHERE email_hash = ?").bind(hash).first();
  if (subscriber) await deleteSubscriber(ctx, subscriber.id);
}

export async function deleteMe(ctx, request) {
  const subscriber = await manageSubscriber(ctx, request);
  await deleteSubscriber(ctx, subscriber.id);
  return json(200, { status: "deleted" });
}

/**
 * POST /v1/unsubscribe. Accepts, in order:
 *  - ?token=<unsubscribe token> (RFC 8058 one-click: form body
 *    "List-Unsubscribe=One-Click"; also any JSON body),
 *  - a JSON body {"token": "<unsubscribe token>"},
 *  - Authorization: Bearer <manage token>.
 */
export async function unsubscribe(ctx, request) {
  await enforce(ctx.db, ctx.settings.pepper, "manageIp", clientIp(request), ctx.now);
  const url = new URL(request.url);
  let token = url.searchParams.get("token");
  if (!token && (request.headers.get("Content-Type") || "").startsWith("application/json")) {
    token = (await readJson(request)).token;
  } else {
    await readBody(request, 1024);
  }
  if (token) {
    const subscriberId = await readUnsubscribeToken(ctx.settings.pepper, token);
    if (!subscriberId) throw new HttpError(400, "invalid_token");
    await deleteSubscriber(ctx, subscriberId);
    return json(200, { status: "unsubscribed" });
  }
  if (request.headers.get("Authorization")) {
    const subscriber = await manageSubscriber(ctx, request);
    await deleteSubscriber(ctx, subscriber.id);
    return json(200, { status: "unsubscribed" });
  }
  throw new HttpError(400, "invalid_token");
}

/** GET /v1/unsubscribe: a confirm page only. Link scanners must not unsubscribe anyone. */
export async function unsubscribePage(ctx, request) {
  const token = new URL(request.url).searchParams.get("token") || "";
  const valid = Boolean(await readUnsubscribeToken(ctx.settings.pepper, token));
  const action = `${ctx.settings.apiUrl}/v1/unsubscribe?token=${encodeURIComponent(token)}`;
  const body = valid
    ? `<form method="post" action="${action.replace(/"/g, "&quot;")}"><input type="hidden" name="List-Unsubscribe" value="One-Click">
<p>Stop all SkateDeals alert emails to this address and delete your alert settings?</p>
<button type="submit" style="font-size:16px;padding:10px 16px">Unsubscribe</button></form>`
    : "<p>This unsubscribe link is not valid. If you already unsubscribed, nothing else is needed.</p>";
  return html(valid ? 200 : 400, `<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1">
<title>SkateDeals alerts</title></head><body style="font-family:Arial,sans-serif;max-width:480px;margin:40px auto;padding:0 16px">
<h1 style="font-size:20px">SkateDeals alerts</h1>${body}</body></html>`);
}

export { deleteSubscriber, links, maskEmail };
