# Level 2 supervised autonomy (issue #113)

Agents build, test, review and (later) fix their own pull requests and show
a working preview. **The owner approves every merge and every production
deployment.** Nothing in this plan merges automatically, deploys the live
site, scrapes stores, sends email, or touches subscriber data.

- [1. Audit](#1-audit-2026-11-01)
- [2. What PR previews add (Phase B)](#2-pr-previews-phase-b)
- [3. Costs](#3-costs)
- [4. Owner setup](#4-owner-setup)
- [5. Mobile runbook](#5-mobile-runbook)
- [6. Agent review and bounded fixes (Phase C, not enabled)](#6-agent-review-and-bounded-fixes-phase-c-not-enabled)
- [7. Off switches and rollback](#7-off-switches-and-rollback)

## 1. Audit (2026-11-01)

**Repository:** public, default branch `main`. **`main` has no branch
protection and no rulesets.** Auto-merge is off. Tag
`skatedeals-standalone-v1` (#112) is the standalone recovery point; it is
not protected yet.

Not readable from an agent session (GitHub denies it): Actions settings,
secret and variable *values*, environments, and the Pages configuration.
Names below come from the workflow files.

### Workflows

| Workflow | Runs on | Token | Secrets / variables | Does |
|---|---|---|---|---|
| CI - Pull Request Tests (`pr-checks.yml`) | PRs to main, pushes to main | read | none | compiles Python, checks page.js, Worker tests, all `test_*.py` |
| Pages - Rebuild Without Scraping (`rebuild-page.yml`) | push to main touching page files; manual | **write** | none | rebuilds and commits the page from saved data |
| Scraper - Run Full Scrape (`scrape.yml`) | 07:17 and 09:43 UTC; manual | **write** | `SMTP_*`, `EMAIL_FROM/TO`, `ADMIN_EMAIL_TO`, `REPORT_URL`, `ALERTS_HMAC_SECRET`; vars `NOTIFICATION_*`, `ALERTS_*` | scrapes, emails, commits data and page |
| Alerts - Check Worker Deployment (`worker-drift.yml`) | daily | read | var `ALERTS_API_URL` | compares the live Worker with main |
| pages build and deployment | GitHub-managed | | | publishes `main` to pchoward.github.io/salesscraper2 |

### Deployment
- **Site:** GitHub Pages from `main`. **Every commit on `main` is production**,
  including the bots' scrape and rebuild commits.
- **Alerts:** Cloudflare Worker + D1 (`worker/`), deployed by hand with
  `worker/deploy.sh` (wrangler 4); the drift check flags an undeployed change.
- **Email:** SMTP secrets in the scrape; Resend in the Worker.
- **Analytics:** Cloudflare Web Analytics beacon in the page.

### Agents today
Claude Code (cloud sessions: branches `claude/*`, PRs, comments; cannot
create tags or change settings), Codex (`codex/*`), Cursor (`cursor/*`),
Grok (advisory). **No agent runs inside GitHub Actions**, and there is no
`AGENTS.md` / `CLAUDE.md`.

### Findings
1. **Unprotected `main`.** Any account or agent with write access can push
   straight to production. See the recommended ruleset in section 4.
2. **No preview before merge.** A UI change was first seen live.
3. **No browser check in CI.** Layout and interaction regressions were
   caught by hand.
4. Actions are pinned to major versions (`@v4`), not commit SHAs. Fine for
   now; SHA pinning is a later hardening step.

## 2. PR previews (Phase B)

```
PR push --> CI - Pull Request Tests  (PR code, read-only, no secrets)
              |- tests            (unchanged)
              `- preview          build preview -> browser checks -> artifact
                     |
                     v  workflow_run (main's code; never runs PR code)
            CI - Publish PR Preview
              |- check the artifact (ci/check_artifact.py)
              |- screenshots -> ci-previews branch (one commit, open PRs only)
              |- optional: Cloudflare Pages preview (pr-N), when set up
              `- one sticky PR comment: tests, checks, screenshots, link
```

- **Preview build** (`ci/build_preview.py`): built from the data already
  committed in the branch. No store requests, email, alerts or analytics:
  the alerts Worker URL, Turnstile key and analytics beacon are left out, so
  the alerts panel shows its offline "soon" state. Every page carries a
  PREVIEW banner and `noindex`.
- **Browser checks** (`ci/smoke.mjs`, Playwright 1.56.1 Chromium), desktop
  1366px and phone 390px:
  - the page loads;
  - a category filter;
  - search;
  - a retailer link;
  - Quick View;
  - alerts stay offline;
  - sport tabs (when the page has them);
  - no page errors and no requests to production hosts.

  Off-site requests are blocked except product photos.
- **Screenshots:** home, search and Quick View at both sizes, shown inline
  in the PR comment from the `ci-previews` branch. That branch holds a single
  force-pushed commit with only open PRs' latest images; it is never merged
  and Pages does not serve it.
- **Fork PRs** get checks, screenshots and a comment, but never a live
  preview deploy.

### Safety
- The PR's code runs only in the `pull_request` job: `contents: read`,
  `persist-credentials: false`, no secrets. GitHub gives fork PRs no secrets
  either way.
- The publisher is a `workflow_run`. GitHub always runs **main's** copy of
  it, and it checks out main. The artifact is treated as untrusted data:
  - PR number and head commit must match an open PR;
  - only real PNGs with known names, and only the four preview site files,
    each under a size cap;
  - comment text is escaped.

  `pull_request_target` is not used.
- Permissions are least-privilege per job. The publisher can write the
  `ci-previews` branch and PR comments; it has no merge step and no
  production deploy.
- `test_ci_preview.py` holds these rules in place (no secrets in the PR job,
  main-only checkout, nothing from the artifact executed, preview never
  production).

**First run:** a `workflow_run` workflow only runs once it is on `main`. On
*this* PR you see the new **Preview build and browser checks** job and its
artifact; the PR comment starts with the first PR pushed after merge.

## 3. Costs

| Item | Expected cost | Basis |
|---|---|---|
| GitHub Actions minutes | **$0** | Standard GitHub-hosted runners are free for public repositories ([GitHub billing](https://docs.github.com/en/billing/concepts/product-billing/github-actions)). About 5-7 runner minutes per PR push. |
| Artifacts | about $0 | ~2-3 MB per run, kept 7 days. GitHub's pages don't clearly say whether public repos are exempt from the 500 MB storage allowance; at this size and retention it stays far below it either way. |
| `ci-previews` branch | $0 | A few MB, rewritten each run. |
| Cloudflare Pages previews (optional) | **$0** on the Free plan | 500 builds per month per account ([Cloudflare limits](https://developers.cloudflare.com/pages/platform/limits/)). It's not clear whether direct uploads count toward that; a few PR pushes a day is far below it either way. |
| Claude in GitHub Actions (Phase C) | not enabled | See section 6. |
| Codex review (Phase C) | not enabled | See section 6. |

Nothing in this PR needs a paid service, a new credential, or a change to
an existing one.

## 4. Owner setup

**A. Merge this PR** after review. PR comments with screenshots start with
the next PR push.

**B. Optional: live preview links (Cloudflare Pages, free).** Skip it, and
the comment still shows screenshots.
1. Cloudflare dashboard → Workers & Pages → Create → Pages → **Upload
   assets** (Direct Upload). Name it e.g. `skatedeals-preview`, and upload
   any placeholder file once. Its production branch is `main`; the
   workflow only ever deploys `pr-N` branches, which are previews.
2. My Profile → API Tokens → Create token → Custom: permission **Account →
   Cloudflare Pages → Edit**, for that account only. Nothing else.
3. GitHub repo → Settings → Secrets and variables → Actions:
   - Secret `CF_PAGES_TOKEN` = the token
   - Variable `CF_ACCOUNT_ID` = your Cloudflare account ID
   - Variable `CF_PAGES_PROJECT` = `skatedeals-preview`
4. Preview URLs look like `https://pr-123.skatedeals-preview.pages.dev`. They
   are public but unlisted, `noindex`, labeled PREVIEW, with alerts and
   analytics off. To make them private, Cloudflare Access can protect the
   project's previews (Zero Trust free tier).

**C. Recommended protection (Settings → Rules → Rulesets):**
1. **Branch ruleset for `main`:** block force pushes and deletions.
   Optionally require a pull request with the "Python and JavaScript
   regression tests" check. Note that the scrape and rebuild workflows push
   to `main` directly, so a "require pull request" rule must let
   **GitHub Actions** bypass it, or those workflows stop. Check this the
   first day after enabling; if the bypass is not offered, keep only the
   force-push and deletion blocks.
2. **Tag ruleset** `skatedeals-standalone-*`: restrict updates and deletions.

## 5. Mobile runbook

Reviewing a PR in the GitHub app:
1. Open the PR. The **SkateDeals PR preview** comment is near the top and
   updates on every push, so there is one comment, not one per push.
2. Read the top line: **Tests** and **Browser** (a check or a cross), plus
   the commit it describes.
3. Tap **Open the preview** (once set up) to use the PREVIEW site, or tap a
   screenshot to see it full size.
4. If something is red, open **What failed** in the comment. **Workflow
   run** has the full log.
5. Merge only when you are happy. Nothing merges by itself. After a merge,
   GitHub Pages publishes `main` within a few minutes.

What the checks mean:

| Check | Fails when |
|---|---|
| Page loads | no deal cards, or no PREVIEW banner |
| Category filter | clicking a category chip does not switch the category |
| Search | searching "baker" finds nothing |
| Retailer link | the first card has no https store link |
| Quick View | Quick View does not open |
| Alerts stay offline | the alerts panel would talk to the live Worker |
| Sport tabs | (ShredDeals) a sport tab does not update the URL |
| No page errors | the page threw a JavaScript error |
| No production calls | the page called the alerts Worker, Turnstile or analytics |

## 6. Agent review and bounded fixes (Phase C, not enabled)

**Needs the owner's decision on credentials and billing before any work.**
Nothing below is set up by this PR.

### Options
- **Codex code review**, as the independent reviewer the issue suggests. It
  runs on a ChatGPT plan through Codex's GitHub connection. OpenAI's
  pricing page says API-key use has no cloud features such as GitHub code
  review, so this uses the plan's Codex allowance, not an API key
  ([Codex pricing](https://developers.openai.com/codex/pricing),
  [usage limits](https://help.openai.com/en/articles/11369540)). Setup is in
  Codex's settings, not in this repository. `openai/codex-action` (Codex
  inside Actions) needs an OpenAI API key and is metered.
- **Claude in GitHub Actions** (`anthropics/claude-code-action`), two ways to
  authenticate:
  - `ANTHROPIC_API_KEY`: Anthropic API, pay per token, separate from a
    claude.ai subscription. Set a monthly spend limit in the Anthropic
    Console.
  - A Claude Pro/Max subscription token (`claude setup-token`, stored as a
    secret). Usage counts toward the plan's limits.

  Check the action's README and Anthropic's current terms for automated use
  before choosing. **Don't assume a chat subscription covers API-key runs.**

### Proposed design (for the follow-up PR, after approval)
1. **Review on request only:** the owner comments `@codex review` (Codex)
   or `@claude review` (Claude). The trigger checks that the commenter is
   the repository owner.
2. **Bounded self-repair**, only:
   - on an agent's own branch (`claude/*` or `codex/*`) and its own PR;
   - after the owner adds the label `agent-fix`;
   - when **CI - Pull Request Tests** failed on that PR's head.

   Limits:
   - **at most 3 attempts per PR**, counted by labels (`agent-fix-1..3`);
     after the third, it comments and stops;
   - 15-minute job timeout and an agent turn cap per attempt;
   - one attempt at a time per PR;
   - removing the label stops it.

   It can push to that branch only. No merge, no `main`, no secrets beyond
   the agent credential, no workflow edits.
3. A push made with the default `GITHUB_TOKEN` does not start new workflow
   runs, so a repair would never be re-tested. The repair needs the agent's
   GitHub App token (the Claude GitHub App or Codex connector) so its push
   triggers CI again. That is part of the credential decision.
4. **Issue pickup** (agents starting from issues) comes later, only for
   issues the owner labels `agent-ready`.

### Budget guardrails
Set before enabling:
- an API spend limit, or subscription-only use;
- at most 3 repair attempts per PR;
- a timeout on every job;
- runs only on the owner's comment or label;
- a monthly review of Actions usage (Settings → Billing) and the agent
  provider's usage page.

## 7. Off switches and rollback

| To | Do |
|---|---|
| Pause previews and comments | Settings → Secrets and variables → Actions → Variables → `PR_PREVIEWS` = `off` |
| Stop live preview deploys only | delete variable `CF_PAGES_PROJECT` (or secret `CF_PAGES_TOKEN`) |
| Stop one workflow | Actions → the workflow → ⋯ → Disable workflow |
| Remove previews entirely | revert this PR; delete the `ci-previews` branch |
| Undo a merged change | the merged PR → **Revert** → merge the revert PR (Pages republishes `main`) |
| Return to standalone SkateDeals | tag `skatedeals-standalone-v1` (#112 has the steps) |

None of these touch the scrape, email, alerts Worker or subscriber data.
