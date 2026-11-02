# Four-sport UI regression and usability audit

Base: `4becde7` on `main`. Branch: `codex/four-sport-ui-audit`.

The compact Keepa-inspired layout is preserved. This review uses saved catalogs;
no scraping, delivery, merge, or deployment ran. Retailer discovery, product
normalization, extraction, sport-owned field definitions, and catalog/history
files are unchanged.

## Results

| Area | Initial audit | After fixes |
| --- | --- | --- |
| Header, sports, active states and responsive hierarchy | Pass | Pass |
| Category/store/brand/search/sort combinations | Pass | Pass |
| Technical specs combined with price/discount bounds | Fail: only cheapest matching offer considered | Pass: one offer must satisfy the whole combination |
| Technical selection visibility and removal | Fail: selections missing from summary/count/recovery | Pass |
| Sport navigation and filter URL isolation | Fail: technical URL keys survived sport switches | Pass |
| Quick View, retailer-first links, chart rendering and local Watch | Needs improvement: stale autocomplete could block cards | Pass for tested interactions |
| Unsupported subscription controls | Fail: non-opted-in sports offered alert actions | Pass: Subscribe disabled; card/Quick View alerts omitted |
| Mobile drawer, overflow and touch targets | Needs improvement: some buttons below 24px | Pass after minimum-target correction |
| Real retailer photo/content and current price verification | Needs improvement | Outside this saved-data UI audit |
| Firefox, Safari/WebKit and physical devices | Needs improvement | Not available in this cloud image |

Viewports: **1440, 1024, 768, 430 and 390px**. Phone checks use touch/mobile
emulation, not merely a narrow desktop window. All network requests outside the
local preview are blocked. Image fallbacks in screenshots are intentional; they
do not establish broken live product images. Preview banners are not production UI.

Saved data reviewed: 1,082 Skate source listings (the renderer applies its
existing eligibility rules), 338 BMX, 429 Ski and 32 MTB listings. The default
Skate Decks view has 635 products. Matching checks compare against the rendered
catalog and an independent oracle over supplied variant offers, not assumed
inventory counts.

## Prioritized defects and reproduction

1. **P1 — variant/range intersection and misleading exclusion.** In the labeled
   MTB fixture, choose Forks & Shocks, 29-inch wheels and 160mm travel. The same
   specification combination has $250 and $300 available variants. Set minimum
   price to $275. Previously the cheapest $250 offer made the entire listing
   disappear; now the $300 variant is shown. A maximum of $280 correctly yields
   zero results. Price and discount bounds must hold on that same variant.
   Also expand the price slider: its old maximum came only from base listing
   prices, making more expensive eligible variants unreachable. It now includes
   available technical-offer prices and excludes sold-out offers.
2. **P1 — invisible technical filters and incomplete empty-state recovery.**
   Choose Ski → Skis → 170–179 cm, or BMX → Frames & Forks → 22 inches. Previously
   the selection affected results without appearing in active chips or the phone
   filter count. Now every selected technical value has an individual remove
   action, contributes to the count, and participates in targeted zero-result
   recovery. Hypothetical recovery counts do not mutate active selections.
   The legacy disappeared table also rejects missing applicable technical facts
   rather than ignoring the selected specification.
3. **P2 — hidden state leaks across sports.** Select a Ski technical value and
   switch to BMX. Previously `ski_length`/other sport-owned keys remained in the
   URL and could unexpectedly reactivate on a later visit. The shell now derives
   all technical parameter names from the existing sport definitions. A fresh
   sport switch clears catalog state; Back/Forward restores the prior exact
   technical selection. Unrelated attribution parameters remain intact.
4. **P2 — stale search suggestions intercept product clicks.** Focus search,
   type a suggested brand, then clear filters or restore another query through
   history. A stale suggestion list could remain expanded over product cards.
   Suggestions now close when filter/history processing changes the query
   without an input event. Normal input and keyboard suggestions are preserved.
5. **P2 — unsupported alerts appear actionable.** Open BMX, Ski or MTB. They
   explicitly declare `alerts: false`, but previously showed enabled Subscribe
   and Alert me actions. Subscribe now remains in the unified header, disabled
   with an explanation; card and Quick View alert actions are absent. Local
   Watch/Track remains available. Skate's existing alerts behavior is preserved;
   live delivery is disabled throughout every preview/test.
6. **P2 — undersized mobile drawer controls.** Open Filters on a phone and
   inspect compact technical/help buttons. Some fell below 24px. The mobile
   drawer now enforces a 24×24px minimum without changing desktop layout,
   extraction, or the compact header. Tests check the fully opened drawer's
   bounds and button heights after its transition.

## Screenshots

| Sport | Desktop, 1440px | Mobile, 390px | Mobile drawer |
| --- | --- | --- | --- |
| Skate | [Desktop](skate-desktop.png) | [Mobile](skate-mobile.png) | [Filters](skate-mobile-filters.png) |
| BMX | [Desktop](bmx-desktop.png) | [Mobile](bmx-mobile.png) | [Filters](bmx-mobile-filters.png) |
| Ski | [Desktop](ski-desktop.png) | [Mobile](ski-mobile.png) | [Filters](ski-mobile-filters.png) |
| MTB | [Desktop](mtb-desktop.png) | [Mobile](mtb-mobile.png) | [Filters](mtb-mobile-filters.png) |

## Regression coverage

The existing Playwright/topbar infrastructure supplies the local preview server
and browser. `ci/audit_sports.cjs` exercises all sports at all five sizes and
saves screenshots plus machine-readable results. Clearly labeled fixtures from
`ci/build_audit_fixtures.py` additionally cover split facts across different
variants, sold-out matches, missing specs, a matching expensive variant, price
boundaries, zero results, and matching card/Quick View prices at desktop/phone
sizes. Synthetic products never enter source catalogs or production outputs.

The existing PR check job runs this audit using its existing Playwright install.
Its **four-sport-ui-audit** artifact contains results/screenshots separately from
the published-preview artifact. No publisher or artifact allowlist is broadened.

```bash
python ci/build_preview.py /tmp/four-sport-site --label 'Four-sport UI audit'
python ci/build_audit_fixtures.py /tmp/four-sport-site
BROWSER_BINARY=/usr/bin/chromium node ci/audit_sports.cjs /tmp/four-sport-site /tmp/four-sport-results
# Omit BROWSER_BINARY when using Playwright's installed Chromium in CI.
python -m pytest -q -k 'not SearchUiTests and not caption_is_below_the_range_thumbs'
```

Validation evidence:

- The full non-legacy suite passed **654 tests and 23 subtests**. A subsequently
  added disappeared-table regression passed in the focused six-test facet run.
- **Eight existing search browser tests passed**, including the new stale-list
  Clear regression, using their original assertions/driver over local HTTP via
  Playwright. This image blocks the normal legacy `file://` Chrome harness.
- **166 responsive acceptance checks passed**; results are in [browser-results.json](browser-results.json).
  Six additional fixture checks verified the explicit selected-variant history
  explanation ([results](variant-history-results.json)). The affected price, Quick
  View and facet follow-up suite passed 15 tests and three subtests.
- JavaScript syntax, workflow YAML parsing and `git diff --check` passed.
- The unrelated legacy slider-caption test was not executed successfully by its
  file-URL harness. The responsive drawer and slider rendering were inspected
  through the HTTP preview instead.

## Data/ownership handoff and remaining limits

- **Ski 178cm** is not an exact selectable value in the supplied contract:
  lengths are grouped as 170–179cm, etc. The audit uses that actual group with
  Armada. Supporting exact lengths needs an explicit upstream field/data
  decision; this UI change does not relabel a range as an exact size.
- The small saved **MTB catalog has no 160mm travel option**. Real-data checks
  use its known available values; the explicit 29-inch/160mm workflow is covered
  by labeled synthetic fixtures. This is coverage work for Claude, not evidence
  that the live UI should manufacture a match.
- Unknown/missing facts are not backfilled. An applicable selected known spec
  excludes missing-fact and sold-out variants. Unknown stock remains unknown,
  following the existing supplied-offer contract.
- Historic charts remain listing-level history, not a verified history of each
  selected variant. Quick View now explicitly explains that distinction when
  showing a selected variant price. Claimed list discounts remain labeled separately from
  tracked price movements.
- Live destination status, retailer images, current inventory/prices, actual
  email delivery and cross-engine/physical-device compatibility remain unverified.
  No external retailer request was used to validate these claims.
- GitHub API access still fails at the proxy's CONNECT step with 403. Git push
  works; use the branch Compare link for PR creation/review. Nothing is merged
  or deployed automatically.
