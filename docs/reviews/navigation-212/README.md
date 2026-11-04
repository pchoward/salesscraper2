# #212 — Sport → category → contextual filters

A focused change to the current ShredDeals shell. The compact primary search,
wordmark alignment and utility actions remain. A crisp white browse row puts the
sport tabs beside a category picker. Choosing a category calls the catalog's
existing category button, which updates the existing contextual filters/results.
The former Products row is hidden only in the embedded site; store chips remain
visible below the header. No extra header row is added.

## What changed

* The picker derives its labels, category identities and availability counts
  from the active sport's real catalog controls. It does not serialize category
  lists or totals into the shell, add empty mockup categories, or build a second
  filter/count implementation.
* Menu choices use the existing category facet semantics. In particular, those
  counts can broaden category-specific size filters. The selected-category
  badge instead mirrors the actual result counter, so a narrowed wheel-size
  result does not claim the broader availability number.
* Search retains its existing precedence over browsing. When the existing search
  parser selects a different product type, the trigger says **Search results**
  and explains that clearing the query returns to unrestricted category browsing.
  No parsing, fuzzy matching, synonym, ranking or query-state logic is rewritten.
* Store selection survives category changes. Search, brand, prices, discounts,
  specifications, zero results and clearing filters update the existing native
  facet counts, which the picker mirrors as they change.
* Disclosure controls support keyboard focus, arrows, Home/End, Escape, outside
  clicks and focus leaving the panel. The menu scrolls within the available
  viewport, including a short tablet/landscape viewport.
* Changing sport/view closes the picker, hides old category controls, and releases
  old choices until the new catalog supplies its own categories/counts. Explore
  does not show stale Deals categories. Back/Forward restores the native state.
* Standalone catalog links retain their original controls. No catalog schemas,
  retailer adapters, discovery, ingestion, prices, scoring, cards, Quick View,
  history, alerts or parked V-Next files are changed.

The only catalog-side layout adjustment skips the now-hidden Products cluster
when fitting the remaining store chips. The underlying category controls remain
in the document for the existing implementation and backwards compatibility.

## Validation

* **20 new category-navigation cases passed** across Skate, Ski, MTB and BMX at
  1440, 1024, 768, 430 and 390px, including a short landscape viewport.
* Checks cover real category selection, wheel-specific filters, original facet
  count parity, actual result badge parity, store/brand/spec/price/discount/search
  combinations, zero results, clearing, retailer-first browsing, sport changes,
  canonical URL slugs and Back/Forward.
* **166 existing four-sport browser checks passed**, including variant-aware
  filters/prices, Quick View, retailer links, Watch/alert capabilities, grouping,
  responsive layout and navigation.
* Existing header/search regression cases and all four public Explore viewport
  checks passed. Autocomplete, keyboard/pointer selection, shortcuts, query chips,
  sorting and the underlying search engine are retained.
* Supported Python/embedded JavaScript suite: **789 tests, OK (9 skipped)**.
  The same nine legacy file-URL Chrome cases remain unsupported here and were
  skipped only by the local runner; none were disabled in CI. Focused publication
  and navigation tests also passed after the final UI changes.
* New browser checks and their screenshot artifact are included in normal PR CI.
  Publication regenerated the public assets with the existing content-versioned
  URLs. There are no new dependencies or public source/data folders.

Commands (existing Playwright infrastructure; no live retailer requests):

```sh
python ci/build_preview.py /tmp/navigation-212 --label "Navigation QA"
BROWSER_BINARY=/usr/bin/chromium node ci/check_category_navigation.cjs /tmp/navigation-212 /tmp/category-shots
BROWSER_BINARY=/usr/bin/chromium node ci/check_header_search.cjs /tmp/navigation-212 /tmp/search-shots
python -m unittest test_shreddeals_publish test_shreddeals test_sport_facets -v
```

## Before/after — same saved category and data

Desktop:

| Sport/category | Before | After | Open picker |
| --- | --- | --- | --- |
| Skate / Wheels | [Before](before-skate-1440.png) | [After](after-skate-1440.png) | [Picker](menu-skate-1440.png) |
| Ski / Skis | [Before](before-ski-1440.png) | [After](after-ski-1440.png) | [Picker](menu-ski-1440.png) |
| MTB / Forks & Shocks | [Before](before-mtb-1440.png) | [After](after-mtb-1440.png) | [Picker](menu-mtb-1440.png) |
| BMX / Bikes | [Before](before-bmx-1440.png) | [After](after-bmx-1440.png) | [Picker](menu-bmx-1440.png) |

Mobile:

| Sport/category | Before | After | Open picker |
| --- | --- | --- | --- |
| Skate / Wheels | [Before](before-skate-390.png) | [After](after-skate-390.png) | [Picker](menu-skate-390.png) |
| Ski / Skis | [Before](before-ski-390.png) | [After](after-ski-390.png) | [Picker](menu-ski-390.png) |
| MTB / Forks & Shocks | [Before](before-mtb-390.png) | [After](after-mtb-390.png) | [Picker](menu-mtb-390.png) |
| BMX / Bikes | [Before](before-bmx-390.png) | [After](after-bmx-390.png) | [Picker](menu-bmx-390.png) |

Screenshots use saved catalogs, not a live scrape. External requests are blocked
in browser QA, so retailer image placeholders are expected. Baseline shell assets
come from main; the same category is selected for each before/after comparison.
Firefox/WebKit were not exercised. The new primary flow is sport then category;
retailers remain independently selectable, including retailer-first browsing.
The full V-Next redesign and hero/brand imagery remain parked.

Owner review/merge is required. No automatic merge, production deployment,
scraping, discovery runs or subscriber messages were performed.
