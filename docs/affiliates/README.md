# #136 — BMX affiliate programs and feed opportunities

**Decision:** do not activate affiliate links or register for any program yet.
This is a review-ready research packet and conditional implementation plan, not
merchant approval. No link transformer is implemented. All five programs remain
disabled, with no ShredDeals publisher/referral IDs configured, account applications or rollout.

As of **November 1, 2026 (Eastern)**, primary-source verification is incomplete.
The current environment's egress proxy rejected the cited public pages and then
the collector's robots requests with **CONNECT 403**. No merchant HTTP response or
current terms were obtained. That is an environment restriction, not evidence
that a program is closed, that a retailer refused us, or that no program exists.
The underlying requests are in [access-attempt.json](access-attempt.json).

The issue's grounded starting points are recorded as **unverified leads**, separate
from current contractual terms in [bmx-programs.json](bmx-programs.json). In
particular, do not put 1.6% and 30 days into a revenue forecast or active config
until the Source US listing and merchant terms have been checked.

## Approval matrix

“Unknown” means not independently verified; it does not mean disallowed or absent.
No application destination is invented when the actual program link is unavailable.

| Retailer | Application / program lead | Network | Commission / cookie | US eligibility | Deal / coupon / comparison policy | Deep links / affiliate feed | Restrictions / evidence confidence and date |
|---|---|---|---|---|---|---|---|
| **Albe's BMX** (current) | Application unknown; [merchant site](https://www.albes.com/) is a discovery/contact lead | Unknown | Unknown / unknown | Publisher country, traffic and destinations unknown | Unknown; obtain merchant-specific permission | Unknown / unknown | No verified active affiliate program; not a finding that none exists. Do not substitute customer rewards. **Unverified; attempted Nov 1, no verification date.** |
| **Circuit BMX** (current) | Application unknown; [merchant site](https://www.circuitbmx.com/) | Unknown | Unknown / unknown | Unknown | Unknown | Unknown / unknown | Ask whether a publisher partnership or permitted product feed is available. Referral/rewards are not equivalent. **Unverified; attempted Nov 1, no verification date.** |
| **Powers BMX** (current) | Application unknown; [merchant site](https://www.powersbmx.com/) | Unknown | Unknown / unknown | Unknown | Unknown, including clearance, seasonal sale and exclusive-code restrictions | Unknown / unknown | No verified current program or terms. Do not invent a commission for the existing store adapter. **Unverified; attempted Nov 1, no verification date.** |
| **Source BMX US** (current) | [FlexOffers directory lead](https://www.flexoffers.com/affiliate-programs/sourcebmx-us-affiliate-program/); application and merchant acceptance pending | **FlexOffers reported by #136; not reverified** | **Lead only: 1.6% / 30 days**; current terms unknown | “US” in the listing is not proof that our publisher country or every US-store URL qualifies | Unknown; obtain current merchant acceptance of price-comparison/deal/coupon traffic | Unknown / unknown, including whether the feed covers `us.sourcebmx.com` and size-level stock | Confirm active status, US versus UK scope, exclusions, reversals, attribution and feed rights. [BMX Union's historical disclosure](https://bmxunion.com/affiliate-disclosure/) is not current ShredDeals approval. **Lead only; attempted Nov 1, no verification date.** |
| **Dan's Comp** (expansion candidate) | [Official sponsorship page](https://www.danscomp.com/sponsorship-requests/i792) reportedly links **Affiliate Program Page**; exact application destination pending | Unknown; do not assume AvantLink or another network | Unknown / unknown | Unknown | Unknown; explicitly disclose our automated comparison, price history and deal listings when requesting eligibility | Unknown / unknown | Follow the actual official program link, verify terms and licensed feed availability before an adapter/application. Sponsorship is not an affiliate contract. **Official-domain lead cited in #136; attempted Nov 1, no verification date.** |

[AvantLink publisher information](https://www.avantlink.com/publishers/) is an
adjacent network lead. #136 reports support for comparison/deal-of-day publishers;
that page was also blocked here. It establishes neither an AvantLink relationship
for any of these five merchants nor approval under a merchant's own terms.

## Recommended order — feeds first, activation later

1. **Verify Dan's Comp and Source US in parallel.** Dan's has the issue's direct
   merchant-to-program lead; follow that actual link and record the application
   destination/network. Source has a named network lead and specific advertised
   terms to check. Neither is currently ready to enable. Choose the first pilot
   by verified publisher acceptance and useful feed access, not the headline rate.
2. **Ask Albe's, Circuit and Powers about direct publisher/feed partnerships** if
   public program discovery yields no verified application. Existing retailer
   coverage makes feed improvements useful even without commission. The unsent
   template below is ready for owner review; no outreach has occurred.
3. **Prefer authorized data feeds** with canonical retailer product URLs, stable
   product/variant IDs, USD prices, retailer compare-at versus observed-history
   distinction, stock by variant and reliable timestamps. Assess exact 20/22-inch
   wheel compatibility, top-tube/bar/crank/axle fields, image rights, licensing,
   cadence, rate limits, partial-feed handling and withdrawal rights. Price-only
   feeds with no availability may be less useful than the current store adapter.
4. **Keep current collection methods unchanged.** The repository uses public
   Shopify collection adapters for the four current stores. Those adapters and
   observed listings are not proof of an affiliate feed license, automation
   permission, a commission relationship or permitted image redistribution.
   Affiliate approval likewise does not override robots/retailer access rules.
5. **Only after owner and merchant approval**, implement one retailer at a time
   under the optional outbound-link contract below, with a separate review PR.
   No forced monetization and no conversion of historical URLs or data files.

## Exact questions to settle before an application or pilot

For each candidate, record a dated primary source or written merchant response:

- Active program, official application URL, network/legal merchant, accepted
  publisher geography and the correct US destination/currency/domain.
- Commission basis (net merchandise versus gross), category/brand exclusions,
  new/existing customer rates, attribution window/model, reversal/return rules,
  coupon deductions and payment thresholds. A cookie duration alone is not a
  guaranteed attribution period across every browser/device.
- Explicit eligibility for ShredDeals' price comparison, historical prices,
  automated catalog/stock collection and deal listings; whether coupon traffic,
  exclusive codes, paid search/trademark bidding, email, social or sub-affiliates
  need additional permission. Do not infer restrictions or permissions.
- Product deep links preserving variant/query parameters; link generation API
  and failure behavior; whether tracking requires scripts/cookies we do not use.
- Licensed feed/API access, variant-level stock/specs and timestamps, product
  identity mapping, image/cache/retention rights, refresh limits, cost and data
  access if the commission relationship ends.

A customer **refer-a-friend**, loyalty-points or rewards offer is a separate
consumer benefit. Do not put it in the affiliate column or automate self-referral,
customer accounts or checkout rewards. A sponsorship/ambassador offer also needs
its own terms rather than being assumed to cover a comparison publisher.

## Unsent partnership / feed inquiry

> We operate ShredDeals, an independent deal and price-history comparison site,
> currently tracking BMX products with retailer-first links. Do you offer a
> publisher affiliate program or a licensed product feed/API for this use?
> Please share the official application and terms, accepted publisher countries,
> treatment of deal/comparison/coupon sites, US-store deep linking, commission
> and attribution terms, and product/variant pricing, stock, specifications and
> image rights. A reliable permitted feed is valuable even without commission.
> We will not activate tracking or use a partner feed before approval.

No email/address is fabricated and no message, form or registration is sent.
Owner approval and accurate business/contact details are needed before outreach
or applications; confidential network credentials do not belong in this document.

## Optional outbound links — design only, requires separate approval

Keep **raw `item.url` authoritative** through scrapers, normalization, identity,
price history, health, matching, saved filters, Quick View and alert state. Never
replace existing JSON/history keys with tracking URLs. In the current code,
Shopify builds canonical product URLs, `normalize_url` feeds history/identity,
and `page._card_store_link` renders the outgoing retailer link. The regression
checks the current direct URL with its variant query and fragment intact.

The eventual transformer belongs at the **final outgoing website href boundary**,
not in the scraper or `normalize_url`. A per-retailer allowlisted setting defaults
to disabled; it requires the actual approved network format and issued publisher
identity. Unknown retailer, disabled program, invalid destination, absent ID or
configuration error falls back to the original direct URL. No invented IDs,
generic redirect service, tracking on page load or changes to checkout behavior.

Preserve the entire canonical destination—including encoded query, variant and
fragment—inside an approved deep link. Match exact retailer/network hosts; reject
credentials, non-HTTPS destinations, open-redirect inputs and deceptive suffixes.
Keep retailer labels and **`target="_blank"` / `rel="noopener"`**, adding
`rel="sponsored"` only on actual affiliate links. The action remains a normal
user-initiated link to that retailer/product, with no new cart, interstitial,
JavaScript navigation or automatic redirect flow. Confirm any network redirect
requirements with the owner; do not silently sacrifice the retailer-first
experience to attribution.

When enabled, show **“Affiliate link — we may earn a commission.”** visibly beside
the affected retailer link, with an explanatory site disclosure as well. A hidden
footer, tooltip or generic disclosure alone is insufficient for this design.
Disabled/direct links must not claim an affiliate relationship. Grok owns catalog
link/disclosure markup; Codex owns header navigation; Claude owns canonical data,
engine/CI. Coordinate the implementation rather than rewriting those areas.
Initially leave subscriber emails, alerts, browser URLs/history and copied
canonical product links unchanged; email monetization needs separate approval.

Post-approval tests should cover each retailer flag on/off, exact-host matching,
query/fragment encoding, malicious destinations, safe fallback, no mutation of
item/history/state, retailer label/new-tab behavior, visible per-link disclosure,
network outage and independent rollback. These are an implementation checklist,
not a claim that affiliate transformation already exists in this PR.

## Finish source verification through Actions

The new **Research - BMX Affiliate Sources** workflow is **manual only**, with a
read-only token, no secrets, no persisted checkout credentials and no publishing.
It does not run existing scraper/notification/deployment workflows. This is a
small CI-owned addition explicitly submitted for Claude's review in this PR.
It has not been triggered; the owner can review/merge the research tooling first.

After that, GitHub app → repository → Actions → **Research - BMX Affiliate
Sources** → **Run workflow**. Open the summary and download the
`bmx-affiliate-research` artifact. It contains `evidence.json` and `summary.md`:
public-source excerpts and actually discovered affiliate links, plus retrieval
failures/robots restrictions. It follows bounded approved-host program links,
including Dan's official Affiliate Program Page destination when on an allowed
host. Existing third-party referral/tracking URLs may be recorded as historical
links but are not followed; product/collection/cart/checkout paths are also blocked. A destination on an unlisted network host is reported but **not fetched**;
review the actual link and add only that needed host in a follow-up if appropriate.

The collector has eight fixed public seed sources, at most 24 pages total,
per-host pauses/crawl-delay handling and a 2 MB response limit. Redirects cannot
escape the HTTPS host allowlist or skip robots. A missing robots file (404) is
recorded and public-page reading may proceed; other unavailable robots policies
stop that host. It does not log headers, cookies, credentials or raw scripts,
execute remote JavaScript, log in, submit forms or fetch product catalogs.
Login-only, JavaScript-only or unreadable terms remain unverified.

**A successful GET/workflow is not merchant approval.** Review excerpts in
context, confirm current terms and eligibility, then update the matrix with
primary-source citations and dates. All tracking stays disabled. If no pages
can be retrieved the command exits 2 and the workflow reports failure while
retaining the evidence. Local equivalent:

```bash
python -m research.affiliates --output-dir /tmp/bmx-affiliate-research
python -m unittest test_affiliate_research test_public_diagnostics test_ci_preview
```

The output directory must be new and outside the checkout. Research code, tests,
source records and evidence are excluded from GitHub Pages. No production product
links or identity/state files are changed. Current live commercial terms remain
an explicit open dependency until evidence is obtained; do not close #136 as
fully verified or approve a monetization rollout from this packet alone.

Validation: **32 relevant tests passed** (research contracts, bounded collection,
manual/read-only workflow, current direct retailer URLs and public-data isolation).
Python syntax checks also passed. Live source terms are not validated by these
offline tests; the eight attempted hosts remain blocked by the environment proxy.
