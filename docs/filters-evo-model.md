# Catalog filters modelled on evo

Owner, 2026-11-21. House rule on every sport: **Brand first, then that heading's size filter, then Gender, then the next most useful filters, with Condition (Demo) last** among the spec sections. evo often leads with size and puts Brand later. We keep Brand first.

This file is the order and the category scope for Claude. Field definitions and extraction stay in `sports/<sport>/facets.py` (and `sports/protection.py` where a sport shares those fields). The page does not reorder sections and does not override a field's categories.

What the page already does for Ski, BMX, and MTB: each technical section gets `data-for` from the field's categories (every menu heading of that sport when the category list is empty). `syncTypeSections` then hides those sections on All, and shows them once a heading is selected. Brand, Stores, Price & discount, and the deal sections (Deal quality, Deal type, Price-drop window) stay up on All. BMX Product kind is left unmarked, so All keeps that filter. MTB has no Product kind field, so All does not keep one. When Claude edits a Ski, BMX, or MTB field's categories, All-vs-heading visibility follows on the next page build. **Order:** `sports/ski/facets.py` `ORDER` lists each heading's sections in order. `sports/facets.py` `sidebar()` stamps each section with `data-rank="Skis:2 Boots:6 …"`, its position on each heading that ranks it. The page sorts by the chosen heading (Codex task 19 in `docs/codex-backlog-2026-11-07.md`). Until that lands, sections keep the `FIELDS` tuple order.

Coverage below is `catalogs/ski/previous_data.json` on 2026-11-21, counted after `sports.headings.heading` (stored parts stay Protection; the page shows Goggles and Helmets). A listing counts when `technical_specs` has a non-empty value. The live page also drops anything under the 10% minimum, so its totals sit a little lower (3,216 deals that day). Counts will move with the next scrape.

Status words:

- **exists** — field, values, and scope are already right.
- **reorder only** — field exists; Claude changes order (and, where noted, which headings it applies to).
- **needs new data field from Claude** — no field yet, or the existing field is too thin to use. Do not add a second field when one already exists.

URL parameter names stay as they are.

One global `FIELDS` tuple cannot satisfy every heading. Boots want Type, then Ability, then Binding compatibility. Bindings want Binding compatibility, then Ability, then Type. Per-heading order has to live in the facet config, with `sidebar()` sorting by the active heading.

## Ski

Menu headings: Skis, Boots, Bindings, Poles, Helmets, Goggles, Gloves, Protection, Packs.

Gender today is Men, Women, Kids (`sports/ski/specs.py`). There is no Unisex value. **Unisex needs a new value from Claude** on the existing `gender` field (`ski_gender`), not a new filter. Coverage for Gender below is Men / Women / Kids only.

Condition and Ability currently have empty categories, so they are offered on every heading. Ability is one helmet and one pole. Condition is 21 skis and 6 bindings. Claude should limit both to **Skis, Boots, Bindings**, and put Condition last on those three.

### Skis (1,009)

| # | Filter | Field | Examples | Also on | Coverage | Status |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Brand | page Brand section | shop brands | every heading | all listings | exists |
| 2 | Ski length | `length` / `ski_length` | 10 cm ranges: Under 100 cm, 150–159 cm, 160–169 cm, 170–179 cm, 180–189 cm | Poles | 638 / 1,009 | reorder only |
| 3 | Gender | `gender` / `ski_gender` | Men, Women, Kids. Unisex needs a value | every Ski heading | 503 / 1,009 | reorder only. Unisex: needs new data field from Claude |
| 4 | Waist width | `waist` / `ski_waist` | Under 85 mm, 85–94 mm, 95–104 mm, 105–114 mm, 115 mm and wider | Skis | 387 / 1,009 | reorder only |
| 5 | Type | `ski_type` / `ski_type` | All-Mountain, Freeride, Park & Freestyle, Carving / Frontside, Powder, Race, Backcountry / Touring | Boots, Bindings | 361 / 1,009 | reorder only |
| 6 | Ability level | `ability` / `ski_ability` | Beginner, Intermediate, Advanced, Expert | Boots, Bindings (Claude: drop the other headings) | 239 / 1,009 | reorder only |
| 7 | Rocker profile | `rocker` / `ski_rocker` | Rocker / Camber / Rocker, Full Camber, Tip Rocker / Camber, Full Rocker | Skis | 250 / 1,009 | reorder only |
| 8 | Bindings | `bindings` / `ski_bindings` | Included, Flat (no bindings) | Skis | 378 / 1,009 | reorder only |
| 9 | Turn radius | `radius` / `ski_radius` | Short (under 16 m), Medium (16–20 m), Long (over 20 m) | Skis | 81 / 1,009 | reorder only |
| 10 | Color | — | evo's color chips | see note under Packs | 0 | needs new data field from Claude |
| 11 | Condition | `condition` / `ski_condition` | Demo | Boots, Bindings | 21 / 1,009 | reorder only. Last |

Current order on this heading: Brand, Condition, Type, Ski length, Waist width, Turn radius, Rocker profile, Bindings, Ability level, Gender.

### Boots (1,185)

| # | Filter | Field | Examples | Also on | Coverage | Status |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Brand | page Brand section | shop brands | every heading | all listings | exists |
| 2 | Boot size (Mondo) | `mondo` / `ski_mondo` | exact mondo, e.g. 22.5, 23.5, 24.5, 25.5, 26.5, 27.5 | Boots | 839 / 1,185 | reorder only |
| 3 | Gender | `gender` / `ski_gender` | Men, Women, Kids. Unisex needs a value | every Ski heading | 618 / 1,185 | reorder only. Unisex: needs new data field from Claude |
| 4 | Flex | `flex` / `ski_flex` | Soft (under 80), Medium (80–100), Stiff (105–120), Very stiff (over 120) | Boots | 1,066 / 1,185 | reorder only |
| 5 | Last width | `last` / `ski_last` | Narrow (98 mm and under), Medium (99–101 mm), Wide (102 mm and over) | Boots | 665 / 1,185 | reorder only |
| 6 | Type | `ski_type` / `ski_type` | Backcountry / Touring, All-Mountain, Race, Park & Freestyle | Skis, Bindings | 197 / 1,185 | reorder only |
| 7 | Ability level | `ability` / `ski_ability` | Beginner, Intermediate, Advanced, Expert | Skis, Bindings | 290 / 1,185 | reorder only |
| 8 | Binding compatibility | `sole` / `ski_sole` | GripWalk, Alpine (ISO 5355), Tech / Pin inserts, Touring (ISO 9523), MNC, WTR | Bindings | 568 / 1,185 | reorder only |
| 9 | Walk mode | `walk` / `ski_walk` | Walk mode | Boots | 109 / 1,185 | reorder only |
| 10 | BOA | — | BOA closure vs buckle | Boots | 0 | needs new data field from Claude |
| 11 | Color | — | evo's color chips | see Packs | 0 | needs new data field from Claude |
| 12 | Condition | `condition` / `ski_condition` | Demo | Skis, Bindings | 0 / 1,185 | reorder only. Last. Section stays hidden while no boot is a demo |

### Bindings (154)

| # | Filter | Field | Examples | Also on | Coverage | Status |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Brand | page Brand section | shop brands | every heading | all listings | exists |
| 2 | DIN | `din` / `ski_din` | Up to 10, 11–13, 14 and up | Bindings | 147 / 154 | reorder only |
| 3 | Brake width | `brake` / `ski_brake` | 76 mm, 85 mm, 95 mm on the four listings that have one | Bindings | 4 / 154 | needs new data field from Claude. The field id already exists; extraction covers 4 listings, which is too thin to be the size filter. Fill `brake`, do not add a second key |
| 4 | Gender | `gender` / `ski_gender` | Men, Women, Kids. Unisex needs a value | every Ski heading | 15 / 154 | reorder only. Unisex: needs new data field from Claude |
| 5 | Binding compatibility | `sole` / `ski_sole` | GripWalk, Alpine (ISO 5355), Touring (ISO 9523), MNC, WTR, Tech / Pin inserts | Boots | 122 / 154 | reorder only |
| 6 | Ability level | `ability` / `ski_ability` | Beginner, Intermediate, Advanced, Expert | Skis, Boots | 39 / 154 | reorder only |
| 7 | Type | `ski_type` / `ski_type` | Backcountry / Touring, All-Mountain, Race, Freeride | Skis, Boots | 16 / 154 | reorder only |
| 8 | Color | — | evo's color chips | see Packs | 0 | needs new data field from Claude |
| 9 | Condition | `condition` / `ski_condition` | Demo | Skis, Boots | 6 / 154 | reorder only. Last |

Owner order here is DIN, then brake width, then Gender. Brake width is the size-shaped filter and still sits after DIN, because that is the order the owner asked for. It stays in the list while Claude fills the data.

### Poles (100)

| # | Filter | Field | Examples | Also on | Coverage | Status |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Brand | page Brand section | shop brands | every heading | all listings | exists |
| 2 | Ski length | `length` / `ski_length` | same 10 cm ranges as Skis | Skis | 0 / 100 | exists as a scope. No pole listing has a length. Claude extracts it where the store states one; the key stays `length` |
| 3 | Gender | `gender` / `ski_gender` | Men, Women, Kids. Unisex needs a value | every Ski heading | 48 / 100 | reorder only. Unisex: needs new data field from Claude |
| 4 | Color | — | evo's color chips | see Packs | 0 | needs new data field from Claude |

Ability is 1 / 100. Leave it off Poles when Claude limits Ability to Skis, Boots, and Bindings. Condition is 0 / 100. Leave it off Poles the same way.

### Goggles (303)

Desired sections, in order. Helmet-only fields are listed after the table; they are a scope change, not part of this order.

| # | Filter | Field | Examples | Also on | Coverage | Status |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Brand | page Brand section | shop brands | every heading | all listings | exists |
| 2 | Gender | `gender` / `ski_gender` | Men, Women, Kids. Unisex needs a value | every Ski heading | 69 / 303 (Men 55, Kids 10, Women 4) | reorder only. Unisex: needs new data field from Claude |
| 3 | Frame size | `goggle_size` / `ski_gsize` | Small, Medium, Large, XL | Goggles. Also Protection today; Claude should keep it on Goggles. Protection has none of these values | 101 / 303 | reorder only |
| 4 | Fit | `goggle_fit` / `ski_gfit` | Low bridge fit, Over glasses (OTG), Kids | Goggles | 62 / 303 | reorder only |
| 5 | Lens | `goggle_lens` / `ski_glens` | Magnetic lens change, Photochromic, Bonus lens included | Goggles | 44 / 303 | reorder only |
| 6 | Lens shape | — | cylindrical, spherical, toric. This is shape, separate from Lens above | Goggles | 0 | needs new data field from Claude |
| 7 | Color | — | evo's lens / frame color | see Packs | 0 | needs new data field from Claude |

Gender before Frame size on Goggles is the owner's order for this heading. The size-then-Gender house rule still holds on Skis, Boots, and Helmets.

**Claude: take Goggles off the helmet-only fields.** `protection.facet_fields` is called from `sports/ski/facets.py` with categories Helmets, Protection, Goggles, Gloves, so choosing Goggles offers those sections. On the 303 goggles none of that data is meaningful:

| Field | Field id | On goggles | Why it is not a goggle filter |
| --- | --- | --- | --- |
| Protects | `protects` / `ski_protects` | 303 / 303 | 301 are "Goggles", 2 are "Goggle lenses". The heading already says that |
| Age | `age` / `ski_age` | 303 / 303 | 283 are Adult because a kind was found, not because the listing stated an age. 13 Kids and 7 Youth come from title words |
| Size | `prot_size` / `ski_psize` | 1 / 303 | one listing, "L" (evo Felsen). Frame size is `goggle_size` |
| Helmet type | `helmet_style` / `ski_helmet` | 0 / 303 | values are helmets ("Snow") |
| Rotational protection | `rotational` / `ski_rotational` | 0 / 303 | MIPS, Spherical, WaveCel are helmets |
| Certification | `certification` / `ski_cert` | 0 / 303 | the certifications in the catalog are on helmets and armor |

Helmets and Protection keep these fields. The page will stop offering them on Goggles once the categories no longer include Goggles.

### Helmets (338)

| # | Filter | Field | Examples | Also on | Coverage | Status |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Brand | page Brand section | shop brands | every heading | all listings | exists |
| 2 | Size | `prot_size` / `ski_psize` | XS, S, M, L, XL, XXL | Protection, Gloves, and Goggles until Claude drops Goggles | 281 / 338 | reorder only |
| 3 | Gender | `gender` / `ski_gender` | Men, Women, Kids. Unisex needs a value | every Ski heading | 80 / 338 | reorder only. Unisex: needs new data field from Claude |
| 4 | Rotational protection | `rotational` / `ski_rotational` | MIPS, Spherical, WaveCel | Protection, Gloves, and Goggles until Claude drops Goggles | 217 / 338 (MIPS 207) | reorder only |
| 5 | Certification | `certification` / `ski_cert` | EN 1077 (EU snow), ASTM F2040 (snow), CPSC (US bike), EN 1078, Certified (standard not named) | Protection, Gloves, and Goggles until Claude drops Goggles | 39 / 338 | reorder only |
| 6 | Age | `age` / `ski_age` | Adult, Youth, Kids | Protection, Gloves, and Goggles until Claude drops Goggles | 338 / 338 (Adult 285, Kids 29, Youth 24) | reorder only |
| 7 | Helmet shell | — | in-mold, hard shell, hybrid | Helmets | 0 | needs new data field from Claude |
| 8 | Helmet type | `helmet_style` / `ski_helmet` | Snow, Full face. Every ski helmet today is Snow | Protection, Gloves, and Goggles until Claude drops Goggles | 338 / 338, all Snow | exists. Keep on Helmets. The chip does not split the list while every value is Snow |
| 9 | Protects | `protects` / `ski_protects` | Helmets, plus the body-part labels on Protection | Protection, Gloves, and Goggles until Claude drops Goggles | 338 / 338, all Helmets | exists. Keep on Helmets |
| 10 | Color | — | evo's color chips | see Packs | 0 | needs new data field from Claude |

Ability is 1 / 338. Leave it off Helmets when Claude limits Ability to Skis, Boots, and Bindings.

### Protection (26)

Same fields as today. Protects is the useful filter on this heading, so it sits after Size and Gender. That is a different relative order from Helmets, where Protects stays after Age. Goggles stay out of this heading (they have their own).

| # | Filter | Field | Examples | Also on | Coverage | Status |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Brand | page Brand section | shop brands | every heading | all listings | exists |
| 2 | Size | `prot_size` / `ski_psize` | XS–XXL | Helmets, Gloves | 18 / 26 | reorder only |
| 3 | Gender | `gender` / `ski_gender` | Men, Women, Kids. Unisex needs a value | every Ski heading | 0 / 26 | reorder only. Unisex: needs new data field from Claude |
| 4 | Protects | `protects` / `ski_protects` | Back & Spine, Hips & Tailbone, Wrists, Chest & Ribs, Knees | Helmets, Gloves | 24 / 26 | reorder only |
| 5 | Certification | `certification` / `ski_cert` | EN 1621 (CE impact armor), Certified (standard not named) | Helmets, Gloves | 7 / 26 | reorder only |
| 6 | Age | `age` / `ski_age` | Adult, Youth, Kids | Helmets, Gloves | 24 / 26 | reorder only |
| 7 | Helmet type | `helmet_style` / `ski_helmet` | Snow, Full face | Helmets, Gloves | 0 / 26 | exists. Keep the scope. Hidden while nothing here has a value |
| 8 | Rotational protection | `rotational` / `ski_rotational` | MIPS and the other systems | Helmets, Gloves | 0 / 26 | exists. Keep the scope. Hidden while nothing here has a value |
| 9 | Color | — | evo's color chips | see Packs | 0 | needs new data field from Claude |

### Gloves (0 listings)

No glove listings in this catalog. When they show up, the order is Brand, Size (`prot_size`), Gender, then the protection fields that a glove actually has (Protects, Age, Certification). Helmet type and Rotational protection stay available only when a glove listing carries that value. Unisex and Color are the same needs-data items as the other headings. Claude should look at Gloves the same way as Goggles before leaving helmet fields on that heading.

### Packs (128)

No spec field has a value. The heading stays Brand plus the generic sections. Color, if Claude adds it, is the first spec section here. evo's pack volume is out of this pass until the owner asks.

Color, wherever it is added, is one field shared by the headings above (Skis, Boots, Bindings, Poles, Goggles, Helmets, Protection, Gloves, Packs), on the same pattern as Skate's color sections. It needs a new data field from Claude.

## BMX, modelled on Dan's Comp

Menu headings: Bikes, Frames & Forks, Bars & Steering, Drivetrain, Wheels & Hubs, Tires & Tubes, Seats & Posts, Brakes, Helmets, Goggles, Gloves, Protection, Packs.

House rule here: **Brand, then that heading's size filter, then the next most useful specs, Condition last.** No Gender on BMX.

Names follow Dan's Comp. The live Dan's Comp sidebar could not be read (Cloudflare), so the names are the ones in `docs/multi-sport-plan.md` section 3.

Coverage is `catalogs/bmx/previous_data.json` on 2026-11-21, counted after `sports.headings.heading` (stored parts stay Steering, Wheels, Wheel Parts, Tires, Seating, Braking; the page shows the headings above). 1,730 listings. A listing counts when `technical_specs` has a non-empty value. The live page also drops anything under the 10% minimum, so its totals sit a little lower. Counts will move with the next scrape.

What the page does now: each spec section except Product kind gets `data-for`. All keeps Brand, Stores, Price & discount, the deal sections, and Product kind. A heading shows the sections whose categories include it. Material, Color, and Condition have empty categories, so they hide on All and show under every heading (a heading with no values still folds that section away). Order is still the one `FIELDS` tuple, on every heading:

Product kind, Wheel size, Condition, Hub Type, Toptube Length, Drive Side, Bar Rise, Crank Length, Axle, Material, Color, then Protects, Helmet type, Certification, Rotational protection, Size, Age.

Several category lists still name the old store parts next to the heading (`Steering` with `Bars & Steering`, `Wheels` and `Wheel Parts` with `Wheels & Hubs`, `Tires` with `Tires & Tubes`). The menu heading is in the list, so the section shows. Claude can drop the old names when editing scope.

Per-heading order is not in this PR. One `FIELDS` tuple cannot hold it (Ski already needed `ORDER`). Claude adds a BMX `ORDER` in `sports/bmx/facets.py` on the same shape as Ski. `sidebar()` will stamp `data-rank` from that. Until then, sections stay in the tuple order above.

Product kind (`kind` / `bmx_kind`, labelled "Product kind") stays on All and on every heading. That is the type filter. Chips for it above the results are Codex task 4 and are not part of this list.

### Bikes (17)

Toptube Length should show once a wheel size is chosen. The page does not do that yet: under Bikes it shows with the other Bikes sections as soon as the heading is selected.

| # | Filter | Field | Examples | Also on | Coverage | Status |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Brand | page Brand section | shop brands | every heading | all listings | exists |
| 2 | Wheel size | `wheel_size` / `bmx_wheel` | 12, 14, 16, 18, 20, 22, 24, 26, 29 | Frames & Forks, Wheels & Hubs, Tires & Tubes. Today also the old names Wheels and Tires | 15 / 17 | reorder only |
| 3 | Toptube Length | `top_tube` / `bmx_tt` | 18"–22.13" in this catalog | Frames & Forks | 5 / 17 | reorder only. Youth lengths: needs new data field from Claude. `sports/bmx/dans.py` keeps only 18–22.5"; fill `top_tube`, do not add a second key. Show it only after a wheel size is chosen |
| 4 | Hub Type | `hub_type` / `bmx_hub` | Cassette, Freecoaster | Wheels & Hubs. Today also Wheels and Wheel Parts | 0 / 17 | exists. The scope already includes Bikes. Hidden here while no bike states one |
| 5 | Drive Side | `drive_side` / `bmx_drive` | Right (RHD), Left (LHD). Universal is not a value yet | Wheels & Hubs, Drivetrain. Today also Wheels and Wheel Parts | 0 / 17 | reorder only. Universal: needs new data field from Claude, on this key |
| 6 | Material | `material` / `bmx_material` | Chromoly, Carbon, Aluminum, Titanium, Hi-Ten, Nylon / Plastic | Frames & Forks, Wheels & Hubs. Empty categories, so every heading today | 0 / 17 | reorder only. Claude limits it to the headings that list it |
| 7 | Color | `color` / `bmx_color` | Black, Chrome / Polished, Red, Blue, and the rest of the colour list | every heading. Empty categories | 14 / 17 | reorder only. Stays on every heading. Claude can leave the category list empty |
| 8 | Condition | `condition` / `bmx_condition` | Demo, Scratch & Dent | no other heading in this list. Empty categories, so every heading today | 0 / 17 | reorder only. Last. Claude limits it to Bikes. Hidden while nothing is a demo |

Axle is on Bikes today (3 / 17: 14mm, 3/8") because `axle` includes Bikes. The desired lists do not put it here. Claude should drop Bikes from `axle`.

### Frames & Forks (130)

Kind is the existing Product kind field (Frames 62, Forks 68).

| # | Filter | Field | Examples | Also on | Coverage | Status |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Brand | page Brand section | shop brands | every heading | all listings | exists |
| 2 | Toptube Length | `top_tube` / `bmx_tt` | 20.5", 20.75", 21", 21.25" | Bikes | 49 / 130 | reorder only. Same youth-length gap as Bikes. This heading's size filter, so it leads |
| 3 | Kind | `kind` / `bmx_kind` | Frames, Forks | every heading today, and All | 130 / 130 | exists. Stays on All |
| 4 | Wheel size | `wheel_size` / `bmx_wheel` | 18, 20, 22, 24 | Bikes, Wheels & Hubs, Tires & Tubes | 88 / 130 | reorder only |
| 5 | Offset | — | fork offset | Frames & Forks | 0 | needs new data field from Claude |
| 6 | Dropouts/Axle | `axle` / `bmx_axle` | 10mm, 3/8". 14mm is on the same key, mostly hubs | Wheels & Hubs. Today also Bikes, Wheels, Wheel Parts | 4 / 130 | needs new data field from Claude. The key exists; 4 listings is too thin for a fork dropout filter. Fill `axle` (10mm / 3/8" on forks), do not add a second key |
| 7 | Chainstay | — | chainstay length | Frames & Forks | 0 | needs new data field from Claude |
| 8 | Bottom Bracket | — | Mid, Spanish, American | Frames & Forks | 0 | needs new data field from Claude |
| 9 | Brake Mounts | — | the mounts a frame or fork states | Frames & Forks | 0 | needs new data field from Claude |
| 10 | Material | `material` / `bmx_material` | Carbon, Aluminum | Bikes, Wheels & Hubs | 8 / 130 | reorder only. Scope as on Bikes |
| 11 | Color | `color` / `bmx_color` | Black, Chrome / Polished, and the rest | every heading | 105 / 130 | reorder only |

Condition is not on this heading. It leaves once Claude limits Condition to Bikes.

### Bars & Steering (212)

| # | Filter | Field | Examples | Also on | Coverage | Status |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Brand | page Brand section | shop brands | every heading | all listings | exists |
| 2 | Kind | `kind` / `bmx_kind` | Handlebars, Stems, Headsets, Grips & Bar Ends, Detanglers | every heading today, and All | 210 / 212 | exists. Stays on All |
| 3 | Bar Rise | `bar_rise` / `bmx_rise` | 8", 8.5", 9", 9.5", 11" | Bars & Steering. Today also the old name Steering | 37 / 212 | reorder only |
| 4 | Width | — | bar width | Bars & Steering | 0 | needs new data field from Claude |
| 5 | Backsweep | — | backsweep | Bars & Steering | 0 | needs new data field from Claude |
| 6 | 2-piece/4-piece | — | 2-piece, 4-piece | Bars & Steering | 0 | needs new data field from Claude |
| 7 | Stem type & Reach | — | Top Load, Front Load, and reach | Bars & Steering | 0 | needs new data field from Claude |
| 8 | Color | `color` / `bmx_color` | Black, Red, Chrome / Polished, and the rest | every heading | 194 / 212 | reorder only |

### Drivetrain (182)

| # | Filter | Field | Examples | Also on | Coverage | Status |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Brand | page Brand section | shop brands | every heading | all listings | exists |
| 2 | Kind | `kind` / `bmx_kind` | Cranks, Sprockets, Bottom Brackets, Chains, Pedals | every heading today, and All | 181 / 182 | exists. Stays on All. Kind is the splitter until the size filters below have data |
| 3 | Crank Length | `crank_length` / `bmx_crank` | 175 mm, the only value in this catalog | Drivetrain | 1 / 182 | needs new data field from Claude. The key exists. `dans.py` only reads 150–185 mm, and one listing is too thin. Fill `crank_length`, do not add a second key. This is the size filter once it has data |
| 4 | Spindle | — | 19mm, 22mm, 24mm | Drivetrain | 0 | needs new data field from Claude |
| 5 | Drive Side | `drive_side` / `bmx_drive` | Right (RHD), Left (LHD). Universal is not a value yet | Bikes, Wheels & Hubs | 3 / 182 | reorder only. Universal on this key, as on Bikes |
| 6 | Sprocket teeth | — | tooth count | Drivetrain | 0 | needs new data field from Claude |
| 7 | Bolt/Spline | — | Bolt, Spline | Drivetrain | 0 | needs new data field from Claude |
| 8 | Color | `color` / `bmx_color` | Black, Chrome / Polished, and the rest | every heading | 115 / 182 | reorder only |

### Wheels & Hubs (416)

| # | Filter | Field | Examples | Also on | Coverage | Status |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Brand | page Brand section | shop brands | every heading | all listings | exists |
| 2 | Wheel size | `wheel_size` / `bmx_wheel` | 12 through 29, mostly 20 | Bikes, Frames & Forks, Tires & Tubes | 79 / 416 | reorder only |
| 3 | Kind | `kind` / `bmx_kind` | Hubs, Rims & Rim Strips, Spokes & Nipples, Pegs, Hub Guards, Wheels, Drivers & Freewheels | every heading today, and All | 416 / 416 | exists. Stays on All |
| 4 | Hub Type | `hub_type` / `bmx_hub` | Freecoaster, Cassette | Bikes | 88 / 416 | reorder only |
| 5 | Driver Teeth | — | 9t and the other counts | Wheels & Hubs | 0 | needs new data field from Claude |
| 6 | Drive Side | `drive_side` / `bmx_drive` | Right (RHD), Left (LHD). Universal is not a value yet | Bikes, Drivetrain | 92 / 416 | reorder only. Universal on this key |
| 7 | Axle | `axle` / `bmx_axle` | 14mm, 10mm, 3/8" | Frames & Forks, as Dropouts/Axle | 33 / 416 | reorder only |
| 8 | Holes | — | rim hole count | Wheels & Hubs | 0 | needs new data field from Claude |
| 9 | Material | `material` / `bmx_material` | Nylon / Plastic, Carbon, Titanium, Chromoly, Aluminum | Bikes, Frames & Forks | 51 / 416 | reorder only. Scope as on Bikes |
| 10 | Color | `color` / `bmx_color` | Black, Chrome / Polished, Oil Slick, and the rest | every heading | 270 / 416 | reorder only |

### Tires & Tubes (119)

| # | Filter | Field | Examples | Also on | Coverage | Status |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Brand | page Brand section | shop brands | every heading | all listings | exists |
| 2 | Size (wheel x width) | `wheel_size` / `bmx_wheel` for the wheel inches | 12, 16, 18, 20, 24, 29. Width (20 × 2.3–2.5) is not read | Bikes, Frames & Forks, Wheels & Hubs, as Wheel size | 68 / 119 have a wheel inch. Width 0 | reorder only for the wheel inch. Width: needs new data field from Claude. Do not add a second wheel-size key |
| 3 | Bead | — | bead | Tires & Tubes | 0 | needs new data field from Claude |
| 4 | Tread | — | tread | Tires & Tubes | 0 | needs new data field from Claude |
| 5 | PSI | — | pressure | Tires & Tubes | 0 | needs new data field from Claude |
| 6 | Color | `color` / `bmx_color` | Black, and a few others | every heading | 47 / 119 | reorder only |

Product kind still shows here (Tires, Tubes) because it is unscoped. This list does not add a Kind row. It stays until someone scopes `kind`.

### Seats & Posts (113)

| # | Filter | Field | Examples | Also on | Coverage | Status |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Brand | page Brand section | shop brands | every heading | all listings | exists |
| 2 | Kind | `kind` / `bmx_kind` | Seats, Seat Posts, Seat Post Clamps | every heading today, and All | 109 / 113 | exists. Stays on All |
| 3 | Style | — | Pivotal, Tripod, Railed | Seats & Posts | 0 | needs new data field from Claude |
| 4 | Color | `color` / `bmx_color` | Black, and the rest | every heading | 63 / 113 | reorder only |

### Brakes (40)

| # | Filter | Field | Examples | Also on | Coverage | Status |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Brand | page Brand section | shop brands | every heading | all listings | exists |
| 2 | Kind | `kind` / `bmx_kind` | Brakes & Accessories | every heading today, and All | 40 / 40 | exists. Stays on All |
| 3 | Color | `color` / `bmx_color` | Black, and the rest | every heading | 23 / 40 | reorder only |

### Helmets, Goggles, Gloves, Protection

One order for these four. Helmet-only rows stay in the shared protection fields (`protects`, `helmet_style`, `certification`, `rotational`, `prot_size`, `age`), scoped today to Protection, Helmets, Goggles, and Gloves. A heading with none of a field's values folds that section away.

| # | Filter | Field | Examples | Coverage | Status |
| --- | --- | --- | --- | --- | --- |
| 1 | Brand | page Brand section | shop brands | all listings | exists |
| 2 | Size | `prot_size` / `bmx_psize` | XS, S, M, L, XL, XXL | Helmets 117 / 129, Gloves 29 / 80, Protection 189 / 264, Goggles 0 / 6 | reorder only |
| 3 | Age | `age` / `bmx_age` | Adult, Youth, Kids | Helmets 129 / 129, Gloves 80 / 80, Protection 264 / 264, Goggles 6 / 6 | reorder only |
| 4 | Protects | `protects` / `bmx_protects` | Helmets, Knees, Elbows, Shins, and the other body parts | Helmets 129 / 129, Goggles 6 / 6, Gloves 80 / 80, Protection 264 / 264 | reorder only |
| 5 | Helmet type | `helmet_style` / `bmx_helmet` | Full face, Half shell (skate / BMX) | Helmets 110 / 129. Goggles, Gloves, and Protection 0 | exists. Hidden on a heading that has none |
| 6 | Certification | `certification` / `bmx_cert` | CPSC, EN 1078, ASTM F2032, EN 1621 | Helmets 77 / 129, Protection 89 / 264. Goggles and Gloves 0 | reorder only |
| 7 | Rotational | `rotational` / `bmx_rotational` | MIPS, Spherical, Kineticore, SPIN | Helmets 51 / 129. The other three 0 | reorder only |
| 8 | Color | `color` / `bmx_color` | Black, White, and the rest | Helmets 96 / 129, Gloves 11 / 80, Protection 125 / 264, Goggles 1 / 6 | reorder only |

Goggles are 6 listings, all Adult, and Protects is Goggles or Goggle lenses. Size, Helmet type, Certification, and Rotational do not split that list. They stay in the shared scope; the empty fold hides them here.

### Packs (22)

No spec field has a value except Color on 2 listings. The heading stays Brand, then Color. Color is the shared `color` field, not a new key.

### What Claude still extracts

Width, Backsweep, piece count (2-piece/4-piece), Offset, Dropouts as the fork reading of `axle`, Chainstay, Bottom Bracket, Brake Mounts, Stem type and reach, Spindle, sprocket teeth, Bolt/Spline, driver teeth, rim holes, tire width plus bead, tread, and PSI, seat style, Universal on `drive_side`, broader crank lengths on `crank_length`, youth top tubes below the 18–22.5" `dans.py` keeps, scoping Material and Condition (Color stays on every heading), and per-heading order as a BMX `ORDER`. Do not add a second key when one of these fields already exists.

This PR does not change that order, and it does not add coverage chips or Kind chips above the results.

## MTB, modelled on evo

Menu headings today: Bikes, Frames, Suspension, Wheels, Tires, Drivetrain, Brakes, Cockpit, Pedals, Helmets, Goggles, Gloves, Protection, Packs.

House rule here: **Brand, then that heading's size filter, then the popular specs, Condition last.** Gender is only on Protection. evo has no frames group; Frames below is the bike list with rear travel and axle instead of fork travel and riding type.

The names are evo's, read from evo's Constructor.io browse API. The suspension heading is **Forks & Shocks** in that model and in the stored category. The page heading is **Suspension** (`sports/headings.py` renames Forks & Shocks). This PR does not rename it. Fields that already list both names keep showing under Suspension.

Coverage is `catalogs/mtb/previous_data.json` on 2026-11-21, counted after `sports.headings.heading` (stored Protection splits into Helmets, Goggles, Gloves, and Protection; stored Forks & Shocks shows as Suspension). 4,656 listings. A listing counts when `technical_specs` has a non-empty value. The page also drops listings the MTB rules reject (frame-protection kits, and anything under the minimum markdown), so its totals sit a little lower (4,603 of these 4,656). Counts will move with the next scrape.

What the page does now: each spec section gets `data-for`. All keeps Brand, Stores, Price & discount, and the deal sections. MTB has no Product kind field, so All does not keep one. Condition and Riding type have empty categories, so they hide on All and show under every heading (a heading with no values still folds that section away). Order is still the one `FIELDS` tuple, on every heading:

Condition, Motor, Suspension, Frame material, Wheel size, Suspension travel, Frame size, Tire width, Axle / spacing, Rotor diameter, Speed, Casing, Tubeless, Riding type, then Protects, Helmet type, Certification, Rotational protection, Size, Age.

Several category lists still name the stored part next to the heading (`Forks & Shocks` with `Suspension`). The menu heading is in the list, so the section shows. Claude can drop the stored name when editing scope.

Per-heading order is not in this PR. One `FIELDS` tuple cannot hold it (Ski already needed `ORDER`). Claude adds an MTB `ORDER` in `sports/mtb/facets.py` on the same shape as Ski. `sidebar()` will stamp `data-rank` from that. Until then, sections stay in the tuple order above.

Motor chips above the results are Codex task 17 (PR #302) and are not part of this list. The Motor section here is the sidebar field `power`.

### Bikes (205)

e-MTB vs Regular is the Motor field.

| # | Filter | Field | Examples | Also on | Coverage | Status |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Brand | page Brand section | shop brands | every heading | all listings | exists |
| 2 | Frame size | `frame_size` / `mtb_frame` | S, M, L, XL, and Santa Cruz S1–S6 | Frames | 184 / 205 | reorder only. This heading's size filter |
| 3 | Wheel size | `wheel_size` / `mtb_wheel` | 29, 27.5 | Frames, Forks & Shocks, Suspension, Wheels, Tires | 33 / 205 | reorder only. Thin here |
| 4 | Motor | `power` / `mtb_motor` | E-MTB, Regular | Frames | 0 / 205 | exists. Field and scope landed in #306. Empty until the next scrape |
| 5 | Suspension | `suspension` / `mtb_suspension` | the bike's suspension layout | Frames | 0 / 205 | exists. Same as Motor: #306, empty until the next scrape |
| 6 | Frame material | `frame_material` / `mtb_material` | carbon, aluminum | Frames | 0 / 205 | exists. Same as Motor: #306, empty until the next scrape |
| 7 | Fork Travel | `travel_mm` / `mtb_travel` | one number today (130, 140, 150, 160, 170). Not split into fork vs rear | Frames, Forks & Shocks, Suspension. Label today is "Suspension travel (mm)" | 32 / 205 have the mixed number | needs new data field from Claude. Split `travel_mm` into Fork Travel and Rear Travel. Do not add a third key |
| 8 | Rear Travel | `travel_mm` / `mtb_travel` | same mixed number | Frames, as Rear Travel | same 32 / 205 | needs new data field from Claude. The other half of the split |
| 9 | Riding type | `riding_type` / `mtb_ride` | enduro. The other values in the file (trail, downhill, dirt jump) are on helmets and pads | no other heading in this list. Empty categories, so every heading today | 1 / 205 | needs new data field from Claude. The key exists (7 listings in the whole file). Fill `riding_type`, do not add a second key, and scope it to Bikes |
| 10 | Condition | `condition` / `mtb_condition` | Demo | the other headings in this model that list it. Empty categories, so every heading today, including Cockpit and Packs | 18 / 205 | reorder only. Last. Claude scopes it to the headings that list it |

Drivetrain Speed is on Bikes today (14 / 205, all 12-speed) because `speed` includes Bikes. This list does not put it here. Claude should drop Bikes from `speed`.

### Frames (53)

26 of the 53 rows are frame-protection kits the page drops, and one is a time-trial module. 26 frames remain, 22 of them with a frame size. The counts below are the file, before that drop.

| # | Filter | Field | Examples | Also on | Coverage | Status |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Brand | page Brand section | shop brands | every heading | all listings | exists |
| 2 | Frame size | `frame_size` / `mtb_frame` | S, M, L, XL, S1–S6 | Bikes | 41 / 53 in the file. 22 / 26 frames the page keeps | reorder only. This heading's size filter |
| 3 | Wheel size | `wheel_size` / `mtb_wheel` | 29, 27.5 | Bikes, Forks & Shocks, Wheels, Tires | 6 / 53 | reorder only. Thin |
| 4 | Motor | `power` / `mtb_motor` | E-MTB, Regular | Bikes | 0 / 53 | exists. Empty until the next scrape, as on Bikes |
| 5 | Suspension | `suspension` / `mtb_suspension` | the frame's layout | Bikes | 0 / 53 | exists. Empty until the next scrape |
| 6 | Frame material | `frame_material` / `mtb_material` | carbon, aluminum | Bikes | 0 / 53 | exists. Empty until the next scrape |
| 7 | Rear Travel | `travel_mm` / `mtb_travel` | 150, 220 on the five frames that have the mixed number | Bikes, as one of the two travel filters | 5 / 53 | needs new data field from Claude. Rear half of the `travel_mm` split. Fork Travel is not on this heading |
| 8 | Axle Configuration | `axle` / `mtb_axle` | 12x148mm and the other spacings, on wheels today. Label today is "Axle / spacing" | Forks & Shocks, Suspension, Wheels | 0 / 53 | needs new data field from Claude. The key exists. Fill `axle` on frames, do not add a second key |
| 9 | Condition | `condition` / `mtb_condition` | Demo | see Bikes | 0 / 53 | reorder only. Last, once Claude scopes it here |

### Forks & Shocks (188)

The page calls this heading Suspension. Wheel size, travel, and axle already include both `Forks & Shocks` and `Suspension`, so they show here.

| # | Filter | Field | Examples | Also on | Coverage | Status |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Brand | page Brand section | shop brands | every heading | all listings | exists |
| 2 | Wheel size | `wheel_size` / `mtb_wheel` | 29, 27.5 | Bikes, Frames, Wheels, Tires | 16 / 188 | reorder only. Thin. This heading's size filter |
| 3 | Fork Travel | `travel_mm` / `mtb_travel` | 100–190. All 20 values are on fork-named rows. Shocks have none | Bikes, Frames, as the mixed travel number | 20 / 188 | needs new data field from Claude. Fork half of the `travel_mm` split. Rear Travel is not on this heading |
| 4 | Axle Configuration | `axle` / `mtb_axle` | 15x110mm and the other spacings, on wheels today | Frames, Wheels | 0 / 188 | needs new data field from Claude. Fill `axle`, as on Frames |
| 5 | Condition | `condition` / `mtb_condition` | Demo | see Bikes | 0 / 188 | reorder only. Last, once Claude scopes it here |

### Wheels (326)

| # | Filter | Field | Examples | Also on | Coverage | Status |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Brand | page Brand section | shop brands | every heading | all listings | exists |
| 2 | Wheel size | `wheel_size` / `mtb_wheel` | 29, 27.5, 26 | Bikes, Frames, Forks & Shocks, Tires | 132 / 326 | reorder only. This heading's size filter |
| 3 | Axle Configuration | `axle` / `mtb_axle` | 12x148mm, 15x110mm, 12x157mm, 12x142mm, 12x100mm | Frames, Forks & Shocks | 26 / 326 | reorder only. The only heading with values today. Claude still fills frames and forks on this key |
| 4 | Condition | `condition` / `mtb_condition` | Demo | see Bikes | 0 / 326 | reorder only. Last, once Claude scopes it here |

### Tires (1,009)

| # | Filter | Field | Examples | Also on | Coverage | Status |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Brand | page Brand section | shop brands | every heading | all listings | exists |
| 2 | Wheel size | `wheel_size` / `mtb_wheel` | 29, 27.5, 26 | Bikes, Frames, Forks & Shocks, Wheels | 917 / 1,009 | reorder only. Strong. This heading's size filter |
| 3 | Width | `tire_width` / `mtb_tirewidth` | 2.4, 2.5, 2.6, 2.25. Label today is "Tire width (in)" | Tires | 816 / 1,009 | reorder only |
| 4 | Casing | `casing` / `mtb_casing` | EXO, DH, EXO+, DoubleDown, Radial | Tires | 571 / 1,009 | reorder only |
| 5 | Tubeless | `tubeless` / `mtb_tubeless` | Tubeless ready | Tires | 500 / 1,009 | reorder only |
| 6 | Condition | `condition` / `mtb_condition` | Demo | see Bikes | 0 / 1,009 | reorder only. Last, once Claude scopes it here |

### Drivetrain (877)

| # | Filter | Field | Examples | Also on | Coverage | Status |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Brand | page Brand section | shop brands | every heading | all listings | exists |
| 2 | Drivetrain Speed | `speed` / `mtb_speed` | 12-speed, 11-speed, 10-speed, down to 7-speed. Label today is "Speed" | Bikes today. This list keeps it on Drivetrain only | 429 / 877 | reorder only. About half the heading. Claude drops Bikes from `speed` |
| 3 | Spindle | — | the spindle a crank states | Drivetrain | 0 | needs new data field from Claude |
| 4 | BB Interface | — | the bottom-bracket interface | Drivetrain | 0 | needs new data field from Claude. The file has bottom brackets and no interface value |
| 5 | Condition | `condition` / `mtb_condition` | Demo | see Bikes | 0 / 877 | reorder only. Last, once Claude scopes it here |

### Brakes (346)

| # | Filter | Field | Examples | Also on | Coverage | Status |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Brand | page Brand section | shop brands | every heading | all listings | exists |
| 2 | Rotor diameter | `rotor_mm` / `mtb_rotor` | 140, 160, 180, 200, 203, 220. Label today is "Rotor diameter (mm)" | Brakes | 30 / 346 | needs new data field from Claude. The key exists and is thin. Fill `rotor_mm`, do not add a second key. 10 bikes and 3 frames also store a diameter; the field does not show those because its categories are Brakes only |
| 3 | Condition | `condition` / `mtb_condition` | Demo | see Bikes | 0 / 346 | reorder only. Last, once Claude scopes it here |

### Cockpit (828)

No spec field has a value on this heading. Brand stays up. The rest is by kind, and none of those keys exist yet. Rough counts from the name and the store type, not from a spec: grips about 262, bars about 157, stems about 130, seatposts about 84, droppers about 73, saddles about 64, headsets about 58. There is no Product kind field. These rows are the filters for that kind, not an All-view type filter. Grips, plain seatposts, and headsets have no filter in this list. Condition is not on this heading.

| Kind | Filters | Status |
| --- | --- | --- |
| Bars | Width, Clamp Diameter | needs new data field from Claude |
| Stems | Length | needs new data field from Claude |
| Droppers | Diameter, travel | needs new data field from Claude |
| Saddles | Width | needs new data field from Claude |

### Pedals (216)

| # | Filter | Field | Examples | Also on | Coverage | Status |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Brand | page Brand section | shop brands | every heading | all listings | exists |
| 2 | Pedal Style | — | Platform, Clipless. Store types already say Flat and Clipless; nothing is extracted | Pedals | 0 / 216 | needs new data field from Claude |
| 3 | Condition | `condition` / `mtb_condition` | Demo | see Bikes | 0 / 216 | reorder only. Last, once Claude scopes it here |

### Helmets, Goggles, Gloves, Protection

One order for these four. The shared protection fields (`prot_size`, `helmet_style`, `rotational`, `certification`, `age`, `protects`) are scoped today to Protection, Helmets, Goggles, and Gloves. A heading with none of a field's values folds that section away.

| # | Filter | Field | Examples | Coverage | Status |
| --- | --- | --- | --- | --- | --- |
| 1 | Brand | page Brand section | shop brands | all listings | exists |
| 2 | Size | `prot_size` / `mtb_psize` | XS, S, M, L, XL, XXL | Helmets 249 / 258, Protection 204 / 224, Gloves 77 / 81, Goggles 4 / 24 | reorder only |
| 3 | Helmet type | `helmet_style` / `mtb_helmet` | Half shell (trail), Full face, Half shell (skate / BMX) | Helmets 235 / 258. Protection, Gloves, and Goggles 0 | reorder only. Hidden on a heading that has none |
| 4 | MIPS/Rotational | `rotational` / `mtb_rotational` | MIPS, Spherical, FLAD / 6D ODS, SPIN, Kineticore. Label today is "Rotational protection" | Helmets 184 / 258. The other three 0 | reorder only |
| 5 | Certification | `certification` / `mtb_cert` | CPSC, EN 1078, ASTM F1952, EN 1621 | Helmets 160 / 258, Protection 113 / 224, Goggles 13 / 24. Gloves 0 | reorder only |
| 6 | Gender | — | the gender a piece states | 0 | needs new data field from Claude. MTB has no gender field. Protection only, not the bike headings |
| 7 | Age | `age` / `mtb_age` | Adult, Youth, Kids | Helmets 258 / 258, Protection 219 / 224, Gloves 81 / 81, Goggles 24 / 24 | reorder only |
| 8 | Protects | `protects` / `mtb_protects` | Helmets, Knees, Elbows, Gloves, Goggles, and the other body parts | Helmets 258 / 258, Protection 223 / 224, Gloves 81 / 81, Goggles 24 / 24 | reorder only |
| 9 | Condition | `condition` / `mtb_condition` | Demo. The 18 demos are bikes, so these four headings are 0 today | Helmets 0 / 258, Protection 0 / 224, Gloves 0 / 81, Goggles 0 / 24 | reorder only. Last. Empty categories show it here until Claude scopes it to these headings |

### Packs (21)

No spec field has a value. The heading stays Brand. Condition is not on this heading.

### Color

One MTB color field, shared the way Skate's color sections are shared. No color key exists today (0 listings). It needs a new data field from Claude. It is not on the per-heading lists above until that field exists and Claude sets its categories. An empty category list would hide it on All and show it under every heading, the same way Condition works today.

### What Claude still extracts

Split `travel_mm` into Fork Travel and Rear Travel. Fill Axle (`axle`) on frames and forks, and Rotor diameter (`rotor_mm`). Riding type coverage, scoped to Bikes. Pedal Style (Platform / Clipless). Bar width and clamp diameter, stem length, dropper diameter and travel, saddle width. Spindle and BB interface. Gender on Protection. An MTB color field. Scope Condition to the headings that list it (not Cockpit, not Packs). Per-heading `ORDER` in `sports/mtb/facets.py`. Drop Bikes from `speed`. Do not add a second key when one of these fields already exists.

Motor, Suspension, and Frame material already exist (#306) and are scoped to Bikes and Frames. They are empty until the next scrape. This PR does not change that order, and it does not add coverage chips or Motor chips above the results.
