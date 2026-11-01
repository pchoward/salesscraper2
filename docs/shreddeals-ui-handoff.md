# ShredDeals catalog UI: handoff to Grok (2026-11-01)

Grok now owns the **catalog page UI**: cards, filters, chips, panels and
search help. That is `page.js`, `page.css`, `mobile.css` and the card and
filter markup in `page.py`. Codex keeps the **homepage, sport tabs and unified
header** (#122). Claude keeps the **engine, scrapers, data and CI**
(docs/shreddeals-ownership.md).

## Where things are

- **Skate (SkateDeals)** is live at pchoward.github.io/salesscraper2, unchanged.
- **BMX** has a working preview with 72 real sale items from Albe's BMX, on
  the `shreddeals-preview` branch:
  https://raw.githack.com/pchoward/salesscraper2/shreddeals-preview/index.html
  (tap BMX). The BMX page is the same `page.js` and `page.py`, driven by
  per-sport settings. It is not on the live site.
- **Ski and MTB** have their settings ready but no stores yet, so their tabs
  say "coming soon".
- **Engine** (#124, merged): `sports/__init__.py` holds each sport's
  settings. A non-Skate page receives:

  ```js
  const SPORT_SETTINGS = {id: "bmx", label: "BMX", defaultPart: "all",
                          parts: ["Bikes", ...], alerts: false};
  ```

  **Skate's page has no `SPORT_SETTINGS`.** Treat "undefined" as Skate and
  keep Skate exactly as it is.
- **Codex's #122** (`codex/unified-shreddeals-header`) replaces the two
  headers and the iframe shell with one native header. Don't edit the header
  (`#stickyBar .topnav`, brand, Deals/Track/Insights/Subscribe) or anything
  in `previews/` or `navigation/`. That's Codex's.

## Your tasks, in order

1. **Price line on cards (biggest visible issue).**
   - **Problem:** a first-day card reads "↓ 91% · Average $2.50 / Now $2.50".
     The 91% is off the store's list price, but the list price isn't shown,
     and an average of one price says nothing.
   - **Fix:** while a listing has under 2 days of history, show the list price
     instead: "~~$27.95~~ $2.50" or "Was $27.95 · Now $2.50". Switch to the
     average once real history exists.
   - **Where:** markup in `page.py`, `_card` near `avg_html` ("Average {symbol}…"
     around line 2425); live update in `page.js` around line 1717
     (`node.textContent = "Average " + …`).
   - **Applies to every sport**, Skate included. It's a UI change you own, so
     Skate's output is allowed to change for this task.
2. **No alert buttons where alerts don't exist.**
   - When `SPORT_SETTINGS.alerts === false`, hide each card's "Alert me" button
     and the Track/watch prompts on cards and in Quick View.
   - Leave the header's Subscribe button alone; Codex's header handles it.
3. **Skate wording on BMX pages.**
   - Go through the BMX preview for skate-only text: search help examples
     ("baker", "spitfire", durometer...), empty states, the "Product
     specifications" section (skate facets should be hidden when no BMX item
     has them), Quick View labels, and the skateboard icon in the page's own
     header strip (if it isn't part of #122's header).
   - Use `SPORT_SETTINGS.label` and `SPORT_SETTINGS.parts` in place of
     hard-coded skate words.
4. **BMX filters, as each one's data arrives.** Claude adds the data fields;
   you build the filter UI. Copy the existing facet pattern (`SPEC_FACETS`,
   `activeSpecKeys`); don't build a new system. Order and labels are in
   docs/multi-sport-plan.md §3, modelled on Dan's Comp:
   - **Wheel size first.** Field `wheel_size` (12/14/16/18/20/22/24/26/27.5/29)
     is coming from Claude next.
   - **Type within a category** (Hubs, Rims, Pegs... inside Wheel Parts), like
     Skate's Protection type. Field `kind` is coming from Claude.
   - Then Hub Type, Toptube Length (shown within a wheel size), Drive Side.
5. **Older iPhones** (#118 follow-up): a regex lookbehind breaks old Safari.
   Low priority.

## How to work

- **Branch:** `grok/<topic>`, from the latest `main`. Open a PR and **don't
  merge**; the owner merges. **Never push to `main`.**
- **Keep `page.js` changes small and guarded.** Skate behaviour must not
  change unless the task says so. Task 1 changes Skate on purpose; tasks 2–4
  are BMX-only and gated on `SPORT_SETTINGS`.
- **Tests:**
  ```bash
  python -m unittest                  # whole suite; must stay green
  node --check page.js
  python ci/build_preview.py /tmp/site --data-root /tmp/bmxdata
  node ci/smoke.mjs /tmp/site /tmp/shots   # desktop + phone checks, screenshots
  ```
  Several tests cut functions out of `page.js` and run them, so a new
  global may need defining in those tests too (see `test_report_extras.py`).
- **Real BMX data locally:** copy it out of the preview branch:
  ```bash
  git fetch origin shreddeals-preview
  mkdir -p /tmp/bmxdata && git archive origin/shreddeals-preview _data | tar -x -C /tmp/bmxdata
  mv /tmp/bmxdata/_data/catalogs /tmp/bmxdata/catalogs
  ```
- **On a phone:** Actions → **ShredDeals - Preview Site** → Run workflow →
  scrape `none`, branch `grok/<topic>` → open the link in the run summary.
- **Don't touch:**
  - `sports/`, `stores/`, `scraper.py`, `filters.py`, `history.py`,
    `pipeline.py`, `ci/` and `.github/` (Claude's);
  - `previews/` and `navigation/` (Codex's);
  - data files.

  Ask through the owner if you need something there.
- **Never** enable alerts, email, a production deploy or a new service.
