# ShredDeals: Ski, MTB and BMX catalogs

The homepage (#119) has Skate · Ski · MTB · BMX tabs. Skate runs on the
existing SkateDeals engine; the others say "coming soon". This is the plan
for filling them, BMX first, by reusing that engine rather than copying it.

## 1. How much is reusable (measured, 2026-11-01)

Share of lines that name a skate concept (deck, wheel, truck, durometer...):

| Layer | Skate-specific | Reuse |
|---|---|---|
| Price history, health checks, sale detection, store runner, stock checks, score | under 2% | as is |
| Page UI, `page.js` (8.7k lines) | ~3% | as is, once categories and spec filters come from per-sport settings |
| Page builder, `page.py` | ~7% | mostly; same condition |
| Shopify store adapter (`stores/shopify.py`) | product-type routing only | per-sport routing table |
| Rules (`filters.py`: brand lists, deck sizes, cruiser rules) | entirely | a rules module per sport |
| Store scrapers | per store | new per store; a Shopify store is ~20 lines of settings |
| Data file paths, scrape workflow | one catalog, hard-wired | a per-sport setting |

So roughly 90% of the code carries over: **one engine, one catalog per
sport.** What each sport supplies:

- categories;
- spec filters (labels, values, ranges, which category shows which);
- rules (what counts as a deal, which brands);
- search vocabulary;
- stores.

## 2. Target layout

```
sports/
  skate/   settings for today's SkateDeals (moved, not changed)
  bmx/     categories, filters, rules, aliases.json, stores
catalogs/
  bmx/     previous_data.json, price_history.json, history.json, ...
bmx.html   built by the same page.py from sports/bmx
```

- **Skate's files stay where they are.** `sale_items_chart.html`,
  `previous_data.json` and the rest don't move, so every existing link,
  alert and bookmark keeps working.
- **Each sport is scraped by its own run**, at its own time, with its own
  health tracking. A BMX store failing never touches Skate.
- **The homepage's sport settings** (`previews/sports.json`) point each tab
  at its catalog page once it exists. Until then the tab says "coming soon".
- **Email digests and alerts stay Skate-only** until a sport is ready, then
  are opted in per sport.

## 3. BMX catalog

Labels follow Dan's Comp and Circuit BMX, whose filters riders already know.

### Categories (one chip row) and Type

| Chip | Type values |
|---|---|
| Bikes | 12" · 14" · 16" · 18" · 20" · 22" Wheels |
| Frames & Forks | Frames · Forks |
| Steering | Handlebars · Stems · Headsets · Grips & Bar Ends · Detanglers |
| Drivetrain | Cranks · Sprockets · Bottom Brackets · Chains · Chain Tensioners · Pedals |
| Wheels | Front · Rear |
| Wheel Parts | Hubs · Drivers & Freewheels · Rims & Rim Strips · Spokes & Nipples · Axles · Hub Guards · Pegs · Valve Caps |
| Tires | Tires · Tubes |
| Seating | Seats · Seat Posts · Seat Post Clamps |
| Braking | Brakes & Accessories |

"Type" works like Skate's Protection type today: a filter inside the chip.

### Filters

These are shared by every category, as on Skate:
- **Brand**, first, with a brand search box;
- Price, % off, Store, Color;
- **Deal type**, which gains Dan's *Clearance* and *Scratch & Dent* next to
  New, Price drop and Lowest.

Spec filters by category, using Dan's labels where it has one:

| Category | Spec filters |
|---|---|
| Bikes | Hub Type (Cassette / Freecoaster), Toptube Length, Drive Side (Right / Left / Universal), Frame Material, Wheel Material |
| Frames | Toptube Length, Chainstay, Bottom Bracket (Mid / Spanish / American), Brake Mounts, Material |
| Forks | Offset, Dropouts (10mm / 3/8"), Brake Mounts |
| Handlebars | Rise, Width, Backsweep, 2-piece / 4-piece |
| Stems | Top Load / Front Load, Reach |
| Cranks | Length, Spindle (19 / 22 / 24mm), Drive Side |
| Sprockets | Teeth, Bolt / Spline Drive |
| Hubs, Wheels | Hub Type, Driver Teeth, Drive Side, Axle (14mm / 10mm), Holes |
| Tires | Size (20 × 2.3–2.5), PSI, Bead, Tread |
| Pedals, Pegs | Material, Axle |
| Seats | Style (Pivotal / Tripod / Railed) |

**Toptube Length shows within a wheel size.** A 12" bike's top tube isn't
comparable with a 20" one's, so the filter appears once a wheel size is
chosen.

### Search
`sports/bmx/aliases.json` will turn typed BMX terms into filters:

| Typed | Means |
|---|---|
| fc | freecoaster |
| cass | cassette |
| rsd, lsd, rhd, lhd | drive side |
| 21 tt, 20.75" | top tube |
| 9t | driver teeth |
| 25/9 | gearing |

Brand nicknames (S&M, WTP for We The People, and so on) are added too, the
same way as Skate's aliases.

## 4. Steps (one PR each)

1. **Store probe** (this PR). "Stores - Probe Candidates" is a manual,
   read-only Actions run that follows robots.txt. For each candidate store
   in `audit/store_candidates.json` it reports:
   - the platform, and so whether `stores/shopify.py` can read it;
   - its sale, clearance and closeout sections;
   - for Shopify, which variant options and product types it uses, which
     says whether Toptube Length and Hub Type can be read as data or must
     come from titles.
2. **"Sport" as an engine setting.** Paths, store lists, rules and search
   vocabulary per sport, and `page.py`/`page.js` categories and spec filters
   driven by settings. Skate is rewritten onto the settings with output
   identical to today, and tests prove it.
3. **First BMX store, end to end:** the first Shopify store the probe
   finds, BMX categories plus the shared filters, `bmx.html`, the homepage
   BMX tab, and a separate BMX scrape run.
4. **BMX spec filters** (Toptube, Hub Type, Drive Side...) from the data the
   probe found, then more stores, Dan's Comp included (custom platform, so
   its own scraper).
5. **Ski, then MTB,** repeating steps 3–4. Ski's sale season is now: last
   season's skis are being marked down.

## 5. Running the probe

GitHub app → repository → Actions → **Stores - Probe Candidates** → Run
workflow → pick a sport. The report appears on the run's page, and Claude can
read it there. Edit `audit/store_candidates.json` to add or remove stores.
