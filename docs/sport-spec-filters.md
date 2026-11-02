# Per-sport specification sidebar contract

Implemented on `codex/mtb-catalog`. Claude owns BMX/Ski offer extraction; Codex owns the sidebar integration. No changes to retailer data extraction are required in `page.js` or `previews/`.

## Field ownership

Each sport owns **`sports/<id>/facets.py`**, exporting a tuple/list named `FIELDS`. The `Sport.facets` property registers that module, for example `facets="sports.bmx.facets"`. Shared rendering lives in `sports/facets.py`; browser behavior lives in `previews/sport-filters.js`.

```python
FIELDS = (
    {"key": "wheel_size", "label": "Wheel size (in)",
     "param": "bmx_wheel", "categories": ("Bikes", "Wheels", "Tires")},
)
```

- `key`: exact key within each offer's `specs`.
- `label`: visible text, including units if applicable.
- `param`: sport-prefixed URL query key; unique within the sport.
- `categories`: exact `item.part` / `Sport.parts` labels where the field applies. An empty tuple means every category. At “All”, every populated field is visible; on a category page, only its applicable fields are visible.
- Dropdown values come only from eligible offers in applicable categories. A field with no known values has no dropdown.

Current definitions:

| Sport | Offer spec key | URL key | Categories |
| --- | --- | --- | --- |
| BMX | `kind` | `bmx_kind` | All |
| BMX | `wheel_size` | `bmx_wheel` | Bikes, Frames & Forks, Wheels, Tires |
| BMX | `condition` | `bmx_condition` | All |
| Ski | `length` | `ski_length` | Skis, Poles |
| Ski | `mondo` | `ski_mondo` | Boots |
| Ski | `style` | `ski_style` | All |
| Ski | `gender` | `ski_gender` | All |

MTB's existing keys and query parameters remain in `sports/mtb/facets.py`, now with category scopes. Skate retains its existing working native spec controls and URL parameters; it has no technical-offer module configured. The shared interface is available to any future sport (or a later explicit Skate migration) without sport checks in page.py/page.js.

## Offer format for Claude

Attach `technical_offers` to the existing canonical listing; do not split products or change their URLs/history identity:

```json
{
  "part": "Boots",
  "url": "https://retailer.example/products/example",
  "technical_offers": [
    {
      "variant_id": "123",
      "price": 199.95,
      "compare": 299.95,
      "available": true,
      "specs": {"mondo": ["26.5"], "style": ["Alpine"], "gender": ["Women"]}
    }
  ]
}
```

Prices are numbers in the listing's currency. `specs` values are arrays of canonical **strings**, even numeric measurements. Use exactly the same spelling/case for a value across offers; the UI does not infer units, synonyms or compatibility. `available` is true, false, or null (unknown); missing specifications are omitted, never invented. Keep the shared parser's existing sale/availability eligibility. Unknown stock remains unknown in the listing; the sidebar never upgrades availability.

Every selected field applicable to a product must match **one eligible offer**. Sold-out offers cannot match. Unknown specifications do not match a selected applicable field. Unrelated categories remain visible, consistent with existing Skate spec filters. A length filter therefore does not hide boots; a simultaneously selected gender filter still applies to boots. Hidden category-specific selections remain in URL state for Back/Forward and become applicable again when returning to that category.

The selected offer supplies current and compare-at prices for sorting and display; the sidebar does not rewrite catalog/history data. Existing native URL history and saved-view controls own navigation. Unknown query values are discarded, query keys are sport-specific, and clear resets technical selections. Diagnostics and recipient addresses are not part of this configuration.

## Validation

`test_sport_facets.py` tests each sport's configuration, category scoping, missing facts, same-variant constraints, sold-out/unknown stock, prices, URL round trips, clear and visibility. `test_mtb_catalog.py` retains adapter/renderer coverage. `previews/check_mtb.py` checks desktop/mobile interaction with the shared module using labeled synthetic fixtures. Real BMX/Ski values will appear once Claude supplies offers; no fake specifications are backfilled into seeded catalogs.

Final validation for this update: 627 tests run, OK (one skipped); eight existing Chrome-dependent tests unavailable. Separate synthetic Firefox desktop/mobile review passed. No production data or notifications were changed.
