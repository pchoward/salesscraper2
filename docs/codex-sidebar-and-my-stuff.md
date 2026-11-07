# Codex brief: sidebar cleanup and "My stuff"

Owner request, 2026-11-07: "everything below Price at the bottom of the
sidebar has not been used, at least by me." Nothing is deleted. Rarely used
tools are folded away, and personal tools move to one menu in the header.
Read `docs/menu-wireframe.md` first. It is the map of every sport's menu,
and "change the wireframe first, then the code" applies here too: add the
sidebar order to the wireframe page when you're done.

Two parts, ideally two PRs. Part A is self-contained. Part B depends on A.

---

## Part A: sidebar ends at Price

### Today (`page.py`, sidebar built after `_section("brand", "Brand", ...)`, ~line 2483)

```
Store chips (top) · <type's spec sections> · Brand
<div class="more-filters" id="morePanel">  Price · Discount
<div class="side-group" aria-label="Deal intelligence">  Deal quality (score) · Deal Type (deals) · Drop Interval (interval)
<div class="side-group" aria-label="Personal tools">  Saved Views (views) · Watching (watching) · Bookmarks (bookmarks)
"Show results" button
```

### Wanted

```
<type's spec sections> · Brand · Store
Price & discount   <- one section: price range, then "At least __% off"
More ▸             <- one collapsed section (closed by default, remembers open/closed
                      like the other sections): Deal quality · Deal type · Price-drop window
(Saved views, Watching, Bookmarks: removed from the sidebar in Part B; until
 Part B lands, keep them at the very bottom under a "My stuff" label)
"Show results"
```

### Rules

- **Keep every state key and URL parameter exactly as is.** That covers `discount`, `discountmax`, `scoremin`, `scoremax`, the deal-type kinds (`state.kinds`), `interval` and `watching` in `decodeQuery`/`encodeQuery` (`page.js`, ~line 3290). Saved links and saved views must restore the same filters.
- **Discount inside Price:** keep both the min and max inputs (`discountMin`, `discountMax`), but show "At least __% off" first and put the max under a small "Up to" field. The dual slider can stay.
- **More** must open by itself when any filter inside it is active, whether from a link or a restored view. Otherwise a filter can be on without the user seeing it. Show a count badge on the closed header ("More · 1").
- Section open/closed memory uses `FILTER_SECTION_KEY` (`salesscraper2.filterSections`); give More its own id (`more`).
- Same on all four sports. The sport pages are built by the same `page.py` (`report.build_report_html(..., sport=...)`).
- **Mobile:** the sidebar is a drawer on phones, and "Show results" stays last.

### Tests to update or add

- `test_report_extras.py` ~line 330 asserts `data-section="views"`, `"watching"` and `"bookmarks"` exist. Update it to where they live after Part B. During Part A they still exist at the bottom.
- `test_page_layout.py` `FilterOrderTests`: the canon order includes `price`, `discount`, `score`, `deals` and `interval`. Update it to the new order. Keep the rule that brand comes first and the type's main size filter comes right after it.
- Add a browser check (pattern: `ci/check_category_navigation.cjs`):
  - Opening `?scoremin=70` shows More open with the badge.
  - A fresh visit has More closed.
  - `?discount=30` puts 30 in "At least % off".
- Run `python -m unittest` and the PR checks (`.github/workflows/pr-checks.yml`).

---

## Part B: "My stuff" menu in the header

### Where

The ShredDeals shell header is `previews/shell.html` plus `navigation/navigation.js` (source: `previews/navigation.js`, copied by `python -m previews.publish`). The catalog page runs in a frame inside the shell. Skate's page talks to the shell through `navigation/skate-bridge.js` (`postMessage` with `type: "shreddeals:..."`, same origin). Saved views, stars and the watch list live in the catalog page's `localStorage` (`salesscraper2.views`, `salesscraper2.stars`). The shell and the pages are the same origin, so the shell can read the same keys.

### Wanted

- A **My stuff** button at the top right of the header, beside search. It opens a small panel with three tabs or sections:
  1. **Saved views:** the list from `salesscraper2.views`. Tapping one opens it (same as the sidebar row does today), plus "Save current view". The page owns saving, so ask it through the bridge, as `shreddeals:save-view`.
  2. **Watching:** toggles the page's watching filter (`toggleWatching()` in the page). Also shows how many starred deals there are.
  3. **Bookmark this selection:** copies the current URL. Keep the existing behaviour.
- **Works on all four sports.** Saved views are per sport today: check the stored view's sport and only list the current sport's views, or label them by sport.
- When the panel is open, the catalog frame isn't interactive behind it on phones. Escape and outside-tap close it. Focus returns to the button.
- **Remove** the "My stuff" block from the sidebar (Part A's temporary home).
- The standalone Skate page (`sale_items_chart.html` opened without the shell) has no shell header. There, keep the three tools at the bottom of the sidebar, as Part A leaves them. Detect with the existing `window.parent === window` check in `skate-bridge.js`.

### Tests

- `previews/check_navigation.py` and `ci/check_sport_menus.cjs` patterns: open My stuff on each sport at 1440 and 390 px. Save a view, reload, and see it listed. Toggle Watching and see the page's results change. Escape closes the panel.
- `test_report_extras.py`: the sidebar no longer has `views`, `watching` and `bookmarks` when rendered inside the shell, and still has them standalone.

---

## Don't change

- **Menu headings and their order:** `sports/headings.py`, Skate `PART_ORDER` in `page.py`, and `docs/menu-wireframe.md`. Claude owns the data side.
- **Any URL parameter name, `localStorage` key, or the saved-view format.** People have saved links and views.
- **Alerts.** Skate has an alerts manager (`ALERTS_SESSION_KEY`). It isn't part of this.

Owner merges; one PR per part; green checks before asking for review.
