# Frontend: Design System, Accessibility & Interaction

Next.js (App Router) + TypeScript, Tailwind CSS, shadcn/ui primitives (Radix), Framer Motion, Recharts, Lucide icons, TanStack Query. Data loading per screen is specified in [api-contracts.md](api-contracts.md#screen-by-screen-data-loading). State boundaries are in [data-ownership.md](data-ownership.md#frontend-state-boundaries).

## Design references

No Apple Design Skill is installed in this environment; Apple's published Human Interface Guidelines are applied directly. Skills used: `ui-ux-pro-max` (typography, target-size guidance; its generated blue, brutalist palette was rejected because it conflicts with the product brief) and `ecc:frontend-design-direction`.

References studied on 2026-11-02, and what was taken from each:

| Reference | Taken |
|---|---|
| The Ringer | Full-bleed feature composition: one big statement beside one big image, with hard contrast between feature and page |
| NBA team and player pages | Solid team color behind a player cutout |
| Sofascore | Two-pane schedule: a compact game list beside the selected game; a list of top performances |
| Dunks & Threes | Small monospaced data labels; logos on white discs |
| react.dev | A large search pill in the header; alternating section bands instead of a grid of cards |
| Linear | Tight, heavy sentence-case headlines; restraint around the product itself |

## Design direction

One product, two registers: a premium basketball publication and a professional analytics platform sharing the same identity. **Broadcast features** run edge to edge in the real team color. **Editorial sections** are open sheets under a fine rule, led by a tight headline. **Terminal data** uses hairline grids, tabular numbers and monospaced labels. **Controls** stay Apple-like: pills, a sliding segment thumb, 44 px targets on touch.

| Principle | Rule in this product |
|---|---|
| One focal point | Every screen has one feature: a team band, a split scoreboard or a forecast block |
| Open, not boxed | Sections are not cards. `Panel` is a rule, a kicker and a headline. Small cards are reserved for discrete items |
| Team color is the photography's stage | `TeamBand` and `teamBandStyle()` set the color; text is black or white by contrast, and a band with white text only ever darkens |
| Amber is earned | Amber marks selected controls, primary actions on the page, and prediction data. Team bands use inverted buttons instead |
| Logos on team color | Always the full-color logo on a white disc (`TeamMark disc`) |
| Honest data | Historical results and forecasts are always labelled and drawn differently. No data means a specific state, never filler |
| No looping motion | Scoreboards stay still; numbers tween only when a value actually changes |

## Tokens

Defined as CSS variables on `:root` (light) and `.dark` in `src/app/globals.css`, mapped into Tailwind. Dark is the default theme. `npm run check:contrast` verifies every required pair in both themes and runs in CI.

| Token | Dark | Light | Use |
|---|---|---|---|
| `--background`, `--cell` | `#090A0C` | `#F7F3EA` (warm ivory) | Page; stat-grid cells and sticky table columns |
| `--card`, `--band-alt` | `#121417` | `#FFFFFF` | Small cards; alternate section band |
| `--popover`, `--muted` | `#1B1D21` | `#FFFFFF`, `#EFE9DC` | Elevated surface; insets and hover |
| `--stage` | `#0E0F12` | `#FFFDF8` | Scoreboard center |
| `--thumb` | `#2C2F35` | `#FFFFFF` | Selected segment |
| `--foreground` | `#F5F5F7` | `#16140F` | Primary text; actual results |
| `--muted-foreground` | `#9A9DA5` | `#5C564A` | Secondary text |
| `--border` | `#2A2D32` | `rgba(58,44,20,.16)` | Fine separators (decorative) |
| `--input` | `#6C707A` | `#8A8373` | Control boundaries (3:1 or better) |
| `--primary`, `--ring` | `#FF9500` | `#A34C00` | Actions, selection, predictions, focus |
| `--chart-2` | `#4CC3E0` | `#00707F` | Secondary series; the second side of a comparison |
| `--positive`, `--negative` | `#3ECF72`, `#FF6B63` | `#1A7A35`, `#BF2229` | Above or below, always paired with an arrow and text |

Forecasts use dashed outlines, hollow diamonds and amber; actual results use solid marks in the text color.

**Utilities** (`globals.css`): `display`, `headline`, `numeral`, `kicker`, `bleed`, `team-band`, `band-alt`, `rule-top`, `stat-grid`, `panel`, `stage`, `btn` with `btn-primary`, `btn-secondary`, `btn-on-band`, `btn-outline-band`, `field`, `material-nav`, `scroll-quiet`. `bleed` runs a section edge to edge while keeping its content on the page grid; it relies on the `@container` frame in `layout.tsx`.

**Typography:** Archivo (variable width) for display and numbers, Geist for reading and controls, Geist Mono for data labels and model versions. All statistics use tabular numerals.

| Style | Size / line height | Face |
|---|---|---|
| Player name (`display`) | `clamp(4rem, 11vw, 9.5rem)` / 0.88 | Archivo 62% width, 800, uppercase |
| Feature statistic (`numeral`) | `clamp(3.75rem, 9vw, 7.5rem)` / 0.95 | Archivo 72% width, 700, tabular |
| Page title | `clamp(3rem, 7vw, 5rem)` / 0.98 | Archivo 88% width, 800, sentence case |
| Section title (`headline`) | 30 px / 1.02 | Archivo 88% width, 800, sentence case |
| Headline | 17 / 22 | Geist 600 |
| Body | 17 / 24 | Geist 400 |
| Subhead | 15 / 20 | Geist 400 |
| Footnote | 13 / 18 | Geist 400 |
| Label (`kicker`) | 12 / 16 | Geist Mono 500, uppercase, tracked |

Sizes are in `rem`, so 200% zoom and browser text scaling work. Nothing smaller than 12 px carries information.

**Spacing:** 4, 8, 12, 16, 20, 24, 32, 48, 56, 80. **Radius:** 4, 6, 8 for small cards; 0 for bands; pills for controls. **Page width:** 84 rem. **Touch targets:** 44 × 44 px for primary controls on touch screens (`pointer-coarse`).

## Navigation and routes

| Route | Screen | Nav |
|---|---|---|
| `/` | Overview | Primary |
| `/players`, `/players/[id]` | Player Explorer, Profile | Primary |
| `/predict` | Prediction Center | Primary |
| `/compare` | Player Comparison | Primary |
| `/models` | Model Analytics | Primary |
| `/games`, `/games/[id]` | Games, Game detail | Secondary ("More") |
| `/teams/[id]` | Team roster with season stats | Reached from any team logo on a team band or scoreboard |
| `/about` | About & Methodology | Secondary ("More") |

- **≥ 768 px:** a translucent top bar with a large search pill (⌘K / Ctrl+K and `/` open it), the five primary destinations (amber underline on the current one) and a "More" menu.
- **< 768 px:** a bottom tab bar with the five primary destinations (44 px targets, labels always visible) and a top bar holding search and "More".
- The active destination uses `aria-current="page"`, a weight change and an indicator, not color alone.
- Every page sets a descriptive `<title>` ("Stephen Curry · Players · NBA Intelligence") and moves focus to its `<h1>` after client navigation.

## Motion

Framer Motion with `MotionConfig reducedMotion="user"`.

| Interaction | Default | Reduced motion |
|---|---|---|
| Page transition | 8 px rise + fade, 240 ms | Effectively instant |
| Selection, toggles | Shared-layout indicator spring (420, 38) | Effectively instant |
| Numbers | Rendered at their value on load; tween for 300 ms only when the value changes | Final value immediately |
| Chart filter change | Recharts animation | Disabled |
| Bars and hover states | 150–300 ms | Effectively instant |
| Skeletons | Pulse, sized like the content they replace | Static |
| Sheets and dialogs | Fade and scale from Radix | Fade |

No parallax, no looping motion, nothing that flashes.

## Accessible components (Phase 2 deliverables)

Built once, reused everywhere:

| Component | Behavior |
|---|---|
| `AppShell`, `TopNav`, `TabBar` | Landmarks (`header`, `nav`, `main`), skip link to main content |
| `PlayerSearch` | WAI-ARIA combobox: arrow keys, Enter, Escape, `aria-activedescendant`, 250 ms debounce, aborts stale requests, clear button, status announcement ("8 results") via a polite live region |
| `SegmentedControl` | Radio group semantics, arrow-key navigation |
| `Select`, `Dialog`, `Sheet`, `Popover`, `Tooltip` | Radix primitives: focus trap and restore, Escape closes; tooltips open on focus and tap, never hover-only |
| `StatTile` | Label, value, unit, delta with icon and text ("▲ 2.1 vs season") |
| `ChartFrame` | Title, units, generated one-sentence summary, a "Show table" toggle rendering a real `<table>`, keyboard focus over data points with a value readout |
| `DataTable` | `<table>` with `<th scope>`, sortable headers as buttons with `aria-sort`, sticky first column, labelled horizontal scroll region on mobile |
| `IntervalBar` | Point estimate and range drawn and stated in text ("27 · likely 21–34") |
| `StateView` | Shared loading skeleton, empty, error-with-retry, stale ("Updated 3 h ago") and unavailable states |
| `InfoHint` | A button that opens a popover explaining a term (MAE, interval, usage) |
| `FreshnessBadge` | "Data through Oct 27, 11:42 PM ET", from `meta.data_freshness` |

Charts never rely on color alone: actual vs predicted differ in line style and marker shape, and series carry direct labels.

## Prediction Center flow

1. **Player:** the search combobox, prefilled from `?player=`.
2. **Game:** a list of the player's upcoming games (date, opponent, home/away), as a radio group.
3. **Generate:** one primary button. It's disabled only while a request is in flight, which also prevents duplicate submissions.
4. **Results:**
   * One forecast cell per headline stat: the estimate, its "usually" range (80%), and a scale marking the last-5 and season averages as actual results.
   * A double-double probability given as both a percentage and a phrase ("about 1 in 3").
   * The model release and data cutoff.
   * The note "Assumes he plays; not a guarantee."
   * A polite live-region announcement when results arrive.
5. **Why:** the main factors are listed in plain language under the forecast, with the model version and data cutoff in a quieter line below them.

Unavailable states name the reason: not enough games this season, no active model, game already started, or a temporary error with a retry.

## Testing

- Vitest + Testing Library for components and hooks.
- `eslint-plugin-jsx-a11y` in lint.
- Playwright + `@axe-core/playwright` on every route at 375, 768, 1024 and 1440 px, plus reduced-motion and 200% zoom projects.
- Manual VoiceOver passes for the primary workflows, recorded in `docs/accessibility-report.md` (created in Phase 12 with real results).
