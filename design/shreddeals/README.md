# ShredDeals visual preview

Isolated design preview for the multi-sport header. It is not the live page.
`design/` is listed in `_config.yml` `exclude`, so GitHub Pages does not publish it.

Open `preview.html` in a browser. Sport and accent theme are in the query string:

- `preview.html?sport=skate&accents=utility`
- `preview.html?sport=ski&accents=sport`

The **Utility / Sport** control in the bar is preview chrome. It only sets `data-accents` on `<html>`. Do not port the control itself unless a production theme switch is wanted. The header, sport nav, and coming-soon blocks are the pieces to map onto the shared header.

## Typography

System UI, same stack as the live catalog: Segoe UI, system-ui, -apple-system, Helvetica Neue, Arial. No webfont request.

| Use | Size | Weight |
|---|---|---|
| Wordmark | 0.95rem, tracking -0.03em | 700 / 600 on “Deals” |
| Sport names | 0.8125rem | 650, not uppercase |
| Section links | 0.72rem, tracking 0.08em | 700, uppercase |
| Coming soon title | 0.92rem | 700 |
| Coming soon copy | 0.78rem | 400 |

Active and hover states change color only. Weight, padding, and border width stay put, so the bar does not shift.

## Color

Neutral base matches the live page (`--grey-900` nav, `--grey-100` canvas, `--grey-200` lines, `--blue` on chips and prices). Sport theme does not repaint those.

`html[data-accents="utility|sport"]` swaps two tokens and nothing else:

| Token | Where it is used |
|---|---|
| `--sd-accent` | Coming Soon icon, left rule, notify hover. Dark enough for an 18px icon on white. |
| `--sd-accent-bright` | Active sport underline and pill on the charcoal bar. |
| `--sd-section-accent` | Deals / Track / Insights / Subscribe underline. Fixed `#60a5fa`. Not part of the theme switch. |
| `--sd-focus` / `--sd-focus-ink` | Keyboard ring. White on the bar, `#1d4ed8` on light panels. Not part of the theme switch. |

Utility (one accent for every sport, the live blue):

| Token | Value |
|---|---|
| `--sd-accent` | `#1d4ed8` |
| `--sd-accent-bright` | `#60a5fa` |

Sport (restrained; underline, pill, and the small icon only):

| Sport | `--sd-accent` | `--sd-accent-bright` |
|---|---|---|
| Skate | `#c2410c` | `#fdba74` |
| Ski | `#0e7490` | `#67e8f9` |
| MTB | `#15803d` | `#86efac` |
| BMX | `#a21caf` | `#f0abfc` |

Other neutrals, if a later header needs the same names: `--sd-nav` `#1c2430`, `--sd-nav-text` `#f8fafc`, `--sd-nav-dim` `#cbd5e1`, `--sd-nav-faint` `#94a3b8`, `--sd-nav-raised` `#263041`, `--sd-paper` `#ffffff`, `--sd-line` `#d5dbe3`, `--sd-ink` `#1e293b`, `--sd-muted` `#526074`, `--sd-fresh` `#4ade80`.

## Navigation

Desktop is one 40px charcoal row: mark + wordmark, Skate Ski MTB BMX, then Deals Track Insights Subscribe, last scan, and the preview accent toggle.

The active sport sets `aria-current="page"`, a 2px inset underline, and an 18% tint of `--sd-accent-bright`. Hover is a light wash and full white type. `:focus-visible` is a 2px white ring inside the bar. Arrow keys, Home, and End move between sports.

On viewports at or under 800px the sports become one horizontally scrolling segmented strip (`flex: 1 0 4.75rem`, scroll-snap, edge mask). Four sports fill a 390px row; a fifth scrolls instead of wrapping or moving into a menu. Section links stay on their own row. The scan time shortens to the clock. Sports are never behind a hamburger.

## Coming soon

Ski, MTB, and BMX replace the results column with a compact panel: 18px sport icon, one title line, one sentence, and **Notify me**. The note under the button is always visible: nothing is saved and no alert is set. Activating the button repeats that it is still a placeholder. There is no form, no address field, and no request.

## Logo

`logo.svg` is the mark plus wordmark in `currentColor`. The header inlines the same two strokes so the mark inherits the bar color. The mark is a camber curve over a baseline: a deck, a ski, or a bar, not a single sport.

## Catalog slice

The block under the header copies the current Keepa-style sidebar (Brand, then deck width), product-type and store chips, toolbar, and 300px cards. Grid columns use the live rule, at most eight across. Quick View, watch, and Alert me stay on the existing hover treatment. Those rules live in the `catalog-slice` section and should not be themed with `--sd-accent`.
