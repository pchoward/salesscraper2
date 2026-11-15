# Navigation link audit — 2026-11-14

Task 15 / PR #287, checked against main's committed catalogs at `c4f255a`, using an inert rebuilt preview. Desktop: 1440 px; phone: 390 px. No retailer inventory was changed or scraped.

## Findings and changes

**Confirmed:** Skate's `type=packs` URL decoded to its default category, Decks. `slugType()` lacked both Packs aliases. The same omission existed in the Python URL model, although the browser uses JavaScript to restore its filters.

Added `pack` and `packs` aliases and the existing canonical `packs` output in both URL codecs. Skate's JavaScript category fallback now reads its rendered category options, so future menu headings can resolve without another fixed-map entry. Existing category slugs, defaults, URL keys, saved-view format, and localStorage keys remain unchanged.

**No additional broken internal navigation routes were found** in the checks below. In this data snapshot, Skate Packs correctly showed 84 results on desktop and phone, with a Packs breadcrumb and pack-only rows. This is a routing fix, not an inventory expansion.

## Browser audit

| Area | Checks | Outcome |
| --- | ---: | --- |
| Category deep links across all four sports, including All | 98 | Passed |
| Corresponding category menu selections | 98 additional selections | Passed |
| Store slug encoding, decoding, and URL-state restoration | 140 | Passed |
| Deals, Track, and Insights section controls | 24 | Passed |
| Internal anchors, destination HTTP responses, and fragment targets | 8 | Passed |
| Subscribe panel open/close or expected disabled state | 8 | Passed |

The core recorded audit contains 270 checks plus the 98 menu selections; eight additional Subscribe checks passed. Across these checks, no browser errors occurred. The anchor inventory included the shell's skip-navigation and standalone-catalog fallback links. The rendered catalogs contained no other internal footer anchors.

The existing public Explore browser suite separately passed at 1440, 768, 430, and 390 px, covering entry to Explore and return to Deals. Unsupported Subscribe controls retain their existing disabled behavior; no subscriptions or messages were sent.

## Regression coverage

The complete Python and embedded JavaScript regression suite passed: **967 tests**.

- The unit regression failed on the original code at `Skate: Packs`, then passed with the fix.
- Every heading in `page.py`'s `PART_ORDER` round-trips in JavaScript and the Python URL model. JavaScript also checks every configured heading for BMX, Ski, and MTB, a synthetic future category, old canonical slugs, both Packs aliases, and unknown categories.
- `ci/check_category_navigation.cjs` now selects every available Skate heading and reloads its deep link at desktop and 390 px. It checks the selected category, visible rows, breadcrumb, and counts, and saves Packs screenshots in the existing browser artifact.
- The expanded category browser suite passed on all four sports at both widths.

## Scope

This audit verifies first-party navigation and URL handling against saved catalog data. External retailer product-page availability, checkout, and outbound destination redirects were not tested. The intermittent bridge initialization errors have their own Task 14 branch; this change stays independent of it.
