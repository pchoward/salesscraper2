# BMX bikes: why the catalog shows 9 discounted bikes, and where freestyle completes could come from

**Audit date: 2026-11-07** · Catalog as of `Rebuild page 2026-11-07 11:59`
(`main` @ 180e0da) · Data sources: `catalogs/bmx/previous_data.json`,
`catalogs/bmx/scrape_health.json` (runs 2026-11-01 → 11-07), the repo's
read-only store probe (`python -m audit.store_probe --url …`), and the
repo's own live preview (`stores.preview(...)`). All live reads respected
each site's robots.txt, made a handful of requests, and saved nothing.

## TL;DR

- The catalog shows **9 discount-listed BMX bikes because 9 is what its
  configured sources actually have available and marked down right now** –
  not a scraper bug, dedup bug or filter regression.
- Supply reality: **the whole Albe's site yields 9 candidates for the
  Bikes part right now — 7 kept and 2 dropped by the e-bike rule
  (Skwad 1 / Skwad 2)** — matching the catalog exactly; Circuit adds 1,
  Powers 1, and **Source's dedicated "BMX Bike Sale" collection is empty
  today** (0 products). 7 + 1 + 1 = 9.
- **The five priority freestyle brands (WeThePeople, Sunday, Cult, Kink,
  Fit) discount nothing on completes today**, and brand-site probes are
  blind where they're USD-readable but locked out of anything richer
  (Dan's Comp is bot-walled, Sunday's Shopify JSON is 404,
  Fitbikeco is WooCommerce with no public API). Until those sources are
  open, the 9 is roughly the reachable floor for the current architecture.
- Haro's bike-sale sections are rich (`in-stock-bikes` shows 7 marked-down
  completes live) but **none are freestyle BMX completes**: 4 e-bikes
  (dropped correctly), 3 klunkers, of which one Klunkerson already reaches
  the catalog through Albe's (cheaper across sites).
- **Skipped product types are a policy, not an accident** and cover
  race/road clothing, tools, stickers, mini BMX and e-bikes; every drop we
  could trace follows the registered skip lists.

## Where the current 9 come from

`catalogs/bmx/previous_data.json` (`Bikes` part) on 2026-11-07:

| Store | Bikes | Marked down |
|---|---|---|
| Albe's BMX | 7 | 7 (Eastern Lowdown, Eastern Cobra, Elite Outlaw 26", Haro Klunkerson 27.5", Kuwahara KW-29, Verde A/V, Elite BMX Destro) |
| Circuit BMX | 1 | 1 (Fit Series 22" Wheel Complete 2026) |
| Powers BMX | 1 | 1 (Radio Cobalt mini Race black/red) |
| Total | **9** | **9** |

Day-by-day bike counts (`scrape_health.json`, one entry per store per day):

| Scrape | Albe's | Circuit | Powers | Source (US) | Total |
|---|---:|---:|---:|---:|---:|
| 11-01 | 7 | 1 | 1 | 0 | 9 |
| 11-02 | 6 | 1 | 1 | 0 | 8 |
| 11-03 | 7 | 1 | 1 | 0 | 9 |
| 11-04 | 7 | 1 | 1 | 0 | 9 |
| 11-05 | 5 | 1 | 1 | 0 | 7 *(+ Fiend feed outage, failed/empty runs)* |
| 11-06 | 7 | 1 | 1 | 0 | 9 |
| 11-07 | 7 | 1 | 1 | 0 | **9** |

So the 9 isn't a new regression of the provider count: it has hovered
between 7 and 9 since the catalog's first week.

## Why Albe's lands on 7 (live walk-through)

Albe's is a Shopify store already covered
`whole_site=True` (the 2026-11-06 audit found 51 markdowns sitting
outside the sale collections, so the whole catalog is scanned). A live
preview of today's feed, Bikes part:

```text
3570 products in the sale collection.
Product types: BMX BIKES 209, Tires 199, codes 192, CLOTHING & SHOES 184, … (full census below)
Bikes: 7 kept of 9 candidates
      (Lowdown $299.95/was $349.95, Cobra $329.95/was $379.95, …,
       Kuwahara KW-29 $1100.00/was $1349.95, …)
Dropped: electric bike 2
```

```text
whole site, whole-bike candidates for the Bikes part: 9
  kept     7 → Eastern Bikes Lowdown ($299.95 was $349.95), Eastern Cobra ($329.95/was $379.95),
              Elite Outlaw 26" ($549.95/was $599.99), Haro Klunkerson 27.5" ($649.00/was $849.99),
              Kuwahara KW-29 ($1100.00/was $1349.95), Verde A/V ($399.95/was $419.95),
              Elite BMX Destro ($369.95/was $398.95)
  dropped  2 "electric bike" → Haro Skwad 1 ($1999.95 was $2599.99), Haro Skwad 2
```

**Every other marked-down whole bike listable on Albe's today loses for one
of two reasons**, both verified against the live variant feed and shipped
rules:

1. **Marked but sold out** — 17 of Albe's 25 marked-down whole bikes have
   **no available variant at all** (every size run reports
   `available: false`), and `stores/shopify.py sale_variants` drops those
   before the listing ever becomes a candidate:

   Black Ops SpecOp-29" Disc · Eastern Big Reaper 26" LTD · Eastern
   Comando 24" LTD · Eastern Growler 26" · Fit CR 26" · Haro Boulevard ·
   Haro La Bastille Pro · Haro Leucadia · Race Inc. Retro RA26-R · Race
   Inc. Retro RA29-R · Radio Asura Pro DJ · Radio Fiend DJ · Radio
   Griffin DJ · Radio Saiko 18" · Radio Saiko · SE Bikes DJ Ripper HD ·
   Throne Cycles The Goon 29"

2. **Reduced-only variant is unsellable or trivially so** — e.g. the four
   closest cases for the freestyle list:

   - `Elite BMX Stealth Bike`: the few remaining variants price at
     $299.00 **with no markdown at all**; the $250/was $289.95 variant
     seen earlier today is gone (walks to 0 sale variants).
   - `Fit CR 29" Bike`: the "discount" variant is $899.95 vs $899.99 —
     **and that variant is unavailable**. The other variant is listed as
     normal. Not a candidate.
   - `Haro Boulevard`: all three marked variants are `available:false`.
   - E-bike candidates (Skwad 1/Skwad 2): dropped by sports/rules.py's
     `_EBIKE` rule, which is covered by `test_bmx_ebikes.py`
     ("an electric bike colour is kept, a bike that IS electric is not").

So the kept list is complete for these rules: no "extra bike exists and
was thrown away by accident". Albe's whole-site variant census (3570
products examined) showed nothing else that belongs in the Bikes part
today.

## Why Source BMX (US) feeds 0 bikes

Source's scraper is the most BMW-relevant one (it reads a bike sale
*collection* — `bmx-bike-sale` — plus a whole-site scan, since its
2026-11-06 audit found 55 markdowns sitting outside collections).
Live on 2026-11-07:

```text
sale collections on us.sourcebmx.com:
  BMX Bike Sale       (bmx-bike-sale)        0 products   ← EMPTY today
  BMX Frame Sale      (bmx-frame-sale)      13 products
  BMX Parts Sale      (bmx-parts-sale)     106 products
  BMX Racing Sale     (bmx-racing-sale)    110 products
  BMX Soft Goods Sale (bmx-clothing-sale)   88 products
  BMX Wheel Sale      (bmx-wheel-sale)      74 products
```

`bmx-bike-sale` has **0 products**; `bmx-racing-sale`'s 110 items are
marked down, but zero of them are whole bikes (the category's bikes sit in
`bmx-bike-sale`, currently empty). So a store that usually carries
something like 4–10 bikes is today at zero, and that's a retail fact,
not a scrape miss.

## Priority five: WeThePeople, Sunday, Cult, Kink, Fit

Every one of the five was probed live on 2026-11-07 (robots, collections,
and — where readable — the actual complete-bike collections):

| Brand | Result | What's planned |
|---|---|---|
| **Cult** | ✅ readable (cultcrew.com, USD Shopify): `Bikes` collection of **19 completes, 0 marked down**; this year's Cyber Monday collection adds 10 marked-down parts (`Hubs/Wheels`→Wheel Parts…) | **wired in PR `claude/bmx-freestyle-sources`** — the catalog gains a Cult feed covering the brand's real catalog paths (and
  the sale-sniffer keeps watching it) |
| **Kink** | ✅ already a store (kinkbmx.com): `Sale` has 19 items, **0 bikes**; the `Bikes` and `2027 Bike Collection` collections have 16/15 full-price completes, no markdowns today | nothing to change; the existing sale plus whole-site-type checks and the sale-sniffer already cover it |
| **Sunday** | ⚠️ readable HTML (`sundaybikes.com` is Shopify-marked) but **`/collections.json`, `/collections/<handle>/products.json` and `/products.json` are all 404** — no Shopify JSON to read, unlike every other brand store | rejected as a source for now; strings note the lock when it reopens |
| **Fit** | ❌ `fitbikeco.com` is WooCommerce, no `✓ /wp-json/wc/store/v1/products` endpoint, no visible "sale" collections | rejected as a source (a custom Woo scraper would be a bigger project — see follow-up issue) |
| **WeThePeople** | ❌ the US domain (`wethepeoplebmx.com`) is a dead 114-byte redirect; the official shop is **EUR/Magento** (`wethepeoplebmx.de`) — out of the USD-feed scope | rejected; both WTP and Monday bikes get sold where Cult does: a dealer feed (see Dan's Comp) |

## Dan's Comp — the aggregator that carries all five, and why we didn't wire it

`danscomp.com` answers 403 for the homepage, `/collections.json` and
`/collections/<handle>/products.json` **even with exactly the Chrome user
agent `stores/shopify.py` uses**. Free plain-HTTP read: no read-only pass
through any of our modules can get to its catalog JSON.

A browser-backed reader (`stores/browser.py`, Selenium, like Zumiez and
Skate Warehouse) would read it — but the BMX/Ski/MTB scrape workflow does
not run a browser today (that's the noted constraint in
`sports/bmx/stores.py`'s header comment), so wiring Dan's Comp as a BMX
source is an owner decision costing minutes per run and a different kind
of flakiness to monitor. **No scraper PR is included in this audit for
that reason**; the follow-up issue names the tradeoff so the owner can
decide with data.

## Haro's bike-sale collection — audited, rejected (for now)

Haro is already a brand store, but its configured sale section is
`summer-parts-sale` (35 items, zero bikes today) — so the store reads
**31 Haro products in the catalog, all parts/frames**. The bike-sale parts
of `harobikes.com` live in different sections:

```text
in-stock-bikes            39 products, 7 marked down
   Klunkerson 27.5"  $649.99/was $849.99    ← BMX, but a klunker; already in the
                                              catalog via Albe's (same price)
   Beasley 27.5      $599.99/was $799.99    ← klunker
   Beasley 27.5 DLX  $699.99/was $899.99    ← klunker
   Skwad LT          $499.00/was $2399.99   ← e-bike (dropped by rule)
   Skwad 1           $1999.99/was $2599.99  ← e-bike (dropped by rule)
   Escondido 1 / 2   $1499.99 & $2999.99    ← e-bikes (dropped by rule)
ebike-sale                  5 marked        ← e-bikes (out of scope)
dropbar-bikes               3 products, 1 marked (Rivette Carbon)
holiday-bike-deals          currently empty
electric-bike-deals         currently empty
```

Net: Haro's bike discounting today is **e-bike-biased and
klunker-biased — zero freestyle completes are marked down**. Adding
`in-stock-bikes` to Haro's feed would add two klunkers (both Beasley
variants) and a duplicate card of the Klunkerson (a different URL than
Albe's, so cross-store merge would not touch it), plus several e-bikes
the rulesheet would reject anyway. Whether those two klunkers count is a
catalog-mix decision (filed as a follow-up), not an obvious fix — so this
audit lands it as data + a follow-up, not a PR.

## Skipped product types — the audit's coverage picture via `sports/bmx/stores.py: TYPES`. Whole-site
scans and probes show what is skipped deliberately:

- **Source BMX US** — the `bmx-clothing-sale` (88) and race-wear types
  inside `bmx-racing-sale` (Race Tops ×10, Race Pants ×2, Race Number
  Plates ×2, T-shirts ×2, Tools ×2, Goggles ×4 are dropped) plus
  clothing-collections; BMX-DJ pads/others drop by filter as intended.
- **Albe's whole site** — full type census from today's preview:
  `CLOTHING & SHOES 184, OTHER SHIT 173, Stickers 100, Tools 75, Mini BMX 7,
  Leisure Bikes 1, Backpack 1, Gift Card 1, Locks 2, Skate Tools 3` plus
  the composite type "codes" (192 — the Albe's "codes" boxes; documented
  in the store function as deliberately filed there, pads included).
- **Cult (new)** — `Merch 263, Softgoods 197, Hats 120, Tops 51, Shoes 24`
  all stay out; only the `Bikes` + `black-friday` collections are read.
- **WeThePeople** — softgoods/cultural merchandise stays out; `Bike Bags`
  handled by `brand_title_part` already.

Nothing in the catalogs covers those deliberately-skipped types today,
and the skip decisions match documented owner choices (owner notes in
`sports/__init__.py`, `docs/multi-sport-plan.md`).

## Accepted / rejected — one-line receipts

| Landscape-item | Verdict | Reason |
|---|---|---|
| 9 live BMX bikes (Albe's 7, Circuit 1, Powers 1) | **accepted already** | marked down, available, in-stock; each is a current freestyle-complete/complete-bike |
| Haro Klunkerson (via Albe's) | **accepted already** | priced down at selling store; no Haro-side duplicate |
| WeThePeople completes | **rejected for now** | no USD retailer feed available from the brand itself (see Dan's Comp) |
| Sunday completes | **rejected for now** | brand site's JSON is locked; no alternative feed |
| Cult completes | **discovered, rejected for now** | 19 live completes, **none marked down today** (the new Cult store watch will include them the moment a markdown lands) |
| Kink completes | **discovered, rejected for now** | 16 live completes, none marked down today |
| Fit completes | **rejected (upstream)** | WooCommerce without a public price API; needs a real scraper build |
| Haro in-stock-bikes (7 marked) | **rejected (for now)** with reasons | e-bikes ×4 dropped by rule; klunkers/dropbar are off the freestyle-complete bar; Klunkerson exists in the catalog already |
| Dan's Comp | **rejected for now** | 403 bot-wall on every path for the stock user agent |

## Follow-ups

- Wired up today: **Cult brand store** (PR
  `claude/bmx-freestyle-sources` — read-only store-probe place for
  cultcrew/sunday/fitbikeco) — this keeps the priority-five question
  live in the sale-sniffer and the store probe.
- Owner decisions pending (issue #243): browser-reading Dan's
  Comp; whether to add Haro's `in-stock-bikes` (+ dedup rule for the
  Klunkerson double); fitbikeco custom scraper; a Sunday recheck when
  their JSON opens.
