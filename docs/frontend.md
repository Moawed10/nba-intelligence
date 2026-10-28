# Frontend: Design System, Accessibility & Interaction

Next.js (App Router) + TypeScript, Tailwind CSS, shadcn/ui primitives (Radix), Framer Motion, Recharts, Lucide icons, TanStack Query. Data loading per screen is specified in [api-contracts.md](api-contracts.md#screen-by-screen-data-loading). State boundaries are in [data-ownership.md](data-ownership.md#frontend-state-boundaries).

## Apple Design Skill

No Apple Design Skill is installed in this environment, and a search of the available skill catalog on 2026-10-28 found none. The design below applies Apple's published Human Interface Guidelines principles directly. It does not claim to use a skill.

To enable one later: if you have the skill's folder (a `SKILL.md` with its references), place it at `~/.claude/skills/<skill-name>/SKILL.md`, or install the plugin that ships it from the Claude app's plugin settings. It will then appear in the skills list, and Phase 2 onward will invoke it. Until then, these installed skills support the same work: `ecc:frontend-design-direction`, `ecc:design-system`, `ecc:motion-foundations`, `ecc:accessibility`, `ecc:frontend-a11y`.

## Design direction

The product should feel like a native Apple app built for analysts: calm surfaces, strong typographic hierarchy, data in front, chrome receding. Its own identity comes from a single court-amber signal color and a broadcast-style number treatment, not from imitating Apple Sports.

Principles, each with a concrete rule:

| Principle | Rule in this product |
|---|---|
| Clarity | Every screen leads with one headline number set (PTS / REB / AST) before any secondary metric |
| Deference | No decorative gradients, glows or illustrations; color is reserved for data and state |
| Depth | Three surface levels plus translucent material only for the navigation bar and sheets |
| Consistency | One spacing scale, one radius scale, one chart frame component, one stat-tile component |
| Precision | 4 pt grid, tabular numerals, numbers right-aligned in tables, one decimal max for averages |
| Simplicity | Progressive disclosure: advanced splits and full logs behind tabs or expanders |
| Delight | Spring-based selection feedback, counters that animate only when a value changes, chart morphs between filters |

## Tokens

Defined as CSS variables on `:root` (light) and `[data-theme="dark"]` / `prefers-color-scheme: dark`, mapped into Tailwind. Dark is the default theme. Text tokens must pass the contrast checks in Phase 2 before use; the ratios below are targets to verify, not measurements.

| Token | Dark | Light | Use |
|---|---|---|---|
| `--bg` | `#000000` | `#F2F2F7` | Page |
| `--surface-1` | `#1C1C1E` | `#FFFFFF` | Cards, tables |
| `--surface-2` | `#2C2C2E` | `#F2F2F7` | Inset controls, hover |
| `--separator` | `rgba(84,84,88,0.65)` | `rgba(60,60,67,0.29)` | Hairlines |
| `--label` | `#FFFFFF` | `#000000` | Primary text |
| `--label-2` | `rgba(235,235,245,0.70)` | `rgba(60,60,67,0.75)` | Secondary text (≥ 4.5:1 target) |
| `--accent` | `#FF9F0A` | `#C25E00` | Interactive, predictions, focus ring |
| `--positive` / `--negative` | `#30D158` / `#FF453A` | `#1A7F37` / `#C9252D` | Above/below average, always paired with ▲/▼ and text |
| `--actual` | `--label` | `--label` | Actual results: solid line, filled markers |
| `--predicted` | `--accent` | `--accent` | Predictions: dashed line, hollow markers, interval band at 20% opacity |

Apple's tertiary label color (30% white) is not used for text: it fails 4.5:1. Team colors appear only in the player header strip and team chips, never as the only carrier of meaning, and with a contrast check on any text placed over them.

**Typography:** `font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Inter", system-ui, sans-serif`. SF Pro renders through the system stack on Apple devices; it is not self-hosted, because its license does not permit web embedding. Inter (via `next/font`) covers other platforms. All statistics use `font-variant-numeric: tabular-nums`.

| Style | Size / line height | Weight |
|---|---|---|
| Large title | 34 / 41 | 700 |
| Title 1 | 28 / 34 | 700 |
| Title 2 | 22 / 28 | 600 |
| Headline | 17 / 22 | 600 |
| Body | 17 / 24 | 400 |
| Subhead | 15 / 20 | 400 |
| Footnote | 13 / 18 | 400 |
| Stat display | 44 / 48 | 600, tabular, tracking −0.02em |

Sizes are in `rem`, so 200% zoom and browser text scaling work. Nothing smaller than 13 px carries essential information.

**Spacing:** 4, 8, 12, 16, 20, 24, 32, 48. **Radius:** 8 (chips), 12 (controls), 16 (cards), 24 (sheets). **Touch targets:** 44 × 44 px minimum for all primary controls.

## Navigation and routes

| Route | Screen | Nav |
|---|---|---|
| `/` | Overview | Primary |
| `/players`, `/players/[id]` | Player Explorer, Profile | Primary |
| `/predict` | Prediction Center | Primary |
| `/compare` | Player Comparison | Primary |
| `/models` | Model Analytics | Primary |
| `/games`, `/games/[id]` | Games, Game detail | Secondary ("More") |
| `/about` | About & Methodology | Secondary ("More") |

- **≥ 768 px:** a translucent top bar with the five primary destinations, a "More" menu, and global player search (⌘K / Ctrl+K and `/` focus it).
- **< 768 px:** a bottom tab bar with the five primary destinations (44 px targets, labels always visible) and a top bar holding search and "More".
- The active destination uses `aria-current="page"`, a weight change and an indicator, not color alone.
- Every page sets a descriptive `<title>` ("Stephen Curry · Players · NBA Intelligence") and moves focus to its `<h1>` after client navigation.

## Motion

Framer Motion with `MotionConfig reducedMotion="user"`.

| Interaction | Default | Reduced motion |
|---|---|---|
| Page transition | 8 px rise + fade, spring (stiffness 300, damping 30) | 120 ms fade only |
| Selection, toggles | Shared-layout indicator spring (400, 40) | Instant |
| Stat counters | Count from previous to new value over ≤ 400 ms, only on change | Final value immediately |
| Chart filter change | Recharts animation 300 ms | Disabled |
| Skeletons | Shimmer | Static |
| Sheets and dialogs | Spring from the edge | Fade |

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
   * One `StatTile` per stat, showing the prediction, its "likely range (80%)", and the last-5 and season averages for context.
   * A double-double probability given as both a percentage and a phrase ("about 1 in 3").
   * The model release and data cutoff.
   * The note "Assumes he plays; not a guarantee."
   * A polite live-region announcement when results arrive.
5. **Why:** an expandable explanation panel lists the top factors in plain language.

Unavailable states name the reason: not enough games this season, no active model, game already started, or a temporary error with a retry.

## Testing

- Vitest + Testing Library for components and hooks.
- `eslint-plugin-jsx-a11y` in lint.
- Playwright + `@axe-core/playwright` on every route at 375, 768, 1024 and 1440 px, plus reduced-motion and 200% zoom projects.
- Manual VoiceOver passes for the primary workflows, recorded in `docs/accessibility-report.md` (created in Phase 12 with real results).
