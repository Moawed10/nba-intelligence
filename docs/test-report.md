# Test Report

Recorded test evidence. Each entry lists the exact command, environment and result. Status claims in [implementation-status.md](implementation-status.md) cite this file.

## Environment (2026-10-28)

| Component | Version |
|---|---|
| OS | macOS (Darwin 27.0.0, arm64) |
| Python | 3.12.15 (`backend/.venv`) |
| PostgreSQL | 16.15 (Homebrew) |
| Node.js | 25.9.0 |
| Next.js / React | 16.4.3 / 19.3 |
| Playwright / Chromium | 1.64.1 |

CI (`.github/workflows/ci.yml`) runs the same suites on Ubuntu with Python 3.12, Node 24 and a `postgres:16` service. CI has **not run yet**, because the repository has no GitHub remote.

## Backend

### Unit, integration and migration tests

```bash
cd backend && NBA_LOG_LEVEL=ERROR .venv/bin/pytest -q --cov=app --cov-report=term
```

**Result:** 88 passed, 0 failed, 0 skipped, in 5.4 s. Statement coverage is 83% overall:

| Module | Coverage |
|---|---|
| `app/ingestion/client.py` | 97% |
| `app/ingestion/jobs.py` | 88% |
| `app/ingestion/transforms.py` | 82% |
| `app/ingestion/writer.py` | 92% |
| `app/ingestion/lifecycle.py` | 100% |
| `app/sync/worker.py` | 87% |
| `app/sync/freshness.py` | 98% |
| `app/models/*` | 100% |

`app/cli.py`, `app/db.py` and `app/logging.py` are exercised by the live runs below, not by tests.

What the suites cover:

| File | Covers |
|---|---|
| `tests/unit/test_client.py` | Retryable vs non-retryable failures, `Retry-After`, 5-attempt cap, throttling, cache only after a valid parse |
| `tests/unit/test_transforms.py` | Box-score validation rules, neutral-site resolution, unfinished games, team-minutes check, schedule filtering, New York season boundary |
| `tests/unit/test_lifecycle.py` | Every allowed and forbidden status transition; final is never downgraded |
| `tests/unit/test_freshness.py` | Fresh / aging / stale / unavailable thresholds |
| `tests/integration/test_ingestion.py` | Three identical runs leave no duplicates, corrections logged, partial-response guard, rollback on failure, advisory-lock exclusion, run status recording, lifecycle events |
| `tests/integration/test_sync.py` | Due-job scheduling, persisted schedules across restart, live-window polling, box-score finalization, historical games finalized without events, outbox drain, abandoned-run recovery, failure retried next cycle, freshness from runs |
| `tests/integration/test_migrations.py` | Models match migrations; downgrade to base and upgrade round trip |

All fixtures are synthetic: season 2099, team ids 1–3.

### Lint and format

```bash
cd backend && .venv/bin/ruff check app tests && .venv/bin/ruff format --check app tests
```

**Result:** all checks passed; 33 files formatted.

### Live ingestion against stats.nba.com

```bash
cd backend && .venv/bin/python -m app.cli ingest backfill --from 2018 --to 2026
```

**Result:** exit 0 in 190.9 s, with 0 retries. 0 player or team box-score lines were rejected in any season. 6 schedule rows were rejected for 2026-27, all NBA Cup knockout games whose teams aren't decided yet.

```bash
cd backend && .venv/bin/python -m app.cli integrity
```

**Result:** 0 orphan player lines, 0 orphan team lines, 0 final games without two team lines, 0 score mismatches, 0 player-point totals differing from team points, 0 duplicate player lines.

| Season | Final games (reg / play-in / playoffs) | Player lines | Completeness |
|---|---|---|---|
| 2018-19 | 1230 / – / 82 | 27,862 | 100% |
| 2019-20 | 1059 / 1 / 83 | 24,105 | 100% |
| 2020-21 | 1080 / 6 / 85 | 25,054 | 100% |
| 2021-22 | 1230 / 6 / 87 | 28,050 | 100% |
| 2022-23 | 1230 / 6 / 84 | 27,740 | 100% |
| 2023-24 | 1230 / 6 / 82 | 28,206 | 100% |
| 2024-25 | 1230 / 6 / 84 | 28,240 | 100% |
| 2025-26 | 1230 / 6 / 85 | 28,698 | 100% |
| 2026-27 (in progress) | 56 final, 1,144 scheduled | 1,275 | 100% of final games |

Totals: 11,428 games, 20,568 team lines, 219,230 player lines, 5,197 players. Across all succeeded game-log runs, 364,110 of 364,238 fetched rows passed validation (99.96%). All 128 non-valid rows came from one run before the neutral-site fix: 118 player lines and 10 team lines from 5 games. After the fix, every valid row is stored.

**Duplicate gate:** `ingest season --season 2025` was run three times. Runs 2 and 3 inserted and updated 0 rows. Row counts before and after were identical: 11,428 / 20,568 / 219,230 / 5,197.

```bash
cd backend && .venv/bin/python -m app.cli sync-once   # twice
```

**Result:**
- First pass: `schedule`, `game_logs`, `metadata` and `corrections` all succeeded.
- Second pass: no jobs due, because the schedules were persisted.

This run found a defect: it emitted 10,284 finalization events for historical games. It was fixed in `app/sync/worker.py` and covered by `test_historical_games_finalize_without_events`; the spurious dev rows were removed.

## Frontend

```bash
cd frontend && npm run lint && npm run typecheck && npm run check:contrast
```

**Result:** ESLint (including the full jsx-a11y recommended set) and TypeScript are clean. All 34 contrast pairs pass WCAG AA (17 per theme).

```bash
cd frontend && npx vitest run --coverage
```

**Result:** 20 passed in 3 files. Statement coverage is 82.78% across `src/lib` and `src/components/data`.

```bash
cd frontend && npx playwright test
```

**Result:** 50 passed and 2 skipped (keyboard-only tests on the touch project) across 4 viewport projects (375, 768, 1024, 1440 px). It covers:
- every route returns 200 with one `h1` and the correct title;
- axe-core WCAG 2.0/2.1/2.2 A and AA scans in dark and light themes, with 0 critical or serious violations;
- no horizontal overflow at each viewport or at 320 px;
- every primary destination is reachable, with `aria-current`;
- mobile tab targets are at least 44×44 px;
- skip link, More menu keyboard use with Escape focus return, and focus on the new page's heading;
- theme persistence across reload;
- reduced-motion transitions are disabled.

Defects found and fixed while writing these tests:
- After navigating from the More menu, focus returned to the menu button instead of the new page's heading.
- Headings got `tabindex` at runtime, which caused a React hydration mismatch.
- Light-theme amber on the page background measured 4.50:1, so it was darkened to `#a84f00`.
