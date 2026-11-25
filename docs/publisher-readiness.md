# ShredDeals publisher readiness

Baseline reviewed November 23, 2026 from the live site and repository at `65bc07f`. The publisher changes in this branch still need review and production verification.

## What the audit found

| Area | Baseline | Change or follow-up |
| --- | --- | --- |
| Publisher information | No dedicated About, Methodology, Contact, Privacy, Terms, or Affiliate Disclosure pages found in the live shell or source. The catalog Insights panel already has original price-change and retailer activity analysis. | Add static About, How it works, Contact and Guides, with links in the existing My stuff panel and a compact footer on publisher pages. [Policy drafts](publisher/policy-drafts.md) stay in `docs/`, excluded from Pages. |
| Canonical domain | HTTP apex and HTTPS www both resolved to the HTTPS apex. The root and Skate catalog had titles, but no canonical, description, or JSON-LD. | Add root and publisher-page canonical URLs, distinct titles and descriptions, and Open Graph text and URLs. Use verified name and URL in `WebSite` markup only. |
| Crawler entry points | No checked-in sitemap or robots file. The live sitemap returned 404; requests for robots and a nonsense URL produced error responses, including upstream 503s, from this environment. The existing generic error documents were not useful publisher navigation. | Add a sitemap of five stable URLs, a robots file that advertises it, and a custom noindex error page. Confirm the production host serves this page with HTTP 404 after release. |
| Catalog and indexing | The root shell loads sport HTML in an iframe. The saved reports include JS data and their renderer materializes cards on demand. The Skate response also contains raw merchant anchors. Interactive facets, search, and Quick View depend on JS. Quick View is a modal in the catalog, with no independently served product landing page. Explore Dirt Jump is explicitly a noindex demo. | Make publisher pages readable without JS. Keep query states shareable and the sitemap limited to stable pages. Defer Product/Offer schema until canonical detail pages have verifiable freshness and offer data. Use Article and BreadcrumbList only once reviewed articles and corresponding visible breadcrumbs exist. |
| Merchant links | Sampled 1,546 product and card retailer anchors in the live Skate HTML, spanning 14 hosts. The sampled links went to retailer domains, used `noopener`, and the only observed query keys were `variant` and `color`. No commission-related score input, affiliate configuration, or merchant click instrumentation was identified in the inspected catalog link code. This sample cannot establish commercial contracts, compliance, or the behavior of every redirect. | Preserve the links. Before monetizing, test current destinations and variants, verify each retailer’s permission and use terms, record paid-link behavior and privacy choices, and place a visible disclosure near qualifying links. Use `sponsored` when the link is commercial. |
| Accessibility and performance | Existing PR workflow has mobile and desktop browser checks, including catalog readiness and navigation. The live Skate HTML had no images with omitted `alt` attributes in the raw response. That is distinct from evaluating alt quality and matching every lazy image. The saved live Skate response was about 19 MiB uncompressed. | New pages are text and shared CSS with no JS, external fonts or analytics additions. Keep the catalog load path intact. See the PR test report for measured checks and their limits. |

## Editorial workflow

The Guides index links to methodology and live categories now. Review two initial articles together with the dated price evidence linked inside each file.

1. [How to tell whether a skateboard deck is a good deal](publisher/deck-deal-guide.md)
2. [What a price drop and a lowest observed price actually tell you](publisher/price-drop-guide.md)

For an approved article, copy the page structure and stylesheet from `guides/index.html`, give it a stable URL and unique description, and include the author or publisher, publication date, sources, and visible links back to Guides and the relevant catalog. Add accurate Article metadata and a breadcrumb only when the page displays that information. Add the approved page to Guides and update the sitemap in the same PR. Keep unapproved copy in `docs/`. RSS can wait until there is a publication cadence.

Useful next landing pages would be Skateboard deck deals (fit, reference price and deck-only comparisons), BMX bike deals (complete vs parts, fit and shipping), MTB component deals (standards and variant compatibility), and ski deals (lengths, bindings and seasonal timing). Each needs useful static text and a link to the corresponding live catalog. Start with decks, and avoid pages generated from every filter combination.

Ideas for later articles include deck width and wheelbase (measure your current deck, compare published specs, account for missing dimensions), BMX discounts (verify axle and driver compatibility, shipping and comparison prices), and MTB offers (confirm interface standards and compare like variants). Develop these only when there is evidence or a practical comparison to show. Link new guides from relevant pages and share useful analysis manually with relevant communities where their rules allow.

## Audience measurement

Cloudflare Web Analytics is already embedded in generated catalogs via `page.py` and observed on the live Skate catalog. The shell has no beacon, and CI removes it. A catalog iframe load may show up as a catalog visit or sport transition. It should not be assumed to represent a new person, and a filter change is not necessarily a separate view. The owner should verify actual measurements and referrer attribution in the Cloudflare dashboard against a clean visit, a sport switch, a direct report visit, and internal navigation. No dashboard access or owner verification was available for this audit. [Cloudflare Web Analytics](https://developers.cloudflare.com/web-analytics/about/)

Keep Cloudflare and Search Console as the initial measurement tools. Use page visits and known referrers from Cloudflare, and Google impressions and clicks from Search Console. Until event collection is reviewed and configured, record category-filter usage, returning visitors, outbound clicks, and search usage as unmeasured. For confirmed email alerts, use an existing aggregate only if it is safe and available. Do not export addresses or tokens. If the owner later approves event measurement, retain only coarse sport or category, action names, retailer domain, and aggregated counts. Keep search text, full merchant URLs, email addresses, and persistent identifiers out of events. Respect applicable consent and opt-out choices.

| Monthly measure | Source |
| --- | --- |
| Visits, traffic sources and most visited pages | Cloudflare, after checking iframe attribution. Use the provider’s metric labels and mark deduplicated visitors unavailable if unmeasured. |
| Google organic impressions and clicks, leading queries and pages | Search Console Performance, using the same date range each month. |
| Merchant clicks, search, category and alert engagement | Report measured aggregates, otherwise record as unmeasured. |
| Approved content published and meaningful referrals or backlinks | Publication log, known referrers, and Search Console Links. |

### Google Search Console setup for the owner

1. Add a Domain property for `shreddeals.com` using the Google account that should own it. Add the provided TXT value in authoritative DNS and verify ownership. Keep it active. [Domain verification](https://support.google.com/webmasters/answer/34592)
2. After release, check that HTTP and www still land on the HTTPS apex. Verify HTTP 200 for robots, sitemap, and the pages in the sitemap. Verify an invalid URL returns HTTP 404 with the custom page.
3. In Sitemaps, submit `https://shreddeals.com/sitemap.xml`. Check that it can be read and that the listed URLs resolve to their declared canonicals. [Sitemaps report](https://support.google.com/webmasters/answer/7451001)
4. Use URL Inspection on the root and one publisher page. Compare the live render and Google-selected canonical. Review the Pages and Performance reports monthly. Search Console setup and indexing are unverified until the owner checks them.

## Publisher profile draft

ShredDeals is an action-sports deal discovery site at `shreddeals.com` for shoppers comparing skateboarding, ski, mountain bike, and BMX gear. It aggregates sale listings across retailers and connects current offers to observations of price changes and tracked lows. Visitors can filter by sport, product type, retailer and available specs, group likely matches across retailers, and use Quick View, saved views, favorites and email alerts where enabled. Examples in the reviewed Skate catalog include Zumiez, Skate Warehouse, Tactics and CCS. Coverage changes with the catalogs. There is no claim of a retailer partnership or gear testing.

Current public discovery surfaces include the catalogs and original analysis in Insights. Search visibility, traffic, and acquisition channels should be supported with measured data before applying. The owner reports little organic traffic so far. Publisher name, contact, jurisdiction, application numbers, and any additional established acquisition channels require owner confirmation. Future monetization may include clearly disclosed commissions on qualifying retailer purchases, subject to approval and merchant terms. No commission or network-affiliation claim is verified.

### AvantLink readiness checklist

- [x] Public HTTPS domain and working multi-sport deal discovery.
- [x] Original tracked-price and retailer activity analysis in the product.
- [ ] Approve and publish the two guides and start a documented publication history.
- [ ] Confirm legal publisher identity, public support and retailer contact, and preferred privacy channel.
- [ ] Review and publish accurate policy and disclosure text when applicable. Verify merchant program terms, content permissions and link labeling before enabling paid links.
- [ ] Verify ownership and indexing. Collect credible monthly traffic and referral reports. Establish a credible publication and outreach record using the channels actually used.
- [ ] Prepare an accurate application and leave merchant acceptance claims out unless verified. Check current requirements and ownership authentication at the time of application. [AvantLink application guidance](https://support.avantlink.com/hc/en-us/articles/203095229-How-to-Become-an-AvantLink-Affiliate) · [Application FAQ](https://support.avantlink.com/hc/en-us/articles/204952129-Affiliate-Application-FAQ) · [Ownership verification](https://support.avantlink.com/hc/en-us/articles/360052486452-Affiliate-Application-Traditional-Affiliate-Website-Ownership-Authentication-Instructions)
