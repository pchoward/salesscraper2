# Faster PR browser checks

The completed task-13 run's browser job took **25m 53s** ([run](https://github.com/pchoward/salesscraper2/actions/runs/43266415886/job/131351071359)). Every suite ran serially on one runner, and the four-sport audit rebuilt the same catalogs a second time.

The new workflow builds the inert preview once, prebuilds truck/audit fixtures, and downloads those inputs into six independent browser groups. Browser runners no longer install Python/report dependencies. Existing Playwright/Chromium versions remain pinned. Old runs for the same PR are cancelled when a newer commit arrives; main runs still finish.

| Group | Suites |
| --- | --- |
| navigation | Category navigation: two parallel width sets (1440/1024/768 and 430/390/320), all four sports |
| controls | Smoke/screenshots, sport menus, sidebar, My stuff, public Explore |
| filters | Truck fit, multiple stores, full-screen phone filters |
| search | Shopify Catalog mocks and header-search synchronization |
| audit-wide | Four-sport audit at 1440, 1024 and 768px |
| audit-phone | Four-sport audit at 430 and 390px; all synthetic fixture checks at their existing desktop/phone widths |

No assertions, sports or viewports were removed. Navigation uses at most two isolated browser processes with separate outputs; other groups run one suite at a time. The only audit-loop switch prevents synthetic fixtures running twice across the two audit groups. Every other suite keeps its original defaults.

## Gates and evidence

The two original required check names remain **Python and JavaScript regression tests** and **Preview build and browser checks**. The latter is now an aggregate gate that waits for the build and every browser group. Missing reports, incomplete task lists, a failed task or a cancelled group all fail it. A group continues to its next suite after a failure so the review captures more than the first defect; suite processes also have a bounded timeout.

Each `browser-review-<group>` artifact contains screenshots, results and a timing report. The combined `browser-review` artifact merges their distinct directories. The job summary lists each group's duration; the timing JSON records every suite. This makes future bottlenecks visible.

The `pr-preview` file contract stays unchanged: pristine public site, PR metadata and the original smoke screenshots/summary. Test fixtures and extra review files never enter the published site. The existing hidden-file exclusion remains on this final artifact for compatibility with main's strict publisher whitelist; the hidden Shopify profile is unnecessary in an offline preview. Production profile publication is unchanged. The dry-run preview is about 113 MiB, so the publisher's stale 64 MiB size cap is raised to a bounded 128 MiB; the strict file/directory whitelist and symlink checks still apply. Main's publisher needs this merged update before it can accept the expanded site. Internal build inputs include that profile so browser groups receive the complete generated site.

PR jobs remain read-only, with credentials disabled in checkouts and no secrets. The separate publisher continues running main's code and validating artifacts. Nothing scrapes, emails, merges or deploys production.

## Local reproduction

Use the existing Python requirements and pinned Playwright setup. Build into directories outside the checkout:

```sh
python ci/build_preview.py /tmp/browser-input/site --label 'Browser CI review'
mkdir -p /tmp/browser-fixtures
python ci/build_audit_fixtures.py /tmp/browser-fixtures
python ci/build_truck_fixtures.py /tmp/browser-fixtures
node ci/run_browser_shard.cjs search /tmp/browser-input/site /tmp/browser-review /tmp/browser-fixtures
```

Use a separate copy of the site for each group when running groups concurrently on one machine, matching the isolated GitHub runners. `BROWSER_BINARY` optionally selects an installed Chromium for local validation; CI keeps Playwright's pinned browser. Run `node ci/summarize_browser_runs.cjs <merged-review-directory>` to verify that every planned task passed and print timings.

The expected speedup comes from separate runners, not weaker tests. Actual wall time still depends on runner availability, setup and artifact transfers. Six runner slots are needed for full parallelism; extra runner startup may increase total Actions minutes even while reducing wait time. Local timings are not a substitute for measuring the first GitHub run.

## Validation on 2026-11-12

Every original browser suite passed locally. The final six reports pass the same aggregate gate used in CI. Category navigation's final two-process run covers all 24 sport/viewport cases and took **215 seconds**, versus **463 seconds** for the initial whole-width group.

| Group | Measured local wall time |
| --- | ---: |
| navigation | 3m 35s |
| controls | 4m 55s |
| filters | 4m 44s |
| search | 5m 14s |
| audit-wide | 4m 56s |
| audit-phone | 3m 22s |

[Raw timing reports](browser-ci-timings.json) record the actual commands and exit statuses. The host had four CPU cores; initial groups ran with at most three local workers, and final navigation used two processes. These are per-group local timings, **not an end-to-end GitHub measurement**. The longest measured group is about five minutes, so runner startup/build/transfer time determines the remaining critical path. The first real Actions run must establish the final speedup.

The assembled real preview also passes the publisher validator at 118,957,243 bytes. Boundary tests accept an expanded catalog and still reject a site over 128 MiB, unknown paths, test fixtures and symlinks. Runner tests cover failures, hung processes, bounded parallel execution and missing/incomplete reports.
