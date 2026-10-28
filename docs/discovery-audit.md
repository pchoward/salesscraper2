# Retailer discovery audit

This is a read-only local diagnostic, separate from the daily scrape. It imports the four current retailers' configuration factories, but never calls their scrapers, parsers, browser, feeds, caches, or debug writers. It performs no network requests and writes only to stdout. No schedule, source, filtering, monitoring, or retailer behavior changes are introduced.

## Manual invocation

From the repository root, using the repository's installed Python dependencies:

```bash
source .venv/bin/activate
python -m audit.discovery
python -m audit.discovery --format json
python -m audit.discovery --manifest tests/fixtures/discovery_audit/manifest.json --catalog tests/fixtures/discovery_audit/catalog.json
python -m unittest test_discovery_audit
```

The first two commands inventory the **current** configured store/category pairs (27 with Protection at CCS, Zumiez, and Tactics) and their entry points, pagination strategy, limits, and dynamic-query caveats. They do not fetch or parse retailer pages. `--catalog` requires `--manifest` and never changes the catalog.

The fixture example is explicitly **synthetic**, not a live capture or inventory estimate. Its two saved Tactics bearing pages contain three distinct candidates, including one duplicate across pages. Against the one-product synthetic saved catalog, two candidates are absent. A page-3 link remains unprovided. This demonstrates a discrepancy and an incomplete evidence set, not two confirmed missing valid sale products.

For your own comparison, create a local manifest in this format. Paths are relative to that manifest; absolute local paths also work. Supply evidence files already obtained through permitted means, not credentials or session cookies.

```json
{
  "version": 1,
  "label": "Permitted saved evidence; capture date and provenance here",
  "observations": [
    {
      "store": "Tactics",
      "category": "Decks",
      "kind": "html",
      "file": "saved-sale-page.html",
      "source_url": "https://www.tactics.com/skateboard-decks/sale"
    }
  ]
}
```

Then run:

```bash
python -m audit.discovery --manifest /path/to/local/manifest.json --catalog previous_data.json --format json
```

Supported kinds:

- `html`: retailer listing anchors, CCS embedded `data-product` objects, and JSON-LD `Product`/`ItemList` identities. A missing/unrecognized grid is inconclusive, rather than evidence of zero inventory. Pagination links are reported, never followed.
- `json`: a locally saved CCS `products` feed batch. Products are deduplicated by URL; variants are not separate products. A full batch is flagged as requiring another page to establish completion.
- `sitemap`: `urlset` or `sitemapindex`, including namespaces. Child sitemaps and page URLs remain separate from product counts; nested image URLs are excluded. No recursive fetching occurs.

Observations must identify an existing category and one of the four existing retailer hosts. External links and unsafe URL schemes are excluded. Product identities omit fragments and query strings, so tracking/variant links do not inflate counts. Pagination URLs retain their queries. Repeated evidence pages are deduplicated at the product-identity level. Unprovided pager links may include earlier or alternative pages, not just the next page.

The JSON output includes each evidence file/source URL, candidate URL lists, sitemap links, parser uncertainty notes, unprovided pagination URLs, unique observed candidates, saved filtered counts, and candidate identities absent from the saved catalog. An absent saved category is **unknown**, not a zero count. Raw page/feed candidates can be full-price, sold out, out of scope, miscategorized, intentionally filtered, or from a different scan date. They are never labelled confirmed missed inventory. Feed comparisons also depend on the manifest author's category assignment; the audit does not classify feed products itself.

## Findings from current code

Source references below refer to functions/classes rather than fragile line numbers. None of these findings establishes a live missing-product count.

| Retailer | Evidence in current configuration | Potential gap / estimated opportunity | Confidence and next step |
| --- | --- | --- | --- |
| CCS | `stores/ccs.py:scrapers` uses `CCSScraper`/`CCSDecksScraper` for decks, wheels, and trucks, inheriting `stores/base.py:Scraper.scrape` (one page). Bearings, sneakers, and accessories use `CCSCatalogScraper` and a shared clearance feed. | **High priority:** three categories lack a pagination walk. The existing paginated clearance feed could provide a parity reference for those three categories. Valid additional product count is unmeasured. | High confidence in the architectural difference; low confidence in inventory uplift until permitted same-date/category/eligibility comparison. Do not switch production sources in this PR. |
| Skate Warehouse | `SkateWarehouseScraper` inherits one-page fetching; `SkateWarehouseMultiScraper.scrape` iterates six configured accessory URLs without following pagination. Bearings/accessories require markdowns. | **High priority after permission review:** all six categories lack an explicit pagination walker. Alternate sale/category paths may contain candidates. No numeric valid-product uplift is established. | High confidence about code behavior; pagination may not actually be needed on every current page. Check permitted saved pages for next links and declared totals before proposing changes. |
| Zumiez | `ZumiezScraper.scrape` walks up to 30 pages, configured `PAGE_SIZE=60`, and stops on a short grid without a next link or repeated raw URLs. Hitting the cap returns accumulated products. Sneakers can expand to tracked-brand queries only under live robots permissions. | **Medium priority:** cap/repeated-grid/partially hydrated next-page responses can conceal a partial discovery result. The theoretical budget is 1,800 raw slots per query, not a measured catalog size or missed-product estimate. | High confidence in stopping behavior; frequency and missed volume unknown. Replay permitted saved pagination/hydration fixtures, distinguish terminal pages from inconclusive ones, and emit discovery diagnostics in a future change. Keep `/graphql` excluded. |
| Tactics | `collect_sale_pages` follows `pagination-next`, protects against failed requests, and stops on loops/redirects. It returns collected pages at the 20-page cap. | **Medium priority:** a cap, redirect loop, or nonempty shell without next links may appear terminal. No evidence that present inventory exceeds the cap. | High confidence in code path; live impact unknown. Future work should surface the termination reason and whether next-page evidence remained. |

CCS's existing feed fails at its 30-page cap and on invalid/failed batches, which is safer than silently returning a capped catalog. No recommendation here removes that protection. Existing product eligibility and brand/size/discount rules are intentional coverage constraints, not automatically discovery bugs.

## Limited public-source investigation — October 18, 2026

Requests used `SkateDealsDiscoveryAudit/1.0`, normal HTTPS verification and the session proxy. This was a small one-off inspection of robots files, indexes, home pages, and available policy pages, not a live catalog crawl. No product-page traversal, anti-bot bypass, account access, endpoint guessing, or new crawl schedule was used. Production scraping behavior was not changed.

| Source | Observed response / evidence | Meaning and limits |
| --- | --- | --- |
| `https://www.zumiez.com/robots.txt` | 200; disallows `/graphql`, broadly disallows `customFilters` queries with specific sale/brand exceptions; advertises `/sitemap.xml` and an image sitemap. | Preserve the query-specific rules. Robots permission alone is not terms approval. |
| `https://www.zumiez.com/sitemap.xml` | 200; a sitemap index with **2 child sitemap URLs** under `/media/sitemap/`. | Public discovery candidates, not two products or a sale feed. Children were not crawled. The retrieved homepage did not expose a terms link in the saved HTML; terms review remains incomplete. |
| `https://www.tactics.com/robots.txt` | 200; excludes account/cart/checkout/search and `/*/rp-` paths. | Do not use excluded searches as alternate discovery paths. |
| `https://www.tactics.com/` and `/info/terms-of-use` | Both 200; the homepage exposes the terms link. | A policy document was retrieved, not a grant of automated collection rights. The saved homepage had one JSON-LD block containing `Organization` and `WebSite`, not product inventory. No sale pages were traversed in this audit. |
| `https://www.skatewarehouse.com/robots.txt` | 200; excludes admin/search paths and advertises `/sitemap.xml`. | Public index availability does not override terms. |
| `https://www.skatewarehouse.com/sitemap.xml` | 200; **934 page URLs**, including **20 URLs containing `sale` or `clearance`** in their paths. | These are index URLs, many categories or out-of-scope apparel, not 934 products or 20 valid misses. Further live probing stopped after reviewing terms. |
| `https://www.skatewarehouse.com/termsofuse.html` | 200; terms restrict “data mining, robots, crawling, data gathering and extraction tools” and refer to bots/spiders/intelligent agents. | **Permission blocker for expanded automated investigation.** Review/obtain authorization before proposing a new live traversal; inspect already permitted local evidence in the meantime. |
| `https://shop.ccs.com/robots.txt`, `/agents.md`, and `/sitemap.xml` | All 200; robots advertises the sitemap; the index contains **30 child sitemap references**, including **19 product shards** and an agentic-discovery reference. | These are index shards across the store, not clearance-product counts. No child/feed/product crawl was performed. The published agent guidance requires appropriate agent identification/Web Bot Auth for hosted requests. That prerequisite was not established, so no expanded CCS live audit is proposed. |

The full live inventories, pagination parity, terms authorization for broader collection, and the number of additional **valid** sale products remain unverified. No volume estimate is fabricated from sitemap counts. The opportunity estimate is therefore structural: CCS has three categories to compare against an existing feed; Skate Warehouse has six categories to assess for pagination after permission review; Zumiez/Tactics need termination evidence before any cap changes.

## Next-step proposal: discovery separate from monitoring

1. Review retailer-specific authorization and current robots/agent requirements before obtaining additional captures. Use signed/supported identification where required. Stop at denials, challenges, or restrictions; do not bypass them.
2. Capture a small, same-date, explicitly permitted sample of entry pages, next pages, relevant feed batches, and declared counts. Keep capture URL/time, termination reason, and scope in the evidence manifest. Run this offline tool; distinguish missing capture pages from actual source coverage gaps.
3. Prioritize CCS feed-vs-HTML parity for the three HTML-only categories. Inspect each candidate with the existing eligibility rules and availability before counting it as a valid miss. Review Skate Warehouse only after its permission blocker is resolved.
4. In a separate PR, consider a discovery stage that emits candidate identities and provenance plus page-completion diagnostics. A price-monitoring stage should consume verified identities under the existing filtering and lifecycle safeguards. A sitemap loc is a lead, never evidence that a product is on sale or discontinued.
5. Keep production changes small: one retailer/category at a time, fixture coverage for terminal/partial/redirected/failed pages, and no rollout until permissions and measured opportunity are established. This PR makes none of those production changes.
