// Local mock of the alerts API for UI work. No Cloudflare account, no email,
// no network: mail lands in GET /v1/mock/outbox, and the Turnstile token
// "mock-turnstile-pass" always passes.
//
//   node dev/mock-server.js            # http://localhost:8787
//   PORT=9000 MANAGE_PAGE_URL=http://localhost:8000/alerts.html node dev/mock-server.js
//
// The fake secrets below exist only in this file and only work in mock mode.

import { createServer } from "node:http";
import { fileURLToPath } from "node:url";
import { handle } from "../src/index.js";
import { runMaintenance } from "../src/maintenance.js";
import { D1Sqlite } from "./d1-sqlite.js";

const port = Number(process.env.PORT || 8787);
const env = {
  DB: new D1Sqlite(process.env.MOCK_DB || ":memory:").applyMigrations(fileURLToPath(new URL("../migrations/", import.meta.url))),
  MODE: "mock",
  HMAC_SECRET: "mock-hmac-secret-not-for-production-000",
  TOKEN_PEPPER: "mock-token-pepper-not-for-production-00",
  PUBLIC_ORIGIN: process.env.PUBLIC_ORIGIN || "https://pchoward.github.io",
  PUBLIC_API_URL: `http://localhost:${port}`,
  MANAGE_PAGE_URL: process.env.MANAGE_PAGE_URL || "http://localhost:8000/alerts.html",
  CONSENT_VERSION: process.env.CONSENT_VERSION || "2026-10",
  EMAIL_FROM: "SkateDeals (mock) <alerts@example.invalid>",
};

const server = createServer(async (incoming, outgoing) => {
  const chunks = [];
  for await (const chunk of incoming) chunks.push(chunk);
  const body = Buffer.concat(chunks);
  const headers = new Headers();
  for (const [name, value] of Object.entries(incoming.headers)) {
    if (typeof value === "string") headers.set(name, value);
  }
  headers.set("CF-Connecting-IP", incoming.socket.remoteAddress || "127.0.0.1");
  const request = new Request(`http://localhost:${port}${incoming.url}`, {
    method: incoming.method,
    headers,
    body: ["GET", "HEAD"].includes(incoming.method) ? undefined : body,
  });
  const response = await handle(request, env);
  outgoing.writeHead(response.status, Object.fromEntries(response.headers));
  outgoing.end(Buffer.from(await response.arrayBuffer()));
});

setInterval(() => runMaintenance(env.DB).catch(() => {}), 3600 * 1000).unref();
server.listen(port, () => {
  console.log(`SkateDeals alerts mock API on http://localhost:${port} (mode: mock, no email is sent)`);
  console.log(`Turnstile token that passes: mock-turnstile-pass. Captured mail: GET /v1/mock/outbox`);
});
