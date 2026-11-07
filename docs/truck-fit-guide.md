# Truck deck-fit guide

The Fits deck UI uses the Independent and Ace table supplied by the owner in the
2026-11-07 task discussion, plus the Ace AF1 80 image (10-inch axle, 188 mm hanger)
and the owner's subsequent **9.75-inch and wider** guidance. This reference was
provided after manufacturer chart access was unavailable in this environment.
It is owner-provided reference data, not an independently verified manufacturer
recommendation. The exact mapping is in `truck_fit.py:TRUCK_SIZES`.

## Interpretation

- Use the supplied **ideal** interval for the primary fit chips. Retain the
  separately supplied maximum interval for Quick View. Do not manufacture an
  ideal interval from an axle width.
- Independent Stage 4 146 has only a maximum interval; show and label that fact.
- Ace AF1 80 has neither a supplied ideal nor a maximum interval. Store its
  owner-approved 9.75+ guidance separately. Put it in the broad **9.5+** group,
  while cards and Quick View show **owner guidance 9.75+**.
- Preserve the owner table's Classic 22 / Low 02 ideal-versus-maximum discrepancy
  and AF1 55's 8.675 upper ideal bound. These need source confirmation before
  changing the reference. They are not silently rounded or swapped.
- Stage 4 and Stage 11, and Ace Classic and AF1, are separate families. An
  unspecified family can share a mapping only when multiple listed families
  explicitly have identical dimensions. A lone known family is insufficient.
- Venture, Thunder, Krux, Royal, Tensor and Slappy retain parsed native/printed
  sizes but have no inferred fit until a reference is supplied. Printed inch
  values cross-check mapped axle widths; conflicting values remove the fit.
- Sizes below 7.75 remain accessible through All or their native brand size.
  The broad 9.5+ group includes ranges that begin above 9.5; inspect exact fit.

## Variants and compatibility

`spec_offers` is authoritative when present. Never fill a missing variant size
from the product title. A match must satisfy fit, native size, availability,
price and discount together on one offer. Explicitly sold-out offers cannot
match; unknown availability remains unknown. Selected variants without list
prices show no claimed discount. Existing history remains listing-level and
Quick View retains its existing selected-variant history explanation.

`trucksize` keeps its previous exact title-token behavior. New `truckfit` and
`trucknative` parameters are independent; native keys include the brand
(`ace:66`, `independent:166`). No localStorage keys or saved-view object shape
change. Stored product/history files and extraction code are unchanged.

## Coverage on the saved catalog

The 77 truck listings on the task's baseline have **55 legacy size tokens**.
The new parser retains **57 native or printed sizes**, including previously
missed Stage 4 166; **29 listings have a referenced deck-fit band**. The other
listings remain accessible without a deck-fit filter. Twenty names still lack a
usable size; variant feeds may improve that coverage after normal scrapes.
No scrape was run to manufacture coverage for this change.

## Regression checks

`test_truck_fit.py` exercises mapping, family ambiguity, AF1 80 provenance,
legacy/new URLs and generated metadata, and runs `test/truck-fit.test.cjs` for
same-offer matching and typed searches. `ci/build_truck_fixtures.py` creates an
isolated labeled preview and `ci/check_truck_fit.cjs` checks zero results,
selected prices, native sizes, Quick View, Back/Forward and overflow at 1440,
390 and 320 pixels. Existing parser expectations remain exact.
