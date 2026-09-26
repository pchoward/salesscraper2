# Skateboard Sale Scraper

Tracks skateboard sales at Zumiez, Skate Warehouse, CCS, and Tactics, then publishes an HTML report. GitHub Actions runs the scraper daily. The page leads with a short digest of new deals and real sale-price drops.

## Layout

```
├── scraper.py                 # Selenium fetch + per-store parsers
├── filters.py                 # Shared allowlists and passes_filters()
├── report.py                  # Catalog diff + HTML report
├── test_filters.py            # Dry-check the filters without scraping
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

## Run

```bash
python scraper.py
```

Chrome or Chromium is required. The browser runs headless.

Dry-check the filters against the examples in `test_filters.py` (no network):

```bash
python test_filters.py
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
