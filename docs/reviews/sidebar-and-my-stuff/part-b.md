# Part B — My stuff in the header

Stacked on `codex/sidebar-price-more` (Part A). The compact header has a **My stuff**
button alongside search. Its panel contains Saved views, Save current view,
Watching with starred/matching counts, and Bookmark this selection. Rename and
Delete remain available. Watching has a visible active state and a Show all deals
exit. Bookmark copies the current full shell URL, retaining unknown parameters;
a selectable link is shown if clipboard access is unavailable.

The catalog owns all operations and persistence. Same-origin, active-catalog
bridge messages call its existing save/apply/rename/delete/watching functions;
`shreddeals:save-view` does not introduce another storage layer. The embedded
sidebar's personal-tools block is moved to an inaccessible hidden fallback in
the catalog document so those native controls/functions remain intact. Standalone
catalogs keep the three sections at the bottom of their drawer. Show results
stays last.

The panel traps keyboard focus, makes the catalog iframe inert, closes on
Escape/outside tap, and restores focus. The search shortcut closes the panel
before focusing search. Sport/mode/history rendering clears stale panel state.
Explore can still bookmark its URL, while catalog personal tools remain disabled.
No alerts-manager/session behavior was changed.

## Storage compatibility found during implementation

Actual custom views are shared `{id, name, query}` objects under
`salesscraper2.views`; there is no mandatory stored sport field. Their format and
keys are unchanged. Untagged legacy views are explicitly labeled **Shared**.
Existing sport tags (a view's sport or the existing `sport` query parameter) are
respected and foreign-sport views are excluded without deleting them. Built-in
presets are shown only when compatible with the current catalog's type/store
options, avoiding Skate-only presets presented as MTB/Ski/BMX presets.

An existing bug discarded valid saved default views because their query is the
empty string. The reader now accepts that string, keeping the original format
and allowing Save → reload → restore to work. Tests inspect the stored object
keys, tag filtering and preservation of unrelated saved records. The stars key,
filter-section key, every URL/state field and saved-view object format remain
unchanged; no migration is performed.

## Validation

* Full Python/embedded JS suite: **862 tests, OK, no skips**.
* Worker Node tests: **5 passed**. Unified-header artifact build and syntax checks
  passed. The legacy browser harness uses the local HTTP Chromium adapter
  described in [Part A](part-a.md); no repository tests are skipped or weakened.
* New My stuff checks: **8 passed** across Skate/Ski/MTB/BMX at 1440/390px,
  including save/reload, default query, apply, rename/delete, shared/tagged views,
  Watching results/counts, full URL copying, keyboard trap/shortcut/Escape,
  outside tap, inert frame and standalone sidebar fallback.
* Inherited sidebar checks: **8 passed**; category/filter/count: **20 passed**;
  sport menus: **16 passed**; search: **10 passed**; Explore: **4 passed**;
  the PR smoke sequence passed.
* Full four-sport audit: **166 passed** (variant price oracles, Quick View,
  retailer links, Watch, URL history, responsive layout and synthetic edge cases).
* After merging current main/catalog updates, publication/sport-facet/workflow
  checks passed (**21 tests**) and all eight My stuff browser cases passed again.

`ci/check_my_stuff.cjs` runs in normal PR CI. Read-only PR checks now run for
stacked bases too; the browser job retains a bounded 20-minute budget for the
additional matrices. No secrets or write permission were added to the PR job.

Screenshots: [desktop](part-b-desktop.png), [mobile](part-b-mobile.png).
They use saved-data previews with external image requests blocked. The wireframe
records the final sidebar/header arrangement in `docs/menu-wireframe.html`.

The code and tests are complete, but GitHub PR creation/check monitoring is
blocked by the running environment's Forbidden response from
`api.github.com/graphql`. Local results above are not a claim that GitHub required
checks have completed. No review, merge or deployment has been performed.
