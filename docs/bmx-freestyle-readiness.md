# Issue #123 — BMX Freestyle readiness and Actions handoff

Base: main `0d5b1c6`. This branch intentionally does not contain the pending
sport-engine changes or duplicate issue #122's header. No production scrape,
engine/header edit, production data/state write, delivery, merge or deployment.


## Current route: Claude's PR #124 supersedes the local-network blocker

The owner relayed Claude's coordination update: #124 (`claude/sport-engine`)
provides the sport engine, first Albe's BMX adapter and manual **ShredDeals -
Preview Site** workflow. Retailer collection runs in GitHub Actions, which can
reach the stores; **local domain changes are not required for this plan**.
The Dan's Comp/Source BMX observations below remain accurate historical evidence,
but do not block the first Albe's preview. Do not duplicate Claude's adapter or
engine. Merge/release decisions remain with the owner.

Sequence: #124, Codex's `codex/unified-shreddeals-header`, then Claude's small
native-header integration PR. Only that last integration changes the live
homepage. Once the engine is merged, #123 should validate the real Actions output,
retailer permission evidence, freestyle versus race selection, 20/22-inch
attributes, availability, observed-history versus compare-at discounts, counts,
health protection and desktop/mobile behavior. The current engine's BMX rules
are broad category/apparel rules; freestyle/race and detailed fit claims must be
verified rather than assumed. Dan's Comp and Source BMX remain optional later
candidates, not requirements before the Albe's preview.

## Historical local observations

On November 1, 2026, attempts to read the candidates' `robots.txt` both returned
**environment proxy CONNECT 403**. These are not retailer HTTP refusals.
No homepage, terms, product feed, category or product page was fetched.
The evidence is `docs/bmx-readiness-observation.json`.

| Candidate | Access rules / terms | Platform / schema | Real eligible products | Suitable adapter |
|---|---|---|---|---|
| Dan's Comp (`www.danscomp.com`) | Unverified: robots request blocked by environment | Unverified | Unknown, not zero | Pending real evidence |
| Source BMX (`www.sourcebmx.com`) | Unverified: robots request blocked by environment | Unverified | Unknown, not zero | Pending real evidence |

No assumption is made that either site is Shopify, that a sale feed exists,
that automated access is permitted, or that any listing is in stock. No mock
BMX inventory is represented as a real catalog. Before/after real catalog counts,
a retailer adapter and real desktop/mobile BMX catalog screenshots are **pending**.

## Useful preparation on this branch

`python -m audit.bmx_readiness --output-dir /tmp/bmx-retailer-evidence`

Use a new directory outside the checkout. The bounded tool reads robots first,
stops when access is unverified/disallowed, respects the research user agent's
crawl delay/request rate, avoids implicit redirects, and captures only permitted
homepage and up to two same-origin linked terms pages. It reuses existing platform
and sale-link discovery. Raw public evidence and a readiness report go only to
the selected external directory. It does not request product feeds or mutate
catalog/history/health/notification files. A successful tool exit means a report
was written, **not** that a retailer scrape succeeded; inspect each status.

Six fixture-based tests cover denied/unavailable robots, the environment-versus-
retailer error distinction, crawl delays, terms capture, unknown product counts,
blocked/foreign terms and output isolation. Fixtures are synthetic access-policy
examples, not retailer product evidence.

## Historical blockers and remaining handoff

1. **Network**: allow `www.danscomp.com`, `www.sourcebmx.com` and `api.github.com`.
   Existing saved custom domains must be preserved. The current runtime has no
   custom destinations enforced. Attempting the supported additive draft update
   failed with `stale_base`; saving changes was not confirmed. The proposed domain
   list is supplied separately as `shreddeals-network-additions.json`. Reconcile
   it in a current environment setup/configuration and apply the policy before
   retrying. No credential values or network bypass are needed.
2. **Engine**: Claude's sport-aware engine is not on main as of this branch's base.
   #123 explicitly requires reading the merged engine PR before integration. Do
   not recreate it or connect a BMX scrape to Skate's global files. The existing
   Shopify downloader can be reused only after platform/feed verification; its
   current filters and category constants are Skate-specific.
3. **Header**: issue #122's reusable native component and working preview are on
   `codex/unified-shreddeals-header`, commit `9194c0b`. The handoff is
   `docs/unified-header.md` on that branch. Inject its config-driven header into
   Claude's actual output pages; do not permanently extend the old iframe shell.

Once access and the engine land, inspect real terms and a bounded permitted
sample, then choose the first suitable retailer. Start with verified freestyle
frames, handlebars, forks, cranks, wheels/tires; explicitly exclude race inventory.
Keep 20-inch and 22-inch attributes distinct, retain unknown compatibility rather
than inferring it, and preserve size-specific price/availability. Capture real
fixtures and request provenance. Use shared runner/history/health safeguards with
separate BMX paths and fail suspicious/failed scans without disappearance updates.

The first preview should show real retailer links and the existing card/Quick View
renderer. Label compare-at discounts separately from observed history, establish
an initial snapshot without invented historical drops, report actual before/after
counts and request costs, test desktop/mobile, then open the adapter/integration
PR for review. No live production scrape or deployment without owner approval.

Validation on the isolated BMX branch: **573 tests completed, OK (one existing
skip)**. Eight Chrome-dependent cases were unavailable in this environment. The
20 focused readiness/store-probe/public-diagnostic tests also passed. These tests
use saved/synthetic inputs; they do not validate a live BMX source or adapter.

The first real Actions run has now succeeded: **72 Albe's listings**, 72 distinct
URLs and 72 rendered cards. See [the validation report](bmx-actions-validation.md)
for counts, screenshots reviewed, scope mismatches and the remaining #123 work.
