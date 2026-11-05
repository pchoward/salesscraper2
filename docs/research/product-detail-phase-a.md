# #219 Phase A — first-party product details

**Recommendation:** add one lightweight, static-hosted **listing detail document**,
with a permanent internal link per retailer listing. Keep Quick View for fast
inspection. Reuse existing price/history/specification logic after separating it
from card DOM; do not restore the old modal wholesale or transplant V-Next.

Research baseline: `origin/main` **2af159c**, inspected November 5, 2026.
This branch changes documentation only. No production UI, data, scraper, workflow
or parked prototype has been changed. Phase B awaits owner feedback.

## What existed — verified history

Dates below are Git commit dates in UTC. Links point to the actual changes.

| Commit | Evidence / behavior |
| --- | --- |
| [1e43c5f](https://github.com/pchoward/salesscraper2/commit/1e43c5f), Oct 11 | `openProduct(id)` opened `#productModal`, filled product metadata, retailer offers and external CTA, and drew a history chart. This was a larger internal **dialog**, not a dedicated product URL. |
| [dde6e4b](https://github.com/pchoward/salesscraper2/commit/dde6e4b), Oct 18; [71a64e9](https://github.com/pchoward/salesscraper2/commit/71a64e9), Oct 18 | Introduced card Quick View, then made it photo-first with image galleries. |
| [c03c35d](https://github.com/pchoward/salesscraper2/commit/c03c35d), Oct 19 | Collapsed extra Quick View content behind “More details.” |
| [ef01e84](https://github.com/pchoward/salesscraper2/commit/ef01e84), Oct 25; [49202c9](https://github.com/pchoward/salesscraper2/commit/49202c9), Oct 25 | Large photo/short specs; product taps opened that photo view. The latter changed `openProduct` from the older modal implementation to `openQuickView`. |
| [7937d0e](https://github.com/pchoward/salesscraper2/commit/7937d0e), Oct 28 | Compact, button-led Quick View on desktop. |
| [9b4fcec](https://github.com/pchoward/salesscraper2/commit/9b4fcec), Oct 29 | Card body click/Enter opened Quick View; title still linked to the store. |
| [e1370be](https://github.com/pchoward/salesscraper2/commit/e1370be), Oct 29 | Explicitly changed image/title/price/empty surface into one retailer link; Quick View became an independent control. This is the source of today's retailer-first card behavior. |

The owner's recollection of a larger internal product experience is supported.
I found dialogs/photo Quick Views in this history, **not evidence of a previous
stable, shareable first-party detail-page route**. The old modal is useful as a
content checklist; current helpers already supersede much of its implementation.

## Three flows

| | Today's ShredDeals | The Dropper reference | Parked V3.2 concept |
| --- | --- | --- | --- |
| Entry | Stretched retailer link; separate Quick View button | Issue describes separate “View details” and “Snag this deal” | Card opens larger on-site drawer |
| Detail | Gallery, title/store/brand, price/compare-at, specs, retailer CTA; history/score/offers under “Price History & Details” | Issue describes internal `/deals/<id>`, larger photo, variants, LOW/HIGH/AVG, related items and retailer exit | Larger photo, metadata, price metrics and Keepa-style chart |
| URL/history | Quick View pushes the **same URL** with `{quick:1}`; no product identifier | Internal product URL, according to issue | `product(id)` toggles drawer; no product URL/router |
| Borrow | Gallery, own-listing series, honest claimed-price note, focus/Escape, score explanation | Separation of internal inspection and explicit retailer action | Progressive disclosure and useful analytical hierarchy |
| Avoid | DOM-coupled renderer; ambiguous “View Deal”; unscoped legacy specs | Long variant tables and misleading minimum-discount headlines | Sample product IDs, unconditional In Stock, fabricated metrics/chart and broad redesign |

**Reference limits:** the environment proxy returns `403 Forbidden` for
`thedropper.shop`; I could not independently inspect either example page. That
column is explicitly the issue's supplied description. PR [#198](https://github.com/pchoward/salesscraper2/pull/198)
was fetched read-only: `design/vnext/SHREDDEALS_VNEXT_CODEX_HANDOFF.md` and
`shreddeals_v3_2_interactive.html`. Its `product()` sets “typical” to `p.was`,
“lowest” to `p.price * .91`, and `chart()` synthesizes points. Borrow no data logic.

## Current Quick View: reusable, with boundaries

Evidence at the baseline:

* `page.py:_card_store_link` emits the full-card vendor anchor with `_blank` /
  `noopener`. `page.css` stretches it at z-index 1; Quick View/other controls and
  spark interactions sit above it. The click capture handler in
  `page.js:wireDealEvents` handles independent controls before table-row behavior.
* `openProduct` calls `openQuickView`. The latter builds a photo-led view, supports
  desktop positioning/mobile sheet, traps Tab, handles Escape/outside dismissal,
  returns focus, and pushes a history entry. `onPagePopState` closes it on Back.
  Its state contains no listing ID, so a copied URL/refresh cannot reopen the item;
  Forward is not a durable product-details route either.
* `quickFacts`, `quickOwnSeries`, `appendQuickGallery`, `drawQuickChart`,
  `appendQuickScore`, and existing offer comparison provide useful foundations.
  `fillQuickView` itself depends on the active card dataset, `#quickBody` and the
  catalog document; loading all of `page.js` in a new page would not be reuse in
  a useful sense. Extract a small pure model/shared formatting layer first.
* History is fetched lazily from the sport's `history.json` and joined by listing
  URL. `quickFacts` clips daily points to 90 days and computes their arithmetic
  mean; its all-time-low summary can cover a different, longer period. Don't label
  LOW/HIGH/AVG as comparable statistics unless all use the same visible window.
* The selected-variant warning in `appendQuickMore` is useful but listing history
  must be distinguished from variant history for **all** sports, not just shoes.
* A real local MTB example, **SRAM XX Direct Mount 2x10 Front Derailleur**, displays
  **“Length 10″”**. Its saved `length` is `10.0`, category `Drivetrain`, and
  `technical_specs` is empty. `quickFacts` blindly appends inch-based length.
  This is evidence of a data/presentation boundary problem, not a new verified
  derailleur dimension. Omit irrelevant specs in details and flag normalization
  to Claude; do not rewrite his extraction work here.

Current screenshots from a saved-data preview, external requests blocked (hence
photo placeholders): [1440px](product-detail-phase-a/current-quick-view-1440.png),
[390px](product-detail-phase-a/current-quick-view-390.png).

## Smallest useful journey and page

1. Image/title/general surface is a **real internal anchor**. Ordinary click stays
   on ShredDeals; Enter, modifier-click, middle-click and Copy link work natively.
2. Quick View remains a separate fast, dismissible summary. Keep its current
   collapsed history initially; add a “Full details” link rather than deleting
   useful existing behavior or building a second modal identical to it.
3. Detail document: larger existing photo/gallery, complete title, brand/category/
   retailer, current observed price and relevant variant, retailer compare-at
   explicitly distinguished from observed history, observation freshness, scoped
   known specs, and a prominent **“View at retailer”** external link.
4. Below: real history with explicit dates/observation count, observed window
   low/high/mean, existing score explanation, and a bounded observed-options list.
   Show missing-history, one-point, image-missing and unknown-stock states honestly.
   No guessed sizes/quantities, made-up 178cm option from a length band, or assumed
   stock because a listing remains in the feed.
5. Existing Watch/Alert adapters only where supported. Do not create a second save
   system or imply email support for other sports. Related products and broader
   cross-retailer recommendations can wait; existing conservative matched offers
   are the only acceptable comparison basis.

Wireframe: [desktop](product-detail-phase-a/proposed-detail-1440.png) /
[390px](product-detail-phase-a/proposed-detail-390.png) /
[responsive HTML](product-detail-phase-a/wireframe.html). These are documentation
layouts with placeholders and no simulated prices/chart, not an implemented UI.
They illustrate content hierarchy, not a header redesign. At 320px the same
single-column structure should apply and must be tested in Phase B.

## Static route, identity and data contract

**Route:** `product.html?sport=mtb&id=<opaque-listing-id>` under the existing site
base path. One actual HTML file makes refresh/new-tab work on GitHub Pages without
rewrites or a custom 404 router. Optional `variant=<observed-id>` only where the
source supports it. Use same-origin links and an explicit safe back-to-deals
fallback; never navigate to an arbitrary `return=` URL.

**Identity is the first prerequisite.** `page.py` sorts records, then assigns
`str(index)`; disappeared rows get `g<index>`. Both are rebuild-local IDs, unsuitable
for public links. `history_identity.py` and `history.py` establish URL-keyed,
retailer-specific identity, guarded Shopify URL moves, and size-change resets.
`matching.py` is conservative same-product grouping, not a universal product ID.
Keep retailers and variants distinct. Do not use titles, group keys or stripped
variant/query URLs as public identity.

Recommended small durable **publication registry**: assign a listing-instance ID
once from sport + whitespace-normalized exact listing URL + a frozen generation
seed (existing history first-seen when present; first publication otherwise).
Persist that assignment separately from scraper schemas. A later first history
observation must not change an already published ID. Existing history reset
signals mint a new instance and leave the old ID inspectable/stale; titles alone
must not reassign IDs. Only existing verified `previous_urls` evidence can add a
URL alias. Detect hash collisions if using truncated hashes. Unknown URL reuse
without any source evidence remains a limitation; don't claim global identity.

This adds a small generated registry, **not a database or matching rewrite**.
Its retention/alias contract needs owner/Claude review before Phase B. Existing
history trims daily data to 90 days and can prune absent listings after 180 days;
therefore it alone cannot promise permanent links. Keep compact tombstones for
published IDs even after detail payload expiry: show last-known metadata when
retained, otherwise an unavailable explanation and browse link. Never substitute
another listing just because an index or URL was reused.

**Payload:** build from the existing normalized report records, saved catalog
fields and own-listing history, not by parsing a live retailer or loading another
catalog iframe. Use one lightweight detail document plus deterministic small JSON
shards (initial proposal: up to 64 per sport, only nonempty shards written),
located by the opaque ID. No whole catalog DOM, full history file, MiniSearch
index or all-sports manifest is required on detail open. Measure payload sizes
before fixing shard width; do not duplicate another 8–27 MB catalog page.

Keep listing-level history separate from `technical_offers` / `spec_offers`.
At this baseline the saved raw catalogs contain:

| Sport | Raw listings | Multiple technical offers | Missing URL-keyed history |
| --- | ---: | ---: | ---: |
| Skate | 1,457 | 0 (separate spec offers exist) | 7 |
| BMX | 769 | 289 | 0 |
| Ski | 1,816 | 816 | 0 |
| MTB | 2,607 | 631 | 8 |

These are file-inspection counts, not claims of verified stock or public filtered
inventory. Images, current/reference prices, category and some specs already exist;
coverage varies. `technical_offers` can carry variant ID, price, compare, available
and scoped specs. `SportSpecFilters.price()` currently returns **price/compare
only**, losing the chosen variant ID. Before switching card navigation, expose
which observed offer produced the visible price (or carry the existing technical
selection and resolve it with the same helper). If no exact variant is known,
label a “from” price and never imply every size costs that amount. An unsupported
or stale `variant` URL shows a clear unavailable state, never another variant's
price under the requested label.

## Risks and proposed PR sequence

| Risk | Smallest mitigation / acceptance gate |
| --- | --- |
| Stretched links, capture handlers, nested controls | Replace the anchor destination/class deliberately; explicit retailer/Quick View/star/alert/chart controls remain siblings above it. No blanket card `onclick` swallowing modified clicks. Test each hit area. |
| Back/Forward, iframe and deferred grid rendering | Do not mix product routes with `{quick:1}` history. Use native navigation; preserve exact catalog query and a tab-scoped scroll/card anchor. Restore after virtualization has materialized that card. BFCache is an optimization, not the contract. New-tab/direct entry gets a browse fallback. |
| Multiple sports / active price | ID and payload sport must agree; reject foreign/unknown IDs. Preserve selected-offer context; no cheapest-other-variant fallback. |
| Incorrect specs or historical claims | Category-scoped fields; same-window statistics; listing-vs-variant disclaimer; last observed date, no live stock promise. “Gone from feed” is not proof of sold out. |
| URL longevity / history pruning | Durable registry and explicit tombstones; verified aliases only; retain earlier listing instance separately. No changing numeric row IDs in URLs. |
| SEO and sharing | Query-route utility works statically but one HTML shell has generic metadata. Do not claim per-product SEO/social previews. Start noindex until canonical/data policy is approved; generated per-product HTML/meta is a later measured decision. |
| Build and catalog performance | Generate artifacts in the existing publish/build path; deterministic incremental shards, size caps, escaped content and safe retailer protocols. No new framework, service, database or full-catalog iframe. Measure cold/warm loads and repository growth. |

**PR 1 — foundation plus opt-in details:** shared detail model, stable registry /
reset/tombstone contract, static document and small payloads, explicit “Full details”
link from Quick View. All four sports, missing history and one multi-variant case.
Owner can review working direct URLs before ordinary card clicks change.

**PR 2 — card navigation contract:** replace stretched retailer destination with
internal link; add clearly labeled retailer CTA; preserve current Quick View,
watch/alert, grouping and exact Back/scroll state. This completes the smallest
useful first release. No general catalog/header/filter redesign.

**Later, only if justified:** richer variant selectors/pagination, proven matched
retailer comparisons, product-specific SEO and richer analytics. Do not add
recommendation machinery or scrape more data just to fill a detail layout.

Ownership: `docs/shreddeals-ownership.md` assigns catalog card UI to **Grok**,
engine/data to **Claude**, and shell/navigation to **Codex**. Phase A edits none of
those production files. For Phase B, agree the shared model and handoff in the PR
before touching card UI; keep Grok's changes separate from Claude's extraction.
Owner reviews and merges. No merge/deploy is authorized here.

## Phase B test plan

Reuse existing unittest/Node tests and `ci/audit_sports.cjs` / Playwright server.
Add identity fixtures for reorder, price/title update, sport/retailer separation,
variant query distinction, missing-first-seen → first history, verified URL move,
size-reset and expired tombstone. Check own-listing 0/1/many history points,
window LOW/HIGH/mean, currency, unknown availability and same-variant prices.

Browser acceptance at 1440, 390 and 320px: image/title/blank surface → internal
URL; modifier/middle click and new-tab refresh; explicit correct vendor exit;
Quick View Escape/Tab/focus/Back; independent save/alert/spark actions; selected
variant price survives navigation; exact sport/query/filter/sort/group/scroll
restoration; stale/disappeared/missing photo and missing-history states; no
horizontal overflow. Cover Skate, BMX, Ski and MTB. Assert no hidden full-catalog
load and retain a bounded DOM/payload budget. Compare catalog render/search timing
before and after the card link change; don't weaken existing search tests.

Phase A verification: inspected Git diffs and current code/data, opened current
Quick View at 1440/390 using an isolated saved-data preview, and rendered the
responsive wireframes locally with no horizontal overflow. Images/network were
blocked; no retailer scraping, email, deployment, UI edits or new dependencies.
