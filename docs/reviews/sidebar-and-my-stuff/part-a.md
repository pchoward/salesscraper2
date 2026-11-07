# Part A — sidebar ends at Price

Brand and the current type's main size/spec controls stay first, followed by
Store and one **Price & discount** section. Both discount bounds and both range
sliders remain; the minimum is labeled **At least % off**, then **Up to % off**.
Store uses the original select and count updates, with no duplicate IDs. Top-row
store chips remain.

**More** contains Deal quality, Deal type and Price-drop window. It starts closed,
uses the existing section preference key with the new `more` section ID, and
opens relevant controls when filters are activated/restored. The badge counts
active controls. Existing preferences, including the old Discount entry, are
preserved. Saved views, Watching and Bookmarks remain last under My stuff until
Part B. Show results stays last in the mobile drawer.

No URL parameter names, state fields, storage keys, saved-view formats, sport
headings, category order, extraction, card behavior or alerts were changed.
The sidebar order is recorded in `docs/menu-wireframe.html`.

Local validation:

* Full Python/embedded JS suite: **861 tests, OK, no skips**.
* Worker Node tests: **5 passed**.
* New sidebar checks: **8 passed**, all four sports at 1440/390px.
* Existing category/filter/count checks: **20 passed**; sport menu checks:
  **16 passed**; search: **10 passed**; Explore: **4 passed**; smoke passed.
* Existing full four-sport audit: **166 passed**, including variants, Quick View,
  retailer links, Back/Forward, layout and labeled synthetic boundary fixtures.
* Updated `test_page_layout.FilterOrderTests`, `test_report_extras` and relevant
  polish expectations; new `ci/check_sidebar.cjs` runs in PR CI.

Managed Chrome blocks file URLs. For the legacy DOM CLI tests only, the unchanged
HTML/JS fixtures were served on local HTTP and rendered by installed Chromium
through Playwright. Assertions were not changed or skipped. Normal GitHub CI
continues using its existing Chrome test harness.

Screenshots: [desktop](part-a-desktop.png), [mobile drawer](part-a-mobile.png).
The checked-in screenshots/results use the tested saved-data snapshot; later
main merges may update inventory counts without changing this UI.

GitHub PR creation/check monitoring is blocked by the environment's Forbidden
response from `api.github.com/graphql`. These results are local validation;
they are not a claim that GitHub required checks have completed. No merge or
deployment was performed.
