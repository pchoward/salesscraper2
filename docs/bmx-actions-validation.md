# Issue #123: first real Albe's Actions preview

Run: https://github.com/pchoward/salesscraper2/actions/runs/41338783215

The owner started **ShredDeals - Preview Site #1** on main `7383c15` after #124.
GitHub reports **Success**. Preview branch commit:
`4a98c48fd9e50c2ec49b2b4a048e13f41c9e6028`.
This review read the published branch and its saved catalog/health/public HTML
and inspected its desktop/mobile BMX screenshots. No additional scrape, workflow
trigger, production update, delivery, merge or deployment was performed.

## Observed counts

| Category | Listings |
|---|---:|
| Bikes | 6 |
| Frames & Forks | 4 |
| Steering | 9 |
| Drivetrain | 13 |
| Wheels | 10 |
| Wheel Parts | 11 |
| Tires | 8 |
| Seating | 11 |
| Braking | 0 |
| Total | 72 |

There are **72 distinct URLs**, and the rendered BMX page contains **72 cards**.
The initial preview went from no saved BMX catalog to 72 observed listings; that
is a first snapshot, not evidence of historical price drops. The first health
checkpoint marks categories as not failed and reports `insufficient_history`:
completeness needs subsequent successful scans, not a presumed mature baseline.
All 72 items say **Check store**, avoiding unsupported in-stock claims.
The page has no `window.SKATEDEALS_ALERTS` live configuration. Its scan timestamp
is `2026-11-01T18:52:07+00:00` (1:52:07 PM Eastern).

## What is working

The actual Actions route reaches Albe's, downloads and normalizes real listings,
saves separate BMX state, builds a BMX page/history and publishes the preview.
The successful workflow includes its browser-check step. Published desktop/mobile
screenshots display the BMX catalog and product images (some desktop images had
not loaded when captured). The current preview still has the old stacked header,
duplicate preview banners and non-Skate subscription buttons; Claude's agreed
header integration follow-up addresses those, with delivery remaining disabled.

## Why #123 is not complete yet

The broad first adapter is not yet a verified freestyle-only catalog. Examples
in the observed data requiring exclusion or explicit scope review:

- Haro Skwad 1 **Electric Bike**;
- Haro Klunkerson **27.5-inch Bike**;
- Elite Outlaw **26-inch Bike** and Haro B.M.F **26-inch** frame/fork kit;
- FIT OEM **16-inch** wheelset and Rant **18-inch** wheels;
- Black Ops **24-inch** fork and Fit **29-inch** rim.

A listing named **SE RACING NARLER RETRO STEM** needs actual fit/product evidence;
its brand/model wording alone is not proof of race-only compatibility. Neither
race nor freestyle status should be guessed from a brand substring.

Structured wheel size, top-tube length, bar rise, crank length and compatibility
fields are absent from this saved normalized snapshot. Exact 20/22-inch filtering
cannot be claimed from these records; request/retain reliable variant/spec data
through an isolated Actions sample before designing the size integration.
Observed compare-at markdowns must remain distinct from historical drops.
Retailer robots/terms evidence still needs verification or a captured reference;
network reachability and a successful scrape are not permission evidence.

This work belongs after #124 and the agreed header handoff. Do not duplicate or
independently rewrite Claude's engine, sport rules or adapter. Coordinate a small
freestyle/data-quality integration, fixture tests from verified source evidence,
and another preview before marking #123 complete. Local retailer domain updates
are not required for the Actions route.
