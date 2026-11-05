# Issue #212 — sport hover, focus and touch menus

Implements the approved November 4 clarification on top of the merged navigation.
The existing logo/search/utility row and compact sport row remain. Hovering or
focusing any sport now opens its categories immediately, without first clicking
the separate category readout. The readout still shows the current result scope.

## Interaction

* Desktop: hover a sport, move into its compact menu, and choose a category.
  Hovering/focusing another sport previews it without changing the current results.
  Clicking a sport opens its All products catalog with stale filters cleared.
* Keyboard: focus opens the menu; Left/Right/Home/End move between sports without
  navigating. Down enters category choices, including after loading. Arrow keys
  move among enabled choices; Enter/Space selects. Escape closes and returns focus
  without reopening. Tab leaving the navigation closes it.
* Touch: tap a sport to open its menu; tap a category or All products to navigate.
  The menu uses two compact columns on mobile, with constrained height and scroll.
* Menus close after category selection, outside clicks, Escape, or pointer exit
  with a 180ms tolerance. Pointer movement across the tab/menu boundary is safe.
  Loading utility links cannot reopen a menu under a stationary pointer.
* Selected sport/category states, URL deep links, Back/Forward, visible store
  chips and category-specific sidebar controls remain catalog-owned.

## Taxonomy, counts and loading

There are no hardcoded example categories, duplicate filter engine or new data
schema. The shell mirrors the catalog's actual category buttons and live native
facet counts. Active-sport category choices preserve the existing own-facet
exclusion semantics; the adjacent result readout reports actual matching rows.
Inactive zero-count choices are disabled as before.

Publication writes `navigation/<sport>-categories.json` from the published
catalog's own category controls (category, order and total count, plus its native
URL slug). The shell fetches and caches this small metadata file for inactive
sports. A content hash in each URL refreshes metadata when a new shell is
published. No inactive catalog is loaded, parsed or mounted in the browser.
The only catalog frame is the selected sport's visible application.

Inactive menus clearly label their counts as totals before filtering. Once a
sport is selected, the existing catalog bridge takes over with live facet counts;
a late metadata response cannot replace that live source. Failed metadata requests
show a retry message and can be retried by reopening the menu. The checked-in
files total about 2.2 KB uncompressed across all four sports (MTB: 622 bytes).
No scraper, inventory request, duplicate filter engine or additional service is
required. The previous hidden-preview-frame implementation has been removed.

## Validation

### Metadata revision

* 59 focused publication, navigation, preview artifact and public-safety tests passed.
* 16 menu cases passed with explicit assertions that inactive sport menus make no
  catalog requests, add no frames and cache metadata fetches.
* The full 20-case count/filter matrix passed; eight desktop/mobile cases passed
  again after the final departing-catalog count guard.
* All 10 search/Explore regression cases passed again.
* Screenshots and menu/search/count result files have been refreshed for this revision.

### Original menu build

* New sport menu checks: 16 passed across all four sports at 1440, 768, 430 and
  390px, including real touch emulation, pointer transitions/dismissal, keyboard,
  inactive-sport selection, All products, result categories and Back/Forward.
  These also assert that hovering/tapping never requests an inactive catalog,
  creates no additional frame, and fetches each metadata file at most once.
* Existing header/search checks: 10 passed, covering autocomplete, query chips,
  keyboard shortcuts, history, standalone search and Explore switching.
* Existing category/filter/count matrix: 20 passed across five viewport widths,
  including combined filters, zero results, native count parity and history.
* Supported Python/embedded JavaScript suite: 800 tests passed, nine skipped only
  in the local runner because the legacy Chrome file-URL harness is unsupported.
  No tests were disabled in CI. Focused publication/navigation checks: 16 passed, including JSON taxonomy/order/counts,
  native slugs, output-catalog precedence and content versions.
* Existing four-sport audit: 70 checks passed at desktop and 390px, including
  Quick View, retailer links, Watch, technical-variant price oracles and six
  labeled synthetic missing-spec/sold-out/boundary cases.
* The four-sport audit's technical-history check now waits for committed URL state
  and restored technical selections instead of fixed 250ms delays. The additional
  catalog loading made that pre-existing timing assumption unreliable.

The new check runs in the existing PR browser job; screenshots join its existing
category-navigation artifact. No new framework or dependencies were introduced.
Production catalogs, scrapers, discovery, V-Next, sidebar extraction, product
cards, price/deal logic, Quick View, alerts and retailer links were not modified.

## Review screenshots

The menu images intentionally show another sport's preview over the currently
selected catalog where applicable; results images show the chosen category.
Images use saved catalogs, block external network requests, and show the existing
preview banner and placeholder images.

| Sport | Desktop menu | Desktop results | Mobile menu | Mobile results |
| --- | --- | --- | --- | --- |
| Skate | [Menu](menu-skate-1440.png) | [Wheels](results-skate-1440.png) | [Menu](menu-skate-390.png) | [Wheels](results-skate-390.png) |
| Ski | [Menu](menu-ski-1440.png) | [Skis](results-ski-1440.png) | [Menu](menu-ski-390.png) | [Skis](results-ski-390.png) |
| MTB | [Menu](menu-mtb-1440.png) | [Forks & Shocks](results-mtb-1440.png) | [Menu](menu-mtb-390.png) | [Forks & Shocks](results-mtb-390.png) |
| BMX | [Menu](menu-bmx-1440.png) | [Bikes](results-bmx-1440.png) | [Menu](menu-bmx-390.png) | [Bikes](results-bmx-390.png) |

The [previous merged navigation review](../navigation-212/README.md) contains the
baseline screenshots for comparison.

Local commands (saved catalogs only):

```sh
python ci/build_preview.py /tmp/sport-menus --label "Sport menu QA"
BROWSER_BINARY=/usr/bin/chromium node ci/check_sport_menus.cjs /tmp/sport-menus /tmp/sport-menu-results
BROWSER_BINARY=/usr/bin/chromium node ci/check_category_navigation.cjs /tmp/sport-menus /tmp/category-results
BROWSER_BINARY=/usr/bin/chromium node ci/check_header_search.cjs /tmp/sport-menus /tmp/search-results
```
