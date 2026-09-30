# Skateboard Sale Scraper

Tracks skateboard sales at Zumiez, Skate Warehouse, CCS, and Tactics, then publishes an HTML report. GitHub Actions runs the scraper daily. The page leads with a short digest of new deals and real sale-price drops.

## Layout

```
├── scraper.py                 # Selenium fetch + per-store parsers
├── filters.py                 # Shared allowlists and passes_filters()
├── report.py                  # Catalog diff + HTML report
├── notify.py                  # SMTP email for deals and store warnings
├── history.py                 # Bounded price history and all-time lows
├── health.py                  # Per-store scrape counts and warnings
├── matching.py                # Conservative cross-store product match
├── pipeline.py                # Post-scrape bookkeeping (never fails the run)
├── test_filters.py            # Dry-check the filters without scraping
├── test_notify.py             # Dry-check the email digest without SMTP
├── test_history.py            # Pruning and all-time-low rules
├── test_health.py             # Two-bad-runs warning and recovery
├── test_matching.py           # Cross-store match and report sections
├── test_pipeline.py           # Bookkeeping stays non-fatal
├── sale_items_chart.html      # Generated report
├── previous_data.json         # Last catalog, for the diff
├── price_history.json         # Bounded daily sale prices
├── scrape_health.json         # Recent per-store, per-part counts
└── .github/workflows/scrape.yml
```

The only workflow is `.github/workflows/scrape.yml`. It checks out the repo, installs Chrome, and runs `python scraper.py`.

## Filter rules

Every store parser and the report call `passes_filters()` in `filters.py`. A listing the parsers drop cannot come back through Recent Changes or the digest.

Names from Skate Warehouse are normalized first: a leading `Clearance` / `Sale`, a non-breaking space, and a glued `-N%` are stripped before brand and size checks.

### Wheels

Bones, Powell, Spitfire, OJ. Case-insensitive, whole word. `OJ` does not match a longer token such as `Mojo`.

### Trucks

Independent, Indy, Ace, Thunder, Venture, Slappy. Whole words, so `Ace` does not match `Space` or `Face`.

### Bearings

Bones (including Bones Swiss), Bronson, CeramicSpeed, Independent, Zealous, Andalé / Andale, Pixel. Case-insensitive. SKF, Modus, and unbranded packs are out.

### Decks

- Known street brands (Baker, Deathwish, Creature, Anti-Hero, Girl, Chocolate, Real, Element, Habitat, Welcome, Birdhouse, Flip, Almost, Plan B, Santa Cruz, Powell, Blind, Enjoi, DGK, and other established brands listed in `filters.py`): **≥10%** off the original price.
- Any other brand: **≥15%** off.
- No original price: dropped.
- Out if the name or URL says cruiser, longboard, mini deck, penny board, or a complete. `Flip Penny` stays (pro model). `dress` does not match `Dressen`. `short` does not match `Shorty's`.
- Width window **7.5–9.5"** when a width can be parsed (the street range around 7.5–9.0, with a little room for shaped decks such as 9.18–9.3). Under 7.5" is a mini. Over 9.5" (including 10.x, which now parses) is out.
- A `W x L` length of **34"** or more, or a lone length such as `30.75"`, is treated as a longboard.
- If no width is present, the deck can still pass the brand, discount, and keyword checks.

### Apparel (every part)

Whole-word hat, cap, shirt, tee, hoodie, jacket, pant, short, shoe, sneaker, sock, backpack, bag, beanie, glove, dress(es).

## Report

- **Store check** (only when needed, at the top): a store and part that normally has items came back empty, or the scrape failed, two runs in a row. One empty or failed run does not warn. The next run that returns items clears it.
- **Digest** (open): new listings, plus sale-price drops of at least **$2 or 5%** versus the previous tracked sale price. The change is labeled as dollars and percent versus that prior sale, not versus MSRP. Rows at an all-time low are badged.
- **All-time lows** (collapsed): listings whose current sale price is the lowest tracked price. A listing needs at least 3 observations spanning 7 days, so a brand-new item is not flagged just because its first price is the only price. The low can be older than the 90-day daily window.
- **Across stores** (open when there is something to show): the same product at two or more stores, with the cheapest price highlighted. Matching requires the same part, brand, and size, plus the same distinctive model words. Deck widths that are just rounding differences snap together (8.12 and 8.125, 8.38 and 8.375). 8.475 does not snap to 8.5. Colors and extra words keep two listings apart. A name that is only a brand and a size (or only generic words like "team") is not grouped. Wheel matches also require a diameter. Truck matches require a hanger or axle size, so hollow and standard stay apart.
- **All Deals** (collapsed): the filtered catalog, still searchable, with the all-time-low badge and a short trend arrow.
- **Removed** (collapsed, only when there is something to show): hidden unless that store/part scrape succeeded. A failed fetch keeps the previous items for that key instead of writing `[]`, so a blocked page does not look like everything sold out.
- Rows that fail `passes_filters()` are not listed as new, dropped, or removed.

On the 2026-09-30 catalog, 114 of 173 filtered listings were at an all-time low. None of them were the same product at two stores, so Across stores is empty until a real pair shows up.

## Price history

`price_history.json` is committed every day, so it has to stay bounded. Each listing keeps:

- daily sale prices for the last **90 days** (`date >= today - 90 days`)
- a summary that is not trimmed with that window: first seen, last seen, observation count, and the all-time low price with the date it was first hit

Listings the current filters reject are dropped (cruiser, mini, off-brand, apparel, and so on). A deck with no original price in this file is kept, because the history never stored MSRP and the discount rule cannot be applied. Size and keyword rejections still apply. A URL in the current passing catalog is always kept. Listings not seen for more than **180 days**, and not in the current catalog, are dropped.

The prune runs at the end of every scrape. A problem in pruning, store health, or the new report sections is logged and does not stop the scrape or the commit.

Cleanup of the file already in the repo, on 2026-09-30, without rewriting git history:

| | Before | After |
| --- | ---: | ---: |
| File size | 2,003,420 bytes | 1,015,967 bytes |
| Listings | 2,726 | 1,574 |
| Daily price points | 51,233 | 15,400 |

About 1 MB is the steady size: roughly the current catalog, one point a day, for 90 days. It no longer grows by every past day.

## Store health

`scrape_health.json` keeps the last 30 runs of per-store, per-part item counts, plus the last time each key actually had items. A failed fetch counts as a bad run even though the report still shows the previous rows. The same calendar day replaces that day's row, so a manual re-run is not a second failure. Keys that have never had items (bearings are often empty) do not warn.

## Email alerts

After each scrape, `notify.py` emails that same digest. Mail goes out when there is at least one new listing, a meaningful price drop ($2 or 5% versus the previous tracked sale price), or a broken-store warning. A warning sends even on a day with no deals. Removals alone do not send mail. An empty digest with no store warning does not send mail.

The message is HTML plus a plain-text fallback, grouped by part (Decks, Wheels, Trucks, Bearings). Each row has the store, the product name linked to the store page, the sale price, and the original price with percent off. Price drops also show the previous sale price and the dollar and percent change. Rows at an all-time low are badged, and the message says how many tracked deals are at an all-time low. When the cheapest store is at least $2 or 5% under the highest for the same product, that comparison is included. A store warning is a block at the top. The message links to the full report on GitHub Pages.

The scraper uses the Python standard library (`smtplib` and `email.message`). There is no new dependency. If a required setting is missing, the run logs one line and continues. If SMTP fails, the error is logged and the scrape still exits successfully, so the workflow can commit `sale_items_chart.html`, `previous_data.json`, `price_history.json`, and `scrape_health.json`.

Add each value as its own secret. In the GitHub repo: **Settings → Secrets and variables → Actions → New repository secret**.

| Secret | Required | Purpose |
| --- | --- | --- |
| `SMTP_HOST` | yes | SMTP server hostname |
| `SMTP_PORT` | no | Default `587` |
| `SMTP_USER` | yes | SMTP username |
| `SMTP_PASSWORD` | yes | SMTP password or API key |
| `EMAIL_FROM` | no | From address. Defaults to `SMTP_USER` |
| `EMAIL_TO` | yes | Recipients, comma-separated |
| `SMTP_SECURITY` | no | `starttls` (default) or `ssl` (use with port 465) |
| `REPORT_URL` | no | Full-report link. Defaults to `https://pchoward.github.io/salesscraper2/sale_items_chart.html` |

GitHub Pages for this repo is the `main` branch at the site root, so that default is the published `sale_items_chart.html`. Do not put addresses in the workflow file. Empty secrets are skipped.

### Gmail

Host `smtp.gmail.com`, port `587`, leave `SMTP_SECURITY` unset (`starttls`). The Google account needs 2-Step Verification. Create an app password and use that as `SMTP_PASSWORD` (not the normal account password). `SMTP_USER` is the Gmail address. Set `EMAIL_FROM` to that same address, or leave it unset.

### Outlook / Microsoft 365

Host `smtp.office365.com`, port `587`, `starttls`. Many Microsoft 365 tenants disable SMTP AUTH, and personal Outlook.com accounts may need an app password, so this may not work.

### Resend or Brevo

A transactional SMTP relay is the reliable option when mailbox SMTP is blocked.

- Resend: host `smtp.resend.com`, port `587` with `starttls` (or port `465` with `SMTP_SECURITY=ssl`). Username `resend`. Password is a Resend API key. `EMAIL_FROM` must be on a domain you have verified in Resend.
- Brevo: host `smtp-relay.brevo.com`, port `587` with `starttls`. Username is the SMTP login from Brevo (it looks like `something@smtp-brevo.com`, not the relay hostname). Password is the SMTP key from Brevo, not the API key.

### Preview without sending

`EMAIL_DRY_RUN=1` or `python scraper.py --email-dry-run` writes `email_preview.html` (gitignored) and does not connect. To review the layout without scraping or credentials, build a labeled sample from the current catalog:

```bash
python notify.py --sample --dry-run
```

That writes `email_preview.html`. Product names are prefixed with `[SAMPLE]`, and the page says it is not a live alert.

## Run

```bash
python scraper.py
```

Chrome or Chromium is required. The browser runs headless.

Dry-check the filters, email, history prune, store warnings, and cross-store match (no network):

```bash
python test_filters.py
python test_notify.py
python test_history.py
python test_health.py
python test_matching.py
python test_pipeline.py
```

## Before / after

From the catalog already in `previous_data.json` (190 listings → 163 kept):

| Listing | Before | After |
| --- | --- | --- |
| SKF Ishod / Louie / Kader / Tiago bearings | Kept (no bearing brand filter) | Dropped |
| Modus ABEC 5 / 7 / Titanium bearings | Kept | Dropped |
| Daddies Trip On This Cruiser deck, Rout Flash Cruiser | Kept | Dropped |
| April MINI Deck 7.25 | Kept at 10% off | Dropped (mini deck, under 7.5") |
| Santa Cruz 10.03 / Heroin 10.25 | Width not parsed, so it stayed | Parsed as 10.x and dropped (above 9.5") |
| Loaded Hola Lou Coyote 30.75 | Kept | Dropped (longboard length) |
| OJ Dressen wheels, Independent Eric Dressen trucks | Kept | Kept (`Dressen` is not `dress`) |
| Flip Penny 8.1 deck | Kept | Kept (pro model, not a Penny board) |
| Baker 8.125 at ~14% off | Kept at the old 10% floor | Kept (known brand, still ≥10%) |
| Vinyl decks at 12% off | Kept | Dropped (unknown brand under 15%) |

`price_history.json` was pruned under the rules above. Listings those filters reject are no longer kept in the history.
