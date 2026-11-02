# Seeing ShredDeals on your phone

The simplest path, all from the GitHub app. No Codespaces, no commands.

## Once, after this PR is merged

GitHub only lists a manual workflow after it is on `main`.

## Live since 2026-11-02

BMX and Ski are on the live site, next to Skate: pchoward.github.io/salesscraper2
(tap BMX or Ski). **"Scraper - BMX, Ski, MTB"** scrapes them every day at
21:37 UTC (2:37 pm Pacific) and publishes to `main`, the way Skate's scrape
does. It shares Skate's lock, never touches Skate's files, and sends no email
or alerts. A sport's tab opens its catalog once it has listings (MTB stays
"coming soon" until its stores land). To pause it: Actions → Scraper - BMX,
Ski, MTB → ⋯ → Disable workflow.

The preview below is now only for trying a branch's code before merging.

## By hand

1. GitHub app → **salesscraper2** → **Actions** → **ShredDeals - Preview Site** →
   **Run workflow**.
   - **Scrape**: `all` (the default) refreshes BMX, Ski and MTB; pick one
     sport to refresh only it; `none` just rebuilds. Skate is never scraped here; its page is
     rebuilt from the data already on `main`.
   - **Branch**: leave `main`, or type a PR's branch to try its code.
2. Wait for the run (about 3–4 minutes) and open it. The summary at the top
   has:
   - **Open on your phone:** a link to the whole site:
     `https://raw.githack.com/pchoward/salesscraper2/shreddeals-preview/index.html`.
     The link stays the same, so bookmark it. After a new run, give it a
     minute or two to refresh.
   - phone screenshots of the homepage, BMX, and an empty sport, in case
     the link is slow;
   - which pages were built, and whether the browser checks passed.

The preview has an orange **PREVIEW** banner. Alerts, email and analytics
are off.

## What it is, and what it isn't

| | Preview | Production (pchoward.github.io/salesscraper2) |
|---|---|---|
| Where | `shreddeals-preview` branch, one commit replaced each run | `main`, served by GitHub Pages |
| Skate | rebuilt from `main`'s saved data | the scrape workflow, unchanged |
| BMX / Ski / MTB | their own data in the branch's `_data/catalogs/<sport>/` | not published yet |
| Email / alerts | never (no secrets in the workflow) | Skate only |

- **Each sport is scraped on its own.** `python scraper.py --sport bmx`
  reads only BMX stores, and writes only `catalogs/bmx/` and `bmx/`.
  Skate's run (`python scraper.py`, the scheduled "Scraper - Run Full
  Scrape") is unchanged and never reads BMX stores. Tests in `test_sports.py`
  run each sport and check that no file or listing crosses between them.
- **BMX price history** builds up run by run on the preview branch. Nothing
  about BMX reaches `main` or the live site until you approve that step.
- **The service in the link: raw.githack.com.** It is a free, long-running
  proxy that serves a public repository's files as a website. It needs no
  account, key or billing, and only reads what is already public in this
  repository. If it is ever down, the run's screenshots and its
  `site` files are still there. GitHub itself cannot serve a second site
  from this repository without changing the Pages setup, which is
  production's.
