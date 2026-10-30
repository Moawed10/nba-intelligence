# Accessibility report

Phase 12 audit, 2026-10-29/30. Everything below comes from automated runs against the production build (`next build` + the E2E stub API) or from reading the accessibility tree; nothing here is estimated. What could not be verified by tooling is listed as such at the end.

**How to reproduce:** `cd frontend && CI=1 npx playwright test tests/e2e/a11y-audit.spec.ts` (writes `test-results/a11y-audit/<project>-<worker>.json`), and `npm run check:contrast`.

## Scope

15 routes and states, each at four viewports (1440, 1024, 768 and 375 px) and in both themes:

| Page | State |
|---|---|
| `/` | Overview with a game day, a score prediction and player shortcuts |
| `/players` | Directory |
| `/players/1000` | Active player: averages, trend, splits, game log, career |
| `/players/1990` | Former player: career only |
| `/predict` | Start (search and scoring leaders) |
| `/predict?player=1000` | Forecast, game list, range chart, head-to-head |
| `/compare` | Empty |
| `/compare?p1=1000&p2=1001` | Two players: head to head, strengths radar, form |
| `/models` | Release, accuracy, algorithms, ranges, prediction check, history |
| `/games?date=2099-11-09` | Final game with full box scores |
| `/games?date=2099-11-10` | Upcoming game with a score prediction |
| `/games/0099000102` | Game page, upcoming |
| `/games/0099000101` | Game page, final |
| `/about` | About |
| `/players/424242` | Not found |

## Results

### WCAG 2.2 AA (axe-core, tags wcag2a, wcag2aa, wcag21a, wcag21aa, wcag22aa)

| Impact | Violations |
|---|---|
| Critical | 0 |
| Serious | 0 |
| Moderate | 0 |
| Minor | 0 |

That is 0 violations of any impact in 118 recorded page × viewport × theme runs, covering all 15 pages in both themes. The two runs missing from the 120 are one viewport of `/games/0099000102`. It was interrupted when another session's test run stopped the shared test servers; the same page passed at the other three viewports and in the final full-suite run.

### Keyboard

On every page, 60 presses of Tab from the top, at 1440, 1024 and 768 px. The check fails if focus stays on one element for three presses (a trap), or if a focused element shows no outline or ring.

| Page | Distinct focus stops | Without a visible indicator | Traps |
|---|---|---|---|
| `/` | 36 | 0 | 0 |
| `/players` | 50 | 0 | 0 |
| `/players/1000` | 33 | 0 | 0 |
| `/players/1990` | 25 | 0 | 0 |
| `/predict` | 19 | 0 | 0 |
| `/predict?player=1000` | 16 | 0 | 0 |
| `/compare` | 14 | 0 | 0 |
| `/compare?p1=1000&p2=1001` | 27 | 0 | 0 |
| `/models` | 39 (27 below 1280 px, where the section rail is hidden) | 0 | 0 |
| `/games?date=2099-11-09` | 26 | 0 | 0 |
| `/games?date=2099-11-10` | 20 | 0 | 0 |
| `/games/0099000102` | 17 | 0 | 0 |
| `/games/0099000101` | 23 | 0 | 0 |
| `/about` | 11 | 0 | 0 |
| `/players/424242` | 11 | 0 | 0 |

The primary workflows are also covered end to end with keys only:
- **Predictions:** search → game → statistic → explanation (`predict.spec.ts`, passed 200/200 repeated runs in Phase 8).
- **Compare:** search, swap and remove.
- **Games:** day navigation, game selection and the game page.
- **Shell:** skip link, More menu with Escape restoring focus.

### Zoom and reflow

Every page was loaded at 640 px (what a 1280 px window shows at 200% zoom) and at 320 px (WCAG reflow), at three desktop viewports. Across all 90 runs, horizontal overflow was 0 px; tables and the game strip scroll inside their own labelled regions.

### Contrast (`npm run check:contrast`)

All 46 pairs pass, 23 per theme:
- **Text, 4.5:1:** foreground and muted text on page, card, popover and muted surfaces; primary text; status colors.
- **Non-text, 3:1:** focus ring on page and card; all five chart colors on cards; the selected segment on its track; the primary color behind highlighted options; text-field and control boundaries.

### Charts and graphics

| Graphic | Text alternative |
|---|---|
| Player trend (profile) | `ChartFrame`: title, units, one-sentence summary, table view |
| Compare form, strengths radar | `ChartFrame` with table view; the radar table lists each percentile and the season value behind it |
| Models: predicted vs actual, misses, range hit rate | `ChartFrame` with table view |
| Forecast vs last 20 games (Predictions) | `role="img"` with a description; the finding is in visible text next to it |
| Win-chance bar | `role="img"` labelled with both percentages, also shown as text |
| Interval bars | `role="img"` labelled with the prediction and range |

### Reduced motion

`shell.spec.ts` › "reduced motion" emulates `prefers-reduced-motion: reduce` and checks that transitions are effectively disabled; it passes. CountUp, the radar and list animations, and section scrolling use the reduced-motion setting.

## Fixes made in this audit

1. **Focus on the game list (Predictions).** The list's focus ring was drawn on its container, not on the focused listbox. It is now drawn on the listbox itself (`components/bits/animated-list.css`).
2. **Focus on the Models section rail.** The section and item buttons had `outline: none` and no replacement; they now show a 2 px ring on keyboard focus (`components/bits/branched-menu.css`).
3. **Text-field and control boundaries.**
   - Inputs, selects and outline buttons used the decorative border color: 1.42:1 in light, 1.34:1 in dark.
   - They now use their own `--input` token: 3.44:1 / 3.08:1 in light (card / page) and 3.72:1 / 4.00:1 in dark (`app/globals.css`).
   - The contrast check now covers it, plus `chart-1`, muted text on popovers and the selected segment.
4. **Heading structure.** Charts inside a panel were announced at the same heading level as the panel. `ChartFrame` takes a heading level, and the five nested charts on Models and Compare are now level 3.
5. **Screen-reader wording on Predictions.**
   - The player card's `pts / reb / ast` labels are read as "Points per game" and so on.
   - The duplicate "Predicted" tag above the game list is hidden from screen readers.
   - The range chart's description no longer repeats the visible summary word for word.

## Accessibility-tree review (not VoiceOver)

The ARIA snapshots of six primary screens were read in full: Overview, player profile, Predictions with a forecast, Compare with two players, Models, and an upcoming game page.
- Every button, link, combobox, listbox, radio group, table and image had a name.
- Selected and pressed states were exposed, and sortable columns announce their full meaning (for example "PTS, Points per game").
- Panels are labelled regions with headings.

The issues found are fixed above (items 4 and 5). One minor point remains: the game page goes from its level-1 title to the level-3 "Our prediction" heading, because the matchup component is shared with the schedule panel, where those headings sit under a level-2 panel title.

## Not verified

- **VoiceOver.** No one listened to the screens with VoiceOver (or NVDA/JAWS). The accessibility-tree review above checks what a screen reader would receive, not how it sounds in practice. Both "VoiceOver pass" and "Manual screen-reader testing" stay open until a person does that pass.
- **Browser zoom.** 200% zoom was tested as the equivalent 640 px layout, not by zooming a real browser.
- **Touch-target size.** It was not measured separately; controls use 36–44 px minimum heights.

## Timing note

The full E2E suite was also run during this audit. Two runs of the forecast render-time test failed while the machine was loaded (load average about 20) and another session's tests shared the same ports. Run alone, the same test passes at every viewport (p95 105–118 ms against a 500 ms limit). In the final full run (441 passed), the Compare chart/table toggle timing test failed once at 768 px with the load average at 28. Alone it passes at every viewport (p95 106–154 ms against 200 ms). Neither timing test touches anything changed in this audit.
