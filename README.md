# Skateboard Sale Scraper

Tracks skateboard sales at Zumiez, Skate Warehouse, CCS, and Tactics, then publishes an HTML report. GitHub Actions runs the scraper daily. The page leads with a short digest of new deals and real sale-price drops.

## Layout

```
├── scraper.py                 # Selenium fetch + per-store parsers
├── filters.py                 # Shared allowlists and passes_filters()
├── report.py                  # Catalog diff + HTML report
├── notify.py                  # SMTP email for new deals and price drops
├── test_filters.py            # Dry-check the filters without scraping
├── test_notify.py             # Dry-check the email digest without SMTP
├── sale_items_chart.html      # Generated report
├── previous_data.json         # Last catalog, for the diff
├── price_history.json         # Daily sale prices
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

- **Digest** (open): new listings, plus sale-price drops of at least **$2 or 5%** versus the previous tracked sale price. The change is labeled as dollars and percent versus that prior sale, not versus MSRP.
- **All Deals** (collapsed): the filtered catalog, still searchable.
- **Removed** (collapsed, only when there is something to show): hidden unless that store/part scrape succeeded. A failed fetch keeps the previous items for that key instead of writing `[]`, so a blocked page does not look like everything sold out.
- Rows that fail `passes_filters()` are not listed as new, dropped, or removed.

## Email alerts

After each scrape, `notify.py` emails that same digest. Mail goes out only when there is at least one new listing or a meaningful price drop ($2 or 5% versus the previous tracked sale price). Removals alone do not send mail. An empty digest does not send mail.

The message is HTML plus a plain-text fallback, grouped by part (Decks, Wheels, Trucks, Bearings). Each row has the store, the product name linked to the store page, the sale price, and the original price with percent off. Price drops also show the previous sale price and the dollar and percent change. The message links to the full report on GitHub Pages.

The scraper uses the Python standard library (`smtplib` and `email.message`). There is no new dependency. If a required setting is missing, the run logs one line and continues. If SMTP fails, the error is logged and the scrape still exits successfully, so the workflow can commit `sale_items_chart.html`, `previous_data.json`, and `price_history.json`.

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

Dry-check the filters and the email digest (no network):

```bash
python test_filters.py
python test_notify.py
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

`price_history.json` is left as-is. A later cleanup can trim entries for listings the filters now reject.
