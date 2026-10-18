# Skateboard Sale Scraper

Tracks skateboard sales at Zumiez, Skate Warehouse, CCS, and Tactics, then publishes a static HTML report. Skate Deluxe and Muir Skate stay in retailer activity, but both scrapers are off: Skate Deluxe is EUR-only and ships from Europe, and Muir Skate's Shopify storefront is unavailable. GitHub Actions runs the scraper daily. The page opens with what changed since yesterday, filterable deal rows, and a smaller header that states the live counts.

## Layout

```
├── scraper.py                 # Runner: isolated stores, report, email
├── schedule.py                # Backup cron no-op when today already succeeded
├── stores/                    # One module per store, shared Scraper interface
├── filters.py                 # Shared allowlists and passes_filters()
├── report.py                  # Catalog diff and digest
├── page.py                    # Static report (inlines page.css and page.js)
├── page.css                   # Report styles
├── mobile.css                 # Phone layout (≤800px), inlined after page.css
├── page.js                    # Filters, cards, charts, sort, stars, drawer, stats
├── notify.py                  # SMTP email for deals, watch alerts, store warnings
├── history.py                 # Bounded price history, images, and all-time lows
├── health.py                  # Per-store scrape counts and warnings
├── matching.py                # Conservative cross-store product match
├── dimensions.py              # Width, length, and wheelbase normalization
├── score.py                   # Deal score and the plain-language breakdown
├── query_state.py             # Filter URL encode and decode, starter views
├── badges.py                  # NEW, down today, lowest ever, back in stock
├── media.py                   # Product image URLs from each store
├── watchlist.py               # watchlist.yaml matching for the page and email
├── watchlist.yaml             # Email alert rules
├── site_sales.py              # Days since each store's last site-wide sale
├── pipeline.py                # Post-scrape bookkeeping (never fails the run)
├── sale_items_chart.html      # Generated report
├── previous_data.json         # Last catalog, for the diff
├── price_history.json         # Bounded daily sale prices
├── scrape_health.json         # Recent per-store, per-part counts
├── site_sales.json            # Per-store sale counts and last site-wide sale
└── .github/workflows/scrape.yml
```

The only workflow is `.github/workflows/scrape.yml`. It checks out the repo, installs Chrome, and runs `python scraper.py`.

The morning cron is `17 7 * * *` (3:17 AM EDT), off the top of the hour. A backup cron at `43 9 * * *` runs only when that morning scrape did not already succeed for the US Eastern date. `schedule.py` reads `scrape_health.json` after checkout and sets `scrape=false` when today's Eastern date already has a run with at least one store/part that did not fail. Chrome, the scrape, and the commit are skipped. `workflow_dispatch` always scrapes. A failed or skipped morning run leaves no successful health row, so the backup scrapes.

Each store runs on its own. An exception or a timeout (12 minutes) is logged, that store's parts are recorded as failed in `scrape_health.json`, and the other stores still finish. The report and the commit still happen. A failed part keeps the previous rows for that key.

Skate Deluxe (`skatedeluxe.com`) has no US or USD storefront. Prices on the public shop are euros and the site ships from Europe. `ENABLED` is false (`EUR-only European store; disabled by owner 2026-10-02`). The parser still reads `/en/c/sale` and is covered by a fixture, but the live run does not call it. Muir Skate is implemented against Shopify `products.json` and covered by a fixture, but `ENABLED` is false: on 2026-10-02 `muirskate.com` returned "This store is unavailable" in headless Chrome, and the collection JSON endpoints 404. Retailer activity still lists both stores as no recorded site-wide sale.

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
- Minimum width **7.5"** when a width can be parsed. Under 7.5" is a mini. There is no maximum: 9.75", 10.0", and 10.25" stay. Two-digit widths parse as widths. Cruisers and longboards are still out by keyword and by length, not for being wide.
- A `W x L` length of **34"** or more, or a lone length such as `30.75"`, is treated as a longboard.
- If no width is present, the deck can still pass the brand, discount, and keyword checks.

### Apparel (every part)

Whole-word hat, cap, shirt, tee, hoodie, jacket, pant, short, shoe, sneaker, sock, backpack, bag, beanie, glove, dress(es).

## Report

The report is one static file. CSS and JavaScript are inlined from `page.css`, `mobile.css`, and `page.js`. There is no server. New-feature failures are logged and do not stop the scrape or the commit.

- **Header**: a dark bar named SkateDeals, with Deals, Track, and Insights. Deals is the list, Track is the Watching filter, and Insights opens deals intelligence. The bar shows how long ago the last scan ran, and whether that scan is current. The visible time is relative (`14 minutes ago`); the exact Eastern timestamp is on hover. The freshness note turns amber when the last scan is older than 36 hours or a store/part failed that day. Hover the relative time for the exact scan timestamp in US Eastern, such as `Oct 1, 2026 8:21:37 AM ET`. Digest counts (all deals, new, price drops, hit lowest, disappeared) sit in the strip under that bar as compact chips. The baseline is a small dropdown, Since yesterday or Since your last visit. Sort and the table/cards switch are on that bar too.
- **What changed**: the digest row opens on **All deals**, so the All Deals table lists every current deal. **Since yesterday** and **Since your last visit** are a baseline switch for those counts. Neither one filters the table, and neither digest chip starts selected. New deals, price drops, and hit lowest tracked price filter the table; click the same chip again or **All deals** to show everything. **Deals disappeared** opens Recently gone and leaves the All Deals table alone. **Clear all** turns the digest chip off along with the other filters. Summary cards stay their own filters and do not select a digest chip. A URL or saved view selects a digest chip only when the query includes `change`. **Since your last visit** compares prices with the last time this browser opened the page (`localStorage` key `salesscraper2.snapshot`). That snapshot is not applied as a table filter.
- **Digest chips** are the filters for what changed. New deals, price drops, and hit lowest tracked price filter the table. Deals disappeared opens Recently gone and leaves the All Deals list alone. Press the same chip again, or All deals, to clear it. A URL can still set the older summary flags (`added`, `dropped`, `low`) without selecting a digest chip.
- **Store check** is not a banner. A Diagnostics link in the footer opens the list. An empty category is a warning only when it usually has items: not empty on most recent runs, and not a low median. A failed fetch still warns after two bad runs. One empty or failed run does not warn. The next run that returns items clears an empty streak. A baseline is dropped when the saved run on its own date is empty or failed, including on a later scrape, so a corrected one-item scrape is not the last good run.
- **Retailer activity**: one line per store, `last site-wide sale N days ago` or `no recorded site-wide sale`. When the latest scan itself trips the spike rule, a banner names the store, how much higher the sale count is than the recent median, and how many hours ago the scan ran. The same banner and lines are in the email. Skate Warehouse's seed does not raise the banner.
- **All-time lows** (collapsed): listings whose current sale price is the lowest tracked price. A listing needs at least 3 observations spanning 7 days, so a brand-new item is not flagged just because its first price is the only price. The low can be older than the 90-day daily window. Column headers sort the table, and Sale price starts low to high. Search, price, store, type, and brand use the same choices as All Deals. Width, discount, score, and deal type do not hide these rows.
- **Across stores** (open when there is something to show): the same product at two or more stores, with the cheapest price highlighted. Matching requires the same part, brand, and size, plus the same distinctive model words. Deck widths that are just rounding differences snap together (8.12 and 8.125, 8.38 and 8.375). 8.475 does not snap to 8.5. Colors and extra words keep two listings apart. A name that is only a brand and a size (or only generic words like "team") is not grouped. Wheel matches also require a diameter. Truck matches require a hanger or axle size, so hollow and standard stay apart. **Group across stores** collapses those same matches into one entry that reads `Product - from $44.99 - 3 stores`. Expanding it shows `Best price:` at the cheapest store, then the other stores sorted by price, each with availability (on sale, sold out, or gone) and a link to its product page. **Price history** on that card opens the combined graph. Matching stays conservative; the toggle does nothing when no pair exists.
- **Filters** sit in a left sidebar flush to the edge, directly under the top bar. The page uses the full window width. The top of the page is three rows: a dark bar with SkateDeals, Deals, Track, Insights, the last scan time, and whether the scan is current; one slim row of small store and product chips, with the count on the same line as the name; then search, the active-filter chips, the result count, the deal-activity chips, the baseline, sort, the table/cards switch, and Group across stores. Store chips are All stores, then Zumiez, Tactics, SkateWarehouse, and CCS when those stores are in the catalog. Any other store, and any store chip that does not fit on that single line, sits in + More stores, which stays hidden when it is empty. Product chips are All, Decks, Trucks, and Wheels when those parts are in the catalog, plus Bearings or Completes only when the catalog has them. Other parts, and any product chip that does not fit on that line, sit in + More. Store and product chips are only in that header row. Store and product selections combine. A fresh visit, and a saved view with no type, selects Decks and leaves `type` out of the URL. `type=deck` still means Decks. `type=all` means every product type, and existing links that name a type keep that type. Decks is the default, so it does not add a type chip; All types and the other types do, and clearing that chip returns to Decks. The sidebar no longer repeats Store or Product Type. With Decks selected it opens on deck width and length. Wheels opens on diameter and durometer. Trucks opens on size, height, and construction when the name says hollow or standard. Brand stays next, then Price, Discount, and Deal quality. Deal Type, Drop Interval, Saved Views, Watching, and Bookmarks follow, collapsed. Choosing All products puts Brand, Price, Discount, and Deal quality first, and folds the spec sections into Product specifications. Picking a spec there switches the product type to that category. A sale at its tracked low reads At lowest tracked price until it meets the existing 3-observation, 7-day rule, then Verified low. A qualified low reached in this scan reads New low and is the only loud one of the three. Highlights stays inside Deal Type. All types shows only those shared filters, plus Price, Discount, and Score. Deck Width, length, and wheelbase appear only when Type is Decks, and Deck Width starts expanded. Wheel diameter, durometer, and shape appear only for Wheels. Truck size and height appear only for Trucks. ABEC appears only for Bearings. A spec section is left out when fewer than 5 listings have that value printed in the name. Drop interval stays visible for every type because it filters price history, not a product measurement. Switching type hides a spec section and keeps the selection; the active-filter chip stays, so the list is never filtered in silence. Wheel, truck, and bearing specs restrict only that type. Length and wheelbase apply only while Decks is selected. Specs for another product type stay remembered and return with that type, and they do not change the list on screen. Price, Discount, Score, Length, Saved Views, and Actions start closed. The sidebar is about 200px wide and scrolls on its own; the results scroll separately. Drop interval (Day, Week, Month, 3 Months, All) keeps items whose tracked price fell by at least $2 or 5% versus the previous daily price inside that window. All is the default and does not hide anything. Deal type reuses the existing New, price-drop, all-time-low, back-in-stock, Watching, and hot (score 70+) rules, with a count beside each. Highlights, in that same list, shows the new deals and biggest drops already chosen for deals intelligence. Price, discount, and score also have a two-handle slider. A category strip above the deals (Decks, Trucks, Wheels, Bearings, when those parts are in the report) sets the same Type filter. Saved views, including the starter presets, are one-click bookmarks in the sidebar. Bookmark this selection uses the existing Save view form. This browser remembers which sections are open (`salesscraper2.filterSections`). Store options include the deal count, such as `Zumiez (274)`. Wheelbase appears when at least 5 listings have that measurement. Watching, Group across stores, Save view, and Clear all stay at the bottom of the sidebar. Clear all also sits at the top of the sidebar. Active choices show up as removable chips in the results toolbar. On a phone the sidebar is a Filters button that opens a slide-in drawer, and the search box stays sticky at the top. Deck width is a two-column grid labeled `7.5`, `7.75`, `8.0`, `8.25`, `8.5`, `8.75`, `9.0`, and `10+`. Each button's tooltip is the real half-open range: `7.5` is 7.5" up to 7.75", `7.75` is 7.75" up to 8.0", `8.0` is 8.0" up to 8.25" (the 8.0–8.125 and 8.125–8.25 buckets), `8.25` is 8.25" up to 8.5" (8.25–8.375 and 8.375–8.5), `8.5` is 8.5" up to 8.75", `8.75` is 8.75" up to 9.0", `9.0` is 9.0" up to 10.0" (9.0–9.25, 9.25–9.5, and 9.5–10.0), and `10+` is 10.0" and wider. Buckets under 7.5" are not shown. The count inside a button is how many decks in those buckets match the other filters. A button with none is dimmed. Several buttons can be on at once. Each exact width still belongs to one underlying bucket: the low end is included and the high end is not, so 8.5" is the `8.5` button and 10.0" is `10+`. The chips filter deck rows only. Wheels, trucks, and bearings stay in the list when a range is selected; they leave only when Type is also Decks. A deck with no parsed width is hidden while any range is on. `8.5` and `8.50` are the same width. Brand is a list of the brands on the page, with a search box. Spellings that differ only by case, such as 5boro and 5Boro, share one entry, and a brand filter matches either spelling. The brand list is a fixed-height scroller under the brand search box. Counts match the other filters, not the whole catalog. Each brand, store, type, length, and width value shows how many deals match the other filters. A zero stays in the list, dimmed, instead of disappearing. Those filters hide table rows and cards. Length and wheelbase dropdowns appear only when at least 5 listings have that measurement. Filters are stored in the URL and restored on load. `width=8.5-8.75` is that chip. `scoremin` and `scoremax` limit the deal score. `width=8.25` and `width=8.25-8.5` from older links still open the buckets that contain those sizes (an old inclusive window that is not itself a chip also includes the bucket that holds its upper end). **Save view** keeps a named bookmark in this browser, with rename and delete. Four starter views stay on the page: Decks 8.25–8.5 at 35% off or more (the chips that cover that window, including `8.5 - 8.75` so an 8.5" deck is included), 8.5 decks under $50 (the `8.5 - 8.75` chip), new Skate Warehouse drops, and watched items at an all-time low. The last two include `type=all`, so they still list every product type now that a missing type means Decks.
- **All Deals**: sortable columns for sale price, original price, percent off, size (numeric), store, brand, days tracked, days at the current price, and deal score. The days cell reads `194d tracked · 1d @ $39.99`, with a ↓ / ↑ / → trend beside it. The default order is newest deals and the biggest recent drop. Headers stick under the filter bar. Each row has an 84px thumbnail (lazy-loaded; a placeholder when the store did not provide an image), a star, a quieter badge row, the lifecycle stage, and a sparkline beside the sale price. The sale price is the loud number; the original price is lighter and struck through. The product title is the loudest text in the row and links to the store page in a new tab. Hover or tap a sparkline, or a point on the price-history chart, for that point's date and exact price. A price reduction on the chart is a larger green marker, and its tooltip says Price reduction. The line is green when the latest change in the selected 30, 90, or 180 day window is a drop, red when that change is an increase, and gray when the price is flat. A dot marks the current price. Click the row or the sale price to open the price-history dialog.
- **Product detail**: click a row, a card, or the sale price. A dialog shows width, length, and wheelbase when the store exposed them, each store's price with the cheapest one marked, availability (on sale, sold out, or gone), and a price graph. The graph switches between 30, 90, and 180 days. Daily prices in `price_history.json` are kept for 90 days; the 180-day view adds the all-time low when that low is older than the daily prices. Green marks a price reduction, purple marks back in stock, gray marks gone, and gold marks the all-time low. A gap of two or more missing days is the stock change. When the same product is at several stores, those stores share one graph. The history line uses one color.
- **Table or cards**: the top bar switches between the table and a card grid. Cards show a prominent percent-off badge, `Now:`, and `Average:` when that mean differs from the current price. The line under the price says `Price unchanged since`, `Dropped from $X on`, or `Up from $X on`, using the tracked prices. A short sparkline sits at the bottom left (a slim flat line when the window does not move) and still uses green, gray, or red for the latest change. All-time low is small muted text. New, back in stock, a drop in the last 3 days, and HOT stay prominent. Clicking the card, other than Details or the retailer link, opens the price-history dialog with the chart, every matched store, and a link out. Hover or tap Details for the rest of the badges and the score breakdown. The desktop grid shows two fewer cards per row than the old 176px minimum, so the cards are wider, and a phone still shows two. Average wraps onto its own line when it does not fit beside Now, and Now stays on one line. Each card title is a fixed three-line box with an ellipsis, and the price, percent off, sparkline, and Details link line up from card to card. A card with no original price shows a neutral “No discount info” label instead of a percent-off badge. The choice is saved in this browser (`salesscraper2.layout`).
- **Price drawer**: the older drawer is still in the page. The sale price opens the detail dialog. Hover or tap the sparkline for the date and exact price.
- **Lifecycle**, stored on each history row: NEW, then PRICE DROP once the sale price is below an earlier tracked price, then ALL-TIME LOW when that rule qualifies, then SOLD OUT when a successful scrape no longer lists it, then GONE after 7 days. A failed scrape does not move a listing to SOLD OUT. The row shows the current stage.
- **Recently gone** (muted, collapsed): SOLD OUT listings from the last 7 days, with the last price and the last seen date. The "deals disappeared" count opens this view and does not filter All Deals. A failed fetch keeps the previous items for that key instead of writing `[]`, so a blocked page does not look like everything sold out. Column headers sort the table, and Last price starts low to high. Search, price, store, type, and brand use the same choices as All Deals. Width, discount, score, and deal type do not hide these rows.
- **Deals intelligence** opens from Insights, not from a highlights dropdown on the deals list. Highlights in Deal Type shows those same new deals and biggest drops in the current table or card grid. The panel still has the biggest price drop, the highest average discount, and the store with the most good discounts. The long good-discount explanation is a tooltip. It also lists new deals today, the biggest drops, average discount by retailer, and stores with the most good discounts. A good discount is at least 30% off and within $2 or 5% of the lowest tracked price, and that low only counts after 3 observations spanning 7 days. The same panel still has deals by width, brands with the most markdowns, lowest average deck prices by brand (brands with at least two decks), and the weekly deck sale-price trend. The score formula sits on the Score column info control and in each score tooltip.
- Rows that fail `passes_filters()` are not listed as new, dropped, or removed.
- The footer links to [Run scraper now](https://github.com/pchoward/salesscraper2/actions/workflows/scrape.yml).

On the 2026-09-30 catalog, 114 of 173 filtered listings were at an all-time low. None of them were the same product at two stores, so Across stores stays empty until a real pair shows up. Image URLs are stored on the next scrape; rows scraped before that show the placeholder.

### Badges

- **NEW**: not in yesterday's catalog and not seen on an earlier day.
- **BACK IN STOCK**: first seen before today, missing from yesterday, present again. This replaces NEW.
- **down $X TODAY**: the sale price fell by at least $2 or 5% versus the previous tracked sale price.
- **LOWEST EVER**: the current sale price is the all-time low under the 3-observation / 7-day rule. A plain price drop does not get this badge.

A row can show a drop and LOWEST EVER together. Watchlist matches get a Watchlist pill.

### Deal score

```
Deal score (0-100) = discount + lowest + recent drop + popular size
```

- Discount is the percent off the original price, capped at 50. A missing original price adds 0.
- Lowest tracked price adds 25 at the all-time low, 18 within $1 or 3% above it, and 10 within $2 or 5%. This part stays 0 until the listing has at least 3 observations spanning 7 days.
- A meaningful drop versus the previous sale price ($2 or 5%) adds 8 points plus 1 point per 5% of that drop, up to 15. A smaller day-to-day dip adds 4.
- A deck from 8.25" to 8.75" adds 10.

Hot means 70 or above. The score button opens a breakdown of the four factors that are actually added: discount depth (max 50), closeness to the lowest tracked price (0–25), recent drop (0–15), and width fit (10 when the deck is 8.25–8.75). Days tracked are listed as context and are not added. The same legend sits above the table. The number is colored: 70 or above hot, 45 or above green, 25 or above amber, and below that gray. A price that changed today or yesterday is labeled Freshly reduced. The column sorts. The numeric formula is unchanged.

### Stars

The star on each row is saved in this browser under `salesscraper2.stars`. **Watching** shows only starred rows. That list is separate from `watchlist.yaml`, which drives the email.

## Watchlist

`watchlist.yaml` is a short list of rules. A match is highlighted on the report. It is an email alert only when a trigger fires. Rules with none of the trigger fields alert when the product is new, back in stock, or the sale price drops by any amount. A match that stays at the same price stays highlighted and does not send another email by itself.

| Field | Meaning |
| --- | --- |
| `id` | Short name used in the email. Optional. |
| `brand` | Brand-wide. Every word must appear in the name. Powell Peralta does not match a Powell deck that is not Peralta. |
| `name` | One product. Antihero matches Anti-Hero and Anti Hero. |
| `part` | Decks, Wheels, Trucks, or Bearings. Defaults to Decks. |
| `min_width` | Inches, inclusive. 8.6 matches 8.60 and anything wider. A deck with no parseable width does not match. |
| `max_width` | Inches, inclusive upper bound. With `min_width`, a range such as 9.5 through 10.0. |
| `width` | Exact inches. 8.5 matches 8.50 and does not match 8.25. Use with `brand`, `part`, and `max_price` for a rule such as any 8.5 inch Anti Hero deck under $50. |
| `max_price` | Alert when the sale price is under this amount and yesterday it was missing or not under it. The row stays highlighted when brand, part, and width match, even above this price. |
| `alert_on_drop` | `true` alerts on any sale-price drop, including under $2 / 5%. |
| `alert_on_low` | `true` also emails when a matching product newly hits its all-time low. A product already at that low yesterday does not send another email. This does not turn off the other alerts. |
| `back_in_stock_width` | Alert only when this width comes back in stock. |
| `note` | Shown in the email. |

Seeded rules, with no target prices:

- Black Label, Powell Peralta, and Heroin decks at 8.6 inches and wider.
- The Antihero Caster deck, any width (the one at Skate Warehouse).

Add another rule by appending a `- id:` block. The commented example in the file shows `max_price`, `alert_on_drop`, and `back_in_stock_width` together. A broken or missing file is logged and treated as no rules.

Matching watchlist alerts are a block at the top of the email. Quiet matches are listed under that as still on sale.

## Site-wide sales

`site_sales.json` records filtered sale counts per store and the last day that looked like a site-wide sale. The scraper only sees sale listings, not the whole catalog. A day counts when all of these are true:

- the count is at least **2.5×** the median of the previous 14 recorded days
- the count is at least **30** items above that median
- at least **7** earlier days are on record

Skate Warehouse is seeded at **2026-07-04**. A detected day replaces that date only when it is later. The date never moves backward. Other stores stay "no recorded site-wide sale" until a day clears the threshold. Daily counts are kept about 120 days. The last-sale date is stored on its own, so trimming the counts does not forget it. The retailer activity panel and the email use the same lines. A sale detected on the latest scan also adds a banner; the seed date does not.

## Price history

`price_history.json` is committed every day, so it has to stay bounded. Each listing keeps:

- daily sale prices for the last **90 days** (`date >= today - 90 days`)
- a summary that is not trimmed with that window: first seen, last seen, observation count, and the all-time low price with the date it was first hit

Listings the current filters reject are dropped (cruiser, mini, off-brand, apparel, and so on). A deck with no original price in this file is kept, because the history never stored MSRP and the discount rule cannot be applied. Size and keyword rejections still apply. A URL in the current passing catalog is always kept. Listings not seen for more than **180 days**, and not in the current catalog, are dropped.

Each listing can also keep the last image URL and parsed width, length, and wheelbase. Those fields are filled when the scraper sees them. A problem in pruning, store health, images, the watchlist, site-wide sales, or the report is logged and does not stop the scrape or the commit.

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

After each scrape, `notify.py` emails that same digest. Mail goes out when there is at least one new listing, a meaningful price drop ($2 or 5% versus the previous tracked sale price), a broken-store warning, or a watchlist alert. A warning or a watchlist alert sends even on a day with no other deals. Removals alone do not send mail. An empty digest with no store warning and no watchlist alert does not send mail.

The message is HTML plus a plain-text fallback, grouped by part (Decks, Wheels, Trucks, Bearings). Each row has the store, the product name linked to the store page, the sale price, and the original price with percent off. Price drops also show the previous sale price and the dollar and percent change. Rows at an all-time low are badged, and the message says how many tracked deals are at an all-time low. When the cheapest store is at least $2 or 5% under the highest for the same product, that comparison is included. A store warning is a block at the top. Watchlist alerts sit above the parts, and each store's days-since-last-site-wide-sale line follows. The message links to the full report on GitHub Pages.

The scraper uses the Python standard library (`smtplib` and `email.message`). There is no new dependency. If a required setting is missing, the run logs one line and continues. If SMTP fails, the error is logged and the scrape still exits successfully, so the workflow can commit `sale_items_chart.html`, `previous_data.json`, `price_history.json`, `scrape_health.json`, and `site_sales.json`.

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

Dry-check the filters, email, history prune, store warnings, cross-store match, deal score, badges, watchlist, site-wide sales, dimensions, and image extraction (no network):

```bash
python test_filters.py
python test_notify.py
python test_history.py
python test_health.py
python test_matching.py
python test_pipeline.py
python test_score.py
python test_badges.py
python test_watchlist.py
python test_site_sales.py
python test_dimensions.py
python test_media.py
python test_stores.py
python test_charts.py
python test_intel.py
python test_report_extras.py
```

## Before / after

From the catalog already in `previous_data.json` (190 listings → 163 kept):

| Listing | Before | After |
| --- | --- | --- |
| SKF Ishod / Louie / Kader / Tiago bearings | Kept (no bearing brand filter) | Dropped |
| Modus ABEC 5 / 7 / Titanium bearings | Kept | Dropped |
| Daddies Trip On This Cruiser deck, Rout Flash Cruiser | Kept | Dropped |
| April MINI Deck 7.25 | Kept at 10% off | Dropped (mini deck, under 7.5") |
| Santa Cruz 10.03 / Heroin 10.25 | Width not parsed, so it stayed | Parsed as 10.x. An earlier 9.5" cap dropped them; that cap is gone, so a wide street deck stays |
| Loaded Hola Lou Coyote 30.75 | Kept | Dropped (longboard length) |
| OJ Dressen wheels, Independent Eric Dressen trucks | Kept | Kept (`Dressen` is not `dress`) |
| Flip Penny 8.1 deck | Kept | Kept (pro model, not a Penny board) |
| Baker 8.125 at ~14% off | Kept at the old 10% floor | Kept (known brand, still ≥10%) |
| Vinyl decks at 12% off | Kept | Dropped (unknown brand under 15%) |

`price_history.json` was pruned under the rules above. Listings those filters reject are no longer kept in the history.
