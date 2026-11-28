# Codex backlog: November 7, 2026

Work for Codex while Claude's usage is low. Do the tasks in order, one PR each, with green checks before review. The owner merges.

**Read first:**
- `docs/menu-wireframe.md`: the menu map and its rules. Change the wireframe first, then the code.
- `docs/codex-sidebar-and-my-stuff.md`: tasks 1 and 2 below.

**Keep unchanged everywhere:**
- URL parameter names
- `localStorage` keys
- the saved-view format
- stored data files (`previous_data.json`, `price_history.json`)
- `sports/headings.py` (Claude's)

**Tests:** `python -m unittest` and the browser checks in `ci/` (pattern: `ci/check_category_navigation.cjs`). New Python test files go in the `_config.yml` exclude list.

---

## 1. Sidebar ends at Price
See `docs/codex-sidebar-and-my-stuff.md`, Part A.

## 2. "My stuff" header menu
See `docs/codex-sidebar-and-my-stuff.md`, Part B.

## 3. Coverage on every filter (all four sports)
**Goal:** a filter shows how much of the heading it can see. Deals without a value never vanish silently.

- **Section header:** each spec section shows "known for N of M" whenever N < M. N is the deals in the current heading with that spec; M is all deals in the heading.
  - Skate sections are built in `page.py` (`_gated`, `_section`).
  - BMX, Ski and MTB sections are built in `sports/facets.py` `sidebar()` and `previews/sport-filters.js`.
- **"Not listed" chip:** add one to each spec section. It selects deals with no value. URL value `none`, e.g. `ski_waist=none`.
- **Visibility by coverage, per heading, recomputed when the heading changes:**
  - 25% or more: shown.
  - 10–25%: moved into the "More" section from task 1.
  - Under 10%: hidden.
- **Done when:**
  - Ski Skis shows Waist under More, labelled "known for 121 of 541" (numbers vary by scrape).
  - Turn radius (3%) isn't shown.
  - A link that sets a hidden filter still works, and opens that section.

## 4. Type chips above the results, and the menu's second line
**Goal:** inside a heading, the types are one tap away (wireframe: "Types").

- **Chip row:** one row of chips above the results, built from fields that already exist.
  - BMX: `technical_specs.kind` (Hubs, Rims, Pegs, Grips, Sprockets…).
  - Ski Skis and Boots: `ski_type`.
  - Protection on every sport: `protects` (Knees, Elbows…).
  - MTB Drivetrain, Brakes, Cockpit and Suspension: map `product_type`. The mapping is in the wireframe's MTB column. Put it in `sports/mtb/facets.py` as `TYPE_CHIPS = {"Shifters": [regex…], …}`.
  - Skate Grip, Hardware & Tools: product type (Grip tape, Hardware, Bushings, Tools & wax).
- **No type, no chip:** deals without a type only show under "All".
- **Menu panel:** the same types appear as a second line under each heading in the category panel (`navigation/navigation.js`, `#categoryChoices`). Read them from `navigation/<sport>-categories.json`; add a `types: [{name, count}]` field in `previews/publish.py` `CategoryParser`.
- **URL:** `type=<heading>&kind=<type>`. Add `kind` to `decodeQuery`/`encodeQuery`.

## 5. Skate specs from names: deck shape, wheel profile, shoe top
Skate's spec parsing lives in `page.py`: `wheel_specs`, `truck_specs`, and the Decks section builders.

- **Decks:** add a Shape filter: Popsicle (default only when the name says so), Shaped, Twin, Cruiser-shaped, Fish/Egg. Read words like "shaped", "egg", "fish", "twin tail", "old school".
- **Wheels:** add Profile (Conical, Radial, Classic, Lock-in, Conical Full) and Surface (Smooth, Treaded).
  - Spitfire names say "Conical Full", "Radial", "Classic"; Bones names say "V1"–"V6".
  - Wheels already has a `shape` field: extend it rather than duplicating.
- **Shoes:** add Top (Low, Mid, High) from names ("Dunk Low", "Hi", "Mid").
- **Coverage:** report it in the PR body as N of M per filter.

## 6. Hide same-price duplicates of one product from one store pair
Cambria and Colorado Cyclist (MTB) often list the same item at the same price, because they share a feed.

- **Card:** in cross-store groups (`matching.py` `cross_store_groups`, shown by `page.py` `_compare_section`), when two offers in a group have the same price and the same name after normalising, show one card that says "Cambria · Colorado Cyclist $X". Don't show two cards.
- **Data:** don't remove either offer, only merge the display.
- **Test:** a group with two equal offers renders one card with both store names.

## 7. Search knows the new headings and specs
`search/search.js` (SYNONYMS, `preferText`) and `page.js` (`technicalSearchWords`).

- **Headings and specs:**
  - "goggles", "gloves" and "helmet" open or prefer those headings on every sport.
  - "12 speed" / "12-speed" / "12sp" matches Speed 12-speed.
  - "exo", "doubledown" and "dd" match tire casing.
  - "tubeless" / "tr" matches Tubeless.
  - "low bridge", "otg" and "bonus lens" match the goggle filters.
  - "lv", "mv" and "hv" match boot last.
- **Tests:** add cases to `test/*.test.js` (`node --test test/*.test.js`).

## 8. Phone pass, all four sports at 390 px
- **Screenshots:** every heading's results, sidebar drawer and category panel on each sport. Use the existing `ci/smoke.mjs` setup.
- **Fix:** anything clipped, overlapping or scrolling sideways.
- **PR:** list what was fixed, with before/after screenshots.

## 9. Keep the wireframe current
After tasks 3–5 land, update `docs/menu-wireframe.html`:
- filters with their coverage
- the new type chips
- the new Skate filters

Then tell the owner the page needs republishing. Claude republishes the artifact from that file.

## 10. Trucks: one "Fits deck" filter that keeps each brand's own sizes
Owner, 2026-11-07: "I kept seeing 151 and thought we didn't have anything bigger."

**The problem:** today's Truck Size filter (`page.py` `truck_specs`, Trucks sections) mixes four systems in one list:
- Independent numbers: 129–151
- Ace numbers: 33–66
- Venture numbers: 5.6
- axle widths in inches: 7.75–11.0

It also misreads names. 55 of 77 trucks get a size. The other 22 are mostly unparsed, not unnamed:
- "Independent 166 Stage 4" is rejected.
- "Reynolds 159 (8.75")" keeps only 8.75.

Checked by Codex, 2026-11-07.

**Split of work:**
- **Claude (extraction):** truck records carry no variant or option data today. Claude adds per-variant truck offers at scrape time: size option, availability and price, like decks' `spec_offers`. It's a separate PR, and the variant part of this task needs it first.
- **Codex:** parsing, the size table and the UI below, built on the names now and on `spec_offers` once they exist.

**What to build:**
1. **Size table.** `TRUCK_SIZES` maps a brand's size to the deck widths it fits (one or two widths):
   - Independent: 109, 129, 139, 144, 149, 151, 159, 166, 169, 215
   - Ace: 00, 11, 22, 33, 44, 55, 60, 66, 77, 80
   - Venture: 5.0, 5.2, 5.6, 5.8, 6.1
   - Thunder: 143, 145, 147, 148, 149, 151, 161
   - Krux, Royal, Tensor and Slappy where their charts give one

   Take the widths from each brand's own published size chart (cite the URL in a comment), not from memory.
   - Map per **product family** where the brand's chart differs by family (e.g. Indy Stage 11 vs Stage 4 or Mid; Thunder Team vs Hollow Lights).
   - A size that spans two widths (e.g. Indy 159) matches both.
   - An unverified size stays unmapped and keeps showing its native number. Don't guess.
2. **Reading sizes.**
   - Read the brand size from the name. Accept 159, 166, 169 and 215.
   - When both a brand number and inches are printed ("159 (8.75")"), keep both: the brand number as the native size, the inches as a cross-check.
   - Once Claude's `spec_offers` land, read variant sizes too.
   - **The variant's fit, stock and displayed price must all come from the same offer,** as decks already do with `spec_offers`.
3. **Sidebar.** One section, **"Fits deck"**, using the deck-width bands:
   - The bands are 7.75 · 8.0 · 8.25 · 8.5 · 8.75 · 9.0 · 9.5+.
   - Each chip lists the brand sizes it covers in small text, e.g. "8.5"  Indy 149 · Ace 55 · Venture 5.8".
4. **Brand row.** A second row, **brand sizes**, appears only when exactly one brand is selected:
   - Independent: 129 · 139 · 144 · 149 · 159 · 166 · 169 · 215
   - Ace: 33 · 44 · 55 · 60 · 66 · 77
5. **Cards.** Show the native size and the fit, e.g. "Independent Stage 11 · 159 (fits ~8.75–9.0")".
6. **Search.** "indy 159", "ace 66" and "9.0 trucks" all find the right trucks.
7. **URL.**
   - Keep `trucksize` with its **exact old matching**, so an old link shows the same trucks it did. Don't silently broaden it into a fit band.
   - Add `truckfit` for the bands and `trucknative` for the brand row.
8. **PR body.** Coverage before and after: trucks with a size went from 55 of 77 to ?.

**Tests:**
- Name parsing: 166, "159 (8.75")", Ace 66, Venture 5.8.
- Variant-only sizes.
- One band chip lists the right brand sizes.
- The brand row only appears with a single brand selected.

## 11. Picking a category from the top menu starts a fresh browse
**Reported by the owner, 2026-11-11 (BMX).** They filtered Protection by Protects: Wrists and Elbows, then picked Seats & Posts from the top menu, then a brand.
- The page showed `BMX / Seats & Posts / supacaz / Wrists / Elbows`: the protection picks rode along into Seats & Posts.
- Reopening the top menu, categories with no matches under those leftover filters were greyed out. Everything was available again only after clearing the filters by hand.

**Cause:** `navigation/navigation.js`, `refreshCategories()`. For the current sport, a menu choice calls `original.click()` on the page's own category button. That swaps only the category and keeps every other filter. The menu's counts and disabled states come from that button's `data-count`, which reflects the leftover filters.

**Wanted:**
- **A top-menu pick resets the browse:**
  - Clear every filter except the sport: brand, store, price, spec and protection picks, and search.
  - The result is the same view as following the category's link fresh (`?type=<slug>`).
  - The page's own category buttons in the sidebar keep today's behaviour (narrow within the current filters).
- **Menu counts are each category's full count,** never zero because of filters the user is about to leave. A category with stock is never greyed out in the top menu.
- **Leftover picks can't hide or decorate results.** If a filter can't apply to the current category (Protects on Seats & Posts), the URL keeps it for old links, but it's left out of the active chips and breadcrumbs.
- **Back** returns to the filtered view the user came from, as today.

**Keep unchanged:** URL parameter names, saved views and `localStorage` keys. Old links with mixed filters must still open.

**Tests:** extend `ci/check_category_navigation.cjs`:
- Filter BMX Protection by Protects: Wrists.
- Pick Seats & Posts from the top menu.
- Check that the breadcrumbs read `BMX / Seats & Posts`, no Protects chip is shown, the result count equals the category's full count, and no top-menu category with items is disabled.
- Press Back and check that the Protection view with Wrists returns.

## 12. Phone filters: a full-screen sheet with a "Show N deals" button
**Owner, 2026-11-12, on an iPhone (390 px).** They compared our Skate › Wheels view with Tactics' skateboard wheels page and want ours to work like Tactics. This makes task 8 concrete for the results view and the filters; do it first.

**What Tactics does well:**
- The landing view is the title, the result count and one large **Filters** button, then products.
- **Filters open full screen.** A sticky bar at the top has a back arrow and **"Apply 139 Results"** with the live count; tapping it closes the filters.
- Brands show the top few plus **"More Brands +"**. Sizes are a grid of tappable chips.

**What ours does now (same width):**
- **Bug: the sort row overlaps.** "Group across stores" sits on top of the `% off` sort box (the right part of the box is covered).
- The filter drawer covers about 90% of the width, so the page shows behind it and the header stays above it. There's no "show results" button: the only way out is ✕, and the result count isn't visible while filtering.
- Before the first deal card there are seven rows: site header, search, Deals/Track/Insights/Subscribe, sport tabs and category, stores, breadcrumbs, the New/Price drops/Hit lowest/Disappeared tabs, count, sort and filters, chips. Cards start about 60% down the first screen; Tactics' start about halfway.

**Wanted, at phone widths only (≤ 640 px). Desktop is unchanged:**
1. **Full-screen filter sheet.** It covers the whole viewport, header included, and the page behind it doesn't scroll.
   - **Top bar (sticky):** a back/close control on the left, the title "Filters", and **Clear all** on the right.
   - **Bottom bar (sticky, thumb reach):** a full-width button **"Show 73 deals"** with the live count, updating as filters change ("Show 0 deals" disabled, with a hint to clear a filter). Tapping it closes the sheet and scrolls to the first card.
   - Filters keep applying live as today; the button just closes the sheet. Back (browser or swipe) closes the sheet and doesn't leave the page.
2. **Inside the sheet:**
   - Sections stay collapsible. The first two sections open by default, plus any section with an active pick.
   - **Brand:** keep the search box and counts, but show the top 8 by count, then **"More brands (N) +"**. Active brands always show.
   - Chip sections (wheel diameter, deck width, sizes) wrap in a grid with 44 px tap targets.
3. **Sort row.** Put **Sort** and **Group across stores** on separate lines, or move "Group across stores" into the sort menu as an option. Nothing may overlap at 320–430 px.
4. **One clear Filters button** in the results bar: full width or prominent, showing the active count ("Filters · 1").
5. **Card names: three lines on phones.** Names are clamped to two lines today. At 390 px, two different TGM wheels, "Satori Skateboard Wheels 52mm Brian Delatorre …", both cut off at "Brian…" and look like duplicates. On phones, clamp the name to 3 lines and show the full name as the link's `title`/accessible name. Desktop stays at its current clamp.
6. **Less chrome above the cards (optional; owner to approve in the PR screenshots).** On phones, the New/Price drops/Hit lowest/Disappeared tabs can collapse into one "All deals ▾" picker, and the stores row can move into the filter sheet under **Store**.

**Keep unchanged:** URL parameters, saved views, `localStorage` keys, and filter behaviour and counts (this is layout only). Desktop layout stays as it is.

**Tests:**
- Extend the phone checks in `ci/` (pattern: `ci/check_category_navigation.cjs`) at 390 × 844 and 320 × 640:
  - Open Skate › Wheels; the sort box and "Group across stores" don't overlap (bounding boxes).
  - Open Filters; the sheet fills the viewport and the page behind it doesn't scroll.
  - Pick a brand; the button count matches the results count after closing.
  - "Show N deals" closes the sheet; browser Back from the open sheet closes it and stays on the page.
  - A card name longer than two lines shows three lines at 390 px.
- Run on all four sports.
- **PR:** before/after phone screenshots of Skate › Wheels results, the open sheet, and the BMX and Ski equivalents.

## 13. Live search across Shopify shops ("More deals from other shops")
See `docs/live-search-catalog.md`: a Worker route that calls Shopify's Global Catalog when a shopper searches, plus a results section below our own search results, with only marked-down items, Shopify's attribution kept and a 10-minute cache at most. **Nothing from it is stored in our catalog.** It's behind a flag that stays off until the owner deploys the Worker and creates a Catalog API client. Promoted placements (paid) are out unless the owner asks.

## 14. Intermittent "child.dealRows is not a function" (flaky browser check)
**Seen:** the PR browser checks fail now and then with `TypeError: child.dealRows is not a function` under "No browser errors". It hits a different sport and width each time: Ski at 390 px on PR 281 (2026-11-12); earlier PRs too. A re-run usually passes. Nothing in the PR's change is involved, so it blocks unrelated PRs.

**Where:** `navigation/navigation.js` `registerCategories(source, child)` calls `child.dealRows()` and `child.typeSlug()` straight away. Those are top-level functions in `page.js`, inlined at the end of the catalog page. `navigation/skate-bridge.js` `mountCategories()` calls `registerCategories` on DOMContentLoaded, or at once when the bridge script (added dynamically in the page `<head>`) runs after parsing. Likely causes to check:
- the bridge running before `page.js` has defined those functions; or
- `child` being a WindowProxy for an iframe that has already started loading another sport's catalog (quick tab switches), so its globals aren't there yet.

**Wanted:**
- No page error in any order of loading. If `child.dealRows`/`child.typeSlug` aren't functions yet, wait for the catalog to say it's ready (an event or a flag `page.js` sets once its functions exist) and register then. Don't swallow the error and leave the menu empty.
- A registration from an iframe that has since moved to another sport is ignored.
- Menu counts and behaviour unchanged. URL parameters, saved views and `localStorage` keys unchanged.
- Keep `previews/navigation.js` and `previews/skate-bridge.js` in step if they're still copies.

**Tests:**
- A check in `ci/` that loads the shell with the bridge delayed or run early (for example, by stalling `page.js` or firing `registerCategories` before it) and asserts no page errors and correct menu counts.
- A check that switches sport tabs quickly (Skate → Ski → MTB within a second) at 390 px and asserts no page errors.
- Run the full browser checks three times in the PR; all green.

## 15. Skate › Packs opens Decks (owner, 2026-11-14)
**Seen:** on the Skate tab, picking **Packs** from the menu opens Decks. The Skate catalog has about 500 pack listings (`data-part="Packs"`); BMX, Ski and MTB open their Packs fine.

**Cause:** the menu link is `?sport=skate&type=packs`. In `page.js`, `slugType()` turns `type` back into a heading with a fixed map (deck, wheel, truck, bearing, sneaker, accessory, complete, protection, helmet). `packs` isn't in it, and Skate has no `SPORT_SETTINGS.parts` for `sportPartForSlug()` to fall back on. So the part stays `DEFAULT_PART` (Decks). `typeSlug("Packs")` already writes `packs` (through `nameSlug`).

**Fix:**
- In `slugType()`'s map, add `pack: "Packs"` and `packs: "Packs"`.
- In `typeSlug()`'s map, add `Packs: "packs"`, so the written slug stays what links already use.
- Check each Skate heading in `page.py` `PART_ORDER` the same way, and make sure every one round-trips through `typeSlug` and `slugType`. Any new Skate heading should work without another map entry: falling back to `nameSlug` over the Skate part list would do.

**Keep:** existing URLs (`type=deck`, `type=protection` and so on), saved views and `localStorage` keys unchanged.

**Tests:**
- A unit check that every Skate heading in `PART_ORDER` round-trips (`slugType(typeSlug(part)) === part`).
- A browser check that Skate › Packs from the menu shows pack cards and the "Packs" breadcrumb, on desktop and at 390 px.

## 16. Promo-code notice on each sport page (owner, 2026-11-19)
**Why:** some store sales are discount codes, not markdowns. Fanatik's Black Friday is "20% off eligible products with code 2026-BFCM-20 at checkout, until Dec 2". Product prices don't change, so no listing shows it. Claude's side (PR "Promo codes") detects these codes twice a day and saves them in **`promos.json`** at the repo root (`promos.py`, `promo-check.yml`). Both emails already show them.

**Data:** `promos.json` holds `{"updated": "2026-11-19", "promos": [...]}`. Each promo:
`{"store": "Fanatik", "code": "2026-BFCM-20", "percent": 20 | "amount": 25, "ends": "2026-12-02" or "", "url": "<the store page it was found on>", "sports": ["mtb"], "first_seen", "last_seen"}`.
Use `promos.for_sport(sport_id)` for a sport's list, and `promos.describe(promo, code=False)` for the wording ("20% off, until Dec 2"). Every field is validated in `promos.py`; no store wording is passed through.

**Wanted:**
- Embed the sport's promos in its page when it's built (`page.py`), like the other page data.
- Above the results, show a slim strip when there are any: **"Promo codes"**, then per store: the store name (linking to `url`), the offer, the code in a monospace chip with a **Copy** button, and "applied at checkout". Collapse to one line plus "+N more" past two codes. Hide codes whose `ends` has passed in the visitor's local date.
- Don't change any listing's price, count or sort; codes never change deal math.
- Phone: one line per code, wrapping cleanly at 320–390 px.
- Let a visitor dismiss a code. Use a **new** `localStorage` key, and keep existing keys, URL parameters and saved views unchanged.
- Add `promos.json` to `rebuild-page.yml`'s `paths`, so a promo update rebuilds the pages.

**Tests:**
- Python: embedding, and expired codes left out at build time.
- Browser checks (pattern: `ci/check_category_navigation.cjs`) on MTB with a fixture promo, desktop and 390 px:
  - the strip shows;
  - Copy puts the code on the clipboard;
  - dismiss persists across a reload;
  - no strip when there are no promos.

## 17. MTB Bikes: "All · E-MTB · Regular" chips at the top (owner, 2026-11-21)
**Why:** 81 of MTB's 205 bikes are e-bikes, mixed in with regular bikes. The owner wants them kept together under **Bikes**, with a filter **at the top** to split them.

**Data (done, Claude's PR "E-MTB filter"):**
- MTB bikes and frames carry the technical spec `power` = `"E-MTB"` or `"Regular"` (`sports/mtb/specs.py`).
- It's a facet field in `sports/mtb/facets.py`: `{"key": "power", "label": "Motor", "param": "mtb_motor", "categories": ("Bikes", "Frames")}`.
- So the shared spec filters already offer it in the sidebar as **Motor**, and the URL is `?sport=mtb&type=bikes&mtb_motor=E-MTB`.
- Values arrive with the next MTB scrape after merge.

**Wanted:**
- When MTB's **Bikes** (or **Frames**) is the active category, show a segmented chip row above the results: **All bikes · E-MTB · Regular**, each with its count.
- The chips drive the same `mtb_motor` filter as the sidebar's Motor facet: no second state, and the same URL parameter, so links and saved views work and match the sidebar.
- Hide the row when every listing has the same value, or when `power` is missing (before the first scrape with it).
- Phone: the row fits at 320–390 px and scrolls sideways if needed. Desktop layout otherwise unchanged.
- Optional, for the owner to approve in the PR screenshots: **E-MTB** and **Regular** links under **Bikes** in the MTB menu, pointing to the same URLs.

**Keep:** existing URL parameters, saved views and `localStorage` keys.

**Tests:** in the `ci/` pattern, using an MTB fixture with both kinds of bike:
- each chip's count matches the facet count;
- picking E-MTB shows only e-bikes, the URL holds `mtb_motor=E-MTB`, and the sidebar's Motor shows the same choice;
- Back restores All;
- desktop and 390 px.
## 18. Flaky MTB browser audit, and a stale summary after re-runs (owner, 2026-11-21)
**Seen:** the same MTB checks in `ci/audit_sports.cjs` fail on unrelated PRs: #293, #296 and #297 (2026-11-19 to 21), each at a different width (430, 768, 1024, 1440). A straight re-run usually passes.
- `mtb <width> Category, store, brand, search, sort and ranges`: **`locator.selectOption: Timeout 5000ms exceeded`** on `#sortSelect`. The select is found but isn't "visible and enabled" within 5 s.
- `mtb <width> Technical combinations and variant price oracle`: actual rows are a small subset of expected (on #297 at 1024: 1 row where the oracle wanted 10). This looks like a knock-on effect: the previous check timed out partway and left filters applied, and this one started from that state.
- Skate, BMX and Ski pass the same checks. MTB is the biggest catalog (about 4,300 rows after the 2026-11-19 scrapes), so a slow render or a busy main thread is the likely cause.

**Wanted:**
1. Find why `#sortSelect` on MTB isn't usable within 5 s: disabled during a re-render, covered, or the page still busy. Fix it in the page if the shopper sees it too (a sort box that can't be used for seconds is a real bug). Otherwise make the check wait for the page's own "ready" state instead of a fixed timeout.
2. Make each audit check start from a clean state (reload or reset the filters), so one failure can't leave filters applied for the next.
3. **Stale summary on re-run:** re-running only the failed browser groups (Actions "Re-run failed jobs") let every group pass, but "Preview build and browser checks" still failed. It read the earlier attempt's `audit-phone` result ("Fail / incomplete"). Only a full re-run clears it. Make the summary read the latest attempt's results.

**Tests:** run the full browser checks three times on one PR, all green. A re-run of only the failed jobs after a forced failure turns the summary green.

## 19. Sort Ski filter sections by the chosen heading (owner, 2026-11-21)
**Why:** Grok's `docs/filters-evo-model.md` gives each Ski heading its own filter order. Boots want Size, Gender, Flex, Last; Bindings want DIN, Brake, Gender. One `FIELDS` tuple can't do both.

**Data (done, Claude's PR "Ski filter order"):** each technical section wrapper in `#contextSpecs` (`<div data-technical-field="…">`) carries `data-rank="Skis:2 Boots:2 Bindings:3 …"`: its 1-based position on every heading that orders it (`sports/ski/facets.py` `ORDER`). Sections a heading doesn't rank have no entry for it. Other sports have no `data-rank`.

**Wanted:** in `page.js` `syncTypeSections`, after the `data-for` loop, reorder the `[data-technical-field]` children of `#contextSpecs` for the chosen `part`:
- sections with a rank for `part` first, ascending;
- then the rest in their built order (remember each section's built index once);
- on "all", and on any heading with no ranks, restore the built order;
- no `data-rank` anywhere: change nothing.

Brand stays first, as it is today. Open/closed state and counts are unchanged.

**Tests:** a browser check on Ski at desktop and 390 px:
- Boots shows Boot size (Mondo), Gender, Flex, Last width in that order;
- Bindings shows DIN, Brake width, Gender;
- Goggles shows Gender, then Frame size;
- All restores the built order;
- MTB and BMX order are unchanged.

## 20. Promo strip: sales with no code (owner, 2026-11-25)
**Why:** Skate Warehouse's Black Friday is "25% off shoes, clothing & accessories, 15% off decks, completes & parts", taken off in the cart with no code. The strip (task 16) shows codes only, so it's missing.

**Data (done, Claude's PR "Promo codes: sales applied with no code"):** `promos.json` can now hold an entry with `"code": ""` and `"auto": true`, plus `"tiers": [{"percent": 25, "on": "shoes, clothing & accessories"}, ...]` (`on` may be empty). `promos.describe(promo, code=False)` gives the full line ("25% off shoes, clothing & accessories, 15% off decks, completes & parts, until Dec 2"). `percent` holds the biggest tier, for the short form. At most one such entry per store. The emails already show them, with a "No code needed" chip.

**Wanted:** in `page.py` `_promo_strip`, stop skipping these entries:
- same row as a code offer, but no `<code>` and no Copy button; show a "No code needed" label in the code's place;
- `data-promo-id` stays `json.dumps([store, code])` (so `["SkateWarehouse", ""]`). Don't change the `shreddeals.promo-dismissed` key or its format; existing dismissals must keep working;
- the short form on phones: "Up to 25% off" when there are several tiers, else "25% off";
- the "applied at checkout" wording still fits.

**Tests:** extend `test_promos.py` `NoCodeTests.test_kept_with_the_codes_and_shown_in_emails` (it now asserts the strip is empty for a no-code entry) to the new markup, and a browser check at desktop and 390 px that Dismiss works on a no-code row and the copy button only appears on code rows.

## 21. Store links in Quick View and group rows: use the sale variant (owner, 2026-11-25)
**Why:** evo's Fox Racing PureVue Goggles were listed at $80.95 (a sale color), but the link opened the product page on Black/Clear at $159.95. A Shopify product page opens on its first variant, which often isn't the one on sale.

**Data and server-built links (done, Claude's PR "Store links open on the sale variant"):** Shopify listings now carry `link` (`<url>?variant=<id>`) when the page would open on another variant. `url` stays the listing's identity (history, watchlists, `data-url`, matching); don't change it. The page's catalog JSON items and matched-group offers include `link` only when it differs from `url`. The card link, the table's product link, the detail rows and the emails already use it (`page.py` `shop_href`).

**Wanted, `page.js`, `href`s only:**
- Quick View "Open product page" (`#drawerLink`): `item.link || item.url`.
- Group rows' "View at <store>" (`.group-store-link`): `offer.link || offer.url`. Carry `link` through the offer clean-up near `url: offer.url || ""` (around line 1718).
- Never use `link` for stars/watchlists, `dataset.url`, or any lookup.

**Tests:** a browser check that a listing with `link` opens it from Quick View and from its group row, and that one without `link` still opens `url`.

## 22. Cards: always "Was · Now" next to the percent; the average goes secondary (owner, 2026-11-25)
**Why:** a card shows the store's percent off (from its own "Was" price), but once a listing has 2+ tracked days at different prices, the comparison switches to our average. evo's Fox Racing PureVue Goggles read "↓49% · Average $74.20 / Now $80.95": the price is above the average, yet the card says 49% off, and the "Was" price ($159.95) the 49% comes from isn't shown. Owner: "always show Was … · Now … next to the percent … Move the average somewhere secondary."

**Today:** `page.py` `_card_price_stat` and `page.js` `paintOneCardStat` show "Average $X / Now $Y" when there are 2+ tracked days that aren't all one price, else "Was $X · Now $Y".

**Wanted:**
1. The price line is always "Was $<price_old> · Now $<price_new>" when the store gives a regular price. With none, show "Now $Y" alone, as today.
2. The average moves to a small secondary line under it, only when there are 2+ tracked days that aren't all one price: "Avg $74.20 (we've seen)". Same chart-window rule as today, so it still follows the 30/90/365 setting. With no average, show no line.
3. Change both places together (server-rendered card and `paintOneCardStat`) so the first paint and the repaint agree.
4. Card height stays stable. Keep the line's slot or match the current card height, so cards in a row still line up on desktop (8 columns) and phones.

**Wording:** "we've seen", never "all-time" or "market average" (`docs/publisher-facts.md`).

**Tests:** update the card-stat tests for the new markup. A browser check at 390 px and desktop that:
- a listing with moving history shows Was · Now plus the Avg line;
- a new listing shows Was · Now with no Avg line;
- changing the chart window updates the Avg line;
- card rows still line up.

## 23. Skate › Packs: a Size (liters) filter (owner, 2026-11-25)
**Added 2026-11-27:** a **Features** filter too, like Tactics' pack sidebar ("we want size and type and skateboard carrier ability"). Data (Claude's PR "Pack features"): each pack row's item may carry `pack_features`, a list in `sports/packs.py` `PACK_FEATURES` order: Skateboard straps, Water resistant, Hydration compatible, Waist strap, Chest strap. It comes from the Shopify feed's description, or from the product page read once per pack (Tactics, Skate Warehouse, CCS, Zumiez). A pack whose description wasn't read yet has none. Stamp it on the row as `data-packfeatures="Skateboard straps|Water resistant"`. The sidebar section **Features** takes multi-select chips with counts in that order; picking two shows packs with both. Add a new URL parameter `packfeat` to `skateQueryKeys`. BMX, Ski and MTB get it through the shared spec filters (`{sport}_packfeat`). **Order on Skate › Backpacks: Type, Size (liters), Features.**
**Added 2026-11-26:** a **Type** filter too (`sports/packs.py` `pack_type(name, product_type)`, values in `PACK_TYPES` order: Backpack, Hydration pack, Hip pack, Protector pack, Avalanche airbag pack, Parts & refills). It works like Size, with the URL parameter `packtype` and `data-packtype` on rows. Every pack has a type.
**Why:** "for all backpacks across all sports we should add size when it's available. Many are 28L, smaller or larger." BMX, Ski and MTB now have it through the shared spec filters. Skate's sidebar is built separately (`page.py` sections plus `page.js`), so Skate needs its own section.

**Data (done, Claude's PR "Packs: a Size filter on every sport"):** `sports/packs.py`:
- `volume_litres(name, description)` gives a pack's litres or `None`. The title wins; a reservoir ("with 3L reservoir") isn't counted; Osprey, CamelBak, EVOC, Deuter and Gregory name the litres in the model ("Sopris 32").
- `volume_size(litres)` gives one of `VOLUME_SIZES`: "Under 15L", "15–24L", "25–34L", "35L+".
- About half of Skate's packs state a size today; streetwear packs (Vans, Nike SB, Herschel) often don't.

**Wanted:**
- In `page.py`, compute the size for each Skate pack row (as for `protection_type`) and stamp it on the row, e.g. `data-packsize="25–34L"`.
- A "Size (liters)" sidebar section on Skate › Packs with count chips in `VOLUME_SIZES` order and multi-select, like Protection type. Rows without a size hide while a size is picked.
- A new URL parameter `packsize`, added to `skateQueryKeys`. Don't rename any existing parameter, and keep old saved views working.

**Tests:**
- A Python test that a pack row carries `data-packsize`.
- A browser check on Skate › Packs at desktop and 390 px: picking 25–34L shows only those packs; the URL gets `packsize`; a reload keeps the pick.

## 24. Type chips at the top of MTB and BMX parts headings (owner, 2026-11-26)
**Why:** MTB headings had more parts than products ("under Suspension you see more suspension parts than suspension"). Like Powers, Source and Circuit, spares now stay in their heading as their own type. The owner wants the main items first, with parts one tap away.

**Data (Claude's PRs "MTB: a Type inside each parts heading, and Tools & Care" and "BMX: spares get their own kind"):**
- **MTB:** every listing under Suspension, Wheels, Tires, Drivetrain, Brakes and Cockpit carries the spec `kind`. It's a sidebar facet in `sports/mtb/facets.py`: `{"key": "kind", "label": "Type", "param": "mtb_type", …}`, with `order` = `sports/mtb/kinds.VALUES`.
  - Example values for Suspension: Forks · Rear Shocks · Coil Springs · Fork Parts · Shock Parts.
  - Each heading's full list is `sports/mtb/kinds.ORDER[<store category>]`. Forks & Shocks is the Suspension heading.
- **BMX:** the existing Type filter (`bmx_kind`, formerly labelled "Product kind") gains Fork Parts, Crank Parts, Headset Parts, Stem Parts and Pedal Parts. Brakes splits into Brakes, Brake Kits, Brake Levers, Brake Cables, Brake Pads and Brake Parts.
- **Values are set when the page is built** (`sports/headings.py` `regroup`), on each offer's specs like any other facet. Nothing waits for a scrape.
- **New heading, Tools & Care,** on MTB and BMX, after the parts headings and before the gear. It needs no UI work beyond what any heading gets. Check its slug opens it, e.g. `?sport=mtb&type=tools-care`.

**Wanted:** the same pattern as task 17 (E-MTB chips).
- **The row:** when an MTB parts heading (Suspension, Wheels, Tires, Drivetrain, Brakes, Cockpit) or any BMX heading is active, show a chip row above the results. It reads **All · <each type in `order`>**, each with its count.
- **Main items lead:** values ending in "Parts", plus "Rim Tape & Valves" and "Tubeless & Repair", sit at the end of the row and look secondary (lighter, or after a divider).
- **One state:** the chips drive the existing facet (`mtb_type` / `bmx_kind`). There's no second state and no new URL parameter, so links and saved views work and match the sidebar.
- **When to hide:** hide the row when a heading has only one type.
- **Phone:** fits at 320–390 px and scrolls sideways if needed. Desktop layout otherwise unchanged.
- **Optional, for the owner to approve in the PR screenshots:** default each MTB parts heading to "main items" (everything except the parts values) on first open, with "All" one tap away.

**Keep:** existing URL parameters, saved views and `localStorage` keys. Task 4's general chip row can reuse this.

**Tests:** in the `ci/` pattern, with an MTB Suspension fixture (forks, shocks, fork parts):
- each chip's count matches the facet count;
- picking Forks shows only forks, the URL holds `mtb_type=Forks`, and the sidebar's Type shows the same;
- Back restores All;
- a BMX Brakes fixture shows Brake Kits · Levers · Cables · Pads · Brake Parts;
- desktop and 390 px.

## 25. Skate: the Packs heading reads "Backpacks" (owner, 2026-11-26)
**Why:** stores name the category "Backpacks" (Skate Warehouse "Backpacks + Bags", Exodus "Backpacks", Source BMX "Backpacks", evo "Backpacks"). Bike shops lead with hydration (Fanatik "Packs & Hydration"). The wireframe (`docs/menu-wireframe.md`, rule 2) now says Backpacks, or Packs & Hydration on MTB.

**Done (Claude's PR "Packs heading: Backpacks, or Packs & Hydration on MTB"):** Ski and BMX show **Backpacks** and MTB shows **Packs & Hydration**, through `sports/headings.py` (`PACKS_HEADING`, `_RENAMED`, `ALIASES` "packs"/"pack"). Stored data keeps the store category "Packs". `sports/facets.py` and the pack Size filter follow the new names.

**Wanted for Skate**, whose menu is built from `page.py` `PART_ORDER` and `page.js`:
- The menu, the chips and the heading show **Backpacks** for the store category `Packs`. Stored data, `data-part` values used for filtering, and alerts stay `Packs`.
- `?type=packs` and `?type=pack` keep opening it (`page.js` slug map near `pack: "Packs"`, `typeSlug`; `query_state.py`). A new `?type=backpacks` opens it too. Saved views and the `localStorage` format don't change.
- The navigation categories JSON (`navigation/skate-categories.json`, built from the page) shows "Backpacks".

**Tests:**
- Python: Skate's menu lists Backpacks and no longer Packs; `?type=packs` decodes to it.
- A browser check: an old `?type=packs` link and a saved view with Packs both open Backpacks at desktop and 390 px.

## 26. Promo strip: show every sale, none folded away (owner, 2026-11-26)
**Why:** on desktop, when a sport has more than 2 offers, the strip (tasks 16 and 20) shows the first one and folds the rest behind "+N more" at the far right of the row. The owner didn't see Skate Warehouse's store-wide Black Friday sale until finding that button: "no need to hide those, they are all important… I want to see all sales there." The emails list every offer; the pages should too.

**Today (2026-11-26):** Skate has 3 offers (CCS, Deathgear, Skate Warehouse), BMX 3, Ski 2, MTB 2. Black Friday week can bring more.

**Wanted (`page.py` `_promo_strip`, `page.js` `initPromoStrip`, CSS):**
1. **Every active offer is visible on every width, with nothing folded.** Remove the "+N more" / "Show less" / "Details" collapse.
   - Desktop: offers wrap onto more lines as needed.
   - Phones: one compact row per offer (store, offer, code or "No code needed", Copy, Dismiss), stacked.
2. **Order:** store-wide sales with no code first (they apply without doing anything), then code offers. Within each group, the biggest percent first, then store A–Z.
3. **Dismiss still works per offer.** Keep the `shreddeals.promo-dismissed` key and its `[store, code]` format, so earlier dismissals stay dismissed. Expired offers (`data-ends`) still hide.
4. Keep it compact. One offer per line on desktop is fine. The strip shouldn't push the first row of deals below the fold on a 1366×768 screen with 4 offers. If it would, use two columns rather than hiding any.

**Data:** unchanged (`promos.json`, `promos.describe`).

**Tests:**
- Update `test_promos.py` and the strip's browser checks for the removed collapse.
- A browser check at 1366 px, 1920 px and 390 px with 4 offers: all 4 are visible without clicking; Dismiss on one leaves 3; a reload keeps that dismissal.

## 27. Promo strip as one row of compact chips (owner, 2026-11-26)
**Supersedes the layout in task 26** (its "nothing folded behind +N more" goal stays). If 26 isn't built yet, build this instead.

**Why:** the strip (tasks 16, 20, 26) is a grid of uneven boxes. Skate Warehouse's tiered sale wraps to three lines while CCS's code takes one, so the spacing is jagged and the first row of deals is pushed down the page (owner's screenshot, Skate, 2026-11-26: four offers take about 90 px on desktop).

**Wanted (`page.py` `_promo_strip`, `page.js` `initPromoStrip`, CSS):**
1. **One horizontal row of chips**, directly above the cards. It scrolls sideways (`overflow-x: auto; white-space: nowrap`, scroll-snap per chip), the same on desktop and phones. Each chip is one line:
   - Code offer: `CCS · 20% off · [BFCM26] ×`
   - No-code sale: `SkateWarehouse · Up to 25% off · No code ⓘ ×`
   - Headline: "Up to N% off" when `tiers` has more than one entry, else "N% off" (or "$N off" from `amount`). `percent` already holds the biggest tier.
   - Store name links to the promo's `url`, as now.
2. **The code chip copies on click.** Remove the separate Copy button. The code is the button (`<button>` holding a `<code>`, `aria-label="Copy code BFCM26"`). On click, show a short "Copied!" tooltip for about 1.5 s, and announce it through an `aria-live="polite"` region.
3. **Details go in a popover.** Put the full `promos.describe(promo, code=False)` line plus "applied at checkout" behind an `ⓘ` button on the chip, e.g. "25% off shoes, clothing & accessories, 15% off decks, completes & parts · Until Dec 2 · Applied at checkout". It opens on hover and focus on desktop and on tap on phones; Esc closes it. Show it only when it adds something beyond the headline (tiers, `reach`, or an end date).
4. **Dismiss becomes a subtle `×`** at the chip's right end (`aria-label="Hide CCS offer"`). Keep the `shreddeals.promo-dismissed` key and its `[store, code]` format, so earlier dismissals stay.
5. **One toggle for the whole strip.** The label reads "Sales & promos (4)", followed by a "Hide ▴" / "Show ▾" button that collapses the row to just the label line. Store the choice under a **new** `localStorage` key (for example `shreddeals.promo-strip-collapsed`). Don't change existing keys, URL parameters or the saved-view format.
6. **Follow the store filter.** When the visitor's store filter (the `store` state in `query_state.py` and the STORES pills) names one or more stores, show only those stores' offers, and hide the strip when none have one. "All stores" shows every offer. Match on the store name (`data-store`) the same way cards do. Update live when the filter changes, with no reload.
7. **Nothing hidden by accident (task 26's point).** Order stays: no-code sales first, then codes, biggest percent first, then store A–Z. When chips overflow the row, show a right-edge fade and a small "→ N more" button that scrolls the row. On desktop, offers that fit must all be visible without scrolling.
8. **Look:** each chip has a 1px border in the card border colour, a light tint (amber for no-code sales, blue for codes), and the same radius as the cards. The code sits in a dashed-border monospace pill, so it reads as a coupon. Define the colours as tokens with dark-mode values, like the rest of `page.css`. The page doesn't use Tailwind, so translate the owner's `border-slate-200` / `bg-blue-50/60` / `border-dashed border-blue-400` into tokens. The strip should be one chip high (about 36–40 px plus the label) at every width.

**Data:** unchanged (`promos.json`, `promos.describe`). Expired offers (`data-ends`) still hide.

**Tests:**
- Update `test_promos.py` for the new markup (no Copy button; the code is a button; the `ⓘ` details hold the describe() line).
- Browser checks at 1366 px, 1920 px and 390 px with 4 fixture offers:
  - the strip is one row high;
  - clicking a code puts it on the clipboard and shows "Copied!";
  - the `ⓘ` popover shows the tiers and the end date;
  - `×` hides one offer and a reload keeps it hidden;
  - Hide collapses the strip and a reload keeps it collapsed;
  - picking a store with no offer hides the strip, and picking CCS shows only CCS;
  - the overflow cue appears when the chips don't fit at 390 px.

## 28. First impressions: real sport links, a tagline, link previews, no stale text (owner, 2026-11-28)
**Why:** an outside review of shreddeals.com read the pages without running JavaScript, the way link previews and search bots do. It found:
- the homepage's hidden "Coming soon / no catalog yet" section, whose wording ("Skate deals are available now while we add more sports") is out of date now that all four sports are live;
- sport tabs that exist only after JavaScript runs (`<div id="sportTabs">` is empty in the HTML, and the `<noscript>` offers only "Open SkateDeals");
- scaffolding text in the markup ("Loading catalog tools…", "Loading catalog…");
- nothing that says what the site is: no tagline, and no meta description or link-preview tags on any page. The Skate page's title still says **"SkateDeals | <date>"** (old name); Ski, MTB and BMX say "ShredDeals <Sport> | <date>".

**The owner wants to stay low-key for now.** Fix how the site reads to a first-time visitor and in a shared link, but add nothing that invites indexing: no sitemap, no structured data, no robots.txt changes.

**Wanted:**
1. **Sport tabs as real links.** `index.html` and each sport page carry the four sport tabs as plain `<a href>` links in the HTML (Skate → `sale_items_chart.html`, Ski → `ski/sale_items_chart.html`, and so on, relative to the page), with the current sport marked `aria-current="page"`. The existing JavaScript enhances them in place (same look, same behaviour, same URL parameters). Without JavaScript they still navigate.
2. **Remove the stale "Coming soon" section** (`#comingSoon`, `#backToSkate`) and the JavaScript that shows it, or rewrite it as a neutral "This sport's catalog couldn't load. Try again" error state, if the code still needs a fallback. Replace the `<noscript>` text with links to all four sports.
3. **A one-line tagline** on the homepage, above the catalog, small and quiet: *"Every shop's sale rack for skate, ski, bike and BMX, in one place."* One line on phones at 390 px; it must not push the first row of deals down noticeably.
4. **Link previews:** on `index.html` and every sport page, add `<meta name="description">` plus `og:title`, `og:description`, `og:type=website` and `og:url`. Example for the Skate page: description "Skate decks, wheels, trucks, shoes and more on sale at skate shops, updated daily." Write a matching line per sport. No `og:image` yet (the owner can add one later).
5. **Titles:** `page.py` line ~2123 builds `<title>{sport.brand} | {date}</title>`. Make every page read **"ShredDeals · Skate deals"**, "ShredDeals · Ski deals", "ShredDeals · MTB deals", "ShredDeals · BMX deals", and the homepage "ShredDeals · Gear on sale". Drop the date from the title (the page already shows "last scan"). Titles are not part of any URL, `localStorage` key or saved view, so old links are unaffected. Change only the visible title text; leave `sport.brand` wherever else it's used.
6. **Status labels start empty.** `#myStuffStatus` ("Loading catalog tools…") and `#catalogLoading` text start empty or visually hidden, and JavaScript sets them when there's something to say. The loading skeleton itself can stay.

**Not now (owner, 2026-11-28):** rendering the catalog directly on the homepage instead of in the `#skateFrame` iframe. That's what search traffic would need, and the owner will come back to it. Lazy-loading the My stuff drawer isn't worth it either (the homepage is ~6 KB).

**Don't change:** URL parameters, `localStorage` keys, the saved-view format, or anything the existing navigation tests rely on.

**Tests:**
- **Python:** each built page has a `<meta name="description">`, the `og:` tags and the new title; Skate's title no longer contains "SkateDeals".
- **Browser checks** (pattern: `ci/check_category_navigation.cjs`):
  - with JavaScript disabled, the homepage and the MTB page show four working sport links;
  - with JavaScript, tabs look and behave as today at desktop and 390 px;
  - the "Coming soon" text appears nowhere in the HTML.
