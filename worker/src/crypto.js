// Tokens, hashes, and the signature on internal requests. Web Crypto only, so
// the same code runs in the Worker and in Node tests.

const encoder = new TextEncoder();

export function base64url(bytes) {
  let binary = "";
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

export function hex(bytes) {
  return [...new Uint8Array(bytes)].map((byte) => byte.toString(16).padStart(2, "0")).join("");
}

export function randomToken(bytes = 32) {
  const buffer = new Uint8Array(bytes);
  crypto.getRandomValues(buffer);
  return base64url(buffer);
}

export function randomId(prefix, bytes = 12) {
  const buffer = new Uint8Array(bytes);
  crypto.getRandomValues(buffer);
  return prefix + hex(buffer);
}

export async function sha256Hex(data) {
  const bytes = typeof data === "string" ? encoder.encode(data) : data;
  return hex(await crypto.subtle.digest("SHA-256", bytes));
}

async function hmacKey(secretBytes) {
  return crypto.subtle.importKey("raw", secretBytes, { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
}

export async function hmacHex(secret, message) {
  const key = await hmacKey(typeof secret === "string" ? encoder.encode(secret) : secret);
  return hex(await crypto.subtle.sign("HMAC", key, encoder.encode(message)));
}

export async function hmacBase64(secretBytes, message) {
  const key = await hmacKey(secretBytes);
  const signature = new Uint8Array(await crypto.subtle.sign("HMAC", key, encoder.encode(message)));
  let binary = "";
  for (const byte of signature) binary += String.fromCharCode(byte);
  return btoa(binary);
}

/** Constant-time comparison for equal-purpose strings. */
export function safeEqual(left, right) {
  const a = encoder.encode(String(left));
  const b = encoder.encode(String(right));
  let diff = a.length ^ b.length;
  for (let index = 0; index < Math.max(a.length, b.length); index += 1) {
    diff |= (a[index] || 0) ^ (b[index] || 0);
  }
  return diff === 0;
}

export function normalizeEmail(value) {
  return String(value || "").trim().toLowerCase();
}

export async function emailHash(pepper, email) {
  return hmacHex(pepper, `email:${normalizeEmail(email)}`);
}

export async function tokenHash(pepper, token) {
  return hmacHex(pepper, `token:${token}`);
}

/**
 * Unsubscribe links must keep working in every email ever sent, without a
 * stored row per email. The token is the subscriber id plus an HMAC of it;
 * it stops working when the subscriber row is deleted.
 */
export async function unsubscribeToken(pepper, subscriberId) {
  return `${subscriberId}.${(await hmacHex(pepper, `unsubscribe:${subscriberId}`)).slice(0, 40)}`;
}

export async function readUnsubscribeToken(pepper, token) {
  const match = /^(s_[0-9a-f]{24})\.([0-9a-f]{40})$/.exec(String(token || ""));
  if (!match) return null;
  const expected = await unsubscribeToken(pepper, match[1]);
  return safeEqual(expected, token) ? match[1] : null;
}

/**
 * Canonical string for internal requests, shared with alerts_delivery.py:
 *   v1\nMETHOD\nPATH_AND_QUERY\nTIMESTAMP\nNONCE\nSHA256_HEX(BODY)
 */
export async function internalSignature(secret, method, pathAndQuery, timestamp, nonce, body) {
  const canonical = ["v1", method.toUpperCase(), pathAndQuery, String(timestamp), nonce, await sha256Hex(body || "")].join("\n");
  return `v1=${await hmacHex(secret, canonical)}`;
}
