// Worker settings, checked on every request. Anything missing or unsafe makes
// the service refuse work (fail closed) instead of guessing.
//
// MODE is required and is one of:
//   production  real email from a verified domain; Turnstile required
//   staging     real email, may use Resend's onboarding@resend.dev test
//               sender, and only to STAGING_ALLOWED_EMAILS
//   mock        never contacts Resend or Turnstile; mail goes to the outbox
//               table and GET /v1/mock/outbox; for local UI work only

export const API_VERSION = "1";
export const RESEND_TEST_SENDER_DOMAIN = "resend.dev";
export const MOCK_TURNSTILE_PASS = "mock-turnstile-pass";

const MODES = new Set(["production", "staging", "mock"]);
const MIN_SECRET_LENGTH = 32;

function text(value) {
  return typeof value === "string" ? value.trim() : "";
}

function senderAddress(from) {
  const match = /<([^<>]+)>\s*$/.exec(from);
  return (match ? match[1] : from).trim().toLowerCase();
}

function httpsUrl(value, allowLocalHttp = false) {
  try {
    const url = new URL(value);
    if (url.protocol === "https:") return url;
    const local = url.hostname === "localhost" || url.hostname === "127.0.0.1";
    return allowLocalHttp && local && url.protocol === "http:" ? url : null;
  } catch {
    return null;
  }
}

function positiveInt(value, fallback, allowZero = false) {
  const number = Number.parseInt(text(value), 10);
  return Number.isFinite(number) && (number > 0 || (allowZero && number === 0)) ? number : fallback;
}

/**
 * Returns { ok, problems, settings }. `problems` lists setting names only,
 * never values, so it is safe to log or return from /v1/health.
 */
export function loadConfig(env) {
  const problems = [];
  const mode = text(env.MODE);
  if (!MODES.has(mode)) problems.push("MODE");
  if (!env.DB || typeof env.DB.prepare !== "function") problems.push("DB");

  for (const name of ["HMAC_SECRET", "TOKEN_PEPPER"]) {
    if (text(env[name]).length < MIN_SECRET_LENGTH) problems.push(name);
  }
  const publicOrigin = text(env.PUBLIC_ORIGIN);
  const origin = httpsUrl(publicOrigin);
  if (!origin || origin.origin !== publicOrigin) problems.push("PUBLIC_ORIGIN");
  // Only mock mode may point links at a local http page or API.
  const manageUrl = httpsUrl(text(env.MANAGE_PAGE_URL), mode === "mock");
  if (!manageUrl) problems.push("MANAGE_PAGE_URL");
  const apiUrl = httpsUrl(text(env.PUBLIC_API_URL), mode === "mock");
  if (!apiUrl) problems.push("PUBLIC_API_URL");
  const consentVersion = text(env.CONSENT_VERSION);
  if (!/^[A-Za-z0-9._-]{1,32}$/.test(consentVersion)) problems.push("CONSENT_VERSION");

  const from = text(env.EMAIL_FROM);
  const sender = senderAddress(from);
  const senderDomain = sender.split("@")[1] || "";
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(sender)) problems.push("EMAIL_FROM");

  const stagingAllowed = text(env.STAGING_ALLOWED_EMAILS)
    .split(",")
    .map((value) => value.trim().toLowerCase())
    .filter(Boolean);

  if (mode === "production" || mode === "staging") {
    if (!text(env.RESEND_API_KEY)) problems.push("RESEND_API_KEY");
    if (!text(env.TURNSTILE_SECRET)) problems.push("TURNSTILE_SECRET");
  }
  if (mode === "production" && senderDomain === RESEND_TEST_SENDER_DOMAIN) {
    // Resend's onboarding sender only reaches the account owner. Public
    // subscribers need a verified sending domain.
    problems.push("EMAIL_FROM");
  }
  if (mode === "staging" && stagingAllowed.length === 0) problems.push("STAGING_ALLOWED_EMAILS");

  const unique = [...new Set(problems)];
  return {
    ok: unique.length === 0,
    problems: unique,
    settings: {
      mode,
      publicOrigin,
      manageUrl: manageUrl ? manageUrl.href : "",
      apiUrl: apiUrl ? apiUrl.href.replace(/\/$/, "") : "",
      consentVersion,
      from,
      hmacSecret: text(env.HMAC_SECRET),
      pepper: text(env.TOKEN_PEPPER),
      resendApiKey: text(env.RESEND_API_KEY),
      resendWebhookSecret: text(env.RESEND_WEBHOOK_SECRET),
      turnstileSecret: text(env.TURNSTILE_SECRET),
      stagingAllowed,
      // "0" closes signups (a rollback switch).
      maxActiveSubscribers: positiveInt(env.MAX_ACTIVE_SUBSCRIBERS, 200, true),
      maxRules: Math.min(positiveInt(env.MAX_RULES_PER_SUBSCRIBER, 10), 25),
      dailyEmailsPerSubscriber: Math.min(positiveInt(env.DAILY_EMAILS_PER_SUBSCRIBER, 3), 10),
    },
  };
}
