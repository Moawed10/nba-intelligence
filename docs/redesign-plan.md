# Product Redesign Plan

**Current visual direction (2026-11-02):** broadcast features, editorial sections and terminal data, specified with its references in [frontend.md](frontend.md#design-references). It replaces the earlier aesthetic guidance; the functional audit and data rules below still hold. Summary of the change:

- **System:** Archivo variable display type, monospaced data labels, open sections instead of cards, full-width team-colored bands, a warm ivory light theme and graphite dark theme.
- **Overview:** compact header, slim still game strip, one full-width feature (standout player, or a matchup when there is none), a two-pane schedule, an editorial ranking beside the leaders, and a quiet model and data band.
- **Player profile:** team-colored dossier hero, section links, and separated season averages, recent games and next-game forecast.
- **Predictions:** player band, game list beside the forecast; estimate, range scale, recent and season averages together; factors always visible; model version and data cutoff in a quiet line.
- **Compare, Games, Models:** split two-team hero, split broadcast scoreboards, mirrored stat rows with side-coded markers, open tables.
- **Removed:** the scrolling ticker animation, count-up on load, the reflective and spotlight card effects, and Barlow Condensed.

## Audit

| Area | Finding |
|---|---|
| Framework | Next.js 16.4 App Router with Cache Components and partial prerendering; data pages render on the server per request inside `Suspense` |
| Styling | Tailwind 4 tokens in `globals.css` (light and dark), shadcn/Radix primitives, Inter, contrast checker in CI |
| Motion | `motion` 14 (Motion for React) with `MotionConfig reducedMotion="user"`; one shared-layout nav indicator and an animated stat counter |
| Charts | Recharts 3 (keyboard accessibility layer on, honors reduced motion) |
| Data | FastAPI over PostgreSQL: 11,428 games, 219,230 player lines (2018-19 to now), schedule for 2026-27, freshness per dataset |
| Working screens | Players directory, search and full profiles (real data, E2E and live-verified) |
| Placeholder screens | Overview, Predictions, Compare, Models show a "not connected" card |
| Missing endpoints | Overview aggregates (standout lines, leaders), season averages in the directory, compare, model registry, predictions (Phase 7 inference) |
| ML | Phase 6 pipeline: 60 leakage-checked features, 4 model families per target, conformal intervals, double-double classifier, registry rows. No inference service yet |
| Auth, preferences | None; theme choice in local storage |
| Tests | pytest (backend), Vitest, Playwright with axe on 4 viewports against a synthetic stub API, live checks against the real API |

**Design resources reviewed.** Componentry, Magic UI, Aceternity and React Bits ship copy-paste Tailwind + Framer Motion components built on the `motion` package this project already uses. Patterns are adapted with the existing dependency; no new animation library is added. Componentry's site states no license on its landing page, so its code is not copied.

**Images.** NBA team logos and player headshots are NBA property, so the product uses team-color monograms and initials instead. Team colors are factual and stored in `teams.primary_color` and `secondary_color`. The owner has also asked for player photos, including former players (Phase 7B: cached by the backend on first view, initials as fallback). The owner asked for team logos in Phase 7: they will be fetched once, served from the app rather than hotlinked, and keep the monogram as fallback. The logos remain NBA trademarks, used here in a non-commercial portfolio project.

## Plan

| Phase | Work | Data dependency | Status |
|---|---|---|---|
| 1 | Audit (this document) | none | Complete |
| 2 | Design system: Geist type, refined tokens and surfaces, motion scale, team monograms, compare bar, skeletons, typed unavailable states | none | Complete |
| 3 | Shell: navigation indicator, page transitions, mobile nav | none | Complete |
| 4 | Players: directory with season averages and sorting, richer search, scouting-report profile, compare entry point | `/players` season averages (new) | Complete |
| 5 | Overview: schedule strip with date navigation, matchup panel, standout performances, leaders, model snapshot, freshness | `/overview`, `/leaders` (new) | Complete |
| 6 | Predictions: player → game → prediction workflow, interval chart, factors, history | Phase 7 inference API | Blocked: workflow and context done; forecast needs Phase 7 |
| 7 | Compare: two selectors, versus hero, comparison bars, trend overlay, URL state | `/compare/players` (new) | Complete (composed from existing endpoints; radar chart open) |
| 8 | Models: registry, evaluation dashboard, algorithm comparison, methodology | `/models` endpoints over the Phase 6 registry | Complete for evaluation records; live accuracy needs Phase 7 |
| 9 | Polish and verification on 4 viewports, both themes, reduced motion | all | Complete for current scope (4 viewports, both themes, reduced motion in E2E) |

Every number on every screen comes from an endpoint. Anything without data shows a typed state: loading, empty, no games scheduled, stale, not yet built, no trained model, backend error, rate limited, or offline.
