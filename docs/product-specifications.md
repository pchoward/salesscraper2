# Product specification coverage

Audited against `4979926` on main (November 1, 2026), after PR #110 merged
as `33b40eb`. This change does not redesign cards, Quick View, or search UX.

## Saved-catalog audit

The saved snapshot contains 645 eligible decks and 41 eligible wheels. There
are 48 raw wheel rows; seven fail existing filters and are excluded below.
Counts are observations, not fixed expected inventory or test assertions.

| Retailer | Missing deck width | Missing wheel diameter | Missing wheel durometer | Best existing source |
|---|---:|---:|---:|---|
| Deathgear | 34 | 0 | 0 | Squarespace variant attributes/body; existing capped deck-detail response |
| Exodus | 13 | 8 | 0 | Shopify options/variant values and `body_html` already downloaded |
| SPoT | 5 | 0 | 0 | Shared Shopify options/description/specification tables |
| Skate Warehouse | 2 | 5 | 0 | Scoped listing-card text/selects; existing deck-detail response for widths |
| CCS | 0 | 6 | 0 | Listing-card embedded `data-product` variants, size selectors, description |
| Tactics | 0 | 2 | 1 | Scoped card text/options/specification tables; absent facts remain unknown |
| TGM | 0 | 0 | 1 | Printed `80HD` manufacturer designation in title |
| Other eligible retailers | 0 | 0 | 0 | Existing title/metadata extraction |
| Total | 54 | 21 | 2 | |

Running the new parser on **only the text still present in this saved catalog**
leaves width and diameter missing counts at 54 and 21. Durometer missing counts
fall from 2 to 1 because TGM's `80HD` is now retained literally. The saved catalog
has no raw descriptions/options for the other missing rows. We did not invent
those values, re-fetch retailer pages, or run a production scrape. Future normal
scrapes can retain the source facts instead of discarding them. Existing cached
wheelbase lookups are not invalidated or expanded just to backfill widths.

The remaining Tactics Shroom Bighead listing has no durometer in its saved
payload. It stays unknown. More generally, a default variant with no size,
multiple unpaired dimensions in marketing copy, or failed optional extraction
stays unknown. Without permitted live source evidence, an absence in saved data
is **not proof that the retailer itself lacks the attribute**.

Reproduce a read-only audit (no catalog/history writes or requests):

```bash
python -m audit.specifications
python -m audit.specifications --replay-saved-text
```

## Before/after fixture replay

Eight **synthetic** fixtures cover the payload shapes and parsing paths of the
retailers above. They are regression examples, not captures proving current live
inventory specifications. Identical fixtures were replayed against base main and
this branch; all eight names, URLs, catalog sale prices, and original prices were
identical. Counts below are missing attributes before → after.

| Retailer | Deck width | Wheel diameter | Wheel durometer |
|---|---:|---:|---:|
| Exodus | 1 → 0 | 1 → 0 (52mm and 54mm, separate prices) | 1 → 0 |
| SPoT | 1 → 0 | — | — |
| Deathgear | 1 → 0 | — | — |
| Skate Warehouse | 1 → 0 | 1 → 0 (52mm and 54mm; disabled 56mm excluded) | 1 → 0 |
| CCS | — | 1 → 0 | 0 → 0 |
| Tactics | — | 1 → 0 | 1 → 0 |

Regression tests also cover fractional widths, ranges, model numbers, length/
wheelbase/contact-patch confusion, unknown and false availability, conflicting
sources, multiple widths/colors, different per-size prices and hardness, failed
optional parsing, cruiser exclusions, and unchanged price-history continuity.

## Additive schema and source rules

`product_specs.py` supplies optional fields:

- `width` / `widths`: exact inch values; the scalar exists only for one size.
- `diameter_mm` / `diameters_mm`: precise millimeters, independent of sidebar
  bands such as `52-53`. A range is not converted into individual diameters.
- `durometers`: manufacturer notation, canonical uppercase (`99A`, `101A`,
  `81B`, `99D`, `80HD`); no scale conversion or model-to-hardness inference.
- `spec_offers`: selected sale variants with variant ID, exact dimension,
  hardness, price, compare-at price, and `available` as true/false/null.
  Unknown availability is never promoted to true. Explicitly unavailable
  offers cannot advertise an eligible dimension in search.
- `spec_conflicts`: optional source conflicts/ambiguity for internal inspection.

Explicit dimension options take precedence over title facts; titles take
precedence over a single unambiguous description measurement. Conflicts between
explicit options and title facts are recorded. Color, SKU, nose/tail, wheelbase,
and wheel/contact-patch width numbers are not bare dimension sources. Invalid
optional input leaves the product intact and does not fail the retailer.

Existing per-width URLs created by the Shopify/Deathgear adapters are preserved
for history compatibility; this change creates no new listing splits or appended
names. Existing unsplit multi-width/multi-color products remain one listing with
multiple offers. Per-size prices are current observations, **not reconstructed
size-specific historical series**.

## Integration, history, and performance

The small PR #110 data adapter reads exact arrays/offer tuples instead of relying
only on wheel-title text. Diameter, hardness, availability, and typed price/
discount conditions must match the **same offer**, preventing a cheap 52mm size
from qualifying as a 54mm deal. Existing sidebar matching consumes the same
size arrays. Old catalog rows still use their previous title/scalar fallbacks.
No controls, result layout, card styling, or Quick View behavior is redesigned.

Raw hardness scales remain unchanged in catalog/history. PR #110's pre-existing
search normalization (`B + 20`, `D` treated as `A`) remains unchanged; its contract
is documented in `tasks/search-upgrade.md`. This scraper does not introduce or
assert any new manufacturer-specific equivalence. `80HD` is retained as a label,
never converted to `80A`; it remains outside the existing numeric-durometer facet
grammar. Brand/model names alone never supply a missing value.

Additive facts survive the existing history serializer. URL/name identity,
first-seen dates, price observations, lows, and name-change safeguards are
unchanged. Fresh offer observations replace old offer metadata; they do not
reset the price series. The rendering/search path uses current offer metadata,
not historical offer availability.

There are **zero new network calls**, endpoints, or request loops. Feed/card data
is already downloaded. Width extraction piggybacks on the existing wheelbase
page response, using its unchanged store eligibility, skip keys, delays,
30-day checks, and 120-page cap. It does not schedule extra pages or retry
already-checked products. No new robots policy is needed or bypassed. Extraction
is local, proportional to existing variant count, with no persistent unbounded
cache. Failed/suspicious retailer retention, miss tracking, stock confirmation,
notification delivery, and production scheduling are untouched.
