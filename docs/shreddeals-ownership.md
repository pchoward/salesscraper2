# ShredDeals: who owns which files

Codex and Claude both work on this repository. To avoid editing the same
files at the same time, each area has one owner. To change a file in an area
it doesn't own, an agent asks first: in the PR, or through the user. If the
change is unavoidable, it keeps the edit small and says so in its PR.

| Area | Files | Owner |
|---|---|---|
| Homepage, sport tabs, unified header | `previews/` (`shell.html`, `navigation.js`, `navigation.css`, `skate-bridge.js`, `shreddeals.py`, `publish.py`, `sports.json`), `navigation/`, `index.html` | **Codex** |
| Catalog page UI | `page.js`, `page.css`, `mobile.css`, the markup in `page.py` | **Codex** (UI-owned) |
| Engine: sports, scraping, data, rules | `sports/`, `scraper.py`, `rebuild_page.py`, `pipeline.py`, `history.py`, `filters.py`, `stores/`, `report.py`, the data parts of `page.py` | **Claude** |
| Build, preview and CI | `ci/`, `.github/workflows/` (except the scrape workflow's delivery steps), `audit/` | **Claude** |
| Data files | `previous_data.json`, `price_history.json`, ..., `catalogs/` | written only by workflows |

## Integration points (the contract between the two)

- **Per-sport settings.** `sports/__init__.py` holds each sport's id, label,
  brand, categories (`parts`), default category, page path and data folder.
  The catalog page gets them as `SPORT_SETTINGS` (`id`, `label`,
  `defaultPart`, `parts`), but only for sports other than Skate. Codex's UI
  should read the categories and labels from there, not hard-code them.
- **Catalog pages.** Each sport's page is `<sport>/sale_items_chart.html`
  with its `history.json` beside it. Skate's stays at the root. Pages load
  the shared bridge from `../navigation/skate-bridge.js`.
- **Homepage config.** A sport's `catalog` in the homepage config points at
  its page. `previews/publish.py` takes
  `catalogs={'bmx': 'bmx/sale_items_chart.html'}`, and the preview build
  passes the sports that have listings. Production passes none yet, so the
  live homepage is unchanged.
- **Frame messages.** These are unchanged: `shreddeals:skate-url`,
  `shreddeals:back` and `shreddeals:restore`. They work for every sport's
  page.

## Claude's small edits to Codex files in the sport-engine PR

These are needed so the BMX tab can open its own page. None changes the look.

- `previews/navigation.js` and its published copy `navigation/navigation.js`:
  - any sport with a `catalog` uses the existing frame (the old code only
    allowed Skate);
  - moving between two sports' catalogs (Skate and BMX) clears the previous one's filters; a "coming soon" tab keeps them for the way back, as before;
  - swapping the frame's page uses `location.replace`, so Back doesn't stop
    on the frame.

  `skateURL` and `mergeSkateURL` still work as before; `catalogURL` is new.
- `previews/publish.py`: the optional `catalogs` argument.
- `page.js`: the default category comes from `SPORT_SETTINGS`, and
  categories and stores without a built-in short name get one made from
  their name. Skate behaves exactly as before.

## For Codex next (UI, not done here)

- **Unified header:** one PREVIEW banner instead of two (homepage plus frame).
  The header's skateboard icon and "Subscribe" and "Alert me" buttons should
  depend on the sport. BMX has no alerts yet, so it should hide them.
- **BMX spec filters** (Hub Type, Toptube Length, Drive Side...) once
  the engine provides the data (docs/multi-sport-plan.md, step 4).
