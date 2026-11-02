# ShredDeals scraper architecture review

**Research date:** 2026-11-02. **ShredDeals baseline:** [`ed941914`](https://github.com/pchoward/salesscraper2/tree/ed941914a9430bf3120c05c33c318b8d483a7ac5).

## Recommendation

**The existing architecture is sufficient for a bounded Dirt Jump Explore pilot.**
Keep the Python adapters, shared feed caches, JSON state, health safeguards and
GitHub Actions. Neither external project demonstrates a reason to rewrite them.
Explore needs a small, explicit inventory/offer path, not a new scraping framework.
It is **not a switch we can turn on today**: current adapters discard full-price
variants before rendering and history updates.

“Adopt Now” below means a requirement for the next pilot design, **not an
implementation made by this research**. No retailer requests, external project
execution, dependency installation, production code/workflow changes, or changes
to Claude's Mike's Bikes/retailer/filtering work were made. Unmerged integration
work is outside this pinned review.

## 1. External repositories: verified implementation, not feature claims

Both requested repositories exist and were accessible through native HTTPS Git.
Their default-branch trees were inspected at these exact commits:

| Repository | Verified revision | What is actually present |
| --- | --- | --- |
| [HasData/auto-ecommerce-scraper](https://github.com/HasData/auto-ecommerce-scraper/tree/97b1e709d3eda721316d12d2883ec0794250e889) | `97b1e709` | 11 tracked files: a small Requests/BeautifulSoup extraction package, Streamlit UI and exports. Shopify/WooCommerce HTML hints, Shopify JSON extraction, Product microdata, then scored repeating-container fallback. Optional HasData rendering/AI. |
| [HasData/ecommerce-price-scraper](https://github.com/HasData/ecommerce-price-scraper/tree/aca8e8f77048644e10d9c98cff0c39c7ea3a85ea) | `aca8e8f7` | 12 tracked files: README, requirements, image and eight standalone pricing examples. Decimal normalization, marketing-text cleanup, currency hints, selector hierarchy, browser-response capture, API/AI examples and a minimal SQLite tracker. |

Important qualifications from the code:

- Auto's [`scrape_shopify_products_json`](https://github.com/HasData/auto-ecommerce-scraper/blob/97b1e709d3eda721316d12d2883ec0794250e889/scraper/platforms.py#L154)
  requests **root `/products.json`**, regardless of the input collection. It
  paginates up to eight pages but returns success at that cap, without marking
  incompleteness. It keeps only the **first variant**, omits compare-at prices,
  and does not establish category membership or complete available inventory.
- Its HTML WooCommerce parser takes the first matching amount inside a price
  element; that is not proof it is the current sale price. The generic cleanup
  [drops fields seen in fewer than 30% of rows or with identical values](https://github.com/HasData/auto-ecommerce-scraper/blob/97b1e709d3eda721316d12d2883ec0794250e889/scraper/utils.py#L241).
  That can discard rare specifications or a valid shared currency/stock value.
- Price Toolkit's [hierarchy example](https://github.com/HasData/ecommerce-price-scraper/blob/aca8e8f77048644e10d9c98cff0c39c7ea3a85ea/examples/04_selector_hierarchy.py#L13)
  really does attempt JSON-LD → microdata → attributes → CSS, but **also calls
  HasData**; README wording that the first four examples run offline is too broad.
  Its JSON-LD handling selects the first offer and is not a general `@graph`,
  product-identity or variant resolver. The browser-response example is
  Nike-specific, not a general category crawler.
- Currency inference is not reliable enough to copy: the
  [symbol loop](https://github.com/HasData/ecommerce-price-scraper/blob/aca8e8f77048644e10d9c98cff0c39c7ea3a85ea/examples/03_currency_detection.py#L21)
  checks `$` before `C$`/`A$`/`R$`; without overriding context, an explicit
  Canadian-dollar string can be classified as USD. Marketing cleanup also
  removes “From,” losing the distinction between a minimum price and an exact offer.
- The [SQLite example](https://github.com/HasData/ecommerce-price-scraper/blob/aca8e8f77048644e10d9c98cff0c39c7ea3a85ea/examples/07_price_monitoring.py#L5)
  appends URL/price/currency/time and compares the last two prices. It stores
  money as `REAL`; converting it back to Decimal does not restore exact stored
  precision. Drop queries filter by URL, not currency or variant. There is no
  retention, completeness gate, lifecycle, or identity migration.

These are source-level findings, not live performance benchmarks. No dedicated
external test suite was found; normalization example 01 has inline sample assertions.
Neither repository uses Scrapy.

## 2. Comparison with ShredDeals

| Capability | Current ShredDeals | Demonstrated improvement / decision |
| --- | --- | --- |
| Platform detection | [`audit/store_probe.py`](https://github.com/pchoward/salesscraper2/blob/ed941914a9430bf3120c05c33c318b8d483a7ac5/audit/store_probe.py#L35) already recognizes Shopify, WooCommerce, BigCommerce, Magento, Salesforce Commerce and others. Production adapters are explicitly configured. | Already adequate for onboarding. Auto's three-way heuristic is narrower and can mistake generic product-card markup for Shopify. **Not Needed:** automatic production adapter selection. Detection does not imply a working WooCommerce inventory adapter. |
| Product/collection discovery | Configured sale collections, shared Shopify feeds and retailer-specific category/pagination adapters. [`audit/discovery.py`](https://github.com/pchoward/salesscraper2/blob/ed941914a9430bf3120c05c33c318b8d483a7ac5/audit/discovery.py#L93) can inspect saved feed, HTML, JSON-LD and sitemap evidence; it is not a full live discovery crawler. | **Adopt Now:** an explicit full-inventory category source plan for the pilot. Root `/products.json` from Auto is a possible permitted source, not proof of dirt-jump coverage and not a preferred store-wide crawl. |
| Structured extraction/fallbacks | Shopify JSON, retailer-specific embedded data (for example The House's `data-gtmdata`), explicit HTML parsers and additive specifications. Unknown/conflicting facts are retained as unknown. | Already stronger for known stores. **Consider Later:** a validated structured-data-first helper for an approved non-Shopify adapter. Borrow the hierarchy/provenance idea, not first-offer/global-price heuristics. |
| Pagination/completeness | [`stores/shopify.py`](https://github.com/pchoward/salesscraper2/blob/ed941914a9430bf3120c05c33c318b8d483a7ac5/stores/shopify.py#L172) caches feeds across categories, deduplicates product IDs/handles, and fails a collection on bad pages or the 20-page cap. Multiple configured collections can still yield a result when one fails. Other adapters have different guarantees. | **Adopt Now:** scope-level completion evidence, particularly for unions of collections. Auto's capped success is a regression. Existing [discovery audit](../discovery-audit.md) also documents one-page and cap/loop limitations; do not call the whole system complete. |
| Variant price, stock, specs | [`sale_variants`](https://github.com/pchoward/salesscraper2/blob/ed941914a9430bf3120c05c33c318b8d483a7ac5/stores/shopify.py#L329) excludes explicit sold-out variants; sport adapters attach per-variant offers/specs. Bounded product-stock enrichment exists. Missing stock is not verified availability. | ShredDeals is substantially ahead of first-variant or AI examples. **Adopt Now:** preserve all eligible inventory offers, allow missing compare-at, and retain same-variant matching. Do not infer stock/specs from aggregate product text. |
| Price history | [`history.py`](https://github.com/pchoward/salesscraper2/blob/ed941914a9430bf3120c05c33c318b8d483a7ac5/history.py#L1) has a 90-day detail window, lifetime summaries, stale pruning, missed-scan lifecycle and exclusion of retained/failed observations. Its stored series is listing-level sale-price history. | Already more capable than the SQLite demonstration. **Adopt Now:** an explicit inventory/variant observation basis; existing sale history must not silently change meaning. |
| Identity and matching | URL-keyed history, conservative size-change resets and alias reconciliation for a known Shopify host set. [`matching.py`](https://github.com/pchoward/salesscraper2/blob/ed941914a9430bf3120c05c33c318b8d483a7ac5/matching.py#L336) supports Skate decks/wheels/trucks/bearings, **not bike matching**. | No external improvement demonstrated. **Consider Later:** verified bike model/year/build/variant matching. Separate retailer listings are sufficient for the pilot; similar titles are not identity evidence. |
| Health/recovery | [`prepare_run`](https://github.com/pchoward/salesscraper2/blob/ed941914a9430bf3120c05c33c318b8d483a7ac5/pipeline.py#L29), [`health.py`](https://github.com/pchoward/salesscraper2/blob/ed941914a9430bf3120c05c33c318b8d483a7ac5/health.py#L1), per-store timeouts and retained prior data protect against failed/suspect scans and false new observations. | Preserve these. **Adopt Now:** separate Explore baselines and source/completeness diagnostics. Count-anomaly detection cannot prove first-scan or category completeness. |
| Permitted access/rate limits | Existing probes/policies, per-adapter delays, sequential store execution and bounded requests. MTB explicitly checks robots per feed/product fetch and limits supplemental stock reads. Policies are not uniform across every adapter. | Neither example supplies a better permitted-access scheduler. **Adopt Now:** verify the broader pilot paths and retailer authorization; existing sale access is not blanket permission for a full catalog. No proxy rotation, challenge bypass or paid extraction APIs. |

## 3. Minimal Dirt Jump Explore design

### Separate observation from Deals eligibility

**Proposed flow:** approved category discovery → normalized available offers →
one observation ledger → separate Explore and discounted-offer projections.

Keep current Deals inputs, filenames and sale predicates unchanged for the first
pilot. Do not remove the global sale gate or send full-price products through the
existing digest/notification pipeline. The barriers are concrete:

- `ShopifyStore` defaults to sale-oriented collections.
- `products_from()` calls `sale_variants()` before producing a listing.
- [`sports/offers.py`](https://github.com/pchoward/salesscraper2/blob/ed941914a9430bf3120c05c33c318b8d483a7ac5/sports/offers.py#L16)
  drops offers with no compare-at; MTB's `_item()` assumes one exists.
- History updates/pruning use existing item eligibility; renderers also assume
  Deals-oriented prices. Merely pointing an adapter at a full category is insufficient.

For the pilot, use a separate, small JSON state scope, for example
`catalogs/mtb/explore/dirt-jump/`, with inventory, observation history and scan
metadata. This is a proposed file scope, **not** a new sport or a database migration.
The legacy Deals writer remains the only writer of its current state. A future
explicit integration can consume the same pilot observations for both views;
do not run two competing writers over production history now.

### Define an offer that can represent full price honestly

Retain retailer, canonical product URL, provider product/variant IDs where
available, current price, explicit currency/market, stock state, variant options,
known specifications, observation time and source/completion provenance.
Compare-at/list price is **optional and separate**. Record whether a reference
price was directly stated or derived from a retailer's discount claim.

Use current price as the observed transaction offer, not evidence of a previous
price. A markdown requires **that offer's** valid compare-at above its current
price; missing compare-at means “discount unknown,” not a fabricated original
price. “From”/ranges remain aggregates unless tied to a purchasable variant.
For new pilot money handling, explicit units plus Decimal/decimal strings or
integer minor units avoid ambiguous floats/cents; standard-library support is
sufficient. Existing `_amount()` treats integers as cents in its expected input
format—do not reuse it on arbitrary dollar-valued JSON without an adapter contract.

Explore should advertise verified available offers. Unknown-stock offers can be
reported separately for investigation, not counted as confirmed available.
Do not turn “left the sale collection” into “sold out.”

### Stable identity and shared history: yes, with a fixed price basis

Mode must never be part of identity: no new URL or history key just because a
product moves between full price and sale. Keep existing canonical URLs and add
retailer product/variant identifiers as evidence; do not broadly rewrite current
URL keys. Current Shopify path reconciliation is limited to its known host set,
not a promise that every new MTB URL alias is recognized.

**Critical example:** variant A is full-price $100; variant B is discounted to
$200 from $400. Explore's cheapest available price is $100; Deals' cheapest
sale offer is $200. Combining those aggregates in one history creates a false
$200→$100 drop, even if neither variant changed price.

Start pilot **per-variant, per-currency/market** observed-price series and let
both pilot projections reference them. Retain listing aggregates with an explicit
basis if needed. Existing listing-level sale histories can remain visible with
that label, but must not be presented as historical prices of a particular
variant. Earlier full-price/variant history cannot be backfilled from a list
price, sitemap date, current compare-at or unmatched legacy aggregate.

### Discover a complete category, not every page on a store

Use one or a few retailer-approved dirt-jump category/collection feeds, then
reuse their downloaded products across projections. Prefer these over scanning
all products and fetching every product page. When only a permitted broader feed
exists, bound it and classify locally. Sitemap entries are discovery leads,
not proof of stock, price, discipline or completeness.

Use Claude's completed retailer adapters/probe results, including Mike's Bikes,
rather than parallel integration work. The current MTB classifier recognizes
Bikes and explicit `dirt jump` riding tags, but lacks a complete Dirt Jump
assortment contract. The pilot should include **complete bikes**, not frames,
forks, tires or accessories sharing a keyword; record discipline evidence and
leave uncertain products out of the confirmed set.

Record intended sources, page/cursor termination, caps, failures, distinct
product/variant counts, stock/spec unknown counts and scan time. Claim complete
only when every intended source finished and classification/stock coverage is
known. Preserve last-good inventory with a stale marker after partial failure;
do not create fresh price points or disappearance events from carried data.

## 4. Performance, storage and framework decisions

At the reviewed commit, saved catalogs/history—not a live inventory estimate—are:

| Sport | Catalog listings | Catalog JSON | Raw price-history JSON |
| --- | ---: | ---: | ---: |
| Skate | 1,082 | 839,569 bytes | 1,946,215 bytes |
| BMX | 338 | 621,323 bytes | 198,076 bytes |
| Ski | 1,415 | 2,658,129 bytes | 777,163 bytes |
| MTB | 32 | 37,451 bytes | 20,799 bytes |

These eight files total about **6.77 MiB**, excluding public HTML/history copies,
Git history and diagnostics. This supports trying bounded JSON state, not a claim
that an all-store inventory will stay small.

Request cost is driven by sources and stock lookups, not by whether an offer is
on sale. Reuse caches; paginate once per source. For `P` pages at allowed delay
`d`, inter-page waiting alone is roughly `(P−1)×d`, plus response/robots/stock
checks. Shared Shopify pages contain up to 250 products; MTB currently budgets
40 supplemental stock lookups per store. These are code limits, not throughput
measurements or guarantees of full coverage. Unknown stock can remain unresolved
when the budget is exhausted.

Measure requests, elapsed time, completion and serialized bytes in the first
permitted pilot runs before raising limits. Existing store timeout is 720 seconds;
the newer-sport Actions job is 30 minutes and sequential. Reuse its locking
principles for any later pilot scheduling, but do not lengthen or modify the live
job as part of research. Give Explore its own health scope so its larger counts
do not corrupt sale baselines.

Variant history grows with `variants × retained observations`, not product count
alone. For illustration, 100 products × 3 variants × about 90 daily observations
is roughly 27,000 points, **not a measured pilot size**. Bound detail retention,
retain useful summaries, and avoid committing raw page captures every run. Git
retains changes after current-file pruning; compression means repository growth
must be measured rather than equated to full file size per commit.

| Classification | Recommendation |
| --- | --- |
| **Adopt Now** | Keep adapters/JSON; separate capture from sale projection; explicit variant/price/currency/stock semantics; bounded category discovery and completion manifests; independent pilot state/health; regression fixtures for full-price, mixed-price variants, missing facts, sold-out offers and failed pagination. These close real Explore gaps. |
| **Consider Later** | Structured-data fallback with field provenance for a specific approved non-Shopify store; locale-aware price fixtures where a retailer needs them; verified manufacturer/model-year/build matching; supported conditional requests and bounded concurrency only after measuring a bottleneck. |
| **Consider Later** | A database can offer indexed variant/range queries, atomic concurrent updates and less JSON rewrite work **if** measured history volume, Git growth or multiple writers become problems. Establish those needs first; the sample SQLite tracker is not a migration design. No migration now. |
| **Not Needed** | Scrapy or another framework for this pilot: no demonstrated throughput advantage or large crawl frontier, and neither reviewed project uses it. A scheduler/database/service rewrite, Streamlit/pandas export UI, production generic-card guessing, AI extraction, paid APIs and proxy/bypass features add no justified pilot value or violate constraints. |

## 5. Licensing, dependencies and useful borrowing

Neither inspected tree contains a `LICENSE`, `COPYING` or explicit license grant;
“educational purposes” in a README is not an open-source reuse license. Public
access alone does not authorize vendoring. Clarify licensing before copying code.
No code was copied here.

Auto adds Streamlit, pandas, openpyxl and lxml for a UI/export tool we do not need.
Price Toolkit's requirements also list Playwright and a `python-decimal` package;
Python already supplies `decimal` and `sqlite3`. HasData rendering/AI/geo examples
introduce API dependence and, in some cases, proxy behavior excluded by this task.
No dependency adoption is recommended.

The useful borrowing is narrow: **make extraction-source provenance explicit,
prefer verified structured offers over visual price text, and keep observed
price/currency distinct from marketing reference prices.** ShredDeals already
implements the more important operational protections. For Dirt Jump Explore,
retain that foundation and design the inventory boundary and history semantics
before implementing anything.
