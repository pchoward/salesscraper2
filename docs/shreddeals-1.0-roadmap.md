# ShredDeals 1.0 — Four-Week Rolling Plan
**Recorded:** November 5, 2026  
**Aspirational checkpoint:** December 3, 2026 (flexible, not a hard deadline)  
**Status:** Planning document; NOT implementation authorization. Owner reviews and merges all PRs.

## Purpose
Give the existing production ShredDeals site a practical "1.0 done" definition while continuing parallel work on data quality, reliability **and usability / UI design**. Retain an enjoyable, flexible iteration process. New ideas may be added to a separate 1.1 / V-Next backlog instead of automatically widening the scope.

## Four loosely scheduled workstreams (parallel, not gated)
| Window | Main focus | Concurrent usability/UI |
|---|---|---|
| Nov 5–11 | Establish data baseline, evaluate catalog coverage, prioritize defects | Compare peer shopping sites and study product-card behavior |
| Nov 12–18 | Fix high-impact gaps, search/facets/retailer coverage | Prototype card-click -> first-party detail page, preserving Quick View |
| Nov 19–25 | Reliability, alert workflows, price quality, performance | Mobile/desktop acceptance, detail layout, search and navigation polish |
| Nov 26–Dec 3 | Stability check, acceptance audit, critical fixes, 1.0 checkpoint | Finish or consciously defer remaining UI ideas |

No hard freeze; these dates are planning cues, not promises. Workstreams can run simultaneously.

## Proposed 1.0 release indicators (measure baselines before committing to thresholds)
- 95%+ audited product classification/metadata correct across a stratified sample of 200 listings.
- 98%+ checked offer prices match retailer-visible prices within a documented freshness window, using a sampled 100 offers.
- 95%+ successful scheduled scraper runs across 14 days, with visible health signals for failure/partial coverage.
- Four active sports: Skate, BMX, Ski, MTB have useful real catalog results, navigation, relevant filters, and search.
- Search relevance: >=90% of an agreed 40-query dataset yield expected relevant products near the top.
- Core shopping flow passes on desktop and mobile: browse, filter, inspect, view history, view at retailer.
- CI green, zero unresolved release-blocking issues; existing supported alert lifecycle tested.
- Establish performance baseline and a practical mobile/desktop load target.

These are proposed measurement goals, not current observed metrics.

## Major UI/usability exploration: product card behavior (PRIORITY DESIGN TOPIC)
Existing behavior: Quick View; clicking many other parts of a card goes directly to vendor.
Desired exploration: card body/image/title opens a **first-party detailed product view**. Keep Quick View as a fast, secondary action. **Visit retailer** remains an explicit, unmistakable external action. Avoid surprising external navigation from general card clicks.

Proposed journey:
1. Scan/filter catalog cards.
2. Tap card -> ShredDeals full product detail (ideally a shareable, back-button-safe URL, not necessarily a popup).
3. Detail shows larger image, price/discount/retailer identity, category/specs and variants *if trustworthy data exists*, price-history chart, lows/highs and price freshness, related products if matches are sound, watch/alert actions where supported.
4. Separate prominent "View at retailer" external action (new tab on desktop only if appropriate).
5. Quick View remains optional for rapid comparison; consider whether it is distinct enough to retain after usability testing.

**Important:** User believes an earlier richer card/detail interaction may have existed. Before implementing, Codex should investigate git history to verify and potentially reuse it. Do not invent history.

## Design reference: The Dropper — https://thedropper.shop/
Reference site inspected 2026-11-05. Its homepage distinguishes "View details" (internal) from "Snag this deal" (external), and product details at `/deals/<id>` show price/discount, in-stock variants with prices, price history (low/high/avg), retailer link and related deals.

**Borrow:** separating browsing from purchase, details URL, useful variant availability, contextual related products, clear buy CTA.
**Be cautious:** many stock/size variants can bury the price-history content; range prices can falsely suggest all variants share a discount; a historical low based on a short observation window can mislead; related listings need reliable matching; don't imply checkout happens on ShredDeals. Keep our dense deal discovery / strong fuzzy search / product price-history strengths.

## New findings triage
- Release blocker: wrong price, broken navigation/search, serious misclassification, unmonitored scrape failures -> fix before release.
- Normal defect: prioritize against actual user impact.
- New enhancement: add to 1.1 unless it clearly improves the agreed core journey within budget.
- Major redesign: retain in V-Next notes at PR #198; do not start it in current site by default.

## Responsibility (based on repository ownership; user can change)
- Claude: scrapers, data, health, CI/alert delivery.
- Codex: main-site unified header/navigation, and coordinate when implementing card/detail UI with current UI owner.
- Catalog UI owner: filters, cards, Quick View, responsive usability.
- Site owner: product direction, review, merges.
- ChatGPT: research/comparisons, acceptance criteria, prioritization.

## Working rhythm
Keep at most 3 principal priorities in flight; agents can handle separate streams in parallel. Weekly lightweight scorecard: current catalog audit %, price audit %, scraper success %, search queries passing, release blockers, core journeys passing. Document measurements, not PR counts.

## Decisions deferred
- Exact detail-page design and whether Quick View is retained unchanged.
- Whether product details are keyed per retailer listing or safely merged cross-store.
- V-Next visual redesign remains parked, separate from current 1.0.
