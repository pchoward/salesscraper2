# Live search across Shopify shops (Shopify Global Catalog)

**Status:** brief for Codex (owner asked, 2026-11-12). Claude researched Shopify's docs; Codex builds it. Docs read 2026-11-12:
- [About Catalogs, including the usage guidelines](https://shopify.dev/docs/agents/catalog)
- [Global Catalog](https://shopify.dev/docs/agents/catalog/global-catalog)
- [Auth and rate limiting](https://shopify.dev/docs/agents/profiles/auth-and-rate-limiting)
- [Agent profile](https://shopify.dev/docs/agents/get-started/profile)
- [Promoted placements](https://shopify.dev/docs/agents/catalog/promoted-placement)

## Why live search and not scraping
Shopify's Global Catalog searches products across all Shopify shops (1B+ products). It can return the shop's original price (`list_price`), so it can show markdowns at shops ShredDeals doesn't scrape. **Its terms rule it out for the daily scrape:**
- "No bulk harvesting: don't conduct any systematic or automated data collection"
- No "standing product database or commerce index"
- Prices may be cached for at most 10 minutes; product metadata and images for 24 hours
- "Don't aggregate, rehost, redistribute… or bulk export"
- "Use Catalog data only for shopper experiences"

What is allowed: a shopper types a search, we ask the Catalog then and there, and we show the results with Shopify's attribution intact. That's this feature.

## What the shopper sees
- After a search on any sport tab, below our own results, show a section: **"More deals from other shops"** (powered by Shopify Catalog).
- It shows up to 12 results. Each card has the image, title, shop name (`seller.name`, and the domain where space allows), price, and the struck `list_price` with % off when present. The card links to the result's product URL **unchanged**: keep the `shcgid`/`shclid` attribution parameters and checkout URLs.
- **Only marked-down items:** keep a result only if it has `list_price` > `price` and the markdown is at least 5% (our rule). If nothing qualifies, hide the section.
- Results load after our own results render, so a slow or failed Catalog call never blocks the page. On error, the section simply doesn't appear.
- These results are **never** saved into our catalog, price history, alerts, "New"/"Price drops", or saved views.

## How it works
1. **Worker route** (`worker/src`, alongside the alerts routes): `GET /v1/catalog-search?q=<text>&sport=<skate|ski|mtb|bmx>`.
   - It calls `https://catalog.shopify.com/api/ucp/mcp`, tool `search_catalog`, with:
     - `catalog.query`: the shopper's text plus the sport word if missing (for example "bmx");
     - `filters.ships_to = {"country": "US"}`;
     - `filters.available = true`;
     - `pagination.limit = 50`.
   - It returns only the fields the card needs.
   - **Agent profile:** every request sends `meta.ucp-agent.profile`, a URL to our UCP profile JSON. Host it on shreddeals.com (for example `/.well-known/ucp-agent.json`), declaring `dev.ucp.shopping.catalog.search`, `dev.ucp.shopping.catalog.lookup` and `dev.shopify.catalog.global`, as in Shopify's example profile.
   - **Auth:** a Catalog API client from Shopify's Dev Dashboard (client ID and secret as Worker secrets, never in the repo). Exchange them for a JWT (60-minute lifetime), cached in memory until shortly before expiry. Authenticated limit: 5 requests/second per client.
   - **Cache:** at most 10 minutes per normalised query (Catalog terms). No other storage.
   - **Rate guard:** per-IP throttle (for example 10 searches/minute) and a global cap under 5/second. Over the limit, return an empty result, not an error page.
   - **CORS:** shreddeals.com only.
2. **Page** (`page.js`): after a search settles (debounce ~400 ms, at least 3 characters), call the route and render the section. Respect the current sport. Don't run a search on page load or for filter-only changes.
3. **Disclosure line** under the section title: "Results from Shopify Catalog. Prices and stock from each shop; check before you buy."

## Owner actions before it can go live
These are the owner's decisions (CLAUDE.md: no new signups without approval):
1. **Deploy the Worker** (`worker/deploy.sh`, Cloudflare account). It isn't deployed today.
2. **Create a Catalog API client** in Shopify's Dev Dashboard and add its ID and secret as Worker secrets.
3. **Promoted placements: off.** They're a paid-referral program (0.3% base commission, more when merchants fund it). Joining needs a saved catalog with "Earn commission" on, and a clear "Sponsored" label on promoted results before the buyer acts. Build nothing for it unless the owner asks.

Until 1 and 2 are done, the section stays hidden (feature flag in the page settings, default off).

## Tests
- **Worker unit tests** (mocked Catalog): request shape (profile, filters, ships_to US), the field mapping, the 5% markdown filter, the 10-minute cache expiry, throttling, and no secrets in responses.
- **Browser check:** with a mocked route, a search shows the section after our results. Links keep the attribution parameters. An error hides the section. Nothing is written to `localStorage` or saved views.
- **Keep unchanged:** URL parameters, saved views, `localStorage` keys, our own search results.
