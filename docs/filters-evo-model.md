# Catalog filters modelled on evo

Owner, 2026-11-21. House rule on every sport: **Brand first, then that heading's size filter, then Gender, then the next most useful filters, with Condition (Demo) last** among the spec sections. evo often leads with size and puts Brand later. We keep Brand first.

This file is the order and the category scope for Claude. Field definitions and extraction stay in `sports/<sport>/facets.py` (and `sports/protection.py` where a sport shares those fields). The page does not reorder sections and does not override a field's categories.

What the page already does for Ski: each technical section gets `data-for` from the field's categories (every Ski menu heading when the category list is empty). `syncTypeSections` then hides those sections on All, and shows them once a heading is selected. Brand, Stores, Price & discount, and the deal sections (Deal quality, Deal type, Price-drop window) stay up on All. BMX and MTB sections are unmarked, so their All list is unchanged. When Claude edits a Ski field's categories, All-vs-heading visibility follows on the next page build. **Order does not.** `sports/facets.py` `sidebar()` emits `FIELDS` in tuple order, one sequence for every heading.

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

Placeholder for Claude. Same house rule: Brand, then the heading's size filter, then the next most useful filters. Dan's Comp is the model (`docs/multi-sport-plan.md` §3). The BMX fields already live in `sports/bmx/facets.py` (`wheel_size`, `kind`, hub type, toptube, drive side, and the rest). This PR does not change their order or their All list.

## MTB, modelled on evo

Placeholder for Claude. Same house rule, with evo's bike filters as the model. MTB fields already live in `sports/mtb/facets.py` (wheel size, travel, frame size, tire width, Motor, and the rest). Motor chips above the results are Codex task 17 (PR #302) and stay out of this work. This PR does not change MTB order or MTB's All list.
