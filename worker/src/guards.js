// Rate limits and Turnstile. Both fail closed: a check that cannot run
// refuses the request.

import { MOCK_TURNSTILE_PASS } from "./config.js";
import { hmacHex } from "./crypto.js";
import { HttpError } from "./http.js";

export const LIMITS = {
  subscribeIp: { limit: 5, window: 3600 },
  subscribeEmail: { limit: 3, window: 86400 },
  linkIp: { limit: 10, window: 3600 },
  linkEmail: { limit: 3, window: 86400 },
  verifyIp: { limit: 30, window: 3600 },
  manageIp: { limit: 60, window: 3600 },
  signupsGlobal: { limit: 200, window: 86400 },
  // Emails per subscriber per day; the limit comes from settings.
  subscriberDaily: { limit: 3, window: 86400 },
};

/**
 * Counts one hit in a fixed window. Returns { allowed, retryAfter }.
 * `key` is hashed with the pepper, so buckets never contain raw IPs or
 * addresses.
 */
export async function hit(db, pepper, name, key, now = Math.floor(Date.now() / 1000), limitOverride = null) {
  const { window } = LIMITS[name];
  const limit = limitOverride || LIMITS[name].limit;
  const bucket = `${name}:${await hmacHex(pepper, `rate:${name}:${key}`)}`;
  const start = now - (now % window);
  await db
    .prepare(
      `INSERT INTO rate_limits (bucket, count, window_start) VALUES (?, 1, ?)
       ON CONFLICT (bucket) DO UPDATE SET
         count = CASE WHEN rate_limits.window_start = excluded.window_start THEN rate_limits.count + 1 ELSE 1 END,
         window_start = excluded.window_start`,
    )
    .bind(bucket, start)
    .run();
  const row = await db.prepare("SELECT count FROM rate_limits WHERE bucket = ?").bind(bucket).first();
  const count = row ? row.count : limit + 1;
  return { allowed: count <= limit, retryAfter: start + window - now };
}

export async function enforce(db, pepper, name, key, now) {
  const result = await hit(db, pepper, name, key, now);
  if (!result.allowed) throw new HttpError(429, "rate_limited", { retryAfter: result.retryAfter });
}

export async function checkTurnstile(settings, token, ip, fetcher = fetch) {
  if (typeof token !== "string" || token.length < 1 || token.length > 2048) {
    throw new HttpError(400, "captcha_failed");
  }
  if (settings.mode === "mock") {
    if (token !== MOCK_TURNSTILE_PASS) throw new HttpError(400, "captcha_failed");
    return;
  }
  let outcome = null;
  try {
    const response = await fetcher("https://challenges.cloudflare.com/turnstile/v0/siteverify", {
      method: "POST",
      body: new URLSearchParams({ secret: settings.turnstileSecret, response: token, remoteip: ip }),
    });
    outcome = response.ok ? await response.json() : null;
  } catch {
    outcome = null;
  }
  if (!outcome || outcome.success !== true) throw new HttpError(400, "captcha_failed");
}
