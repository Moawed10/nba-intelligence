# Implementation Status

The authoritative ledger of development progress. A status here is only as good as its evidence. When this document and executable evidence disagree, the evidence wins and this document is corrected (see [data-ownership.md](data-ownership.md#evidence-hierarchy-for-progress-claims)).

**Last updated:** 2026-10-28

## Master status

| Phase | Name | Status | Progress | Blockers |
|---|---|---|---|---|
| 1 | Repository Audit & Architecture | Complete | 100% (8/8) | None |
| 2 | Design System & Foundation | Complete | 100% (12/12) | None |
| 3 | Database, Ingestion & Sync | In Progress | 95% (18/19) | Prediction-evaluation handlers (Phase 7) |
| 4 | Core Backend APIs | Complete | 100% (11/11) | None |
| 5 | Player Explorer & Profile | Not Started | 0% (0/11) | Phases 2, 4 |
| 6 | Machine Learning Pipeline | Not Started | 0% (0/13) | Phase 3 |
| 7 | Prediction API & Inference | Not Started | 0% (0/14) | Phases 4, 6 |
| 8 | Prediction Center | Not Started | 0% (0/12) | Phases 2, 7 |
| 9 | Model Analytics | Not Started | 0% (0/10) | Phases 6, 7 |
| 10 | Player Comparison | Not Started | 0% (0/9) | Phases 4, 5 |
| 11 | Overview & Games | Not Started | 0% (0/9) | Phases 4, 5 |
| 12 | Accessibility Audit | Not Started | 0% (0/10) | Core screens |
| 13 | Performance & Security | Not Started | 0% (0/12) | Core functionality |
| 14 | Testing & Integration | Not Started | 0% (0/10) | Integrated features |
| 15 | Deployment & Portfolio | Not Started | 0% (0/14) | Release gates |

**Overall:** 49 / 174 verified deliverables = **28%**.

Progress = verified completed deliverables ÷ required deliverables, rounded. Allowed statuses: Not Started, In Progress, Blocked, Verification Pending, Complete. Criterion results: Pass, Fail, Not Verified.

## Milestones

| Milestone | Required phases | Status |
|---|---|---|
| Architecture Ready | 1 | Pass |
| Application Foundation | 2 | Pass |
| Real NBA Data Available | 3–4 | Not Verified (data and read API verified; Phase 3 closes with the Phase 7 handlers) |
| Player Analytics Functional | 5 | Not Verified |
| ML Models Validated | 6 | Not Verified |
| Prediction Backend Functional | 7 | Not Verified |
| Functional MVP | 1–8 + applicable security, accessibility, integration checks | Not Verified |
| Analytics Features Complete | 9–11 | Not Verified |
| Release Quality Gates | 12–14 | Not Verified |
| Production Release | 15 | Not Verified |

## Threshold classification

| Class | Covers |
|---|---|
| Release blocker | Security, data integrity, prediction correctness, critical accessibility, broken core workflows, failing required tests |
| Performance gate | Latency, responsiveness, Core Web Vitals, reliability |
| Quality target | Coverage, usability improvements |
| Research objective | ML accuracy improvements (e.g. ≥ 5% MAE reduction over baseline) |

Thresholds are not weakened to close a phase. An unrealistic threshold gets measured evidence and a proposed adjustment for approval.

---

### Phase 1 — Repository Audit & Architecture

**Status:** Complete · **Progress:** 100% (8/8) · **Last Updated:** 2026-10-28
**Dependencies:** None
**Objective:** Establish the architecture, ownership boundaries, contracts and schema before any implementation.

#### Deliverables

- [x] Inspect the repository: empty (greenfield); no existing routes, endpoints, models or ML code to preserve
- [x] Identify completed, incomplete and broken functionality: none exists
- [x] Review the dev environment: Python 3.12.15 (venv `backend/.venv`), Node 25.9.0, PostgreSQL 16.15 (Homebrew); Docker absent ([ADR 0006](decisions/0006-local-postgres-without-docker.md))
- [x] Verify the data source: live `nba_api` 1.12.0 probe ([architecture.md § NBA data source findings](architecture.md#nba-data-source-findings))
- [x] System architecture with a five-layer diagram: [architecture.md](architecture.md)
- [x] Ownership boundaries and source of truth: [data-ownership.md](data-ownership.md)
- [x] API contracts and DB schema: [api-contracts.md](api-contracts.md), [database.md](database.md), plus [model-methodology.md](model-methodology.md), [frontend.md](frontend.md), [decisions/](decisions/)
- [x] Development checklist: this document

#### Acceptance criteria

| Criterion | Threshold | Actual | Status |
|---|---|---|---|
| Existing routes, endpoints, models, ML components inventoried | 100% | 100%: the repository contained 0 files before work began | Pass |
| Planned endpoints assigned to a backend module | 100% | 26 / 26 (25 required + `/overview`) | Pass |
| DB entities documented with PK and relationships | 100% | 16 / 16 tables have a PK and appear in the ER diagram | Pass |
| Unresolved critical architecture decisions | 0 | 0 critical; 2 non-critical deferred (below) | Pass |
| Required architecture documents have substantive content | All | 8 docs (architecture, data ownership, data sync, database, API contracts, model methodology, frontend, this ledger) plus 6 ADRs | Pass |
| Architecture diagram showing the five layers | ≥ 1 | 1 (layers L1–L5 in [architecture.md](architecture.md#system-diagram)) | Pass |
| Architecture review | Owner sign-off | Approved by owner in chat, 2026-10-28 | Pass |

Deferred non-critical decisions: (1) production hosting provider, decided in Phase 15; (2) whether to display NBA CDN headshots, decided in Phase 15, with a monogram fallback until then.

#### Implementation evidence

**Files created:** `docs/architecture.md`, `docs/data-ownership.md`, `docs/data-synchronization.md`, `docs/database.md`, `docs/api-contracts.md`, `docs/model-methodology.md`, `docs/frontend.md`, `docs/implementation-status.md`, `docs/decisions/0001`–`0006` + `README.md`, `README.md`, `.gitignore`
**Files modified:** none (no pre-existing files)
**Endpoints implemented:** none (design phase)
**Tests added:** none (design phase)

**Commands executed:**

| Command | Result |
|---|---|
| `find ~/Desktop ~/Projects ~/Documents -maxdepth 3 -iname "*nba*"` | No existing NBA project found |
| `brew install postgresql@16 && brew services start postgresql@16` | Exit 0; `pg_isready` → accepting connections; PostgreSQL 16.15 |
| `python3.12 -m venv backend/.venv && pip install nba_api pandas` | nba_api 1.12.0 installed |
| nba_api probe script (LeagueGameLog P/T, ScheduleLeagueV2, LeagueDashTeamStats, CommonPlayerInfo) | All OK. 2025-26 P: 26,651 rows (6.2 s); 2018-19 P: 26,101; 2026-27 P: 1,275 (Oct 20–27); 2025-26 T: 2,460; 2026-27 schedule: 1,274 rows; team advanced: 30 rows |
| Doc gate script (endpoint/module mapping, table PK + ER coverage, diagram layers) | 26/26 endpoints mapped, 0 missing required; 16/16 tables with PK in ER (re-run after sync design); 5 layers |

#### Issues and blockers

| Issue | Severity | Impact | Resolution |
|---|---|---|---|
| No Apple Design Skill available | Low | Design relies on HIG principles applied directly | Documented in [frontend.md](frontend.md#apple-design-skill) with enablement steps |
| stats.nba.com cloud-IP blocking (reported, unverified here) | Medium | Hosted ingestion may fail | Ingestion runs where reachable ([ADR 0002](decisions/0002-no-http-admin-operations.md)); verify in Phase 15 |
| Docker not installed | Low | No local compose | Homebrew Postgres locally; containers in CI ([ADR 0006](decisions/0006-local-postgres-without-docker.md)) |

#### Next actions

1. Owner reviews the architecture documents.
2. Phase 2: scaffold `frontend/` (Next.js, TypeScript, Tailwind, shadcn/ui) with tokens, `AppShell` and navigation.
3. Phase 3 (independent of 2): backend scaffold, SQLAlchemy models, first Alembic migration on a clean database.

#### Completion decision

**Result:** Pass. **Reason:** all 7 criteria pass: 6 by the gate scripts recorded above, and the architecture review by owner approval on 2026-10-28.

---

### Phase 2 — Design System & Application Foundation

**Status:** Complete · **Progress:** 100% (12/12) · **Last Updated:** 2026-10-28
**Dependencies:** Phase 1; PlayerSearch and generated types were completed with Phase 4
**Objective:** A themed, accessible, responsive application shell and the shared components every screen uses.

#### Deliverables

- [x] Next.js 16 + TypeScript (strict) app in `frontend/`
- [x] Tailwind 4 + shadcn/ui (Radix) configured with tokens (`src/app/globals.css`)
- [x] Light and dark themes with a persisted choice and no flash (`components/shell/theme-toggle.tsx`)
- [x] Typography scale with tabular numerals
- [x] `TopNav`, `TabBar`, `MoreMenu`, skip link, landmarks, `RouteFocus` (`components/shell/`)
- [x] All 7 routes resolve; data screens show the honest `NotConnected` state; `/about` has real content
- [x] `PlayerSearch` combobox (`components/data/player-search.tsx`: WAI-ARIA list autocomplete, 250 ms debounce, aborted stale requests), plus `SegmentedControl`, Dialog/Sheet/Popover/Tooltip and `InfoHint`
- [x] `StatTile`, `ChartFrame` (with table view), `DataTable`, `IntervalBar` (`components/data/`)
- [x] `StateView` (loading, empty, error, stale, unavailable) and `FreshnessBadge`
- [x] Centralized API client (`lib/api/server.ts`, `client.ts`, `errors.ts`) with types generated from `backend/openapi.json` (`lib/api/schema.d.ts`, `types.ts`); CI fails if they drift
- [x] `MotionConfig reducedMotion="user"` and a global reduced-motion rule
- [x] Vitest, ESLint (full jsx-a11y), Playwright + axe-core, contrast checker

#### Acceptance criteria

| Criterion | Threshold | Actual | Status |
|---|---|---|---|
| Primary nav links resolve | 100% | 5/5 primary and 2/2 secondary return 200 and render their `h1` (E2E, 4 viewports) | Pass |
| Shared interactive components keyboard-operable | 100% | 7 / 7: SegmentedControl, DataTable sort, ChartFrame toggle, More menu, theme toggle, skip link, PlayerSearch (unit and E2E keyboard tests) | Pass |
| Form controls with accessible names | 100% | 0 axe `label`/`button-name`/`link-name` violations on 7 routes × 2 themes × 4 viewports | Pass |
| Critical axe violations in shared components | 0 | 0 critical or serious | Pass |
| Layouts work at 375 / 768 / 1024 / 1440 px | All | No horizontal overflow at all 4, plus 320 px | Pass |
| Essential targets meet WCAG 2.2 AA sizing | 100% or documented exceptions | Mobile tab links ≥ 44×44 px (measured); buttons 40 px, 44 px on coarse pointers | Pass |
| Nonessential animations respect reduced motion | 100% | Computed transition duration < 1 ms under `prefers-reduced-motion` (E2E); Motion `reducedMotion="user"` | Pass |
| Statement coverage, shared UI utilities | ≥ 80% | 88.26% | Pass |

#### Implementation evidence

**Files created:** `frontend/` (scaffold), `src/app/globals.css`, `src/app/layout.tsx`, `src/app/{page,players,predict,compare,models,games,about}/page.tsx`, `src/components/shell/*`, `src/components/data/*`, `src/components/providers.tsx`, `src/lib/{format.ts,api/*}`, `scripts/check-contrast.mjs`, `vitest.config.mts`, `playwright.config.ts`, `tests/unit/*`, `tests/e2e/shell.spec.ts`, `.github/workflows/ci.yml`
**Tests added:** 20 Vitest unit tests; 52 Playwright checks (50 run, 2 skipped by design). See [test-report.md](test-report.md#frontend).
**Commands executed:** `npm run lint`, `npm run typecheck`, `npm run check:contrast`, `npx vitest run --coverage`, `npx playwright test`, all passing.

#### Issues and blockers

| Issue | Severity | Impact | Resolution |
|---|---|---|---|
| PlayerSearch and generated API types need the API | Medium (resolved) | Were blocked on Phase 4 | Built with Phase 4 |
| Highlighted menu item and search option were invisible in dark mode (`accent` token equalled the popover color) | High (fixed) | Keyboard users could not see the current item | `accent` now maps to the primary fill; contrast checker covers it (6.78:1 dark, 5.55:1 light) |
| `npm audit` reports advisories in dev dependencies | Unknown | Not triaged | Triage in Phase 13 |
| VoiceOver not tested manually | Medium | Screen-reader behavior verified only via axe and semantics | Manual pass in Phase 12 |

#### Completion decision

**Result:** Complete. **Reason:** 12 / 12 deliverables and 8 / 8 criteria pass. Open items (manual VoiceOver pass, `npm audit` triage) are tracked in Phases 12 and 13.

---

### Phase 3 — Database, NBA Data Ingestion & Synchronization

**Status:** In Progress · **Progress:** 95% (18/19) · **Last Updated:** 2026-10-28
**Dependencies:** Phase 1 (done); the last deliverable completes with Phase 7
**Objective:** Real NBA data for 2018-19 onward, stored without duplicates, with provenance, freshness and automatic synchronization.

#### Deliverables

- [x] `backend/pyproject.toml`, `app/config.py`, `app/db.py` (UTC sessions, pooling), `app/logging.py` (JSON logs)
- [x] SQLAlchemy models for all 16 tables (`app/models/`)
- [x] Alembic setup and initial migration, including `pg_trgm` and enum cleanup on downgrade
- [x] `app/ingestion/client.py`: throttling, timeouts, full-jitter backoff ≤ 5 attempts, `Retry-After`, on-disk cache for completed seasons
- [x] Teams and players sync (`ingest teams`, `ingest players`)
- [x] Season backfill via `LeagueGameLog`, with neutral-site home resolution from the schedule
- [x] Schedule sync via `ScheduleLeagueV2`
- [x] Row validation and rejection counting (`app/ingestion/transforms.py`)
- [x] Idempotent upserts with `IS DISTINCT FROM` guards (`app/ingestion/writer.py`)
- [x] `ingestion_runs` freshness tracking and `source_corrections` logging
- [x] `app/cli.py` (`ingest`, `sync-worker`, `sync-once`, `data-status`, `integrity`, `runs`)
- [x] Ingestion and idempotency tests (`tests/integration/test_ingestion.py`)
- [x] Reconciliation report (`python -m app.cli integrity`)
- [x] Sync worker with persisted `sync_schedules`, game-aware polling and advisory-lock exclusion (`app/sync/worker.py`)
- [x] Game lifecycle state machine with no-downgrade rule (`app/ingestion/lifecycle.py`)
- [ ] `sync_events` outbox and handlers. Emission, dedupe and drain are done; prediction-evaluation handlers come in Phase 7.
- [x] Freshness exposed in `GET /api/v1/data-status` and in `meta.data_freshness` on every data response (6 datasets; the 2 prediction datasets are added with Phase 7)
- [x] Retry classification, full-jitter backoff, `Retry-After`, lease recovery
- [x] Weekly corrections job; sync tests including the New York season boundary

#### Acceptance criteria

| Criterion | Threshold | Actual | Status |
|---|---|---|---|
| Migrations succeed on clean PostgreSQL | 100% | Upgrade, downgrade and re-upgrade on a clean DB; `alembic check` shows no drift | Pass |
| Complete historical regular seasons ingested | ≥ 3 | 8 (2018-19 to 2025-26) | Pass |
| Valid source records persisted | ≥ 99.5% | 100% of valid rows stored; 364,110 / 364,238 fetched rows valid (99.96%) | Pass |
| Duplicates after 3 identical runs | 0 | 0 (2025-26 run 3×; counts identical; integration test) | Pass |
| FK relationships validated | 100% | 24 FKs enforced; orphan checks 0 | Pass |
| Player stats reference valid players and games | 100% | 0 orphan player lines of 219,230 | Pass |
| Expected completed-game player records present | ≥ 95% | 100% of final games in every completed season have lines for both teams | Pass |
| Retries use exponential backoff | ≤ 5 attempts | Capped at 5, jittered (unit tests) | Pass |
| Failed jobs preserve committed data | Yes | Source failure, partial response and mid-transaction crash leave counts unchanged (integration tests) | Pass |
| Concurrent executions of the same job | 0 | Second runner skipped while the lock is held (integration test) | Pass |
| Executions with persisted job status | 100% | 61 / 61 dev runs finished with a status; test asserts no unfinished runs | Pass |
| Retry behavior bounded and tested | Yes | Unit tests for statuses, timeouts, cap, `Retry-After` | Pass |
| Failed/interrupted job recovery | Integration test | Abandoned-lease recovery and next-cycle retry tests | Pass |
| Finalized-game reconciliation fixtures passing | 100% | Data side passes (finalization, events); prediction evaluation pending Phase 7 | Not Verified |
| Cache invalidation on tested dependencies | 100% | Cached responses are keyed by `data_version`; a new succeeded run invalidates them (`test_cache_hits_skip_the_database_until_data_version_changes`, unit tests) | Pass |
| Freshness metadata for synchronized datasets | All 8 | 6 / 8 (prediction features and predictions pending Phase 7) | Not Verified |
| Scheduler restart recovery | Verified | Persisted `next_run_at`; restart at the same instant runs nothing (test and live) | Pass |
| Critical sync tests passing | 100% | 171 / 171 backend tests | Pass |

#### Implementation evidence

**Files created:** `backend/` (`app/config.py`, `db.py`, `logging.py`, `cli.py`, `models/*`, `ingestion/*`, `sync/*`), `alembic/` + initial migration, `tests/{unit,integration}/*`
**Tests added:** 88 (see [test-report.md](test-report.md#backend))
**Commands executed:** `pytest` (88 passed); `ingest backfill --from 2018 --to 2026` (exit 0, 191 s); `integrity` (all checks 0); `ingest season --season 2025` ×3 (0 inserts/updates on reruns); `sync-once` ×2; `data-status` (6 datasets fresh)

#### Issues and blockers

| Issue | Severity | Impact | Resolution |
|---|---|---|---|
| Neutral-site games list both teams as away | High (fixed) | 5 games per season were rejected | Resolve home team from the schedule; regression test |
| Filling an empty score was logged as a correction | Medium (fixed) | 2,640 false corrections in dev | Ignore stored nulls; dev rows removed; regression test |
| First sync pass emitted events for 10,284 historical games | Medium (fixed) | Would trigger evaluation of old games | Events only for games ≤ 36 h old; drain loops to empty; regression tests |
| Live in-game scores are not ingested | Low | Live status comes from the schedule; scores land when the game is final | Documented in data-synchronization.md |
| Cloud-IP blocking of stats.nba.com is untested | Medium | Hosted ingestion may fail | Verify in Phase 15 |

#### Next actions

1. Phase 7: prediction-evaluation handlers and prediction freshness datasets.
2. Phase 6: feature pipeline on the 219,230 stored player lines.

#### Completion decision

**Result:** Not Verified. **Reason:** 16 of 18 criteria pass; the other 2 depend on Phase 7 predictions.

---

### Phase 4 — Core Read-Only Backend APIs

**Status:** Complete · **Progress:** 100% (11/11) · **Last Updated:** 2026-10-28
**Dependencies:** Phase 3
**Objective:** Fast, bounded, documented read endpoints over the verified NBA data, with one error format and freshness on every response.

#### Deliverables

- [x] `app/main.py`: app factory, request id (echoed or generated), JSON access log, error envelope (`app/api/errors.py`), CORS off unless `NBA_CORS_ORIGINS` is set
- [x] `app/stats/` statistic definitions, shared by every endpoint (ML pipeline will import the same module)
- [x] `/players`, `/players/search` (accent-insensitive trigram search; migration `3c1d7e9a2b45`)
- [x] `/players/{id}`, `/stats` (seasons plus home/away and rest splits), `/games`, `/trends` (rolling 3/5/10 over previous games)
- [x] `/teams`, `/teams/{id}`, `/teams/{id}/stats` (pace and ratings from team logs)
- [x] `/games`, `/games/upcoming`, `/games/{id}`, `/games/{id}/boxscore`
- [x] `/health`, `/readiness`, `/data-status`
- [x] Pagination (`limit` ≤ 100, `offset`), filters and sort allow-lists validated by the schema
- [x] Data-version cache (`app/services/cache.py`) plus `Cache-Control` per endpoint
- [x] Integration tests per endpoint (success, invalid input, missing resource): `tests/api/`
- [x] Latency benchmark script (`scripts/benchmark.py`) and documented workload

#### Acceptance criteria

| Criterion | Threshold | Actual | Status |
|---|---|---|---|
| Required player/team/game endpoints implemented | 100% | 16 / 16 read endpoints in the contract table (prediction, compare, model and overview endpoints belong to Phases 7–11) | Pass |
| Endpoints in OpenAPI | 100% | 16 / 16, all `GET` (`test_every_endpoint_is_documented_read_only`); schema committed as `backend/openapi.json` with a drift test | Pass |
| Success / invalid / missing tests per endpoint | 100% where applicable | Every endpoint has a success test; every parameterised endpoint has invalid-input tests; every `{id}` endpoint has a 404 test (`tests/api/`, 66 tests) | Pass |
| Statement coverage, core API logic | ≥ 85% | `app/api` 95–100%, `app/services` 98–100%, `app/stats` 100%, `app/schemas` 100% | Pass |
| Player search p95 (20 clients, 1,000 req) | < 300 ms | 38.0 ms uncached, 32.7 ms with cache | Pass |
| Player profile p95 | < 500 ms | 74.9 ms uncached, 47.9 ms with cache | Pass |
| Game log p95 | < 700 ms | 102.0 ms (not cached) | Pass |
| Unbounded queries | 0 | Lists capped at 100 rows; games window ≤ 31 days; upcoming ≤ 14 days and 100 rows; per-player reads ≤ one stored career (max 718 lines); rosters ≤ 18; team season ≤ 107 games | Pass |
| N+1 patterns on primary endpoints | 0 | Query count identical for page sizes 1–16 on players, game log and games; box score ≤ 4 queries (`tests/api/test_queries.py`) | Pass |
| List endpoints enforce limits | 100% | `limit` > 100 (or > 20 for search) returns 422 on every list endpoint | Pass |

#### Implementation evidence

**Files created:** `backend/app/main.py`, `app/api/{deps,errors}.py`, `app/api/v1/{players,teams,games,system}.py`, `app/schemas/{common,resources}.py`, `app/services/{cache,common,players,teams,games,system}.py`, `app/stats/__init__.py`, `alembic/versions/20261028_3c1d7e9a2b45_accent_insensitive_search.py`, `scripts/benchmark.py`, `openapi.json`, `tests/api/*`, `tests/unit/{test_stats,test_cache,test_openapi}.py`
**Tests added:** 83 backend tests (171 total). See [test-report.md](test-report.md#phase-4-read-api).
**Commands executed:** `pytest --cov=app` (171 passed, 92%); `ruff check` and `ruff format --check` (clean); `scripts/benchmark.py` with and without the response cache (0 errors in 6,000 requests); manual browser check of `/players` search against the real database through the Next.js proxy.

#### Issues and blockers

| Issue | Severity | Impact | Resolution |
|---|---|---|---|
| Rest-day splits started each season at null | Medium (fixed) | Season openers dropped out of rest splits | Rest days computed over the whole stored career, as defined; test |
| Team record treated ties as losses | Low (fixed) | Would misreport any tied fixture | Wins and losses counted explicitly; test |
| `dict(Result)` treated a SQLAlchemy result as a mapping | Medium (fixed) | `/data-status` returned 500 | Fixed and covered by `test_data_status` |
| Search threshold 0.4 matched unrelated names ("jokic" → Magic Johnson) | Low (fixed) | Noisy results | Threshold 0.6 (Postgres default); still matches one-typo names ("lebrn" → LeBron James) |
| Rate limiting and the 16 KB body limit are not implemented | Medium | No write endpoints exist yet | Phase 13 (with `POST /predictions` in Phase 7) |
| Nicknames ("SGA") don't match | Low | Name search only | Not planned |

#### Completion decision

**Result:** Complete. **Reason:** 11 / 11 deliverables and 10 / 10 criteria pass with recorded evidence.

---

### Phase 5 — Player Explorer & Player Profile

**Status:** Not Started · **Progress:** 0% (0/11) · **Dependencies:** Phases 2, 4

#### Deliverables

- [ ] `/players` directory with server-rendered first page
- [ ] Autocomplete wired to `/players/search`
- [ ] Team and position filters in the URL
- [ ] Profile header (`/players/[id]`)
- [ ] Season averages (`StatTile` row)
- [ ] Recent games and paged full log (`DataTable`)
- [ ] Trend charts with rolling averages (`ChartFrame`)
- [ ] Season and stat selectors (URL state)
- [ ] Home/away and rest splits (progressive disclosure)
- [ ] Loading, empty, error and stale states
- [ ] Playwright + axe workflows, including a 100-query search fixture

#### Acceptance criteria

| Criterion | Threshold | Actual | Status |
|---|---|---|---|
| Relevant results for documented 100 player queries | ≥ 95% | Not measured | Not Verified |
| Search debounce | 200–350 ms | Not measured | Not Verified |
| Search results update p95 | ≤ 500 ms | Not measured | Not Verified |
| Profiles match backend statistics | 100% | Not measured | Not Verified |
| Filters update the correct data | 100% | Not measured | Not Verified |
| Broken primary navigation actions | 0 | Not measured | Not Verified |
| Critical accessibility violations | 0 | Not measured | Not Verified |
| Horizontal overflow at 375 px | None | Not measured | Not Verified |
| Primary player workflows passing E2E | ≥ 90% | Not measured | Not Verified |

**Evidence:** none yet · **Decision:** Not Verified (not started)

---

### Phase 6 — Machine Learning Data Pipeline

**Status:** Not Started · **Progress:** 0% (0/13) · **Dependencies:** Phase 3

#### Deliverables

- [ ] `app/ml/dataset.py`: training frame from PostgreSQL at a recorded `data_version`
- [ ] `app/ml/features.py` per [model-methodology.md](model-methodology.md#features)
- [ ] Rolling 3/5/10, season-to-date and trend features
- [ ] Opponent, pace, home/away and history-vs-opponent features
- [ ] Rest and back-to-back features
- [ ] Leakage tests (fixture, perturbation, split boundary, opponent dates)
- [ ] Chronological splits
- [ ] Rolling baseline
- [ ] Ridge, Random Forest, XGBoost per target
- [ ] MAE / RMSE / R² evaluation, per target, per algorithm and per season
- [ ] Mondrian split-conformal intervals and test coverage
- [ ] Double-double classifier with isotonic calibration
- [ ] Artifacts + registry rows + reproducibility test

#### Acceptance criteria

| Criterion | Threshold | Actual | Status |
|---|---|---|---|
| Detected future-data leakage | 0 | Not measured | Not Verified |
| Rolling features exclude target game | 100% | Not measured | Not Verified |
| Partitions chronological | 100% | Not measured | Not Verified |
| Model families implemented | 4 / 4 | Not measured | Not Verified |
| Targets evaluated (pts, reb, ast minimum) | ≥ 3 | Not measured | Not Verified |
| MAE, RMSE, R² reported for every target × model | 100% | Not measured | Not Verified |
| Retraining reproducible within tolerance | 1e-6 / 1e-3 (XGB) | Not measured | Not Verified |
| Artifacts with version + schema metadata | 100% | Not measured | Not Verified |
| 80% interval empirical coverage | 75–85% | Not measured | Not Verified |
| Advanced vs baseline on same observations | Yes | Not measured | Not Verified |
| Research objective: test MAE reduction vs baseline | ≥ 5% on ≥ 1 target | Not measured | Not Verified |

**Evidence:** none yet · **Decision:** Not Verified (not started)

---

### Phase 7 — Prediction API & Inference Engine

**Status:** Not Started · **Progress:** 0% (0/14) · **Dependencies:** Phases 4, 6

#### Deliverables

- [ ] Artifact loader with SHA-256 and schema checks
- [ ] Inference service (bounded thread pool)
- [ ] Player and matchup validation
- [ ] Pregame feature snapshot at `min(now, tipoff_at)`
- [ ] Predictions for all 7 regression targets
- [ ] Conformal intervals at inference
- [ ] Double-double probability
- [ ] Append-only persistence (`predictions`, `prediction_values`)
- [ ] Snapshot-hash reuse (the prediction cache)
- [ ] `POST /predictions`, `GET /predictions/{id}`, `/history`, `/explanation`
- [ ] Error handling: `insufficient_data`, `invalid_matchup`, `game_already_started`, `model_unavailable`
- [ ] Prediction API, reproducibility and immutability tests
- [ ] Prediction freshness service (current/stale/invalid/superseded/final_pregame)
- [ ] Dependency-aware refresh inserting superseding rows, stopping at tip-off

#### Acceptance criteria

| Criterion | Threshold | Actual | Status |
|---|---|---|---|
| Valid fixtures produce correct responses | 100% | Not measured | Not Verified |
| Invalid player/game combos return proper errors | 100% | Not measured | Not Verified |
| Predictions reference valid model versions | 100% | Not measured | Not Verified |
| Predictions with data cutoff timestamp | 100% | Not measured | Not Verified |
| Training operations during inference | 0 | Not measured | Not Verified |
| Inference p95, loaded model | < 1.5 s | Not measured | Not Verified |
| Success across 1,000 valid requests | ≥ 99% | Not measured | Not Verified |
| Same model + snapshot reproduces values | Within 1e-9 | Not measured | Not Verified |
| Silently overwritten predictions | 0 | Not measured | Not Verified |
| New pregame predictions after tip-off | 0 | Not measured | Not Verified |

**Evidence:** none yet · **Decision:** Not Verified (not started)

---

### Phase 8 — Prediction Center Frontend

**Status:** Not Started · **Progress:** 0% (0/12) · **Dependencies:** Phases 2, 7

#### Deliverables

- [ ] Player selection (`?player=`)
- [ ] Upcoming game selection
- [ ] Submit to `POST /predictions`, duplicate-safe
- [ ] Predicted values (`StatTile`)
- [ ] Interval display (`IntervalBar`) labelled "likely range (80%)"
- [ ] Last-5 and season comparisons
- [ ] Prediction distribution visualization
- [ ] Explanation panel
- [ ] Model release and data cutoff display
- [ ] Loading, error and named unavailable states
- [ ] Keyboard-only workflow
- [ ] Mobile layout

#### Acceptance criteria

| Criterion | Threshold | Actual | Status |
|---|---|---|---|
| Workflow steps functional | 100% | Not measured | Not Verified |
| Successful automated workflows (100 runs) | ≥ 95% | Not measured | Not Verified |
| Displayed values match API | 100% | Not measured | Not Verified |
| Intervals state their meaning | 100% | Not measured | Not Verified |
| Unavailable predictions explained | 100% | Not measured | Not Verified |
| Render after API response p95 | ≤ 500 ms | Not measured | Not Verified |
| Critical accessibility violations | 0 | Not measured | Not Verified |
| Full keyboard workflow | Yes | Not measured | Not Verified |
| Horizontal overflow at 375 px | None | Not measured | Not Verified |

**Evidence:** none yet · **Decision:** Not Verified (not started)

---

### Phase 9 — Model Analytics & Historical Evaluation

**Status:** Not Started · **Progress:** 0% (0/10) · **Dependencies:** Phases 6, 7

#### Deliverables

- [ ] `/models` screen
- [ ] Metrics from `/models/metrics`
- [ ] Baseline vs advanced comparison
- [ ] Actual-vs-predicted chart
- [ ] Residual distributions
- [ ] Interval coverage per target and bin
- [ ] Historical prediction explorer
- [ ] Backtest vs pregame labelling
- [ ] Release selection
- [ ] Methodology explanation

#### Acceptance criteria

| Criterion | Threshold | Actual | Status |
|---|---|---|---|
| Displayed metrics traceable to evaluation records | 100% | Not measured | Not Verified |
| Fabricated performance values | 0 | Not measured | Not Verified |
| Comparisons on consistent test observations | 100% | Not measured | Not Verified |
| Evaluation records cite model + period | 100% | Not measured | Not Verified |
| Primary targets show MAE and RMSE | All | Not measured | Not Verified |
| Coverage shown for calibrated targets | All | Not measured | Not Verified |
| Backtests distinguished from pregame | Yes | Not measured | Not Verified |
| Analytics integration tests passing | ≥ 95% (100% critical) | Not measured | Not Verified |

**Evidence:** none yet · **Decision:** Not Verified (not started)

---

### Phase 10 — Player Comparison

**Status:** Not Started · **Progress:** 0% (0/9) · **Dependencies:** Phases 4, 5

#### Deliverables

- [ ] Dual player selection (`?p1=&p2=`)
- [ ] `GET /compare/players` endpoint + integration
- [ ] Side-by-side stats
- [ ] Radar chart (league-percentile normalized)
- [ ] Trend overlays
- [ ] Season selection
- [ ] Swap players
- [ ] Mobile layout
- [ ] Accessible chart alternatives

#### Acceptance criteria

| Criterion | Threshold | Actual | Status |
|---|---|---|---|
| Matching season definitions | 100% | Not measured | Not Verified |
| Values match API | 100% | Not measured | Not Verified |
| Swap without page reload | Yes | Not measured | Not Verified |
| Interaction response p95 (non-network) | ≤ 200 ms | Not measured | Not Verified |
| Chart alternatives | All charts | Not measured | Not Verified |
| Critical accessibility violations | 0 | Not measured | Not Verified |
| Mobile overflow outside scroll regions | None | Not measured | Not Verified |
| Comparison workflows passing | ≥ 95% | Not measured | Not Verified |

**Evidence:** none yet · **Decision:** Not Verified (not started)

---

### Phase 11 — Overview, Games & Supporting Screens

**Status:** Not Started · **Progress:** 0% (0/9) · **Dependencies:** Phases 4, 5

#### Deliverables

- [ ] `GET /overview` + `/` screen
- [ ] Featured players and recent performances
- [ ] Upcoming matchups
- [ ] Prediction shortcuts
- [ ] `/games` with date navigation
- [ ] `/games/[id]` matchup detail
- [ ] Completed results and box scores
- [ ] `/about` methodology, data sources, limitations, repository link
- [ ] All routes connected

#### Acceptance criteria

| Criterion | Threshold | Actual | Status |
|---|---|---|---|
| Planned routes implemented | 100% | Not measured | Not Verified |
| Broken internal links | 0 | Not measured | Not Verified |
| Game results traceable to stored records | 100% | Not measured | Not Verified |
| Status labels match backend | 100% | Not measured | Not Verified |
| Actual results distinguished from predictions | 100% | Not measured | Not Verified |
| Supporting-screen E2E passing | ≥ 95% | Not measured | Not Verified |
| Loading, empty and error states on all pages | All | Not measured | Not Verified |

**Evidence:** none yet · **Decision:** Not Verified (not started)

---

### Phase 12 — Accessibility & Usability Audit

**Status:** Not Started · **Progress:** 0% (0/10) · **Dependencies:** Core screens

#### Deliverables

- [ ] WCAG 2.2 AA audit of every route
- [ ] Keyboard-only pass
- [ ] VoiceOver pass for primary workflows
- [ ] Contrast validation of all tokens in both themes
- [ ] 200% zoom and 320 px reflow
- [ ] Chart alternatives verified
- [ ] Reduced-motion verified
- [ ] Loading and error state review
- [ ] Usability fixes in primary workflows
- [ ] `docs/accessibility-report.md` with real results

#### Acceptance criteria

| Criterion | Threshold | Actual | Status |
|---|---|---|---|
| Critical or serious axe violations | 0 | Not measured | Not Verified |
| Primary workflows keyboard-operable | 100% | Not measured | Not Verified |
| Essential controls with accessible names | 100% | Not measured | Not Verified |
| Normal text contrast | ≥ 4.5:1 | Not measured | Not Verified |
| Large text contrast | ≥ 3:1 | Not measured | Not Verified |
| Essential non-text contrast | ≥ 3:1 | Not measured | Not Verified |
| Essential charts with alternatives | 100% | Not measured | Not Verified |
| Nonessential motion respects preference | 100% | Not measured | Not Verified |
| Usable at 200% zoom | All primary screens | Not measured | Not Verified |
| No content loss at 320 px reflow | Yes | Not measured | Not Verified |
| Keyboard traps | 0 | Not measured | Not Verified |
| Manual screen-reader testing | All primary workflows | Not measured | Not Verified |

**Evidence:** none yet · **Decision:** Not Verified (not started)

---

### Phase 13 — Performance, Security & Reliability

**Status:** Not Started · **Progress:** 0% (0/12) · **Dependencies:** Core functionality

#### Deliverables

- [ ] Query profiling (`EXPLAIN ANALYZE` on primary endpoints)
- [ ] N+1 fixes
- [ ] Response-time optimization
- [ ] Cache tuning
- [ ] Image and chart rendering optimization
- [ ] Rate limiting (`slowapi`)
- [ ] CORS validation
- [ ] Secrets in environment only; secret scan
- [ ] Ingestion failure tests
- [ ] Inference failure tests
- [ ] Connection pool limits verified
- [ ] Structured logging and monitoring

#### Acceptance criteria

| Criterion | Threshold | Actual | Status |
|---|---|---|---|
| LCP p75 | ≤ 2.5 s | Not measured | Not Verified |
| INP p75 | ≤ 200 ms | Not measured | Not Verified |
| CLS p75 | ≤ 0.1 | Not measured | Not Verified |
| Successful responses under load test | ≥ 95% | Not measured | Not Verified |
| Critical/high vulnerabilities in prod deps | 0 | Not measured | Not Verified |
| Secrets committed | 0 | Not measured | Not Verified |
| Admin operations publicly reachable | 0 | Not measured | Not Verified |
| Prediction rate limiting | Verified | Not measured | Not Verified |
| Pool within configured limits | Yes | Not measured | Not Verified |
| Failed ingestion corrupts data | Never | Not measured | Not Verified |

**Evidence:** none yet · **Decision:** Not Verified (not started)

---

### Phase 14 — Automated Testing & Integration

**Status:** Not Started · **Progress:** 0% (0/10) · **Dependencies:** Integrated features

#### Deliverables

- [ ] Frontend unit tests
- [ ] Backend unit tests
- [ ] Database integration tests
- [ ] Ingestion tests
- [ ] ML tests
- [ ] Prediction API tests
- [ ] Playwright E2E
- [ ] Full workflow tests
- [ ] `docs/test-report.md` with commands, environment and results
- [ ] `.github/workflows/ci.yml` on pull requests (lint, types, tests, migrations, OpenAPI type diff)

#### Acceptance criteria

| Criterion | Threshold | Actual | Status |
|---|---|---|---|
| Critical-path tests passing | 100% | Not measured | Not Verified |
| Backend business-logic coverage | ≥ 85% | Not measured | Not Verified |
| Frontend business-logic coverage | ≥ 80% | Not measured | Not Verified |
| Migrations tested on clean DB | 100% | Not measured | Not Verified |
| Primary workflows covered by E2E | 100% | Not measured | Not Verified |
| CI on pull requests | Yes | Not measured | Not Verified |
| Failing required checks | 0 | Not measured | Not Verified |
| Known release-blocking defects | 0 | Not measured | Not Verified |

**Evidence:** none yet · **Decision:** Not Verified (not started)

---

### Phase 15 — Deployment & Portfolio Presentation

**Status:** Not Started · **Progress:** 0% (0/14) · **Dependencies:** Release gates

#### Deliverables

- [ ] Backend and frontend Dockerfiles, `docker-compose.yml`
- [ ] Production environment variables (`.env.example` complete)
- [ ] Hosted PostgreSQL
- [ ] FastAPI deployed
- [ ] Next.js deployed
- [ ] Scheduled ingestion from a reachable host
- [ ] Production model loading verified
- [ ] Production prediction smoke test
- [ ] Monitoring
- [ ] README (overview, architecture, setup, testing, data, real results)
- [ ] Architecture diagrams in README
- [ ] Screenshots of the real application
- [ ] Measured model performance documented
- [ ] Live and repository links

#### Acceptance criteria

| Criterion | Threshold | Actual | Status |
|---|---|---|---|
| Frontend and backend deployed | Yes | Not measured | Not Verified |
| Required env vars documented | 100% | Not measured | Not Verified |
| Migrations succeed in deployment | Yes | Not measured | Not Verified |
| `/health` and `/readiness` correct | Yes | Not measured | Not Verified |
| Search, profile, prediction smoke tests | Pass | Not measured | Not Verified |
| Healthy request success, 7-day window | ≥ 99% | Not measured | Not Verified |
| Scheduled ingestion success, 7-day window | ≥ 95% | Not measured | Not Verified |
| Production secrets exposed | 0 | Not measured | Not Verified |
| README complete with real results | Yes | Not measured | Not Verified |
| Screenshots from the actual app | 100% | Not measured | Not Verified |
| Live and repo links functional | Yes | Not measured | Not Verified |

**Evidence:** none yet · **Decision:** Not Verified (not started; the 7-day gates need 7 days of observation)

---

## Session log

### Session — 2026-10-28

**Phase:** 1

**Completed:**
- Confirmed no existing project; created the repository at `~/Desktop/nba-intelligence` and initialized git (no commits yet).
- Installed and started PostgreSQL 16.15; created a Python 3.12 venv with nba_api 1.12.0.
- Probed live nba_api endpoints and recorded data source findings and limitations.
- Wrote the architecture, data-ownership, database, API-contract, model-methodology and frontend documents, plus 6 ADRs.
- Ran the Phase 1 gate checks (26/26 endpoints mapped, 16/16 tables with PK in ER (re-run after sync design), 5 layers in the diagram).

**Files changed:** `docs/**`, `README.md`, `.gitignore`

**Tests run:** none (no code yet). Verification was the probe and doc gate scripts listed under Phase 1.

**Problems encountered:** Docker absent (Homebrew Postgres used instead); no Apple Design Skill available.

**Next step:** owner architecture review, then Phase 2 frontend foundation and the Phase 3 backend scaffold.

### Session — 2026-10-28 (synchronization request)

**Phase:** 1 (design), with deliverables assigned to Phases 3 and 7

**Completed:**
- Inspected the repository: no ingestion, scheduler or prediction code exists yet, so automatic synchronization cannot be implemented or verified this session.
- Designed the synchronization system in `docs/data-synchronization.md`; added `sync_schedules`, `sync_events`, lifecycle columns, lease fields and `supersedes_prediction_id` to `docs/database.md`.
- Added 6 sync deliverables and 9 gates to Phase 3, and 2 deliverables and 1 gate to Phase 7.

**Files changed:** `docs/data-synchronization.md`, `docs/database.md`, `docs/architecture.md`, `docs/implementation-status.md`

**Tests run:** Phase 1 doc gate script re-run (see Phase 1 evidence).

**Problems encountered:** The request assumed existing ingestion foundations; none exist. Implementation is blocked on Phase 3.

**Next step:** Phase 3 backend scaffold and models, including the sync tables.

### Session — 2026-10-28 (Phases 2 and 3)

**Phase:** 3, then 2

**Completed:**
- Backend scaffold, 16 models, migration, NBA client, ingestion, CLI, sync worker and freshness service.
- Backfilled 2018-19 through 2026-27 from stats.nba.com: 11,428 games and 219,230 player lines, with all integrity checks at 0.
- Frontend foundation: tokens, shell, shared accessible components, API client, 7 routes, unit and E2E tests.
- CI workflow (not yet run: no GitHub remote).

**Files changed:** `backend/**`, `frontend/**`, `.github/workflows/ci.yml`, `docs/test-report.md`, this file.

**Tests run:** backend 88 passed; frontend unit 20 passed; Playwright 50 passed, 2 skipped. Details in [test-report.md](test-report.md).

**Problems encountered:**
- Neutral-site games, false corrections and the historical finalization event flood (all fixed with regression tests).
- npm peer conflicts (`@types/node` 20 vs Vitest 5).
- Radix menu focus return after navigation, and a hydration mismatch from runtime `tabindex` (both fixed).
- Creating the GitHub repository was blocked by the session's permission rules, so commits are local only.

**Next step:** Phase 4 read-only API.


### Session — 2026-10-28 (Phase 4)

**Phase:** 4, finishing Phase 2

**Completed:**
- FastAPI app with request ids, error envelope, freshness meta and a data-version cache; 16 read endpoints.
- Shared statistic definitions (`app/stats`) and accent-insensitive player search (migration `3c1d7e9a2b45`).
- OpenAPI schema committed and frontend types generated from it; `PlayerSearch` combobox on `/players`.
- Benchmark: every latency gate passes by at least 3× with the cache off.

**Files changed:** `backend/app/{main.py,api,schemas,services,stats}`, `backend/alembic/versions/`, `backend/tests/{api,unit}`, `backend/scripts/benchmark.py`, `backend/openapi.json`, `frontend/src/{lib/api,components/data,app/players}`, `frontend/tests/`, `.github/workflows/ci.yml`, docs.

**Tests run:** backend 171 passed (92% coverage); frontend unit 27 passed (88.26%); Playwright 57 passed, 3 skipped; contrast 36 / 36.

**Problems encountered:** see the Phase 4 issues table, plus the invisible dark-mode highlight found during the browser check (fixed in the theme tokens).

**Next step:** Phase 5 (Player Explorer and Profile) on the new endpoints, or Phase 6 (ML pipeline).
