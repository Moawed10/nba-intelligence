# Test Report

Recorded test evidence. Entries are historical: each records what was true on the date and commit it names, and later code may differ. Each entry lists the exact command, environment and result. Status claims in [implementation-status.md](implementation-status.md) cite this file.

## Environment (2026-10-28)

| Component | Version |
|---|---|
| OS | macOS (Darwin 27.0.0, arm64) |
| Python | 3.12.15 (`backend/.venv`) |
| PostgreSQL | 16.15 (Homebrew) |
| Node.js | 25.9.0 |
| Next.js / React | 16.4.3 / 19.3 |
| Playwright / Chromium | 1.64.1 |

CI (`.github/workflows/ci.yml`) runs the same suites on Ubuntu with Python 3.12, Node 24 and a `postgres:16` service. (Historical note, 2026-10-28: at that date the repository had no GitHub remote and CI had not run. It has run since; see [Release readiness](#release-readiness-baseline-2026-11-02).)

## Backend

### Unit, integration and migration tests

```bash
cd backend && NBA_LOG_LEVEL=ERROR .venv/bin/pytest -q --cov=app --cov-report=term
```

**Result (Phase 3):** 88 passed, 0 failed, 0 skipped, in 5.4 s. Statement coverage is 83% overall. Phase 4 results are [below](#phase-4-read-api).

Phase 3 coverage:

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

## Phase 4 read API

```bash
cd backend && NBA_LOG_LEVEL=ERROR .venv/bin/pytest -q --cov=app --cov-report=term
```

**Result:** 171 passed, 0 failed, 0 skipped. Statement coverage is 92% overall: `app/api` 95–100%, `app/services` 98–100%, `app/stats` 100%, `app/schemas` 100%. Ruff check and format are clean.

| File | Covers |
|---|---|
| `tests/api/test_players.py` | Directory filters, sorting, pagination; accent-insensitive search and literal wildcards; profile, season stats and splits, game log, trends; 404 and invalid-input cases |
| `tests/api/test_teams_games.py` | Teams, records, pace and ratings from the shared definitions; null (not zero) values without games; games window, filters, upcoming, detail, box score, 409 before final |
| `tests/api/test_system.py` | Every endpoint in OpenAPI and read-only; health, readiness, database outage as 503 without internals; data-status counts; request ids; 500 hides details |
| `tests/api/test_queries.py` | Query counts constant across page sizes; box score ≤ 4 queries; cache hits skip the database until `data_version` changes |
| `tests/unit/test_stats.py` | Every statistic definition against hand-computed values |
| `tests/unit/test_cache.py`, `test_openapi.py` | Memo TTL, versioned keys, disabled cache; committed OpenAPI schema matches the app |

API fixtures load synthetic season 2099 through the real ingestion pipeline.

### Latency benchmark

```bash
cd backend && .venv/bin/uvicorn --factory app.main:build --port 8765 &
.venv/bin/python scripts/benchmark.py --base-url http://127.0.0.1:8765
```

Workload: 1,000 requests per scenario from 20 concurrent clients against one uvicorn process on an Apple M2 (8 cores), local PostgreSQL 16 holding the full dataset. Profile and game-log requests draw from 200 active players (seed 7); search draws from 30 name fragments. The uncached run sets `NBA_API_CACHE_ENABLED=false`.

| Scenario | p50 | p95 | p99 | Errors | Gate (p95) |
|---|---|---|---|---|---|
| Player search, uncached | 17.1 ms | 38.0 ms | 47.5 ms | 0 | < 300 ms |
| Player search, cached | 12.3 ms | 32.7 ms | 45.8 ms | 0 | |
| Player profile, uncached | 43.9 ms | 74.9 ms | 95.6 ms | 0 | < 500 ms |
| Player profile, cached | 15.8 ms | 47.9 ms | 66.5 ms | 0 | |
| Game log (never cached) | 58.4 ms | 102.0 ms | 119.4 ms | 0 | < 700 ms |

These are local numbers; a hosted database adds network latency, so the gates are re-measured in Phase 15.

## Frontend

```bash
cd frontend && npm run lint && npm run typecheck && npm run check:contrast
```

**Result:** ESLint (including the full jsx-a11y recommended set) and TypeScript are clean. All 36 contrast pairs pass WCAG AA (18 per theme), including the highlighted-option color against popovers.

```bash
cd frontend && npx vitest run --coverage
```

**Result:** 27 passed in 4 files, including 7 `PlayerSearch` tests (debounce, request, keyboard and pointer selection, Escape, empty and error states). Statement coverage is 88.26% across `src/lib` and `src/components/data`.

```bash
cd frontend && npx playwright test
```

**Result:** 57 passed and 3 skipped (keyboard-only tests on the touch project) across 4 viewport projects (375, 768, 1024, 1440 px). `tests/e2e/player-search.spec.ts` stubs the search endpoint with synthetic results and runs axe while the listbox is open. It covers:
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

## Phase 5 player explorer and profile

### Unit and end-to-end

```bash
cd frontend && npx vitest run --coverage && npx playwright test
```

**Result:** 38 unit tests passed (88.23% statement coverage). Playwright: 109 passed, 3 skipped (keyboard-only tests on the touch project). Server-rendered pages read from `tests/e2e/stub-api.mjs`, a synthetic API (season 2099-00, teams Alpha and Bravo) that Playwright starts next to an isolated build in `.next-e2e`.

`tests/e2e/players.spec.ts` covers: server-rendered first page and pagination; team, position and former-player filters in the URL and after reload; empty state with "Clear filters"; search to profile with focus on the new heading; profile values equal to the API response; stat and season selectors; chart table view; keyboard-opened splits; game-log pagination; a player with no games; not-found; a 503 shown as plain language; axe in both themes; no overflow.

### Live checks against the real dataset

```bash
cd backend && .venv/bin/uvicorn --factory app.main:build --port 8000 &
cd frontend && npx playwright test -c playwright.live.config.ts
```

| Check | Result |
|---|---|
| 100 documented search queries (`tests/live/search-queries.json`) with the intended player in the top 3 | 100 / 100 |
| Last keystroke to visible results, 25 queries typed at 40 ms per key | p50 329 ms, p95 336 ms (250 ms debounce included); 1 request per query |
| Profile tiles equal to `GET /players/{id}/stats` for 25 active players | 175 / 175 values |

The query set is regenerated with `backend/scripts/search_queries.py`: the 100 active players with the most games since 2018-19, as 40 accent-free full names, 30 full names missing one letter of the last name, and 30 unique last names.

### CI

The first CI runs on GitHub found two problems that local runs missed: the type-check needed Next.js route types generated first, and the top bar overflowed by 8–15 px at 768 px with Linux font metrics. Both are fixed, and an E2E check now requires at least 24 px of spare room in the top bar.

## Phase 6 machine learning pipeline

### Tests

```bash
cd backend && NBA_LOG_LEVEL=ERROR .venv/bin/pytest -q --cov=app
```

**Result:** 197 passed, 0 failed (93% statement coverage; `app/ml` 94–100%). ML tests use a synthetic league (seasons 2090–2093) and cover:

- rolling features equal independently computed means of previous games;
- perturbing every statistic on or after a date leaves all 60 features for that date unchanged;
- every joined history predates its target game, and a same-day source is detected;
- eligibility, the previous-season fallback, back-to-back from schedule dates;
- chronological splits (an overlapping plan raises) and feature-schema hashing;
- the baseline definition, non-negative predictions, double-double calibration outputs;
- conformal rank and near-nominal coverage;
- retraining reproducibility (1e-6; XGBoost 1e-3);
- artifact SHA-256 and schema refusal; registry rows written and reloadable.

### Training run on real data

```bash
cd backend && .venv/bin/python -m app.cli train
```

**Result:** release `2026.10.29-1` (candidate), data_version 61, feature schema `35b40abdaf39d73f`, seed 20261028, 663 s wall time on an Apple M2 (peak 1.5 GB).

Rows: 218,346 player-games.
- Train: 154,918 (2018-10-26 to 2024-06-17).
- Validation: 27,537 (2024-25).
- Test: 27,999 (2025-26, regular season and playoffs).

Leakage check: 0 of 218,346 rows use a source on or after their game date. The run started from commit `abf084f` plus the uncommitted Phase 6 code that was committed right after it. That is recorded as `git_dirty: true` in `backend/artifacts/2026.10.29-1/report.json`.

Results are from the held-out 2025-26 test season. The selected model per target was chosen by validation MAE, and every family is scored on identical rows:

| Target | Selected | Test MAE | Baseline MAE | MAE reduction | RMSE | R² | 80% interval coverage (by minutes tertile) | Test MAE by family |
|---|---|---|---|---|---|---|---|---|
| Points | xgboost | 4.550 | 4.685 | 2.9% | 5.939 | 0.532 | 80.1% (79.3, 80.4, 80.5) | baseline 4.685 · ridge 4.563 · forest 4.572 · xgboost 4.550 |
| Rebounds | xgboost | 1.885 | 1.940 | 2.8% | 2.476 | 0.446 | 80.4% (80.7, 80.3, 80.2) | baseline 1.940 · ridge 1.890 · forest 1.893 · xgboost 1.885 |
| Assists | xgboost | 1.336 | 1.372 | 2.6% | 1.809 | 0.501 | 80.0% (80.4, 79.4, 80.2) | baseline 1.372 · ridge 1.339 · forest 1.341 · xgboost 1.336 |
| 3-pointers made | xgboost | 0.889 | 0.904 | 1.6% | 1.229 | 0.317 | 80.2% (78.5, 81.4, 80.5) | baseline 0.904 · ridge 0.893 · forest 0.891 · xgboost 0.889 |
| Steals | ridge | 0.719 | 0.738 | 2.7% | 0.939 | 0.112 | 79.5% (79.4, 79.3, 79.8) | baseline 0.738 · ridge 0.719 · forest 0.722 · xgboost 0.721 |
| Blocks | rolling baseline | 0.511 | 0.511 | 0.0% | 0.749 | 0.159 | 82.3% (83.6, 81.0, 82.4) | baseline 0.511 · ridge 0.520 · forest 0.522 · xgboost 0.521 |
| Minutes | xgboost | 4.846 | 5.210 | 7.0% | 6.290 | 0.632 | 80.5% (79.5, 81.4, 80.6) | baseline 5.210 · ridge 4.928 · forest 4.895 · xgboost 4.846 |

**Double-double probability:** xgboost classifier, chosen by raw validation log loss (0.1969 vs logistic 0.2012), with isotonic calibration on 2024-25.
- Test Brier score 0.0528, against a base-rate Brier score of 0.0676.
- Log loss 0.1859; base rate 7.3%.
- Reliability bins are in the report file.

Findings, as measured:
- The ≥ 5% MAE-reduction research objective is met for minutes (7.0%). The other targets improve on the baseline by 1.6–2.9%. Blocks do not improve, so the baseline is the shipped blocks model.
- Interval coverage is 79.5–82.3% for every target and 78.5–83.6% in every minutes bin, inside the 75–85% gate.
- Registry: 1 release and 37 model versions (7 targets × 4 held-out families, 7 production refits, 2 double-double), with 16 persisted artifacts (6.0 MB) and 58 evaluation rows.

A second real-data run for points, unregistered and meant to repeat the reproducibility check at full scale, was stopped before it finished. Reproducibility is verified by the automated test on the synthetic league.

## Product redesign (Overview, Compare, Models, Predictions, Games)

### Automated

| Suite | Result |
|---|---|
| ESLint, `tsc --noEmit` (after `next typegen`) | Clean |
| Vitest unit | 38 passed |
| Playwright, 4 viewports (1440, 1024, 768, 375) | 204 passed, 4 skipped (desktop-only or pointer-only cases) |

New E2E specs run against the synthetic stub API (`tests/e2e/stub-api.mjs`, season 2099-00, never real data):

- `overview.spec.ts`: date browsing, matchup and top scorers, leader categories, standouts, model accuracy, freshness.
- `compare.spec.ts`: picking, swapping, season change, remove, duplicate guard, no shared season, unknown id, chart/table.
- `models.spec.ts`: release status, accuracy rows, algorithm ranking, ranges, double-double, unknown version, features.
- `predict.spec.ts`: search and leader quick picks, game switching, the not-serving forecast state, former and unknown players.
- `games.spec.ts`: full box scores, linkable dates, malformed date.

Each spec includes an axe pass (WCAG 2.2 AA tags, serious and critical violations must be 0) in dark and light themes, plus a horizontal-overflow check.

### Manual checks against the real API

- Overview at 1440 and 375 px, no console errors. Leaders, standouts and model metrics match `/overview`.
- Compare for Jokić and Dončić defaults to 2025-26 (71 and 64 games) because 2026-27 has fewer than 10 games for both.
- Models shows release `2026.10.29-1` as a candidate; table values match `/models/2026.10.29-1`.
- Predictions for Jokić lists 6 upcoming games. Rest, defensive rating and pace match `/teams/{id}/stats`.
- Games for 2026-10-27 shows 4 finals with full box scores, including overtime team minutes.

### CI fixes

- Linux CI rendered the position filter wider than macOS at 320 px; it now scrolls within its column.
- The top-bar slack test counted a gap for the hidden desktop navigation; it now measures visible items only.
- Light-theme contrast of the "Selected" algorithm badge was borderline on Linux; it is now a solid primary chip.
- Wide-table scroll containers on narrow viewports are now focusable, labelled regions (axe `scrollable-region-focusable`).
- `/games` reads the clock after `connection()`, so the default date is resolved per request instead of during prerender.
- CI run 40882783640 passed (backend and frontend jobs).

## Phase 7 inference

| Check | Result |
|---|---|
| Backend suite | 210 passed (13 in `tests/api/test_predictions.py`) |
| Served features equal the training row for the same game | Pass (all 60 features) |
| 1,000 real `POST /predictions` across 50 player-games | 936 succeeded, 64 correctly refused (`insufficient_data`), 0 errors |
| Latency, warm | p50 63 ms, p95 69 ms, max 145 ms; first call 1.07 s (loads and verifies artifacts) |
| Recompute from stored snapshots | 57 / 57 hashes match; max absolute difference 0.0 |
| Retrain from clean commit `da61251` | Release `2026.10.29-2`: every selected metric and calibration identical to `-1`; two random-forest candidates differ at the 16th decimal |

The first reproducibility run found a real bug: snapshots were stored rounded to 6 decimals while the model saw full precision, so XGBoost splits could differ by up to 0.68 points. Snapshots now keep full precision and the model reads the snapshot itself. The 57 forecasts made before the fix remain stored and are superseded by new rows.

## Release readiness baseline (2026-11-02)

Environment: macOS (Darwin 27.0.0, arm64), Python 3.12.15, PostgreSQL 16.15, Node 25.9.0. Branch `release-readiness`. No Docker on this machine.

### Dependency lock and clean setup

| Check | Command or method | Result |
|---|---|---|
| Lock files are reproducible | `sh scripts/lock.sh` twice | Byte-identical |
| Hash-checked install | `pip install --require-hashes -r requirements-dev.lock`, `pip check` | Clean |
| Bundle tests after the docstring removal | `pytest tests/integration/test_release_bundle.py` | 4 passed |
| Real release moved between machines | `artifacts export 2026.10.29-3`, then import into a new empty database with its own artifact directory, `artifacts verify`, `activate` | 19 artifacts, 6,308,098 bytes; status `active`; 43 versions and 67 evaluations, the same as the source |
| Clean-room setup | Fresh `git clone` into a scratch directory, following [setup.md](setup.md) with a new database and the bundle above | Install, migrations on an empty database, import, verify, activate, API start, frontend `npm ci` and build, `/about` 200, `/models` 200, `/api/v1/health` ok |
| Backend suite in the clean-room checkout | `pytest -q` run 7 times | First run 4 failed, 1 error, 280 passed. The next 6 runs all 285 passed |

The first clean-room run's failure details were not kept (only the last lines of the log). The likely cause is that `NBA_TEST_DATABASE_URL` was set in `.env`, which the test suite does not read, so that run used the shared default `nba_intelligence_test` while another session was running tests against it. This is likely, not proven. [setup.md](setup.md) now says the variable is read from the shell only.

Not covered by the clean-room run: a real `ingest backfill` and `train`. Both call or depend on stats.nba.com data and were run earlier on the main checkout ([Phase 3](#live-ingestion-against-statsnbacom), [Phase 6](#training-run-on-real-data)).

### CI history

| Commit | Result |
|---|---|
| `9938ecf` (Phase 12) | Passed |
| `e1fccc5` (Phase 9) | Passed |
| `02b7c97`, `cb2bd67`, `6c2c900`, `d6f8b74` | Cancelled by a newer push, so those commits never had a completed run of their own |
| `6f600ad` | Failed on a line-length lint error, fixed in `6c2c900` |

### Real-backend prediction workflow

```bash
cd frontend && npm run test:fullstack
```

Real Next.js production build, real FastAPI on its own port, isolated PostgreSQL database `nba_intelligence_fullstack`, synthetic season 2099 from `backend/tests/fullstack/scenario.json`, loaded through the real ingestion jobs. The model release is registered and activated through the real registry functions, using deterministic artifacts. `stub-api.mjs` is not used and no request is intercepted. Time comes from a clock file read only by the test factory `tests.fullstack.app:build`. There are no sleeps. The test fails if the browser requests any host other than localhost, and the test factory replaces the photo cache so the API makes no NBA requests either.

**Result:** 1 test passed, 14 steps, 2.4 min test time (2.7 min with the production build).

Expected values are calculated in the test from the scenario's numbers, not read from application code:

| Check | Expected and observed |
|---|---|
| First forecast (mean of 6 games) | 21.667 points, range 18.667 to 24.667 |
| After an earlier game arrives | Appended row at 23.0 superseding the original; original row unchanged |
| Repeated request with the same inputs | Same row returned, HTTP 200, no new row |
| Past tip-off | HTTP 409 `game_already_started`; the page says "This game has started"; no new row |
| Live points MAE, coverage (2 final forecasts) | 3.0, 50% |
| Live points RMSE | 3.606 |
| Double-double Brier (n=2) | 0.3125 |
| Backtest points MAE, coverage (n=10) | 0.68, 90%, unaffected by live forecasts |
| Repeated scoring | Stored evaluations for the game unchanged |

Bugs this suite found, all fixed:

- `/models/{version}/analytics?kind=pregame` counted superseded forecasts, so revisions were overweighted. It now counts each player-game's final forecast, the same as `/live`.
- A refresh chose the forecast to supersede by timestamp, which is ambiguous when two forecasts share one. It now picks the forecast nothing has superseded.
- Scoring from a sync event used the system clock rather than the worker's.
- A refused "Update forecast" showed nothing. It now keeps the stored forecast and shows the reason (`tests/unit/forecast.test.tsx`).

The backend suite after these fixes: 285 passed.

## Team forecast lifecycle (2026-11-02)

`tests/api/test_game_forecasts.py` covers freshness, refresh, closing at tip-off, postponed and cancelled games, scoring by sync event, repeated scoring, source corrections, and live metrics compared with values calculated in the test. Headline metrics count only the forecast nothing superseded.

These run against the small fixture league with the 10-game minimum lowered to 3, because the fixture has too few games for a team forecast. The real-backend suite does not exercise team forecasts for the same reason, so team forecasts have **not** been tested through a browser against the real API. The UI is covered by stub-API tests.

On a copy of the real database restored on 2026-11-02, the first maintenance run scored 49 stored score forecasts. The 22 final forecasts behind them gave a score MAE of 10.63 points, winner accuracy of 63.6% and a Brier score of 0.216. That is a small early sample, not an accuracy claim, and the real database has not been scored yet.

## Security and reliability (2026-11-02)

| Check | Command | Result |
|---|---|---|
| Python advisories | `pip-audit -r requirements.lock --require-hashes --disable-pip` | No known vulnerabilities |
| npm advisories, production dependencies | `npm audit --omit=dev` | 0 high or critical. 4 moderate and 2 low, all through the `shadcn` CLI package (`@shadcn/registry`, `@ts-morph/common`, `deepmerge`, `minimatch`, `shadcn`, `ts-morph`) |
| Secrets in history, local | Pattern search of `git log -p --all` | No matches. A pattern search is weaker than a real scanner |
| Secrets in history, CI | gitleaks in the `security` job | Passed at `e90f099` |
| Rate limiting | `tests/api/test_rate_limit.py` | Predictable 429 with `Retry-After`; per-client and global limits; reads unaffected |
| Failure paths | `tests/api/test_failure_paths.py` | Controlled 503 for database outage, exhausted pool, missing or corrupt artifacts, no active release and inference overload; generic 500 for anything else; nothing internal in responses |
| Source failures | `tests/integration/` (existing) | Failed runs are recorded, roll back, and leave data untouched |

A real leak was found and fixed: the public `model_unavailable` message included the artifact file path and hash. It now goes to the log only.

### Load test

```bash
cd backend && .venv/bin/python scripts/load_test.py --base-url http://127.0.0.1:8703 --requests 1000 --clients 20
```

- **Environment:** one uvicorn process, on a MacBook (arm64, 8 CPUs, 8 GB) shared with other running work; PostgreSQL 16.15 on the same machine; `NBA_DB_POOL_SIZE=10`, `NBA_DB_MAX_OVERFLOW=10`. No network between client and server. These numbers do not predict a hosted deployment.
- **Data:** a restored copy of the real database, active release `2026.10.29-3`.
- **Workload:** each scenario runs separately: 1,000 requests from 20 concurrent clients, seed 7, across 62 upcoming games and 300 distinct player-games. Rate limits were raised for this test. The first scenarios warm caches. Forecast scenarios mix first-time computation with repeats.
- **Measured** on 2026-11-02:

| Scenario | Requests | Clients | Statuses | Unexpected | p50 ms | p95 ms | p99 ms | Max ms | Requests/s |
|---|---|---|---|---|---|---|---|---|---|
| `read_player_profile` | 1000 | 20 | 200: 1000 | 0 | 47 | 237 | 344 | 569 | 274.0 |
| `read_games_by_date` | 1000 | 20 | 200: 1000 | 0 | 202 | 600 | 1000 | 1159 | 81.4 |
| `read_model_summary` | 1000 | 20 | 200: 1000 | 0 | 54 | 193 | 259 | 434 | 250.0 |
| `forecast_player` | 1000 | 20 | 200: 640, 201: 252, 422: 108 | 0 | 1668 | 4563 | 5479 | 7133 | 10.1 |
| `forecast_game` | 1000 | 20 | 200: 1000 | 0 | 565 | 750 | 1210 | 1523 | 34.0 |

A 422 is a player with too few games, which is the correct answer. There were no 5xx responses. Forecasts handled about 10 requests per second, which is why the default global limit is 600 per minute. Under this concurrency a forecast takes seconds, far above the 69 ms p95 of the sequential run in [Phase 7](#phase-7-inference); four run at once and the rest queue. No performance gate is claimed from these numbers.

### Accessibility

`frontend/tests/e2e/a11y-audit.spec.ts` runs in CI on every viewport; see [accessibility-report.md](accessibility-report.md). The manual screen-reader checklist in that report has **not** been performed. A local full run on 2026-11-02 gave 434 passed and 28 failed, while another session ran Playwright on the same machine and ports and a database rehearsal ran alongside it. Those failures were not investigated one by one, so that run proves nothing either way. CI's `frontend` job, which runs the full suite without that interference, passed at `e90f099`.

## Deployment and operations rehearsal (2026-11-02)

Everything here ran on the development Mac against the real data, in throwaway copies. The real database was only read by `pg_dump`. Nothing has been deployed.

| Check | Result |
|---|---|
| `scripts/backup.sh nba_intelligence` | 24,004,893-byte dump with a checksum |
| `scripts/restore_check.sh <dump> nba_intelligence` | Checksum OK; restored into a new database; row counts of 12 main tables match the source; temporary database dropped |
| Migrate the restored copy down one step and back up | Worked |
| First `app.cli predictions` on the copy | Scored 49 score forecasts and 272 player forecasts |
| `app.cli ops-check` on the copy | Correctly reported overdue jobs and waiting events, because no worker runs against the copy; `scoring` went from fail to ok after maintenance; `model` ok |
| Roll back the model release, then forward | `2026.10.29-2` verified and activated, `-3` retired; then `-3` active again |
| `app.cli source-check` from the Mac | Reachable, 45 rows, 0.87 s. **Not** tested from any cloud host |
| Frontend production build with no API running | Builds, so images can be built without a live API |
| Docker images and Compose stack | Not run locally (no Docker). CI's `containers` job built and smoke-tested them at `e90f099` |

The rehearsal found one more bug, now fixed with a test: a forecast for a player who did not play kept its game in the pending list, so the game was rescored on every maintenance run.

CI on `e90f099` (run 41484295687): `backend`, `frontend`, `fullstack`, `security` and `containers` all passed. Those results predate later merges from main (the redesign, team pages and defender matchups). On the merged code, locally: backend 347 passed, frontend lint and typecheck clean, unit tests 40 passed, and `npm run test:fullstack` 1 passed. Main's `player_matchups` migration and this branch's `game_prediction_evaluations` migration shared a parent, so the branch's now follows main's; upgrade, downgrade and upgrade again worked on an empty database.

Not demonstrated: a hosted smoke test, a real restore on a host, alert delivery, and any of the seven-day thresholds.

