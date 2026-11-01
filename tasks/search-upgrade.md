# Task: Upgrade SkateDeals search

## Context
SkateDeals tracks skateboard part deals (decks, wheels, trucks, bearings) across several online shops. The current search box works well — results populate after one or two characters — but it only does plain substring matching. This task makes search typo-tolerant, skate-aware, and able to turn natural queries like `spitfire 54mm 99a under 30` into filters.

**Constraints**
- No paid or hosted AI/search services. Everything runs client-side with free, open-source libraries.
- Keep the instant-as-you-type feel. Search must stay fast at ~500 items and remain usable up to ~10,000.
- Don't break existing filters (store, type, wheel diameter, durometer, price, discount, score). Search and filters must combine.

## Before you start
1. Read the repo to find: the search box component, where the product list is loaded, the product data shape, and how existing sidebar filters are applied. Follow the existing framework, file layout, and code style.
2. If an `AGENTS.md` / `CLAUDE.md` exists, follow it. Stay within the search/UI and normalization code; don't touch scrapers unless a field needed for search is missing (if so, note it rather than changing scrapers).
3. Work on a new branch and open a PR. Keep commits per phase.

## Phase 1 — Search engine: fuzzy matching + ranking
- Replace substring matching with **MiniSearch** (preferred; Fuse.js or FlexSearch acceptable if MiniSearch doesn't fit the stack). Build the index once when data loads; rebuild only when data changes.
- Index fields with weights: `brand` (high), `model`/`name` (high), `category` (medium), `store` (low), any description/tags (low).
- Enable prefix matching and fuzzy matching (edit distance ~0.2, but **no fuzzy for terms under 3 characters** to avoid noise).
- For 1–2 character queries, rank **word-start matches above mid-word matches** (`bo` → Bones before "Combo").
- Debounce input ~100 ms.

## Phase 2 — Skate vocabulary (aliases & normalization)
- Create a data file (e.g. `search/aliases.json`) mapping aliases → canonical terms. Seed it with at least:
  - Brands: `spitty`→Spitfire, `indy`/`indys`→Independent, `oj`/`o.j.`/`ojs`→OJ, `bones`/`bonez`→Bones, `thunder`, `venture`, `ace`, `powell`/`powell peralta`.
  - Models/shapes: `f4`/`formula 4`→Formula Four, `chubbies`, `bighead`, `classic`, `conical`, `radial`, `double duro`, `hardline`, `elite`.
  - Categories: `wheel`/`wheels`, `deck`/`decks`/`board`, `truck`/`trucks`, `bearing`/`bearings`.
- Mine the existing product names to suggest additional aliases; add the obvious ones.
- Normalize both indexed text and queries: lowercase, strip punctuation (`O.J.`→`oj`), unify units (`54 mm`/`54mm`, `8.25in`/`8.25"`→`8.25`), split combined duro (`101a/95a` → both tokens).
- Aliases must be easy to edit without touching code.

## Phase 3 — Query understanding (parse queries into filters)
Write a pure, unit-tested parser: `parseQuery(text) → { filters, remainingText }`. Recognize:
| Pattern | Example | Filter |
|---|---|---|
| Wheel diameter | `54mm`, `54 mm` | diameter = 54 |
| Durometer | `99a`, `101a`, `84b`, `99d` | durometer, **normalized to A-scale** (Spitfire `d` = A-scale; `b` + 20 = A) |
| Deck width | `8.25`, `8.5 deck`, `8.25in` | deck width (only for values ~7.0–10.0) |
| Price max | `under 30`, `<30`, `<$30`, `below 30` | price ≤ 30 |
| Price min | `over 20`, `>20` | price ≥ 20 |
| Discount | `40% off`, `40%+` | discount ≥ 40 |
| Store | `tactics`, `ccs`, `zumiez`, `skate warehouse` | store |
| Category | `wheels`, `decks`, `trucks`, `bearings` | type |

- Remaining text goes to the fuzzy search.
- Parsed filters merge with sidebar filters (AND). If they conflict, the typed query wins for that search only; don't overwrite the user's sidebar selections.
- If the repo has no durometer normalization yet, put it in one shared helper used by both the parser and the durometer facet.

## Phase 4 — UX
- **Filter chips**: show parsed filters as removable chips under the search box (`54mm ×`, `99a ×`, `< $30 ×`). Removing a chip removes that token from the query.
- **Grouped autocomplete dropdown**: sections for Brands, Models, Sizes, and top Products (max ~8 rows total). Selecting a brand/size applies it as a filter.
- **Highlight** matched text in results and suggestions.
- **Keyboard**: `/` focuses search, ↑/↓ moves through suggestions, Enter selects, Esc closes.
- **URL sync**: query and filters reflected in the URL (e.g. `?q=spitfire&d=54&duro=99a&max=30`) so searches can be bookmarked/shared; loading the URL restores the state.
- **Recent searches**: last ~5 in localStorage (wrap access in try/catch; work fine without it).
- **Zero results**: show a "Did you mean …?" suggestion (closest brand/model term), then a relaxed fallback (e.g. nearest wheel sizes ±1–2mm or drop the price cap) labeled clearly as "Close matches."
- Accessible: proper labels/ARIA for the combobox and listbox.

## Tests (required)
- Unit tests for `parseQuery` covering every row in the table above, combinations (`spitfire 54mm 99a under 30`), and non-matches (`8.25` shouldn't become a price; `99` alone isn't a durometer).
- Unit tests for normalization (`O.J.`, `101a/95a`, `54 mm`, `84b`→104a, `99d`→99a).
- Search ranking tests on a small fixture set: `bo` ranks Bones first; `spitfre` finds Spitfire; `spitty bighead` finds Spitfire Bighead; `oj chubbies 54` finds OJ Chubbies 54mm.
- A quick performance check: indexing + a query on 10,000 synthetic items stays well under 100 ms per query.

## Acceptance criteria
- [ ] Typos, nicknames, and punctuation variants find the right products.
- [ ] `spitfire 54mm 99a under 30` returns only Spitfire 54mm 99a-equivalent wheels ≤ $30, with chips shown.
- [ ] Short queries still populate instantly, with sensible ranking.
- [ ] Search combines correctly with all existing sidebar filters.
- [ ] URL reflects searches and restores them on reload.
- [ ] Zero-result searches show a suggestion and/or close matches, never a dead end.
- [ ] All tests pass; no new paid services or external API calls.
- [ ] PR description summarizes changes per phase and lists any data gaps found (e.g. missing deck width or durometer fields).
