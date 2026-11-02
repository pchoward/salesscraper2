# Scoped Explore engine (#169)

Review implementation following research PR #168. **Not enabled on the live site.**
Deals stays the default and continues through its existing sale-only pipeline.
No Explore offers enter sale snapshots, alert scoring, or subscriber delivery.

## Capture boundary

`scopes.json` describes sport, category, discipline, market/currency and explicit
Shopify collection sources. Sources require a reviewed type allowlist,
`approved: true`, and a nonempty `approval_note`. The checked-in candidates are
unapproved: their retailer policies, feeds, classifications and live coverage
could not be verified through this environment's proxy. Do not approve them by
merely enabling network access. Dan's Comp needs a separately verified adapter;
no HTML guessing fallback is installed.

The source types are **proposed, unverified mappings**, not claims about actual
retailer taxonomy. Verify every configured type and variant option against a
permitted feed before promotion. A broad `Bikes` type alone must not be used to
qualify Dirt Jump inventory: require a verified dedicated complete-bike source
and structured discipline tags where necessary. Frames, tires and accessories
must remain excluded. Wheel diameter and model keywords are not proof.

The collector intentionally separates structured inventory extraction from
`stores.shopify.sale_variants`. It reuses the existing Shopify collection
protocol, without changing the Deals adapter or adding a framework/dependency.
A `Reader` may be reused across scope captures in one process: feed responses
are cached by exact URL, preventing duplicate pagination requests. It is not a
persistent cache and does not coordinate independent scraper processes. No
workflow schedules this command; do not run it concurrently with live scraping
of the same retailer. Scheduling/coordination needs review before rollout.

```sh
python -m explore mtb-dirt-jump --state-dir /tmp/explore-state
```

This explicit command currently performs **zero network requests** because every
source is unapproved. It writes a failed/stale manifest and exits 1, rather than
publishing an empty successful catalog. Use a separate state folder, never the
Deals catalog folders. State writes use an atomic replacement; a single writer
per state file is required.

## Data semantics

* Schema v1: one scoped JSON snapshot containing `offers`, `history`, completion
  manifests, last-success/attempt times, stale state, and metrics.
* Identity hashes retailer origin + provider product ID + provider variant ID +
  market + currency. Collection, scope and sale status are absent from the key.
  Same retailer variants can therefore retain identity across Deals/Explore
  projections; existing Deals history files/keys are not migrated or rewritten.
  Histories currently remain isolated in each scoped snapshot; cross-scope
  consolidation can be added if overlapping production scopes justify it.
* Each variant has its own positive current price, nullable genuine retailer
  compare-at reference, boolean-or-unknown stock, exact labeled option specs,
  observation timestamp, retailer-first variant URL and field provenance.
  Unknown stock is retained diagnostically but excluded from available results.
* Shopify collection prices must be major-unit strings. The configured currency
  and market must be verified during source review. Numeric/cents payloads need
  an explicit adapter, not automatic guessing or conversion.
* History contains verified in-stock observed prices only: one latest point per
  UTC observation day, up to 90 points and lifetime observed low/high. Compare-at
  is never inserted as a historical observation. Absent identities expire after
  180 days. No synthetic price-drop or sold-out history points are invented.
* All sources must reach a short/empty terminal page. Repeated product IDs,
  malformed eligible offers, failed requests and page caps fail the snapshot.
  Partial failures retain the entire last-good offers/history without fresh
  timestamps or observations. A completely verified empty inventory can clear
  current offers, while retaining history for its retention window.
* Eligibility uses configured structured product types and optional exact tags.
  Specifications come only from the selected variant's labeled options. Unknown
  facts do not satisfy selected filters. There is no bike compatibility guessing,
  cross-retailer model matching, or independent rewrite of Claude's extraction.

## Access and budgets

Normal environment proxy/TLS; honest user agent; no redirects, retries, browser
bypass or paid API. Approval and readable robots policy are required before feed
access. Robots disallow, 404, 403 and unreadable policy all fail closed. Respect
crawl-delay/request-rate, with a 1.5-second minimum. Defaults: 30 total uncached
requests, 120 seconds per Reader, 15-second maximum request timeout, 4 MiB per
response, 250 products/page, four pages/source (configurable up to 20). A full
final page at the cap is **incomplete**, not proof of inventory completeness.
Metrics include successful pages, products read, elapsed time, current offer
count, serialized state bytes, and CLI transport requests/response bytes.

No live runtime/storage measurements are claimed. Measure approved source
counts, unknown stock, rejected taxonomy, request cost and Git growth before
raising budgets or considering scheduling. Keep JSON; no migration is justified.

## Review UI and tests

```sh
python ci/build_explore_preview.py /tmp/explore-preview
BROWSER_BINARY=/usr/bin/chromium node ci/check_explore.cjs /tmp/explore-preview /tmp/explore-shots
python -m unittest test_explore test_shreddeals_publish -v
```

The inert preview uses existing saved Deals catalogs and **synthetic Explore
fixtures**, including a second sport (Ski). It reuses `page.css`, the shell and
same-origin navigation bridge. The Explore entry is injected only into this
opt-in review build. Default `previews.publish` output does not expose Explore.
All source cards and screenshots are explicitly labeled synthetic.

The view supports category/store/brand/search, dynamic variant-specification
facets, regular/discounted prices, sorting, Cards/Table, zero results, URL/history,
retailer-first variant links, and Quick View with observed price history. Cards
show variants separately to avoid ambiguous cheapest-price claims. Reference
prices are explicitly retailer compare-at, not historical savings. No alerts or
Watch controls are offered. This is a compact review interface, not a claim that
live inventory or retailer images have been collected.

See [review evidence](../docs/reviews/explore-pilot/README.md) for screenshots,
coverage limitations and verification. Production source approval, a permitted
live capture and rollout review remain outstanding; no workflow or deployment
was changed.
