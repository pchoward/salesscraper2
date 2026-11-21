# ShredDeals — Future UI Design Handoff for Codex

**Status:** DESIGN CONCEPT / PARKED — **do not implement or change `main` yet**.
**Date:** November 4, 2026
**Repository:** `pchoward/salesscraper2`
**Latest interactive prototype:** `shreddeals_v3_2_interactive.html` (self-contained; illustrative data)

## Decision and sequencing

The current ShredDeals multisport site remains the priority. Continue existing work on scraper discovery/health, multisport category coverage, protection brands/products, price accuracy, alerting, and current UI functionality. The new interface should **not** be merged piecemeal into `main` or distract agents from existing mainline priorities. Revisit this handoff when the user explicitly authorizes the V-next implementation. At that time create a dedicated branch or isolated preview, use small PRs, require review/CI, and preserve the production experience until approved.

## Approved visual direction

The **white and crisp** retail-style concept is the reference, not the earlier dark prototype. Clean black/white UI, neon-lime accents, thin-line monochrome icons, bold sport navigation, search prominent in the header, compact but clear filter controls, airy four-/five-column mega menus and changing sport-specific left hero images. Tactics and Evo influenced the browsing/navigation model. Keepa influenced the **deep product price analysis**, not the appearance of the home page.

**Keep both halves:** (1) approachable retail-style product discovery and (2) detailed Keepa-inspired historical price intelligence once a product is selected. Do not turn the service into a generic checkout store: products still link to participating retailers.

The prototype is a design/interaction reference, **not production code ready to transplant**. Sample products, numbers, prices, images, simulated charts and brand representations are illustrative, not verified live catalog data.

## Current prototype behavior to preserve or develop

- Top nav: Skate, BMX, MTB, Ski, Protection, Deals, Sale; cohesive icons and clear active state.
- Each sport opens the same mega-menu composition: left sport-specific image, context-aware categories, sport/type/discipline, shopping/deal shortcuts, top brands; imagery and links change when sport changes.
- Protection menu is coverage-centered across sports: helmets, knee pads, elbow pads, wrist guards, hip/tailbone, ankle/shin, back/chest, bundles. Support multi-sport matching without falsely claiming product suitability or certification.
- Search, sport switching, filters, sorting, saved items, responsive behaviors and price-history drill-down should work with actual mainline product/catalog data eventually.
- Preserve powerful existing functions from main (quick view, historical data, product sizes/widths, alerts, scoring, deal types, store filtering, URL state, mobile behavior). First inventory current features against prototype so nothing gets lost.

## Pending: icon legend and art direction

Use one icon style: small **simple readable outline equipment silhouettes** (consistent stroke, rounded joins, 20–24 px nav, ~16–18 px menu) that remain identifiable at small sizes. Avoid random emoji, decorative stick-figure abstractions and invented brand-logo imitations.

| Location | Target icon | Design notes |
|---|---|---|
| Top nav: Skate | **Slim skateboard deck with wheels** | Current version is too chunky; refine proportions so deck is long/thin with modest wheel size |
| Top nav: BMX | BMX bike side silhouette | Keep simple and recognizable |
| Top nav: MTB | Mountain peaks | Existing concept is fine; consistent stroke weight |
| Top nav: Ski | **Two skis crossed in an X** | User explicitly prefers internationally recognizable crossed skis; **do not use goggles** |
| Top nav: Protection | Shield | Current direction works |
| Top nav: Deals | Flame | Current direction works |
| Top nav: Sale | Price tag | Current direction works |
| Protection: Helmets | Helmet profile | Good in current version |
| Protection: Knee pads | Pair of knee pads / joint guard | Read as knee protection, not abstract shape |
| Protection: Elbow pads | Elbow joint and pad | Clearly different from knee pads |
| Protection: Wrist guards | Hand + wrist brace | Avoid generic glove when possible |
| Protection: Hip & tailbone | Padded shorts | Shorts shape with padding panels |
| Protection: Ankle / shin | Shin / ankle guard | Tall tapered lower leg guard |
| Protection: Back & chest | Torso armor | Good in current version |
| Protection: Pads & bundles | Group of protective items | Simple grouped pads |
| Skate categories | Deck, trucks, wheels, bearings, shoes etc. | Literal gear silhouettes, not clip-art |
| BMX categories | BMX bike, bars, pedals, tires, helmet etc. | Literal gear silhouettes |
| MTB categories | Bike, fork, tire, gloves, armor etc. | Literal gear silhouettes |
| Ski categories | Skis, boots, poles, bindings etc. | Literal gear silhouettes |
| Brands | Clean **text-first** brand names with optional neutral marker | No fake logos. If real authorized/official logo assets are available, use those later; otherwise omit graphic. |

## New interaction concept: product card -> larger detail card

**Important opportunity drawn from the dropper.shop site.** Today the live product card largely offers (a) Quick View or (b) go to the vendor. V-next should make the **product card itself** open a richer, larger, in-site detail experience; the vendor link remains an explicit secondary/primary CTA inside it.

Suggested progression:
1. Browse filtered deals in a product grid; entire card click/tap opens an **expanded product view** (modal/sheet on desktop or mobile, or dedicated route if testing shows better navigation/accessibility).
2. Show larger photos, complete product name, available sizes/variants, store, current price, previous/reference price, percent off, stock freshness and deal score where grounded.
3. Present Keepa-inspired price history and actionable insights: recorded low, typical price, recent drops, observation window, and comparison across retailers where stable product matching is reliable. Do not fabricate history or imply a lowest-ever price without sufficient tracked observations.
4. Provide **View at Retailer** and **Track Price / Alert Me** buttons; quick view may be folded into or replaced by this richer view after UX review, but do not remove working existing behavior prematurely.
5. Back/forward, deep links, keyboard/escape closure, mobile navigation, scroll restoration and filters must remain usable. The flow is **browse -> inspect internally -> optionally visit retailer**, not immediate redirect.

Before implementation, review dropper.shop's interaction only as design inspiration and implement independently; do not copy proprietary code/assets.

## Suggested implementation sequence (when authorized)

1. Feature inventory + technical plan: map old UI/filter/quick-view/alerts/history behavior to V-next; identify risks of iframe and data generation approaches.
2. Header + sport mega-menu shell in isolated V-next preview; icon library/legend; correct crossed skis and slim skateboard. Verify responsive design.
3. Filter/sidebar and dense product-grid views using **real existing catalog data** and correct category-specific filters.
4. Expanded card/product detail experience, with existing price history and alerts preserved. Measure desktop and mobile usability.
5. Visual regression, accessibility, deep-linking, performance, compatibility with build/preview workflows; staged migration proposal.

**Guardrails:** no direct pushes to `main`; one focused PR at a time; do not commit volatile generated sport catalog pages unless a workflow explicitly requires them; keep existing scheduled scrapers and alerts working; validate on Linux CI and browser; no unreviewed deploy or merge.

## Included references

- `shreddeals_v3_2_interactive.html` — latest working visual/functional sample (self-contained).
- `shreddeals_protection_mega_menu_ui.png` — original bright reference.
- `shreddeals_skate_mega_menu_storefront.png` — skate navigation/look reference.
- `shreddeals_protection_gear_marketplace.png` — protection product detail direction.

## Codex first task — only when the user reactivates this project

Review the attached V-next handoff and prototype alongside the current `main` architecture. **Do not implement yet.** Produce a gap analysis and an incremental, low-risk implementation plan, identifying features in `main` that must not regress; propose which interaction should be the default when tapping a product card. Wait for explicit approval before coding.

**Repository note:** The HTML prototype is self-contained and stored alongside this document. The separate PNG concept references are available in the original handoff ZIP shared in the design discussion; they are not included in this repository PR.
