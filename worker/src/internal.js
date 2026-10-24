// Internal API for the daily GitHub Actions job. Every request is signed with
// HMAC_SECRET (see crypto.internalSignature) and can be used once.
//
// GET  /v1/internal/routes      verified subscribers' rules, no addresses
// POST /v1/internal/deliveries  engine hits and the daily digest to email,
//                               idempotent per event

import { internalSignature, safeEqual } from "./crypto.js";
import { digestEmail, sendEmail, STORE_HOSTS } from "./email.js";
import { hit } from "./guards.js";
import { HttpError, json, MAX_INTERNAL_BODY, readBody } from "./http.js";
import { links } from "./subscribers.js";

const CLOCK_SKEW = 300;
const HEX64 = /^[0-9a-f]{64}$/;
const ROUTE = /^[A-Za-z0-9_-]{1,64}$/;
// The Python engine's reason labels (notification_engine.LABELS).
export const REASONS = new Set([
  "New watch match",
  "Maximum price reached",
  "Meaningful price drop",
  "Verified historical low",
  "Back in stock (verified)",
]);
const MAX_DELIVERIES = 500;
const MAX_HITS = 25;
const MAX_EVENTS_PER_HIT = 20;
// The general digest: one email section a day, at most this many listings.
// `total` says how many qualified before the cap.
export const MAX_DIGEST_ITEMS = 30;
export const DIGEST_KINDS = new Set(["new", "drop", "low"]);

export async function authenticate(ctx, request, rawBody) {
  const timestamp = request.headers.get("X-SkateDeals-Timestamp") || "";
  const nonce = request.headers.get("X-SkateDeals-Nonce") || "";
  const signature = request.headers.get("X-SkateDeals-Signature") || "";
  if (!/^\d{10}$/.test(timestamp) || Math.abs(ctx.now - Number(timestamp)) > CLOCK_SKEW) {
    throw new HttpError(401, "unauthorized");
  }
  if (!/^[A-Za-z0-9_-]{16,64}$/.test(nonce)) throw new HttpError(401, "unauthorized");
  const url = new URL(request.url);
  const expected = await internalSignature(
    ctx.settings.hmacSecret,
    request.method,
    url.pathname + url.search,
    timestamp,
    nonce,
    rawBody,
  );
  if (!safeEqual(expected, signature)) throw new HttpError(401, "unauthorized");
  const stored = await ctx.db
    .prepare("INSERT OR IGNORE INTO nonces (nonce, expires_at) VALUES (?, ?)")
    .bind(nonce, ctx.now + 2 * CLOCK_SKEW)
    .run();
  if (!stored.meta || stored.meta.changes !== 1) throw new HttpError(401, "unauthorized");
}

export async function routes(ctx, request) {
  await authenticate(ctx, request, "");
  const { results } = await ctx.db
    .prepare(
      `SELECT s.route_id, r.id AS rule_id, r.fields
       FROM subscribers s JOIN rules r ON r.subscriber_id = s.id
       WHERE s.status = 'active'
       ORDER BY s.route_id, r.position`,
    )
    .all();
  const byRoute = new Map();
  for (const row of results) {
    if (!byRoute.has(row.route_id)) byRoute.set(row.route_id, []);
    byRoute.get(row.route_id).push({ id: row.rule_id, ...JSON.parse(row.fields) });
  }
  return json(200, {
    version: 1,
    generated_at: new Date(ctx.now * 1000).toISOString(),
    routes: [...byRoute.entries()].map(([route_id, rules]) => ({ route_id, rules })),
  });
}

function shortText(value, limit) {
  if (typeof value !== "string") return null;
  const text = value.replace(/\s+/g, " ").trim();
  return text && text.length <= limit && !/[\u0000-\u001f\u007f]/.test(text) ? text : null;
}

function price(value) {
  if (value === undefined || value === null || value === "") return null;
  const number = Number(value);
  return Number.isFinite(number) && number >= 0 && number < 100000 ? number.toFixed(2) : undefined;
}

function cleanItem(item) {
  if (!item || typeof item !== "object") return null;
  const name = shortText(item.name, 200);
  const store = shortText(item.store, 40);
  const part = shortText(item.part, 20);
  let url;
  try {
    url = new URL(item.url);
  } catch {
    return null;
  }
  // Only links to the stores this site tracks: the mailer is never an open relay.
  if (url.protocol !== "https:" || !STORE_HOSTS.has(url.hostname) || url.username || url.password) return null;
  const priceNew = price(item.price_new);
  const priceOld = price(item.price_old);
  if (!name || !store || !part || !priceNew || priceOld === undefined) return null;
  return { name, store, part, url: url.href, price_new: priceNew, ...(priceOld ? { price_old: priceOld } : {}) };
}

function cleanHit(input) {
  if (!input || typeof input !== "object") return null;
  const eventIds = input.event_ids;
  if (!Array.isArray(eventIds) || eventIds.length < 1 || eventIds.length > MAX_EVENTS_PER_HIT) return null;
  if (!eventIds.every((id) => typeof id === "string" && HEX64.test(id))) return null;
  const reasons = input.reasons;
  if (!Array.isArray(reasons) || reasons.length < 1 || !reasons.every((reason) => REASONS.has(reason))) return null;
  const note = input.note === undefined || input.note === "" ? "" : shortText(input.note, 160);
  if (note === null) return null;
  const item = cleanItem(input.item);
  if (!item) return null;
  return { event_ids: [...new Set(eventIds)], reasons: [...new Set(reasons)], note, item };
}

/** The digest section: one event id for the whole section, so it goes out once. */
function cleanDigest(input) {
  if (!input || typeof input !== "object" || !HEX64.test(input.event_id || "")) return null;
  const items = input.items;
  if (!Array.isArray(items) || items.length < 1 || items.length > MAX_DIGEST_ITEMS) return null;
  if (!Number.isInteger(input.total) || input.total < items.length || input.total > 100000) return null;
  const clean = [];
  for (const entry of items) {
    if (!entry || !DIGEST_KINDS.has(entry.kind)) return null;
    const item = cleanItem(entry.item);
    const before = price(entry.price_before);
    if (!item || before === undefined || (entry.kind === "drop" && !before)) return null;
    clean.push({ kind: entry.kind, item, ...(before ? { price_before: before } : {}) });
  }
  return { event_id: input.event_id, total: input.total, items: clean };
}

function parseDeliveries(raw) {
  let body;
  try {
    body = JSON.parse(raw);
  } catch {
    throw new HttpError(400, "invalid_json");
  }
  if (!body || body.version !== 1 || !Array.isArray(body.deliveries) || body.deliveries.length > MAX_DELIVERIES) {
    throw new HttpError(400, "invalid_request");
  }
  const seen = new Set();
  return body.deliveries.map((delivery) => {
    if (!delivery || !ROUTE.test(delivery.route_id || "") || !HEX64.test(delivery.delivery_id || "")) {
      throw new HttpError(400, "invalid_request");
    }
    if (seen.has(delivery.delivery_id)) throw new HttpError(400, "invalid_request");
    seen.add(delivery.delivery_id);
    const rawHits = delivery.hits === undefined ? [] : delivery.hits;
    if (!Array.isArray(rawHits) || rawHits.length > MAX_HITS) throw new HttpError(400, "invalid_request");
    const hits = rawHits.map(cleanHit);
    if (hits.includes(null)) throw new HttpError(400, "invalid_request");
    const digest = delivery.digest === undefined ? null : cleanDigest(delivery.digest);
    if (delivery.digest !== undefined && !digest) throw new HttpError(400, "invalid_request");
    if (hits.length === 0 && !digest) throw new HttpError(400, "invalid_request");
    return { route_id: delivery.route_id, delivery_id: delivery.delivery_id, hits, digest };
  });
}

/**
 * Result statuses, mapped by alerts_delivery.py onto the engine journal:
 *   sent       emailed now; mark events delivered
 *   duplicate  every event was already emailed; mark delivered
 *   inactive   no verified subscriber for this route; drop the events
 *   deferred   daily email cap reached; keep events pending
 *   failed     provider refused before accepting; keep pending (safe retry)
 *   uncertain  provider may have accepted; hold, never resend automatically
 */
async function deliverOne(ctx, delivery) {
  const subscriber = await ctx.db
    .prepare("SELECT * FROM subscribers WHERE route_id = ? AND status = 'active'")
    .bind(delivery.route_id)
    .first();
  if (!subscriber) return "inactive";

  const digestIds = delivery.digest ? [delivery.digest.event_id] : [];
  const eventIds = [...new Set([...delivery.hits.flatMap((hit) => hit.event_ids), ...digestIds])];
  const placeholders = eventIds.map(() => "?").join(", ");
  const { results } = await ctx.db
    .prepare(`SELECT event_id, status FROM deliveries WHERE subscriber_id = ? AND event_id IN (${placeholders})`)
    .bind(subscriber.id, ...eventIds)
    .all();
  if (results.some((row) => row.status !== "sent")) return "uncertain";
  const done = new Set(results.map((row) => row.event_id));
  const fresh = delivery.hits.filter((hit) => hit.event_ids.some((id) => !done.has(id)));
  const digest = delivery.digest && !done.has(delivery.digest.event_id) ? delivery.digest : null;
  if (fresh.length === 0 && !digest) return "duplicate";

  const cap = await hit(ctx.db, ctx.settings.pepper, "subscriberDaily", subscriber.id, ctx.now, ctx.settings.dailyEmailsPerSubscriber);
  if (!cap.allowed) return "deferred";

  const pending = [...new Set([...fresh.flatMap((hit) => hit.event_ids), ...(digest ? [digest.event_id] : [])])].filter(
    (id) => !done.has(id),
  );
  await ctx.db.batch(
    pending.map((id) =>
      ctx.db
        .prepare(
          "INSERT INTO deliveries (subscriber_id, event_id, delivery_id, status, created_at, updated_at) VALUES (?, ?, ?, 'sending', ?, ?)",
        )
        .bind(subscriber.id, id, delivery.delivery_id, ctx.now, ctx.now),
    ),
  );

  const urls = await links(ctx, subscriber.id);
  const message = digestEmail(fresh, urls, digest);
  const outcome = await sendEmail(
    ctx.env,
    ctx.settings,
    {
      to: subscriber.email,
      idempotencyKey: `skatedeals-${subscriber.id}-${delivery.delivery_id}`,
      headers: {
        "List-Unsubscribe": `<${urls.unsubscribe}>`,
        "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
      },
      ...message,
    },
    ctx.fetch,
  );
  const mark = (status) =>
    ctx.db.batch(
      pending.map((id) =>
        status === null
          ? ctx.db.prepare("DELETE FROM deliveries WHERE subscriber_id = ? AND event_id = ?").bind(subscriber.id, id)
          : ctx.db
              .prepare("UPDATE deliveries SET status = ?, updated_at = ? WHERE subscriber_id = ? AND event_id = ?")
              .bind(status, ctx.now, subscriber.id, id),
      ),
    );
  if (outcome === "sent") {
    await mark("sent");
    return "sent";
  }
  if (outcome === "failed") {
    await mark(null);
    return "failed";
  }
  await mark("uncertain");
  return "uncertain";
}

export async function deliveries(ctx, request) {
  const raw = await readBody(request, MAX_INTERNAL_BODY);
  await authenticate(ctx, request, raw);
  if (!(request.headers.get("Content-Type") || "").startsWith("application/json")) {
    throw new HttpError(415, "json_required");
  }
  const parsed = parseDeliveries(raw);
  const results = [];
  for (const delivery of parsed) {
    let status;
    try {
      status = await deliverOne(ctx, delivery);
    } catch {
      status = "uncertain";
    }
    results.push({ route_id: delivery.route_id, delivery_id: delivery.delivery_id, status });
  }
  return json(200, { version: 1, results });
}
