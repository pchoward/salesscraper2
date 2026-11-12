# Task 13: live Shopify Catalog search

Implementation of [the brief](live-search-catalog.md). The feature remains **off by default**, on both the page and Worker. No deployment, Shopify client creation, paid service or promoted-placement signup is part of this change.

## Behavior

A shopper typing at least three characters triggers one debounced request after 400ms. It runs separately from first-party filtering. The section appears below our results only when eligible results arrive, with Shopify disclosure and up to 12 cards. Slow responses cannot overwrite a newer query. Errors and empty responses hide the section. Bookmarked searches, saved-view restoration, page load and filter-only changes never initiate a Catalog request.

Each card uses one variant's current and reference prices in the same currency, with a minimum 5% markdown. It rejects explicitly unavailable variants and does not combine price-range minima with another variant's list price. One offer per product/seller avoids filling the section with duplicate size variants. Product and checkout URLs retain their original attribution parameters and fragments. UCP money amounts are ISO 4217 minor units; the UI formats USD, JPY and other currencies accordingly. Retailer list prices remain reference prices, never observed price history.

Catalog cards use separate DOM classes and do not enter our catalog JSON, deal counts, grouping, history, alerts, change tabs, stars or saved views. Existing URL parameters and localStorage keys are unchanged. Saving a view may still save the shopper's ordinary search query, as before; it never saves Catalog results.

## Worker contract and limits

`GET /v1/catalog-search?q=<3–200 characters>&sport=<skate|ski|mtb|bmx>` accepts requests from `https://shreddeals.com` only. It calls `search_catalog` at `https://catalog.shopify.com/api/ucp/mcp` with our agent profile, the sport word when absent, US shipping, available inventory, and limit 50. It follows no pagination and returns only card fields plus expiry metadata. JSON, MCP text content and SSE replies are supported. Unnegotiated Global Catalog extension responses fail closed.

The route uses its own opt-in flag and credentials, independently of email-alert configuration. It reuses the existing D1 `rate_limits` table and `TOKEN_PEPPER`: 10 requests per IP per fixed minute, plus a shared atomic 300ms admission gate immediately before upstream Catalog calls. The gate permits at most four calls in a rolling second across Worker isolates, including after slow token refreshes. Throttling, missing credentials and upstream failures return `{ "items": [] }`. Tokens, secrets, upstream errors and raw product payloads are never returned or logged.

The existing daily Worker cron retires two-day-old Catalog counters even when email alerts are unconfigured. Only opaque rate counters are written to D1; no queries, products or price observations are written there. Catalog responses have `Cache-Control: no-store`. A bounded in-memory cache holds up to 200 normalized sport/query entries for no more than ten minutes, never served stale. Identical concurrent requests share a call. JWTs are cached until shortly before their lifetime expires; no new service or database migration is required.

Replies include remaining cache lifetime. The browser reduces it by request elapsed time, expires displayed prices, and clears stale results on page visibility/history restoration. It does not turn a nine-minute-old cached response into another ten minutes of browser caching.

## Owner-controlled activation

1. Merge this change after both PR checks pass. The normal Pages rebuild publishes the profile at `https://shreddeals.com/.well-known/ucp-agent.json`; `_config.yml` explicitly includes this hidden directory. Preview builds keep the feature off.
2. Create a **Catalog API client** in Shopify's Dev Dashboard. Add its values to the Worker via `wrangler secret put SHOPIFY_CATALOG_CLIENT_ID` and `wrangler secret put SHOPIFY_CATALOG_CLIENT_SECRET`. Never place them in the page config, repository, PR or chat.
3. Keep the existing D1 binding/migrations and a 32+ character `TOKEN_PEPPER`. Set `CATALOG_SEARCH_ENABLED = "true"` under `[vars]` in the owner's private Worker config. Deploy through `worker/deploy.sh` from current main; this change does not deploy it.
4. Verify the public profile is reachable and make an owner-controlled search against the deployed route from the production origin. Confirm token exchange, negotiated Global Catalog capability, a known marked-down variant, its currency/stock, and the attributed destination link. This is the required live integration check before enabling shoppers.
5. In `page.py`, set `LIVE_CATALOG_UI_CONFIG` to `{"enabled": True, "apiBase": "https://<the-deployed-worker-host>"}` in a separate reviewed change. No credentials belong here. The normal page rebuild applies it to all four sports.

Rollback: turn either flag off. The page flag hides the experience; the Worker flag stops upstream searches. No catalog/history rollback or migration is needed.

Promoted placements are not requested or implemented. This change makes no enrollment or commission decision.

## Verification and limits

Worker tests use local SQLite and mocked Shopify responses. They cover the protocol, thin field mapping, same-variant 5% boundary, stock/currency checks, intact links, TTL, token reuse/refresh, concurrent calls, cross-isolate rate limits, CORS and safe failures. Python tests cover default-off configuration, safe embedding, currency units and profile publication. The browser check mocks both the route and sample images and covers all four sports on desktop and phone, own-results isolation, no automatic search on load/filter changes, stale response suppression, errors, storage, expiry and disabled operation.

Screenshots: [review gallery](reviews/live-catalog-search/README.md). They contain clearly labeled fictional Catalog products; they are not inventory or a live Shopify validation.

The environment denied Shopify's documentation/API domains and has no Catalog client credentials. No authenticated live API call was made. The owner's live check above remains necessary. The agent profile is pinned to `2026-04-08`; update versions deliberately after checking upstream support.

Protocol references checked through public GitHub sources on 2026-11-12 (no code dependencies added):

- [UCP catalog model and minor currency units](https://github.com/Universal-Commerce-Protocol/ucp/blob/main/docs/specification/shopping/catalog/index.md) and [price schema](https://github.com/Universal-Commerce-Protocol/ucp/blob/main/source/schemas/common/types/price.json).
- [Public Shopify Catalog sample: token exchange](https://github.com/shopify-apac-ts/shopify-ucp-demo-mcp/blob/main/src/auth.ts), [MCP request/response transport](https://github.com/shopify-apac-ts/shopify-ucp-demo-mcp/blob/main/src/catalog.ts), and [field mapping](https://github.com/shopify-apac-ts/shopify-ucp-demo-mcp/blob/main/docs/catalog-field-mapping.md).
- [Public Shopify-compatible agent profile](https://github.com/ToddWelch/ucp-agent-profile/blob/main/agent-profile.json); the base and Global Catalog capability identifiers/schema URLs match the brief. Shopify's primary documentation links remain in the original brief.
