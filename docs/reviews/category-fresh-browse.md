# Fresh category navigation — #254 / #255

Primary instructions: PR [#254](https://github.com/pchoward/salesscraper2/pull/254),
task 11 in its backlog file. Acceptance checklist:
[issue #255](https://github.com/pchoward/salesscraper2/issues/255).

## Behavior

A top-menu category pick is navigation: clear catalog-owned query parameters,
including search, retailer, brand, prices, technical dimensions and personal
view filters, and open the selected sport/category through the existing shell
URL/history path. Unrelated analytics parameters survive. The existing sidebar
category function still narrows within the current filters. No URL parameter,
localStorage key or saved-view object format changes.

Active top-menu category totals are counted once from the loaded catalog's
actual current rows, ignoring removed listings and filter state. Inactive sports
continue to use the small published category JSON; hover/focus/touch does not
load catalog iframes. The category button's result count and the sidebar retain
live filtered counts. Only a genuinely empty category may be disabled.

Technical-filter actions now accept the active category, using the existing
configured category applicability. Inapplicable dimensions are omitted from
active chips, breadcrumbs and reset recommendations. Their selected state
remains in direct links and saved snapshots and becomes applicable again if the
user returns through the sidebar. Filtering itself already respected field
applicability; no second filter engine was added.

## Regression coverage

- Pure navigation tests verify same-sport and cross-sport fresh URLs, preservation
  of unrelated parameters, unchanged direct-link behavior and unfiltered counts.
- Technical-facet tests verify hidden actions retain their encoded state.
- `ci/check_category_navigation.cjs` checks full menu counts under brand, retailer,
  price and search constraints; sidebar versus top-menu behavior; Back/Forward;
  Protection (Wrists/Elbows) → Seats & Posts → Bikes; clean breadcrumbs; the
  Supacaz legacy mixed URL; and saved snapshot round-trip.
- `ci/check_sport_menus.cjs` retains hover, focus and touch coverage without
  hidden catalog loads. Readiness waits account for real category navigation.
- Public navigation assets and their content versions are regenerated with
  `python -m previews.publish`.

Browser checks use saved real catalogs with external requests blocked. No
scraping, stored catalog/history updates, notifications, heading changes,
merging or deployment are part of this fix.

## Local validation

- Full Python/embedded-JavaScript suite: **901 tests, OK**.
- Category navigation and #255 acceptance: all four sports at **1440px and
  390px**, eight passes.
- Hover/focus/touch menus: all four sports at **1440, 768, 430 and 390px**,
  sixteen passes, including no inactive catalog iframe requests.
- GitHub PR checks are separate from these local results and must be green
  before the PR is called ready for owner review.
