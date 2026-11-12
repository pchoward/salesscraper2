// Shopper-triggered Shopify Global Catalog search. No catalog data is persisted.
import { hmacHex } from './crypto.js';
import { json, withHeaders } from './http.js';

export const CATALOG_ENDPOINT = 'https://catalog.shopify.com/api/ucp/mcp';
export const TOKEN_ENDPOINT = 'https://api.shopify.com/auth/access_token';
export const AGENT_PROFILE = 'https://shreddeals.com/.well-known/ucp-agent.json';
export const CACHE_MS = 600_000;
const ORIGIN = 'https://shreddeals.com';
const SPORTS = new Set(['skate', 'ski', 'mtb', 'bmx']);
const MAX_CACHE = 200;

function text(value, limit = 300) {
  return typeof value === 'string' ? value.trim().slice(0, limit) : '';
}
function https(value) {
  if (typeof value !== 'string' || value.length > 4096 || value.trim() !== value) return '';
  try {
    const url = new URL(value);
    return url.protocol === 'https:' && !url.username && !url.password ? value : '';
  } catch { return ''; }
}
function money(value) {
  return value && Number.isSafeInteger(value.amount) && value.amount >= 0 && /^[A-Z]{3}$/.test(value.currency)
    ? { amount: value.amount, currency: value.currency } : null;
}
function image(variant, product) {
  return [...(Array.isArray(variant.media) ? variant.media : []), ...(Array.isArray(product.media) ? product.media : [])]
    .filter(item => item && item.type === 'image').map(item => https(item.url)).find(Boolean) || '';
}

// A markdown always compares the same variant, seller and currency. Never
// combine a product's price-range minimum with another variant's list price.
export function catalogCards(data) {
  if (!Array.isArray(data?.ucp?.capabilities?.['dev.shopify.catalog.global'])) return [];
  const cards = [], seen = new Set();
  for (const product of (Array.isArray(data.products) ? data.products.slice(0, 50) : [])) {
    if (!product || typeof product !== 'object') continue;
    for (const variant of (Array.isArray(product.variants) ? product.variants : [])) {
      if (!variant || typeof variant !== 'object') continue;
      const price = money(variant.price), list = money(variant.list_price);
      if (!price || !list || price.currency !== list.currency || list.amount <= price.amount ||
          (list.amount - price.amount) * 100 < list.amount * 5 || variant.availability?.available === false ||
          ['out_of_stock', 'sold_out'].includes(variant.availability?.status)) continue;
      const url = https(variant.url) || https(variant.checkout_url) || https(product.url);
      const title = text(product.title), seller = variant.seller || {};
      if (!url || !title) continue;
      const domain = new URL(https(seller.url) || url).hostname;
      const key = `${product.id || title}\n${seller.id || domain}`;
      if (seen.has(key)) continue;
      seen.add(key);
      const variantTitle = text(variant.title, 120);
      cards.push({ title: title + (variantTitle && !/^default( title)?$/i.test(variantTitle) ? ' — ' + variantTitle : ''),
        url, image: image(variant, product), seller: { name: text(seller.name, 120) || domain, domain },
        price, list_price: list, discount: Math.floor((list.amount - price.amount) * 100 / list.amount) });
      if (cards.length === 12) return cards;
    }
  }
  return cards;
}

async function boundedText(response, limit) {
  if (Number(response.headers.get('Content-Length')) > limit) throw new Error('large_response');
  const reader = response.body?.getReader();
  if (!reader) throw new Error('empty_response');
  const chunks = []; let size = 0;
  for (;;) {
    const { done, value } = await reader.read(); if (done) break;
    size += value.byteLength;
    if (size > limit) { await reader.cancel(); throw new Error('large_response'); }
    chunks.push(value);
  }
  const joined = new Uint8Array(size); let offset = 0;
  for (const chunk of chunks) { joined.set(chunk, offset); offset += chunk.byteLength; }
  return new TextDecoder().decode(joined);
}
async function catalogData(response) {
  const raw = await boundedText(response, 2 * 1024 * 1024);
  let envelope;
  if (response.headers.get('Content-Type')?.includes('text/event-stream')) {
    for (const event of raw.split(/\r?\n\r?\n/)) {
      const lines = event.split(/\r?\n/).filter(line => line.startsWith('data:')).map(line => line.slice(5).trimStart());
      if (!lines.length) continue;
      const value = JSON.parse(lines.join('\n'));
      if (value.id === 1 && (value.result || value.error)) envelope = value;
    }
  } else envelope = JSON.parse(raw);
  if (!envelope || envelope.error || envelope.result?.isError) throw new Error('catalog_error');
  const result = envelope.result;
  return result.structuredContent ?? JSON.parse(result.content?.find(item => item.type === 'text')?.text || 'null');
}

export function catalogRequest(query, sport) {
  const words = query.toLowerCase().match(/[a-z0-9]+/g) || [];
  return { jsonrpc: '2.0', id: 1, method: 'tools/call', params: { name: 'search_catalog', arguments: {
    meta: { 'ucp-agent': { profile: AGENT_PROFILE } },
    catalog: { query: words.includes(sport) ? query : `${query} ${sport}`,
      filters: { ships_to: { country: 'US' }, available: true }, pagination: { limit: 50 } },
  } } };
}

// Existing D1 rate_limits table only stores opaque counters, never searches or
// products. The global 300ms gate is shared across Worker isolates/POPs and
// admits at most four Catalog calls in any rolling second, without a new service.
async function allowIp(env, ip, now) {
  const bucket = 'catalogIp:' + await hmacHex(env.TOKEN_PEPPER, ip);
  const start = Math.floor(now / 60) * 60;
  const row = await env.DB.prepare(`INSERT INTO rate_limits (bucket,count,window_start) VALUES (?,1,?)
    ON CONFLICT(bucket) DO UPDATE SET count=CASE WHEN window_start=excluded.window_start THEN count+1 ELSE 1 END,
    window_start=excluded.window_start RETURNING count`).bind(bucket, start).first();
  return row?.count <= 10;
}
async function allowGlobal(env, nowMs) {
  const bucket = 'catalogGlobal:' + await hmacHex(env.TOKEN_PEPPER, env.SHOPIFY_CATALOG_CLIENT_ID);
  const row = await env.DB.prepare(`INSERT INTO rate_limits (bucket,count,window_start) VALUES (?,?,?)
    ON CONFLICT(bucket) DO UPDATE SET count=excluded.count,window_start=excluded.window_start
    WHERE rate_limits.count <= excluded.count-300 RETURNING count`)
    .bind(bucket, Math.floor(nowMs), Math.floor(nowMs / 1000)).first();
  return Boolean(row);
}

export function createCatalogSearch() {
  const states = new WeakMap();
  return async function catalogSearch(request, env, deps = {}) {
    const origin = request.headers.get('Origin');
    const cors = origin === ORIGIN ? { 'Access-Control-Allow-Origin': ORIGIN, 'Access-Control-Allow-Methods': 'GET, OPTIONS',
      'Access-Control-Max-Age': '600', Vary: 'Origin' } : {};
    if (origin !== ORIGIN) return json(403, { error: 'origin_not_allowed' });
    if (request.method === 'OPTIONS') return new Response(null, { status: 204, headers: cors });
    const time = () => deps.now ? deps.now() * 1000 : Date.now();
    const reply = body => withHeaders(json(200, body.expires_at ? {...body,
      max_age_ms: Math.max(0, Math.min(CACHE_MS, body.expires_at-time()))} : body), cors);
    if (request.method !== 'GET') return withHeaders(json(405, { error: 'method_not_allowed' }), cors);
    const empty = () => reply({ items: [] });
    if (env.CATALOG_SEARCH_ENABLED !== 'true' || !text(env.SHOPIFY_CATALOG_CLIENT_ID) || !text(env.SHOPIFY_CATALOG_CLIENT_SECRET) ||
        !env.DB?.prepare || typeof env.TOKEN_PEPPER !== 'string' || env.TOKEN_PEPPER.length < 32) return empty();
    const url = new URL(request.url), sport = url.searchParams.get('sport');
    const rawQuery = url.searchParams.get('q') || '';
    if (rawQuery.length > 200) return empty();
    const query = rawQuery.normalize('NFKC').trim().replace(/\s+/g, ' ').toLowerCase();
    if (query.length < 3 || !SPORTS.has(sport)) return empty();
    const nowMs = time();
    const fetcher = deps.fetch || fetch;
    let state = states.get(env);
    const credentials = env.SHOPIFY_CATALOG_CLIENT_ID + '\n' + env.SHOPIFY_CATALOG_CLIENT_SECRET;
    if (!state || state.credentials !== credentials) {
      state = { credentials, cache: new Map(), inflight: new Map(), token: '', tokenUntil: 0, tokenPromise: null };
      states.set(env, state);
    }
    // Expired entries are deleted, not served stale, including on upstream errors.
    for (const [key, value] of state.cache) if (value.expires_at <= nowMs) state.cache.delete(key);
    try {
      if (!await allowIp(env, request.headers.get('CF-Connecting-IP') || 'unknown', nowMs / 1000)) return empty();
      const key = sport + '\n' + query;
      if (state.cache.has(key)) return reply(state.cache.get(key));
      if (state.inflight.has(key)) return reply(await state.inflight.get(key));
      if (state.inflight.size >= MAX_CACHE) return empty();
      const run = async () => {
        if (!state.token || nowMs >= state.tokenUntil) {
          if (!state.tokenPromise) state.tokenPromise = (async () => {
            const response = await fetcher(TOKEN_ENDPOINT, { method: 'POST', redirect: 'error', signal: AbortSignal.timeout(8000),
              headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ grant_type: 'client_credentials',
                client_id: env.SHOPIFY_CATALOG_CLIENT_ID, client_secret: env.SHOPIFY_CATALOG_CLIENT_SECRET }) });
            if (!response.ok) throw new Error('auth_failed');
            const token = JSON.parse(await boundedText(response, 64 * 1024));
            if (typeof token.access_token !== 'string' || !token.access_token) throw new Error('auth_failed');
            state.token = token.access_token;
            const lifetime = Number.isFinite(token.expires_in) ? Math.min(3600, token.expires_in) : 3600;
            state.tokenUntil = nowMs + Math.max(0, lifetime - 60) * 1000;
          })().finally(() => { state.tokenPromise = null; });
          await state.tokenPromise;
        }
        const requestMs = time();
        if (!await allowGlobal(env, requestMs)) return { items: [] };
        const response = await fetcher(CATALOG_ENDPOINT, { method: 'POST', redirect: 'error', signal: AbortSignal.timeout(8000),
          headers: { 'Content-Type': 'application/json', Accept: 'application/json, text/event-stream', Authorization: `Bearer ${state.token}` },
          body: JSON.stringify(catalogRequest(query, sport)) });
        if (!response.ok) { if (response.status === 401) { state.token = ''; state.tokenUntil = 0; } throw new Error('catalog_failed'); }
        const body = { items: catalogCards(await catalogData(response)), expires_at: nowMs + CACHE_MS };
        if (state.cache.size >= MAX_CACHE) state.cache.delete(state.cache.keys().next().value);
        state.cache.set(key, body);
        return body;
      };
      const promise = run().finally(() => state.inflight.delete(key));
      state.inflight.set(key, promise);
      return reply(await promise);
    } catch { return empty(); } // Never expose tokens, upstream messages or retailer payloads.
  };
}
export const catalogSearch = createCatalogSearch();

// Same two-day counter retention as alert maintenance; no product/query rows.
export async function pruneCatalogLimits(db, now = Math.floor(Date.now() / 1000)) {
  return db.prepare("DELETE FROM rate_limits WHERE (bucket LIKE 'catalogIp:%' OR bucket LIKE 'catalogGlobal:%') AND window_start < ?")
    .bind(now - 2 * 86400).run();
}
