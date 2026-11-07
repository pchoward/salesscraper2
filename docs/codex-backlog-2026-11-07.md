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
