// Resend delivery webhooks (signed with Svix). A permanent bounce or a spam
// complaint deletes the subscriber and keeps only a suppression hash.
// Disabled (503) until RESEND_WEBHOOK_SECRET is set.

import { emailHash, hmacBase64, safeEqual } from "./crypto.js";
import { HttpError, json, readBody } from "./http.js";
import { deleteBySubscriberHash } from "./subscribers.js";

const TOLERANCE = 300;

function secretBytes(secret) {
  const raw = secret.startsWith("whsec_") ? secret.slice(6) : secret;
  try {
    return Uint8Array.from(atob(raw), (char) => char.charCodeAt(0));
  } catch {
    return null;
  }
}

export async function verifySvix(secret, headers, body, now) {
  const id = headers.get("svix-id") || "";
  const timestamp = headers.get("svix-timestamp") || "";
  const signatures = (headers.get("svix-signature") || "").split(" ");
  const key = secretBytes(secret);
  if (!key || !id || !/^\d{10}$/.test(timestamp) || Math.abs(now - Number(timestamp)) > TOLERANCE) return false;
  const expected = await hmacBase64(key, `${id}.${timestamp}.${body}`);
  return signatures.some((entry) => {
    const [version, value] = entry.split(",");
    return version === "v1" && value && safeEqual(value, expected);
  });
}

export async function resendWebhook(ctx, request) {
  if (!ctx.settings.resendWebhookSecret) throw new HttpError(503, "webhook_disabled");
  const raw = await readBody(request, 64 * 1024);
  if (!(await verifySvix(ctx.settings.resendWebhookSecret, request.headers, raw, ctx.now))) {
    throw new HttpError(401, "unauthorized");
  }
  let event;
  try {
    event = JSON.parse(raw);
  } catch {
    throw new HttpError(400, "invalid_json");
  }
  const type = event && event.type;
  const data = (event && event.data) || {};
  let reason = null;
  if (type === "email.complained") reason = "complaint";
  // A temporary bounce (full mailbox) is not a reason to drop someone.
  if (type === "email.bounced" && !(data.bounce && /transient|temporary/i.test(String(data.bounce.type || "")))) {
    reason = "bounce";
  }
  if (reason) {
    const recipients = Array.isArray(data.to) ? data.to : [data.to];
    for (const address of recipients.filter((value) => typeof value === "string").slice(0, 50)) {
      const hash = await emailHash(ctx.settings.pepper, address);
      await ctx.db
        .prepare("INSERT OR IGNORE INTO suppressions (email_hash, reason, created_at) VALUES (?, ?, ?)")
        .bind(hash, reason, ctx.now)
        .run();
      await deleteBySubscriberHash(ctx, hash);
    }
  }
  return json(200, { ok: true });
}
