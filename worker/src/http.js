// JSON responses, CORS, and bounded request bodies.

export const MAX_PUBLIC_BODY = 16 * 1024;
export const MAX_INTERNAL_BODY = 1024 * 1024;

const SECURITY_HEADERS = {
  "Cache-Control": "no-store",
  "X-Content-Type-Options": "nosniff",
  "Referrer-Policy": "no-referrer",
};

export class HttpError extends Error {
  constructor(status, code, extra = {}) {
    super(code);
    this.status = status;
    this.code = code;
    this.extra = extra;
  }
}

export function json(status, body, headers = {}) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json; charset=utf-8", ...SECURITY_HEADERS, ...headers },
  });
}

export function html(status, body) {
  return new Response(body, {
    status,
    headers: {
      "Content-Type": "text/html; charset=utf-8",
      "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'",
      ...SECURITY_HEADERS,
    },
  });
}

export function errorResponse(error) {
  if (error instanceof HttpError) {
    const headers = error.extra.retryAfter ? { "Retry-After": String(error.extra.retryAfter) } : {};
    const body = { error: error.code };
    if (error.extra.fields) body.fields = error.extra.fields;
    if (error.extra.retryAfter) body.retry_after = error.extra.retryAfter;
    return json(error.status, body, headers);
  }
  return json(500, { error: "internal_error" });
}

function originAllowed(origin, settings) {
  if (!origin) return false;
  if (origin === settings.publicOrigin) return true;
  if (settings.mode === "mock") {
    return /^http:\/\/(localhost|127\.0\.0\.1)(:\d{1,5})?$/.test(origin);
  }
  return false;
}

export function corsHeaders(request, settings) {
  const origin = request.headers.get("Origin");
  if (!originAllowed(origin, settings)) return {};
  return {
    "Access-Control-Allow-Origin": origin,
    "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, Authorization",
    "Access-Control-Max-Age": "600",
    Vary: "Origin",
  };
}

export function withHeaders(response, headers) {
  const merged = new Response(response.body, response);
  for (const [name, value] of Object.entries(headers)) merged.headers.set(name, value);
  return merged;
}

export async function readBody(request, limit) {
  const declared = Number(request.headers.get("Content-Length") || 0);
  if (declared > limit) throw new HttpError(413, "body_too_large");
  const raw = await request.text();
  if (new TextEncoder().encode(raw).length > limit) throw new HttpError(413, "body_too_large");
  return raw;
}

export async function readJson(request, limit = MAX_PUBLIC_BODY) {
  const type = request.headers.get("Content-Type") || "";
  if (!type.toLowerCase().startsWith("application/json")) throw new HttpError(415, "json_required");
  const raw = await readBody(request, limit);
  try {
    const value = JSON.parse(raw);
    if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("not an object");
    return value;
  } catch {
    throw new HttpError(400, "invalid_json");
  }
}

export function bearerToken(request) {
  const header = request.headers.get("Authorization") || "";
  const match = /^Bearer ([A-Za-z0-9_-]{20,100})$/.exec(header);
  if (!match) throw new HttpError(401, "invalid_token");
  return match[1];
}

export function clientIp(request) {
  return request.headers.get("CF-Connecting-IP") || "unknown";
}
