// SkateDeals alerts Worker. See docs/alerts-api.md for the API contract and
// docs/alerts-backend.md for setup. Nothing here runs until the owner deploys
// it with their own Cloudflare account and secrets.

import { API_VERSION, loadConfig } from "./config.js";
import { corsHeaders, errorResponse, HttpError, json, withHeaders } from "./http.js";
import { deliveries, routes } from "./internal.js";
import { runMaintenance } from "./maintenance.js";
import {
  deleteMe,
  getPreferences,
  putPreferences,
  requestLink,
  subscribe,
  unsubscribe,
  unsubscribePage,
  verify,
} from "./subscribers.js";
import { resendWebhook } from "./webhooks.js";

const PUBLIC = {
  "/v1/subscribe": { POST: subscribe },
  "/v1/verify": { POST: verify },
  "/v1/link": { POST: requestLink },
  "/v1/preferences": { GET: getPreferences, PUT: putPreferences },
  "/v1/subscriber": { DELETE: deleteMe },
  "/v1/unsubscribe": { POST: unsubscribe, GET: unsubscribePage },
};
const INTERNAL = {
  "/v1/internal/routes": { GET: routes },
  "/v1/internal/deliveries": { POST: deliveries },
  "/v1/webhooks/resend": { POST: resendWebhook },
};

async function mockOutbox(ctx, request) {
  if (request.method === "DELETE") {
    await ctx.db.prepare("DELETE FROM outbox").run();
    return json(200, { messages: [] });
  }
  const { results } = await ctx.db
    .prepare("SELECT id, to_addr, subject, text_body, headers, created_at FROM outbox ORDER BY id DESC LIMIT 20")
    .all();
  return json(200, {
    messages: results.map((row) => ({
      id: row.id,
      to: row.to_addr,
      subject: row.subject,
      text: row.text_body,
      headers: JSON.parse(row.headers),
      links: row.text_body.match(/https?:\/\/\S+/g) || [],
      created_at: new Date(row.created_at * 1000).toISOString(),
    })),
  });
}

/**
 * CORS headers from settings that passed validation only: a rejected
 * PUBLIC_ORIGIN is never trusted, and localhost is allowed only when the
 * mode really is mock. Used even while the service is misconfigured, so the
 * page can read the 503 and say alerts are unavailable.
 */
function trustedCors(request, config) {
  const settings = {
    ...config.settings,
    publicOrigin: config.problems.includes("PUBLIC_ORIGIN") ? "" : config.settings.publicOrigin,
    mode: config.problems.includes("MODE") ? "" : config.settings.mode,
  };
  return corsHeaders(request, settings);
}

function preflight(cors) {
  return cors["Access-Control-Allow-Origin"]
    ? new Response(null, { status: 204, headers: cors })
    : json(403, { error: "origin_not_allowed" });
}

function health(request, config) {
  const cors = trustedCors(request, config);
  if (request.method === "OPTIONS") return preflight(cors);
  if (request.method !== "GET") return withHeaders(json(405, { error: "method_not_allowed" }), cors);
  const response = config.ok
    ? json(200, { ok: true, api_version: API_VERSION, mode: config.settings.mode })
    : json(503, { ok: false, problems: config.problems });
  return withHeaders(response, cors);
}

/**
 * Handles one request. `deps` lets tests replace outbound fetch (Resend and
 * Turnstile) and the clock; production uses the defaults.
 */
export async function handle(request, env, deps = {}) {
  const url = new URL(request.url);
  const config = loadConfig(env);
  if (url.pathname === "/v1/health") return health(request, config);
  // Fail closed: no endpoint does anything while settings are incomplete.
  if (!config.ok) {
    const browserFacing = Boolean(PUBLIC[url.pathname]) || url.pathname === "/v1/mock/outbox";
    const cors = browserFacing ? trustedCors(request, config) : {};
    if (browserFacing && request.method === "OPTIONS") return preflight(cors);
    return withHeaders(json(503, { error: "service_unavailable" }), cors);
  }

  const settings = config.settings;
  const ctx = {
    env,
    db: env.DB,
    settings,
    now: deps.now ? deps.now() : Math.floor(Date.now() / 1000),
    fetch: deps.fetch || fetch,
  };

  const publicRoute = PUBLIC[url.pathname];
  const isMock = settings.mode === "mock" && url.pathname === "/v1/mock/outbox";
  if (publicRoute || isMock) {
    const cors = corsHeaders(request, settings);
    if (request.method === "OPTIONS") return preflight(cors);
    let response;
    try {
      if (isMock) {
        if (!["GET", "DELETE"].includes(request.method)) throw new HttpError(405, "method_not_allowed");
        response = await mockOutbox(ctx, request);
      } else {
        const handler = publicRoute[request.method];
        if (!handler) throw new HttpError(405, "method_not_allowed");
        response = await handler(ctx, request);
      }
    } catch (error) {
      response = errorResponse(error);
    }
    return withHeaders(response, cors);
  }

  const internalRoute = INTERNAL[url.pathname];
  if (internalRoute) {
    try {
      const handler = internalRoute[request.method];
      if (!handler) throw new HttpError(405, "method_not_allowed");
      return await handler(ctx, request);
    } catch (error) {
      return errorResponse(error);
    }
  }
  return json(404, { error: "not_found" });
}

export default {
  fetch(request, env) {
    return handle(request, env);
  },
  async scheduled(_event, env, ctx) {
    if (!loadConfig(env).ok) return;
    ctx.waitUntil(runMaintenance(env.DB));
  },
};
