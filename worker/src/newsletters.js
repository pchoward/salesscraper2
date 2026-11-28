// Store newsletters -> promo codes (owner, 2026-11-27).
//
// Cloudflare Email Routing sends mail for the deals inbox to this Worker's
// `email` handler. A message is kept only when it is addressed to
// NEWSLETTER_INBOX, its From domain is a known store's (SENDERS), and
// Cloudflare's own Authentication-Results says DMARC passed for that domain,
// so a forged "From: jensonusa.com" is dropped. Everything else is dropped
// silently. The store name comes from SENDERS, never from the mail.
//
// The promo check (promos.py, GitHub Actions) reads stored mail with a signed
// GET /v1/internal/newsletters and finds codes with the same rules it uses on
// store pages. Mail text is data, never instructions.

import { internalSignature, safeEqual } from "./crypto.js";
import { HttpError, json } from "./http.js";

// Sender domain (or a subdomain of it) -> store name.
export const SENDERS = {
  "jensonusa.com": "Jenson USA",
  "danscomp.com": "Dan's Comp",
  "competitivecyclist.com": "Competitive Cyclist",
};
export const MAX_RAW = 1_000_000; // bytes; bigger mail is dropped
export const MAX_TEXT = 20_000; // characters of text kept per mail
const MAX_LIST = 200;
export const KEEP_SECONDS = 45 * 86400;
const CLOCK_SKEW = 300;

export function storeFor(domain, senders = SENDERS) {
  const host = String(domain || "").toLowerCase().replace(/\.$/, "");
  for (const [known, store] of Object.entries(senders)) {
    if (host === known || host.endsWith("." + known)) return { domain: known, store };
  }
  return null;
}

/** The domain of the first address in a From header. */
export function fromDomain(header) {
  const match = String(header || "").match(/<?[^<>\s@]+@([A-Za-z0-9.-]+)>?\s*$/) ||
    String(header || "").match(/@([A-Za-z0-9.-]+)/);
  return match ? match[1].toLowerCase() : "";
}

/** True when Authentication-Results shows DMARC passing for `domain`. */
export function dmarcPassed(results, domain) {
  for (const header of [].concat(results || [])) {
    const text = String(header).toLowerCase();
    const found = text.match(/dmarc=pass[^;]*?header\.from=([a-z0-9.-]+)/);
    if (found && (found[1] === domain || found[1].endsWith("." + domain))) return true;
  }
  return false;
}

function headerBlock(raw) {
  const split = raw.search(/\r?\n\r?\n/);
  const head = split < 0 ? raw : raw.slice(0, split);
  const body = split < 0 ? "" : raw.slice(split).replace(/^\r?\n\r?\n/, "");
  const headers = {};
  for (const line of head.replace(/\r?\n[ \t]+/g, " ").split(/\r?\n/)) {
    const colon = line.indexOf(":");
    if (colon > 0) {
      const name = line.slice(0, colon).trim().toLowerCase();
      (headers[name] = headers[name] || []).push(line.slice(colon + 1).trim());
    }
  }
  return { headers, body };
}

function decodeQuotedPrintable(text) {
  const bytes = [];
  const source = text.replace(/=\r?\n/g, "");
  for (let i = 0; i < source.length; i++) {
    if (source[i] === "=" && /^[0-9A-Fa-f]{2}$/.test(source.slice(i + 1, i + 3))) {
      bytes.push(parseInt(source.slice(i + 1, i + 3), 16));
      i += 2;
    } else {
      bytes.push(source.charCodeAt(i) & 0xff);
    }
  }
  return new TextDecoder().decode(new Uint8Array(bytes));
}

function decodeBase64(text) {
  try {
    const binary = atob(text.replace(/[^A-Za-z0-9+/=]/g, ""));
    return new TextDecoder().decode(Uint8Array.from(binary, (c) => c.charCodeAt(0)));
  } catch {
    return "";
  }
}

export function htmlToText(html) {
  return String(html)
    .replace(/<(script|style|head)[\s\S]*?<\/\1>/gi, " ")
    .replace(/<br\s*\/?>|<\/(p|div|tr|td|li|h\d)>/gi, "\n")
    .replace(/<[^>]+>/g, " ")
    .replace(/&nbsp;/gi, " ").replace(/&amp;/gi, "&").replace(/&lt;/gi, "<").replace(/&gt;/gi, ">")
    .replace(/&quot;/gi, '"').replace(/&#39;|&apos;/gi, "'").replace(/&#(\d+);/g, (_, n) => String.fromCharCode(Number(n)))
    .replace(/[ \t ]+/g, " ")
    .replace(/\s*\n\s*/g, "\n")
    .trim();
}

/** Plain text and subject of a raw MIME message: text/plain parts, or HTML ones as text. */
export function mailText(raw) {
  const { headers, body } = headerBlock(raw);
  const subject = decodeWords((headers.subject || [""])[0]);
  const plain = [];
  const html = [];
  (function walk(partHeaders, partBody, depth) {
    if (depth > 5) return;
    const type = ((partHeaders["content-type"] || ["text/plain"])[0]).toLowerCase();
    const boundary = (partHeaders["content-type"] || [""])[0].match(/boundary="?([^";]+)"?/i);
    if (type.startsWith("multipart/") && boundary) {
      for (const chunk of partBody.split("--" + boundary[1]).slice(1)) {
        if (chunk.startsWith("--")) break;
        const part = headerBlock(chunk.replace(/^\r?\n/, ""));
        walk(part.headers, part.body, depth + 1);
      }
      return;
    }
    const encoding = ((partHeaders["content-transfer-encoding"] || [""])[0]).toLowerCase();
    let text = partBody;
    if (encoding === "base64") text = decodeBase64(text);
    else if (encoding === "quoted-printable") text = decodeQuotedPrintable(text);
    if (type.startsWith("text/plain")) plain.push(text);
    else if (type.startsWith("text/html")) html.push(text);
  })(headers, body, 0);
  const text = plain.length ? plain.join("\n") : htmlToText(html.join("\n"));
  return { subject: subject.slice(0, 300), text: text.replace(/\r/g, "").slice(0, MAX_TEXT), headers };
}

function decodeWords(value) {
  return String(value).replace(/=\?[^?]+\?([BbQq])\?([^?]*)\?=/g, (_, kind, data) =>
    kind.toUpperCase() === "B" ? decodeBase64(data) : decodeQuotedPrintable(data.replace(/_/g, " ")));
}

async function sha256(text) {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
  return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

/** True when this Worker is set up to take newsletters. */
export function newslettersEnabled(env) {
  return Boolean(env && env.DB && env.DB.prepare && String(env.NEWSLETTER_INBOX || "").includes("@") &&
    String(env.HMAC_SECRET || "").length >= 32);
}

/**
 * The Worker's `email` handler. Returns what happened ("stored", "duplicate"
 * or a reason it was dropped), for tests and logs. Never throws.
 */
export async function receiveEmail(message, env, now = Math.floor(Date.now() / 1000)) {
  try {
    if (!newslettersEnabled(env)) return "disabled";
    if (String(message.to || "").toLowerCase() !== String(env.NEWSLETTER_INBOX).toLowerCase()) return "not_inbox";
    if (Number(message.rawSize || 0) > MAX_RAW) return "too_big";
    const raw = await new Response(message.raw).text();
    if (raw.length > MAX_RAW) return "too_big";
    const mail = mailText(raw);
    const domain = fromDomain((mail.headers.from || [""])[0]);
    const sender = storeFor(domain);
    if (!sender) return "unknown_sender";
    const results = (message.headers && message.headers.get && message.headers.get("Authentication-Results")) ||
      mail.headers["authentication-results"] || [];
    if (!dmarcPassed(results, sender.domain)) return "not_authenticated";
    const key = await sha256((mail.headers["message-id"] || [raw])[0]);
    const stored = await env.DB
      .prepare("INSERT OR IGNORE INTO newsletters (message_key, store, received_at, subject, body) VALUES (?, ?, ?, ?, ?)")
      .bind(key, sender.store, now, mail.subject, mail.text)
      .run();
    return stored.meta && stored.meta.changes === 1 ? "stored" : "duplicate";
  } catch (error) {
    console.log("newsletter dropped:", error && error.name);
    return "error";
  }
}

/** Signed GET /v1/internal/newsletters?since=<unix seconds>: stored mail, newest first. */
export async function listNewsletters(request, env, now = Math.floor(Date.now() / 1000)) {
  if (!newslettersEnabled(env)) return json(503, { error: "service_unavailable" });
  if (request.method !== "GET") return json(405, { error: "method_not_allowed" });
  try {
    const timestamp = request.headers.get("X-SkateDeals-Timestamp") || "";
    const nonce = request.headers.get("X-SkateDeals-Nonce") || "";
    const signature = request.headers.get("X-SkateDeals-Signature") || "";
    if (!/^\d{10}$/.test(timestamp) || Math.abs(now - Number(timestamp)) > CLOCK_SKEW) throw new HttpError(401, "unauthorized");
    if (!/^[A-Za-z0-9_-]{16,64}$/.test(nonce)) throw new HttpError(401, "unauthorized");
    const url = new URL(request.url);
    const expected = await internalSignature(env.HMAC_SECRET, "GET", url.pathname + url.search, timestamp, nonce, "");
    if (!safeEqual(expected, signature)) throw new HttpError(401, "unauthorized");
    const used = await env.DB.prepare("INSERT OR IGNORE INTO nonces (nonce, expires_at) VALUES (?, ?)")
      .bind(nonce, now + 2 * CLOCK_SKEW).run();
    if (!used.meta || used.meta.changes !== 1) throw new HttpError(401, "unauthorized");
    const since = Math.max(0, Number(url.searchParams.get("since") || 0) | 0);
    const { results } = await env.DB
      .prepare("SELECT store, received_at, subject, body FROM newsletters WHERE received_at >= ? ORDER BY received_at DESC LIMIT ?")
      .bind(since, MAX_LIST).all();
    return json(200, {
      newsletters: results.map((row) => ({
        store: row.store, received_at: row.received_at, subject: row.subject, text: row.body,
      })),
    });
  } catch (error) {
    if (error instanceof HttpError) return json(error.status, { error: error.code || "unauthorized" });
    return json(500, { error: "internal_error" });
  }
}

/** Daily: forget mail older than KEEP_SECONDS. */
export async function pruneNewsletters(db, now = Math.floor(Date.now() / 1000)) {
  const result = await db.prepare("DELETE FROM newsletters WHERE received_at < ?").bind(now - KEEP_SECONDS).run();
  await db.prepare("DELETE FROM nonces WHERE expires_at < ?").bind(now).run();
  return result.meta ? result.meta.changes : 0;
}
