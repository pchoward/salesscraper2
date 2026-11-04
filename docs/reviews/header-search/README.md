# PR #199 header search fixes

Fixes the three review findings on the existing `ui/current-header-layout-search`
branch. This is the current-site top bar, not the parked V-Next design.

* Regenerated the checked-in public homepage and navigation assets using
  `python -m previews.publish`; publication consistency tests now pass.
* Forward header searches to the active Deals or Explore search input, retaining
  each catalog's existing filtering implementation and variant-specific behavior.
* Synchronize the header after Clear all, Explore reset, programmatic search-chip
  changes, URL/history restoration and sport/view switches. A search chip removed
  before the debounced URL commit also stays synchronized.
* Observe the existing rendered search state for programmatic input changes;
  no input-property interception, polling or duplicate search engine.
* Validate search-sync message origin, sender and catalog path, rejecting queued
  messages from another sport/view. Disable header search for an empty catalog.
* Add `ci/check_header_search.cjs` to normal PR browser checks, with screenshots
  uploaded separately from the public preview artifact.

## Validation

The new local-only Chromium tests pass for all four sports and Explore at
1440px and 390px. They cover initial URL queries, header/native search, real
zero-result filtering, Clear all, chip removal, category/store preservation,
Back/Forward, view/sport switches, stale-message rejection, the keyboard shortcut,
and empty catalogs/returning to a supported sport. See `search-results.json`.

The supported Python/embedded-JavaScript suite reports **763 tests, OK (9 skipped)**.
The nine legacy file-URL Chrome cases remain unsupported by this environment;
CI tests are unchanged. Publication/header/Explore/artifact focused tests also
pass. All **70** existing desktop/mobile four-sport regression checks pass,
including Quick View, alerts, retailer links, technical filters and navigation.

No scraping, email, merge or deployment was performed. Retailer image requests
are blocked during browser QA; screenshot image placeholders are expected.
The original advanced search remains in the catalog for its existing suggestions.

[Desktop](desktop.png) · [Mobile](mobile.png)
