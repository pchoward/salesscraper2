# MTB catalog — issue #135

Branch: `codex/mtb-catalog`, based on live main after #141. No production data, workflows, or existing sport histories are changed. Claude's live multi-sport engine owns scheduling, state and publishing; these adapters plug into its existing MTB registration. No affiliate integration.

## Sources and verification status

| Retailer | Shopify collection | #137 sampled products / markdowns | Accepted live MTB listings |
| --- | --- | --- | --- |
| Worldwide Cyclery | `deals` | 133 / 35 | Pending Actions verification |
| Fanatik | `fanatik-outlet` | 27 / 27 | Pending Actions verification |

The #137 numbers are research leads, not completeness thresholds or promised listing counts. No original probe JSON was available. Reproducing the probe locally was blocked by the environment's retailer access policy. Do not interpret synthetic QA inventory as merchant data. Access-rule findings and real retained counts must be reviewed from the Actions run before merging.

Run **Actions → ShredDeals - Preview Site → Run workflow**, with **Scrape `mtb`** and **Branch/ref `codex/mtb-catalog`**. The existing workflow produces the phone preview link and saved catalog. This environment cannot dispatch Actions or open PRs through the GitHub API (Forbidden); git branch pushes work. No production scrape has been run for this task.

## Implementation and boundaries

`sports/mtb/stores.py` uses the shared Shopify parser and pagination, with MTB-only classification and specification modules. Categories are Bikes, Frames, Forks & Shocks, Wheels, Tires, Drivetrain, Brakes, Cockpit, Pedals and Protection. Explicit road/gravel/BMX and unrelated apparel are excluded; unidentified equipment is not silently treated as a complete empty scrape. Trail, enduro, downhill and dirt-jump labels are collected when explicitly present; generic MTB components remain eligible.

Exact wheel size, fork travel, frame size, tire width, axle dimensions, rotor diameter and riding labels come from titles, named variant options, explicit description labels and HTML specification tables. Unknown or conflicting dimensions are withheld. Offset and shock stroke are not suspension travel. Manufacturer model numbers do not establish compatibility.

One canonical product URL remains one listing. Variant offers retain their own prices, compare-at prices, stock flags and specifications. Multiple active filters must match the same eligible variant. Filtered prices and “Was” amounts reflect that matching offer; history identity and historical calculations remain unchanged. Known sold-out offers are excluded; unknown availability remains “Check store”, never an asserted in-stock offer.

### Integration handoff

Only the MTB entry in `sports/__init__.py` changes scraper/rule registration. No shared Shopify parser changes are needed. `page.py` has a small MTB-only facet/config insertion; `page.js` has guarded optional `SportSpecFilters` hooks for filtering, prices, state and browser navigation. `previews/sport-filters.js` is an optional configurable module, not a new page engine. Existing Skate/BMX query state is unchanged when the module is absent. Claude's main-branch non-Skate alert guard is retained. Grok/Claude should review these small shared UI hooks alongside ongoing page work.

### Requests and safeguards

Per retailer/run: one robots.txt request, existing collection pagination, and at most 40 optional `.js` stock lookups for relevant discounted products whose feed lacks stock flags. No browser startup or unconditional individual product-page requests. Results (including failures) are cached across all ten category calls. Every collection/stock URL is robots-checked and rate-limited using the shared delay or a greater advertised crawl delay. Missing robots policy fails closed except a 404. A failed collection page fails the retailer instead of publishing a partial complete scan; normal engine stale-data protection is preserved. Stock lookup errors, disallowed URLs or exhausted budget leave availability unknown without failing the retailer. Applicable retailer terms still require review; robots checks do not establish permission beyond the published policy.

## Isolated local review

Use saved, valid MTB scan state without fetching or sending anything:

```bash
python -m previews.mtb_catalog --data-root /path/to/saved-state --output-dir /tmp/mtb-review
# Open /tmp/mtb-review/index.html (or serve this directory for browser navigation).
```

The command requires saved MTB catalog/checkpoint metadata and preserves its original timestamp. It refuses empty or invalid saved state. It prints the exact homepage path, writes outside the checkout into a new output directory, disables alerts, and never updates source state.

For parser/UI QA only:

```bash
python -m previews.mtb_catalog --fixture --output-dir /tmp/mtb-fixture-review
```

This explicitly labeled synthetic fixture contains 12 listings; it is not a real catalog or evidence of current retailer pricing. The fixed fixture scan timestamp is not presented as a new scan. The review manifest records `synthetic`, `scraping: false`, and `delivery: false`.

## Validation

Fixture regressions cover both retailer configurations, exclusions, dimensions, ambiguity/conflicts, variants, stock uncertainty/budgets, robots/pagination failures, request caching, isolation, renderer integration and URL state. The synthetic Firefox review passed at 1440×1000 and true mobile 390×844: same-variant filtering, current/compare-at prices, impossible sold-out combinations, clear, sort, Quick View, Back/Forward, mobile drawer, retailer links and absent alert configuration.

Screenshots below are **synthetic QA only**, pending real Actions inventory verification:

- [Desktop](screenshots/mtb/desktop-mtb.png)
- [Mobile](screenshots/mtb/mobile-mtb.png)
- [Mobile filters](screenshots/mtb/mobile-filters.png)
- [Quick View](screenshots/mtb/desktop-quickview.png)
- [Browser results](screenshots/mtb/browser-results.json)

Eight existing Chrome-dependent tests cannot run in this environment; the separate Firefox review is additional coverage, not a claim those Chrome cases passed. See the PR for final suite counts.
