# ShredDeals publisher facts

Verified facts for the About and How ShredDeals Works pages, the guides and the publisher profile (Codex's publisher-readiness brief, 2026-11-23). Quote these instead of guessing. Each fact names its source in the code, so it can be re-checked.

Numbers are as of **2026-11-23**. Claude keeps this file current when stores or rules change.

## What ShredDeals is
- A deal finder for four sports: **Skate, BMX, Ski and MTB**.
  - There is no snowboard section. Snowboards are not scraped (owner, 2026-11-21).
  - Don't write "skiing/snowboarding". Ski covers skis, boots, bindings, poles, helmets, goggles, protection and packs.
- It lists only items a store has marked down. Each listing links straight to the store's own product page, and the purchase happens at the store.
- **The site doesn't sell anything.** As of this date it has **no affiliate links and no affiliate partnerships**: every store link is a plain link.

## Coverage on 2026-11-23

| Sport | Listings | Stores with listings | Price history since |
|---|---|---|---|
| Skate | 1,922 | 15 | 2026-08-25 |
| BMX | 1,774 | 24 | 2026-11-01 |
| Ski | 3,248 | 16 | 2026-11-01 |
| MTB | 5,102 | 21 | 2026-11-02 |

Sources: `previous_data.json` (root for Skate, `catalogs/<sport>/` for the others) and `price_history.json`.

**Stores:**
- **Skate:** 187 Killer Pads, CCS, Deathgear, Demon, Exodus, Kinetic, SPoT, SkatePro, Skate Warehouse, SoCal, Sourceboards, TGM, Tactics, Triple 8, Zumiez.
- **BMX:** 187 Killer Pads, 7iDP, Albe's BMX, Bikes Online, CCS, Cambria, Circuit BMX, Colorado Cyclist, Demon, Exodus, Fiend, G-Form, Haro, Kali, Kink, Powers BMX, SkatePro, SoCal, Source BMX US, Sparky's Brands, TGM, Tactics, Triple 8, Troy Lee Designs.
- **Ski:** Aspen Ski and Board, Bern, Christy Sports, Demon, EVOC, evo, Gear West, SkatePro, Ski Essentials, Skipro, Smith, The House, The Pro Ski and Ride, Triple 8, Utah Ski, Willis Ski and Board.
- **MTB:** 7iDP, Alpinestars, Bern, Bicycle Warehouse, Bike Mart, Bikes Online, Cambria, Colorado Cyclist, Demon, EVOC, evo, Fanatik, G-Form, Kali, Mike's Bikes, Race Face, Smith, The Lost Co., Troy Lee Designs, Worldwide Cyclery, Zeitbike.

Store lists change, so don't hard-code counts in pages. If a page shows counts, compute them at build time.

## How often data refreshes
These are the GitHub Actions schedules, in UTC. GitHub can run a scheduled job late or skip it; on 2026-11-21 the 21:37 run didn't start. So say "**daily**", never "real-time" or "hourly".

| What | When (UTC) | Source |
|---|---|---|
| Skate scrape | 07:17, with backups at 09:43, 12:41, 15:47 and 18:53. A backup runs only if that day's scrape hasn't succeeded. | `.github/workflows/scrape.yml` |
| BMX, Ski and MTB scrapes | 21:37, with backups at 00:19 and 03:23 | `.github/workflows/scrape-sports.yml` |
| Sale check (store-wide sale banners) | every 2 hours | `.github/workflows/sale-sniffer.yml` |
| Promo-code check | 06:47 and 21:07 | `.github/workflows/promo-check.yml` |

## What counts as a deal
From `filters.py`:
- **Minimum markdown:** at least **5% off** the store's own regular ("was") price, in every sport and category. The owner lowered this from 10% on 2026-11-11.
  - **Skateboard decks are stricter:** 10% for known brands, 15% for unknown brands.
- **Minimum price:** nothing under **$2**.
- **The percent off is calculated from the store's own two prices**, the sale price and the store's listed regular price. It is not an MSRP we look up. Say "X% off the store's listed price".
- **Stock:**
  - Sold-out items aren't listed, and only sizes the store lists as buyable count.
  - Some stores don't publish stock, and those listings show "Check store".

## Price history and "lowest observed"
From `history.py` and `sale_events.py`:
- Every scrape records the price of each listing. A listing's history starts **the day ShredDeals first saw it**, not when the store first sold it.
- **"All-time low" means the lowest price ShredDeals has recorded** for that listing. It is not the lowest price in the market.
  - Write "lowest price we've seen", or explain the term wherever it appears.
  - Skate history starts 2026-08-25 and the other sports start 2026-11-01. Lows from before those dates are unknown.
- **"Price drop"** means a price that fell since an earlier scrape. The digests count a drop only if it's at least $2 or 5% (`MIN_DROP_PERCENT`).
- **Gone:** a listing is called gone only after **two scrapes on different days** miss it (`GONE_AFTER_MISSES = 2`). This avoids false alarms from a store's temporary glitch.
- **Store sales** (`sale_events.py`): ShredDeals spots a sale when at least 10 listings it already tracks, and at least 10% of a store's listings, are cut by the same amount on the same day. The sale is treated as running until prices go back up.
  - The wording says what happened ("last time", "usually") and never predicts a sale.
  - It never calls a sale "sitewide" unless the store says so.
- **Promo codes** (`promos.py`): codes are read from stores' own pages and banners. ShredDeals doesn't verify that a code works at checkout. Say "as shown by the store".

## Matching and specs (limits to state)
- **Cross-store matching** (`matching.py`) is conservative. It groups only listings with the same brand, part, size and distinctive model words. Many identical products at different stores stay unmatched. Never claim full comparison across stores.
- **Filters** such as waist width, wheel size, travel and deck width come from **what the store states** in its title, tags or description. A missing value means the store didn't state it.
  - A few values follow a labeled convention, e.g. ski waist width from the model number, labeled "(stated or model number)".
  - ShredDeals doesn't test or review products. Don't imply hands-on testing.

## Alerts, email and stored data (for the Privacy draft)
Verify each item against the code before publishing; this is a summary.
- **Owner's email digests** (`notify.py`, `sports_email.py`): one Skate email and one BMX/Ski/MTB email per day, sent to the owner's own recipients through Resend. They are not public signups.
- **Subscriber alerts** (`worker/`, `docs/alerts-backend.md`):
  - A Cloudflare Worker with a D1 database, running in **staging only**. Production signups and delivery are **off** (`ALERTS_DELIVERY_ENABLED` unset).
  - When turned on, it stores a subscriber's email and alert settings, keyed by a hashed token, and sends through Resend from `alerts@shreddeals.com` with double opt-in.
  - The privacy draft must say whether this is live **on the date it's published**.
- **In the visitor's browser** (`page.js`, `localStorage`):
  - favorites/watchlist, saved views and filter layout
  - the collapsed state of filter sections
  - dismissed promo notices (Codex, task 16)
  - All of this stays in that browser and isn't sent to ShredDeals.
- **Analytics:** none found in `page.py`, `page.js` or `index.html` on 2026-11-23 (no gtag, GTM or Plausible).
- **Hosting:** GitHub Pages (shreddeals.com). Pages and Cloudflare (DNS, Worker) keep their own server logs.
- **Product photos** are shown from each store's own image addresses (hotlinked) and aren't copied to ShredDeals. Product names, prices and photos belong to the stores and brands.

## How we collect data (for the publisher profile and the terms review)
- **Public data only:**
  - each store's public sale pages and Shopify product feeds
  - each store's robots.txt is respected. After PR #329, it's checked before every scrape.
- **Stores that block automated reading are left out, never worked around.** Examples: Jenson USA and Competitive Cyclist (bot walls); Stacked BMX, whose robots.txt disallows everything (removed 2026-11-21).
- **Request rate:** a pause of at least 1.5 seconds between page requests, or longer if a store's robots.txt asks for it.
- **Open question for the owner before any affiliate application:** some merchants' affiliate terms limit reusing their content. For example, evo's terms ask for written consent to reuse its content. Once a merchant approves ShredDeals, the plan is to take its data from the affiliate feed instead of scraping. Don't describe ShredDeals as "partnered with" or "approved by" any store or network until that happens.

## Words to use and avoid

| Use | Avoid |
|---|---|
| lowest price we've seen | all-time low (unless explained), lowest price anywhere |
| X% off the store's listed price | X% off MSRP |
| updated daily | real-time, live prices |
| as shown by the store | verified code, guaranteed |
| we list deals from N stores | partnered with, official retailer |
