# Seeing ShredDeals on your phone

The simplest path, all from the GitHub app. No Codespaces, no commands.

## Once, after this PR is merged

GitHub only lists a manual workflow after it is on `main`.

## Daily

The workflow also runs by itself every day at 21:37 UTC (2:37 pm Pacific),
scraping BMX into the preview, so BMX price history builds up. The phone link
always shows the latest run. To pause it: Actions → ShredDeals - Preview Site
→ ⋯ → Disable workflow.

## By hand

1. GitHub app → **salesscraper2** → **Actions** → **ShredDeals - Preview Site** →
   **Run workflow**.
   - **Scrape**: `bmx` refreshes BMX deals from Albe's BMX first (about a
     minute). `none` just rebuilds. Skate is never scraped here; its page is
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

## Going live with BMX (later, needs your approval)

1. Move BMX's data from the preview branch into `main`'s `catalogs/bmx/`.
2. Add a scheduled BMX scrape: the same `python scraper.py --sport bmx`.
3. Have `previews/publish.py` list BMX's page, so the homepage BMX tab opens
   it instead of "coming soon".

Each is a small PR. None of them sends email: delivery stays Skate-only
until a sport is opted in (`sports/__init__.py`, `delivery=True`).
