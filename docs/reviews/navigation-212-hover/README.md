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

An inactive sport is loaded on demand in one hidden same-origin catalog frame.
Its original controls calculate the available categories/counts; its bridge does
not install the main shell's search, utility or history forwarding. Only one
inactive preview frame is retained at a time. Menus say when counts describe the
other sport before applying filters. Choosing its category starts a fresh sport
scope using the native category URL slug. No scraper runs or live inventory
requests are used to populate menus.

This avoids publishing a second taxonomy/count dataset. The tradeoff is a first
hover loading delay and the cost of parsing one additional saved catalog. A
future lightweight catalog-owned navigation endpoint could reduce that cost;
that is outside this focused UI change.

## Validation

* New sport menu checks: 16 passed across all four sports at 1440, 768, 430 and
  390px, including real touch emulation, pointer transitions/dismissal, keyboard,
  inactive-sport selection, All products, result categories and Back/Forward.
* Existing header/search checks: 10 passed, covering autocomplete, query chips,
  keyboard shortcuts, history, standalone search and Explore switching.
* Existing category/filter/count matrix: 20 passed across five viewport widths,
  including combined filters, zero results, native count parity and history.
* Supported Python/embedded JavaScript suite: 800 tests passed, nine skipped only
  in the local runner because the legacy Chrome file-URL harness is unsupported.
  No tests were disabled in CI. Focused publication/navigation checks: 45 passed.
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
