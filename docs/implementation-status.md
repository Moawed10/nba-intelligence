# Implementation Status

The authoritative ledger of development progress. A status here is only as good as its evidence. When this document and executable evidence disagree, the evidence wins and this document is corrected (see [data-ownership.md](data-ownership.md#evidence-hierarchy-for-progress-claims)).

**Last updated:** 2026-11-02

## Master status

| Phase | Name | Status | Progress | Blockers |
|---|---|---|---|---|
| 1 | Repository Audit & Architecture | Complete | 100% (8/8) | None |
| 2 | Design System & Foundation | Complete | 100% (12/12) | None |
| 3 | Database, Ingestion & Sync | Complete | 100% (19/19) | None |
| 4 | Core Backend APIs | Complete | 100% (11/11) | None |
| 5 | Player Explorer & Profile | Complete | 100% (11/11) | None |
| 6 | Machine Learning Pipeline | Complete | 100% (13/13) | None |
| 7 | Prediction API & Inference | Complete | 100% (15/15) | None |
| 7B | Player Photos & Team History | Complete | 100% (7/7) | None |
| 8 | Prediction Center | Complete | 100% (12/12) | None |
| 9 | Model Analytics | Complete | 100% (10/10) | None |
| 10 | Player Comparison | Complete | 100% (9/9) | None |
| 11 | Overview & Games | Complete | 100% (9/9) | None |
| 12 | Accessibility Audit | Verification Pending | 90% (9/10) | VoiceOver pass needs a person |
| 13 | Performance & Security | Not Started | 0% (0/12) | Core functionality |
| 14 | Testing & Integration | Not Started | 0% (0/10) | Integrated features |
| 15 | Deployment & Portfolio | Not Started | 0% (0/14) | Release gates |

**Overall:** 145 / 182 verified deliverables = **80%**.

Progress = verified completed deliverables ÷ required deliverables, rounded. Allowed statuses: Not Started, In Progress, Blocked, Verification Pending, Complete. Criterion results: Pass, Fail, Not Verified.

## Milestones

| Milestone | Required phases | Status |
|---|---|---|
| Architecture Ready | 1 | Pass |
| Application Foundation | 2 | Pass |
| Real NBA Data Available | 3–4 | Pass |
| Player Analytics Functional | 5 | Pass |
| ML Models Validated | 6 | Pass |
| Prediction Backend Functional | 7 | Pass |
| Functional MVP | 1–8 + applicable security, accessibility, integration checks | Not Verified |
| Analytics Features Complete | 9–11 | Not Verified (9, 10, 11 in progress) |
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

**Status:** Complete · **Progress:** 100% (19/19) · **Last Updated:** 2026-10-29
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
- [x] `sync_events` outbox and handlers. `GAME_STATS_FINALIZED` scores that game's forecasts (Phase 7).
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
| Finalized-game reconciliation fixtures passing | 100% | Finalization, events and forecast scoring (`test_final_pregame_forecast_is_scored_and_counted_live`) | Pass |
| Cache invalidation on tested dependencies | 100% | Cached responses are keyed by `data_version`; a new succeeded run invalidates them (`test_cache_hits_skip_the_database_until_data_version_changes`, unit tests) | Pass |
| Freshness metadata for synchronized datasets | All 8 | 8 / 8: every prediction response carries a freshness state and reason | Pass |
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

**Result:** Pass. **Reason:** 18 of 18 criteria pass after the Phase 7 handlers.

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

**Status:** Complete · **Progress:** 100% (11/11) · **Last Updated:** 2026-10-28
**Dependencies:** Phases 2, 4
**Objective:** Find any player and read their real season averages, trends, splits and game log, on any screen size and with any input method.

#### Deliverables

- [x] `/players` directory with a server-rendered first page (`app/players/directory.tsx`, 25 per page)
- [x] Autocomplete wired to `/players/search`; choosing a player opens the profile
- [x] Team, position and former-player filters in the URL, with optimistic controls
- [x] Profile header (`/players/[id]`): name, team, position, height, weight, data freshness; title "Name · Players · NBA Intelligence"
- [x] Season averages (`StatTile` rows: 7 per-game stats, FG%, 3P%, FT%, TS% with made–attempted)
- [x] Paged full game log (`DataTable`, 20 per page)
- [x] Trend chart with previous-5 and previous-10 averages (`ChartFrame` with summary sentence and table view)
- [x] Season and stat selectors in the URL (`?season=`, `?stat=`, `?log=`)
- [x] Home/away and rest splits behind a native disclosure
- [x] Loading (streamed `Suspense` sections), empty, error, not-found and stale states
- [x] Playwright + axe workflows (`tests/e2e/players.spec.ts` against a synthetic stub API) and the 100-query search fixture (`tests/live/search-queries.json`, generated by `backend/scripts/search_queries.py`)

The "recent games" block from the original design was folded into the game log, which opens on the most recent games.

#### Acceptance criteria

| Criterion | Threshold | Actual | Status |
|---|---|---|---|
| Relevant results for documented 100 player queries | ≥ 95% | 100 / 100 have the intended player in the top 3 (40 full names, 30 one-letter typos, 30 unique last names; live data) | Pass |
| Search debounce | 200–350 ms | 250 ms; unit test shows no request before 190 ms; live typing at 40 ms per key sends exactly 1 request per query | Pass |
| Search results update p95 | ≤ 500 ms | 336 ms p95, 329 ms p50 from last keystroke to visible results, debounce included (25 live queries) | Pass |
| Profiles match backend statistics | 100% | 175 / 175 per-game values across 25 real players equal the API; stub E2E checks the same on 4 viewports | Pass |
| Filters update the correct data | 100% | Team, position, team + position and former-player filters return the expected row counts and survive reload (E2E) | Pass |
| Broken primary navigation actions | 0 | 0: shell navigation, directory links, search-to-profile, pagination and selectors all pass E2E | Pass |
| Critical accessibility violations | 0 | 0 critical or serious on the directory and profile, both themes, 4 viewports, plus the open search listbox | Pass |
| Horizontal overflow at 375 px | None | 0 px on directory and profile (E2E) | Pass |
| Primary player workflows passing E2E | ≥ 90% | 100%: 48 / 48 player workflow runs (12 tests × 4 viewports) | Pass |

#### Implementation evidence

**Files created:** `frontend/src/app/players/{directory,directory-controls,filters}.tsx/ts`, `src/app/players/[id]/{page,profile,profile-client,stats,not-found,error}.tsx/ts`, `src/components/data/{pagination,api-error}.tsx`, `src/components/shell/with-pathname.tsx`, `src/lib/url.ts`, `tests/e2e/{stub-api.mjs,players.spec.ts}`, `tests/live/*`, `playwright.live.config.ts`, `tests/unit/{url,pagination}.test.ts(x)`, `backend/scripts/search_queries.py`
**Tests added:** 11 unit tests (38 total); 49 E2E runs (109 passed, 3 skipped); 3 live checks. See [test-report.md](test-report.md#phase-5-player-explorer-and-profile).
**Commands executed:** `npm run lint`, `npm run typecheck`, `npx vitest run --coverage` (88.23%), `npx playwright test`, `npx playwright test -c playwright.live.config.ts`, `npm run build` (players routes partially prerendered).

#### Issues and blockers

| Issue | Severity | Impact | Resolution |
|---|---|---|---|
| Top bar overflowed by 8–15 px at 768 px on Linux (found by the first CI run) | Medium (fixed) | Horizontal scroll on tablets | Wordmark hidden at tablet width, tighter link padding; E2E now requires ≥ 24 px spare room |
| CI type-check failed: route types are generated by Next.js | High (fixed) | CI red | `typecheck` runs `next typegen` first |
| Focus landed on the previous page's heading after search navigation | Medium (fixed) | Screen readers announced the wrong page | RouteFocus follows the new heading as it streams in, without stealing focus the user moved |
| Nav read the pathname outside `Suspense`, blocking prerendering of dynamic routes | Medium (fixed) | Next.js 16 error on `/players/[id]` | Pathname read pushed into a small `Suspense` leaf (`WithPathname`) |
| A server component imported a constant from a `"use client"` module | High (fixed) | Directory crashed with filters | Shared constants moved to plain modules |
| Filter checkbox only changed after the server responded | Low (fixed) | Felt unresponsive | `useOptimistic` for filters and selectors |
| A not-found player returns HTTP 200 | Low | The page streams, so the status is sent before the lookup | Content and `noindex` are correct; revisit if SEO matters |

#### Completion decision

**Result:** Complete. **Reason:** 11 / 11 deliverables and 9 / 9 criteria pass with recorded evidence.

---

### Phase 6 — Machine Learning Data Pipeline

**Status:** Complete · **Progress:** 100% (13/13) · **Last Updated:** 2026-10-29
**Dependencies:** Phase 3

#### Deliverables

- [x] `app/ml/dataset.py`: training frame from PostgreSQL at a recorded `data_version`
- [x] `app/ml/features.py`: 60 features. Every history is joined strictly before the game (`merge_asof`, no exact matches), and source dates are carried so leakage can be counted
- [x] Rolling 3/5/10, season-to-date (with previous-season fallback) and trend features
- [x] Opponent defense and pace, own pace, home/away, and a shrunk history against the opponent
- [x] Rest and back-to-back features from schedule dates
- [x] Leakage tests: fixture, perturbation, split boundary, opponent and history source dates
- [x] Chronological splits (`app/ml/splits.py`; overlapping plans raise)
- [x] Rolling baseline (previous 10 games)
- [x] Ridge, Random Forest and XGBoost per target (`app/ml/models.py`)
- [x] MAE / RMSE / R² per target, per algorithm, per season and per season type
- [x] Mondrian split-conformal intervals and test coverage (`app/ml/conformal.py`)
- [x] Double-double classifier with isotonic calibration (`app/ml/classifier.py`)
- [x] Artifacts (SHA-256, feature schema, library versions), registry rows and a reproducibility test (`app/ml/artifacts.py`, `app/ml/train.py`, `python -m app.cli train`)

#### Acceptance criteria

| Criterion | Threshold | Actual | Status |
|---|---|---|---|
| Detected future-data leakage | 0 | 0 of 218,346 rows (source-date check on every row), plus perturbation and fixture tests | Pass |
| Rolling features exclude target game | 100% | 100%: fixture test against independent means; perturbing game *k* onward changes no feature at *k* | Pass |
| Partitions chronological | 100% | Train ends 2024-06-17; validation runs 2024-10-22 to 2025-06-22; test starts 2025-10-21 | Pass |
| Model families implemented | 4 / 4 | Baseline, Ridge, Random Forest and XGBoost on every target | Pass |
| Targets evaluated (pts, reb, ast minimum) | ≥ 3 | 7 regression targets plus double-double | Pass |
| MAE, RMSE, R² reported for every target × model | 100% | 28 / 28 on validation and test, stored as `model_evaluations` | Pass |
| Retraining reproducible within tolerance | 1e-6 / 1e-3 (XGB) | An automated test trains twice and every target and family agrees within tolerance (synthetic league). The full-scale real-data rerun was stopped before it finished | Pass |
| Artifacts with version + schema metadata | 100% | All 16 persisted artifacts carry the release, feature schema hash, features and library versions; loading verifies the SHA-256 and the schema | Pass |
| 80% interval empirical coverage | 75–85% | 79.5–82.3% per target; 78.5–83.6% per minutes bin (test season) | Pass |
| Advanced vs baseline on same observations | Yes | Every family is scored on the same 27,999 test rows; `baseline_mae` is stored with each evaluation | Pass |
| Research objective: test MAE reduction vs baseline | ≥ 5% on ≥ 1 target | Minutes 7.0%; points 2.9%, rebounds 2.8%, steals 2.7%, assists 2.6%, 3PM 1.6%, blocks 0% (baseline selected) | Pass (research objective) |

#### Implementation evidence

**Files created:**
- `backend/app/ml/{dataset,features,splits,models,classifier,conformal,metrics,artifacts,train}.py`
- `tests/ml_fixtures.py`, `tests/unit/test_ml_{features,training}.py`, `tests/integration/test_ml_registry.py`, `tests/api/test_ml_dataset.py`
- the `train` CLI command

**Tests added:** 21. See [test-report.md](test-report.md#phase-6-machine-learning-pipeline).
**Commands executed:** `pytest` (197 passed); `python -m app.cli train` (release `2026.10.29-1`, 663 s).

#### Issues and blockers

| Issue | Severity | Impact | Resolution |
|---|---|---|---|
| `is_home` was both an identifier and a feature, which duplicated a column | High (fixed) | Would have broken model fitting | Identity columns now exclude features; covered by tests |
| XGBoost needs the OpenMP runtime on macOS | Low (fixed) | Import failed | `brew install libomp`; the Linux CI wheels include it |
| Gains over the baseline are modest except for minutes | Informational | Most box-score variance is game-to-game noise the features can't see (no injury, lineup or betting-line data) | Reported as measured |
| The release was trained from a working tree with uncommitted Phase 6 code | Low | `git_sha` alone doesn't identify the code | Recorded as `git_dirty: true`; the code was committed immediately after; retrain from a clean tree before activation in Phase 7 |

#### Completion decision

**Result:** Complete. **Reason:** 13 / 13 deliverables and 11 / 11 criteria pass, with recorded evidence.

---

### Phase 7 — Prediction API & Inference Engine

**Status:** Complete · **Progress:** 100% (15/15) · **Dependencies:** Phases 4, 6

#### Deliverables

- [x] Artifact loader with SHA-256 and schema checks
- [x] Inference service (bounded thread pool)
- [x] Player and matchup validation
- [x] Pregame feature snapshot at `min(now, tipoff_at)`
- [x] Predictions for all 7 regression targets
- [x] Conformal intervals at inference
- [x] Double-double probability
- [x] Append-only persistence (`predictions`, `prediction_values`)
- [x] Snapshot-hash reuse (the prediction cache)
- [x] `POST /predictions`, `GET /predictions/{id}`, `/history`, `/explanation`
- [x] Error handling: `insufficient_data`, `invalid_matchup`, `game_already_started`, `model_unavailable`
- [x] Prediction API, reproducibility and immutability tests
- [x] Prediction freshness service (current/stale/invalid/superseded/final_pregame)
- [x] Dependency-aware refresh inserting superseding rows, stopping at tip-off
- [x] Team logos in place of abbreviation monograms (owner request, 2026-10-29): fetched once into `frontend/public/logos/{team_id}.svg` by a script, served by the app (never hotlinked from nba.com), used by `TeamMark` with the team name as alt text and the monogram as fallback

#### Acceptance criteria

| Criterion | Threshold | Actual | Status |
|---|---|---|---|
| Valid fixtures produce correct responses | 100% | 13 / 13 prediction tests (`tests/api/test_predictions.py`) | Pass |
| Invalid player/game combos return proper errors | 100% | 5 / 5 cases: invalid matchup, final game, after tip-off, too few games, unknown player | Pass |
| Predictions reference valid model versions | 100% | Foreign key to `model_releases`; version returned on every response | Pass |
| Predictions with data cutoff timestamp | 100% | Non-null column with a cutoff ≤ creation check | Pass |
| Training operations during inference | 0 | 0: the request path only loads artifacts and calls `predict` | Pass |
| Inference p95, loaded model | < 1.5 s | 69 ms over 1,000 real requests (first call, which loads artifacts: 1.07 s) | Pass |
| Success across 1,000 valid requests | ≥ 99% | 936 / 936 eligible requests; 64 correctly refused as `insufficient_data` | Pass |
| Same model + snapshot reproduces values | Within 1e-9 | 0.0 across 57 real forecasts (after the full-precision snapshot fix) | Pass |
| Silently overwritten predictions | 0 | 0: changed inputs append a superseding row; test checks the old row is unchanged | Pass |
| New pregame predictions after tip-off | 0 | 0: refused with 409 `game_already_started` (tested) | Pass |

**Evidence:** `backend/app/ml/inference.py`, `backend/app/services/{predictions,prediction_lifecycle}.py`, `backend/app/sync/worker.py` (`predictions` job every 15 min and the `GAME_STATS_FINALIZED` handler), `backend/tests/api/test_predictions.py` (22 tests). Release `2026.10.29-2` was retrained from a clean commit and activated. Inference runs at most 4 at a time (`inference_busy` after 10 s). Explanations are at `GET /predictions/{id}/explanation`, and live accuracy at `GET /models/{version}/live`. A forecast older than 12 h whose inputs are unchanged stays `current`, since the same model and snapshot give the same forecast. Age only triggers a recheck. · **Decision:** Pass
---

### Phase 7B — Player Photos & Team History

**Status:** Complete · **Progress:** 100% (7/7) · **Dependencies:** Phases 3, 4, 5 · Owner request, 2026-10-29

#### Deliverables

- [x] Player photo cache: the backend fetches each photo once from the NBA CDN on first request, stores it on disk outside git (about 95 MB for all 5,197 players at 260×190), and serves it with long cache headers; the browser never contacts nba.com
- [x] `PlayerAvatar` shows the photo for current and former players, with initials when the source has no photo
- [x] Historical backfill for seasons before 2018-19, as far back as the source provides (season totals per franchise from `TeamYearByYearStats`, not individual game logs: 1,717 team-seasons from 1946-47)
- [x] Team identity per season (name, city and abbreviation as they were that year, e.g. 2007-08 Seattle SuperSonics)
- [x] Team statistics for any covered season; possession-based numbers (pace, ratings) marked unavailable for seasons whose source lacks turnovers or offensive rebounds (to be verified per season)
- [x] Team comparison: any two team-seasons side by side (`?t1=&s1=&t2=&s2=`), record, scoring, shooting and ratings, with a table equivalent
- [x] API and E2E tests, including photo fallback and early-era unavailable states

#### Acceptance criteria

| Criterion | Threshold | Actual | Status |
|---|---|---|---|
| Browser requests to nba.com | 0 | 0: logos are bundled and photos come from `/api/v1/players/{id}/photo`; no nba.com URL in frontend code | Pass |
| Players showing a photo or an initials fallback | 100% | Photo when the source has one (former players included, e.g. Michael Jordan), initials on 404; tested | Pass |
| Team-season values match stored game logs | 100% | Values come straight from the source's season totals; transform and API tests; spot checks (1978-79 SuperSonics 52-30 champions, 2015-16 Warriors 73-9) | Pass |
| Seasons with unavailable stats labelled, not estimated | 100% | Zeros meaning "not recorded" stored as NULL and shown as —; explained on the page | Pass |
| Comparison state survives reload and sharing | Yes | `?t1=&s1=&t2=&s2=`; E2E on 4 viewports | Pass |

**Evidence:** `backend/app/services/photos.py`, `backend/app/ingestion/{jobs,transforms}.py` (`ingest team-history`), migration `9557f53a4198`, `frontend/src/app/compare/teams/`, `tests/api/test_{photos,team_history}.py`, `tests/e2e/compare-teams.spec.ts`. What the source records: turnovers and offensive rebounds from 1973-74, 3-pointers from 1982-83, pace and ratings from 1996-97. Only the 30 current franchises' histories are included, not defunct teams. · **Decision:** Pass

---

### Phase 8 — Prediction Center Frontend

**Status:** Complete · **Progress:** 100% (12/12) · **Dependencies:** Phases 2, 7

#### Deliverables

- [x] Player selection (`?player=`)
- [x] Upcoming game selection
- [x] Submit to `POST /predictions`, duplicate-safe
- [x] Predicted values (`StatTile`)
- [x] Interval display (`IntervalBar`) labelled "likely range (80%)"
- [x] Last-5 and season comparisons
- [x] Prediction distribution visualization (forecast range over the player's real last 20 games)
- [x] Explanation panel
- [x] Model release and data cutoff display
- [x] Loading, error and named unavailable states
- [x] Keyboard-only workflow
- [x] Mobile layout

#### Acceptance criteria

| Criterion | Threshold | Actual | Status |
|---|---|---|---|
| Workflow steps functional | 100% | Pick player, pick game, forecast, range chart, explanation all pass | Pass |
| Successful automated workflows (100 runs) | ≥ 95% | 200/200 (keyboard workflow and forecast workflow, 100 each) | Pass |
| Displayed values match API | 100% | Forecast values and chart counts asserted against the API | Pass |
| Intervals state their meaning | 100% | "Usually 16–32", "about 4 games out of 5", chart caption | Pass |
| Unavailable predictions explained | 100% | Too few games, no serving release, unknown player | Pass |
| Render after API response p95 | ≤ 500 ms | 8 ms (20 game switches, production build, desktop) | Pass |
| Critical accessibility violations | 0 | 0 (axe, both themes, 4 viewports) | Pass |
| Full keyboard workflow | Yes | Search → game → statistic → explanation, keys only | Pass |
| Horizontal overflow at 375 px | None | None | Pass |

**Evidence:** `frontend/src/app/predict/`, `tests/e2e/predict.spec.ts` (16 runs across 4 viewports; axe serious/critical 0 in both themes; no overflow at 375 px). The forecast panel states that no release is serving predictions instead of showing a number. Forecasts render with `IntervalBar` ranges; the explanation shows the averages the model received, labelled as inputs rather than attributions. The range chart plots real games only, with the forecast and its 80% band on top; nothing is simulated. · **Decision:** Pass

---

### Phase 9 — Model Analytics & Historical Evaluation

**Status:** Complete · **Progress:** 100% (10/10) · **Dependencies:** Phases 6, 7

#### Deliverables

- [x] `/models` screen
- [x] Metrics from `/models/metrics`
- [x] Baseline vs advanced comparison
- [x] Actual-vs-predicted chart
- [x] Residual distributions
- [x] Interval coverage per target and bin
- [x] Historical prediction explorer
- [x] Backtest vs pregame labelling
- [x] Release selection
- [x] Methodology explanation

#### Acceptance criteria

| Criterion | Threshold | Actual | Status |
|---|---|---|---|
| Displayed metrics traceable to evaluation records | 100% | Stored backtests reproduce the registry's test n, MAE and coverage exactly for all 7 stats; analytics are computed from stored evaluations (asserted in tests) | Pass |
| Fabricated performance values | 0 | 0: every chart comes from stored, scored predictions; empty states when none exist | Pass |
| Comparisons on consistent test observations | 100% | Algorithms and backtests use the same 27,999 test-season player-games | Pass |
| Evaluation records cite model + period | 100% | Analytics return release, algorithm and first/last game | Pass |
| Primary targets show MAE and RMSE | All | All 7 statistics | Pass |
| Coverage shown for calibrated targets | All | Overall and per predicted-minutes bin, all 7 statistics | Pass |
| Backtests distinguished from pregame | Yes | Stored `kind`, separate toggle and a stated note on both panels | Pass |
| Analytics integration tests passing | ≥ 95% (100% critical) | 100% (6 backend, 2 new E2E × 4 viewports) | Pass |

**Evidence:** `backend/app/ml/backtest.py` (`app.cli backtest <version>`), `GET /models/{version}/analytics`, `GET /predictions/history`, `backend/tests/api/test_model_analytics.py`, `frontend/src/app/models/analytics.tsx`, `tests/e2e/models.spec.ts`. Backtests come from the release's held-out models (trained before the test season, calibrated on validation) and are labelled as such; live pregame forecasts are a separate kind. · **Decision:** Pass

---

### Phase 10 — Player Comparison

**Status:** Complete · **Progress:** 100% (9/9) · **Dependencies:** Phases 4, 5

#### Deliverables

- [x] Dual player selection (`?p1=&p2=`)
- [x] `GET /compare/players` endpoint + integration
- [x] Side-by-side stats
- [x] Radar chart (league-percentile normalized)
- [x] Trend overlays
- [x] Season selection
- [x] Swap players
- [x] Mobile layout
- [x] Accessible chart alternatives

#### Acceptance criteria

| Criterion | Threshold | Actual | Status |
|---|---|---|---|
| Matching season definitions | 100% | Both lines come from the same regular-season aggregation as `/players/{id}/stats` (asserted equal) | Pass |
| Values match API | 100% | Radar table percentiles asserted against `/compare/players` | Pass |
| Swap without page reload | Yes | Swap and season change are client navigations (E2E) | Pass |
| Interaction response p95 (non-network) | ≤ 200 ms | 69 ms (chart/table toggle, 20 runs) | Pass |
| Chart alternatives | All charts | Radar and form chart each have a table view and a text summary | Pass |
| Critical accessibility violations | 0 | 0 (axe, both themes, 4 viewports) | Pass |
| Mobile overflow outside scroll regions | None | None | Pass |
| Comparison workflows passing | ≥ 95% | 155/155 (Compare suite × 5 runs × 4 viewports) | Pass |

**Evidence:** `backend/app/services/compare.py`, `GET /compare/players`, `backend/tests/api/test_compare.py`, `frontend/src/app/compare/`, `tests/e2e/compare.spec.ts`. Percentiles rank players with at least 40% of their team's games and 10 minutes per game that season; the page states the rule and the pool size, and flags a player below it. · **Decision:** Pass

---

### Phase 11 — Overview, Games & Supporting Screens

**Status:** Complete · **Progress:** 100% (9/9) · **Dependencies:** Phases 4, 5

#### Deliverables

- [x] `GET /overview` + `/` screen
- [x] Featured players and recent performances
- [x] Upcoming matchups
- [x] Prediction shortcuts (each upcoming game lists both teams' leading scorers, linked to their forecast for that game)
- [x] `/games` with date navigation
- [x] `/games/[id]` matchup detail
- [x] Completed results and box scores
- [x] `/about` methodology, data sources, limitations, repository link (shown when `NEXT_PUBLIC_REPOSITORY_URL` is set; the repository is private for now)
- [x] All routes connected

#### Acceptance criteria

| Criterion | Threshold | Actual | Status |
|---|---|---|---|
| Planned routes implemented | 100% | `/`, `/players`, `/players/[id]`, `/predict`, `/compare`, `/models`, `/games`, `/games/[id]`, `/about` | Pass |
| Broken internal links | 0 | 0 of 56 crawled links (`shell.spec.ts`) | Pass |
| Game results traceable to stored records | 100% | Scores and box scores render from `/games` and `/games/{id}/boxscore` (asserted in E2E) | Pass |
| Status labels match backend | 100% | Labels map each backend status (final, in progress, postponed, cancelled, scheduled time) | Pass |
| Actual results distinguished from predictions | 100% | Predicted scores are labelled "Our prediction" and announced as predicted; finals show the real score | Pass |
| Supporting-screen E2E passing | ≥ 95% | 100% (overview, games, shell suites) | Pass |
| Loading, empty and error states on all pages | All | Each page has loading, empty and error views (covered by E2E) | Pass |

**Evidence:** `frontend/src/app/page.tsx`, `frontend/src/app/_overview/`, `frontend/src/app/games/`, `frontend/src/app/about/`, `GET /leaders?team_id=`, `tests/e2e/{overview,games,shell}.spec.ts`. · **Decision:** Pass

---

### Phase 12 — Accessibility & Usability Audit

**Status:** Verification Pending · **Progress:** 90% (9/10) · **Dependencies:** Core screens

#### Deliverables

- [x] WCAG 2.2 AA audit of every route (15 routes and states × 4 viewports × 2 themes)
- [x] Keyboard-only pass
- [ ] VoiceOver pass for primary workflows (an accessibility-tree review was done instead; a person still needs to listen)
- [x] Contrast validation of all tokens in both themes
- [x] 200% zoom and 320 px reflow
- [x] Chart alternatives verified
- [x] Reduced-motion verified
- [x] Loading and error state review
- [x] Usability fixes in primary workflows
- [x] `docs/accessibility-report.md` with real results

#### Acceptance criteria

| Criterion | Threshold | Actual | Status |
|---|---|---|---|
| Critical or serious axe violations | 0 | 0 (and 0 moderate or minor) in 118 page × viewport × theme runs | Pass |
| Primary workflows keyboard-operable | 100% | Predictions, Compare, Games, Models and the shell covered with keys only | Pass |
| Essential controls with accessible names | 100% | axe name rules pass; the accessibility-tree review found no unnamed control | Pass |
| Normal text contrast | ≥ 4.5:1 | All text pairs pass in both themes (`check:contrast`) | Pass |
| Large text contrast | ≥ 3:1 | Covered by the 4.5:1 text pairs | Pass |
| Essential non-text contrast | ≥ 3:1 | Focus ring, chart colors, selected segment and control boundaries (new `--input` token) pass | Pass |
| Essential charts with alternatives | 100% | 6 charts with table views and summaries; 3 graphics with `role="img"` labels | Pass |
| Nonessential motion respects preference | 100% | Reduced-motion E2E passes | Pass |
| Usable at 200% zoom | All primary screens | 0 px overflow at the 640 px equivalent layout, all 15 pages | Pass |
| No content loss at 320 px reflow | Yes | 0 px overflow at 320 px, all 15 pages | Pass |
| Keyboard traps | 0 | 0 across 45 page × viewport keyboard passes | Pass |
| Manual screen-reader testing | All primary workflows | Not done: accessibility-tree review only | Not Verified |

**Evidence:** `docs/accessibility-report.md`, `frontend/tests/e2e/a11y-audit.spec.ts`, `frontend/scripts/check-contrast.mjs`. · **Decision:** Verification Pending (manual VoiceOver pass)

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

### Session — 2026-10-28 (Phase 5)

**Phase:** 5

**Completed:**
- Player directory with URL filters and pagination; profile with averages, trend chart, splits and paged game log.
- E2E against a synthetic stub API; live checks against the real API (search relevance, search latency, profile values).
- First CI runs: fixed the generated-types type-check failure and a Linux-only top bar overflow.

**Files changed:** `frontend/src/{app/players,components,lib}`, `frontend/tests/{e2e,live,unit}`, `frontend/{playwright.config.ts,playwright.live.config.ts,next.config.ts,tsconfig.json,eslint.config.mjs,.prettierrc.json}`, `backend/scripts/search_queries.py`, docs.

**Tests run:** frontend unit 38 passed; Playwright 109 passed, 3 skipped; live 3 / 3; backend unchanged at 171 passed.

**Problems encountered:** see the Phase 5 issues table.

**Next step:** Phase 6, the ML data pipeline.

### Session — 2026-10-29 (Phase 6, redesign start)

**Phase:** 6, then the product redesign ([redesign-plan.md](redesign-plan.md))

**Completed:**
- Built the ML pipeline, then trained and registered the first candidate release, `2026.10.29-1`, on real data.
- Added read-only endpoints for the redesign:
  - `/overview`, `/leaders`, `/standouts`, `/models` and `/models/{version}`;
  - season averages and stat sorting in `/players`;
  - team colors on every team reference (migration `5d2e8b1c7a90`).
- Wrote the redesign audit and plan.
- Switched to Geist typography and a refined dark palette (36 / 36 contrast pairs pass).

**Tests run:** backend 197 passed; frontend type-check clean.

**Next step:** redesign phases 2–9.

### Session — 2026-10-29 (redesign phases 5–9)

**Phase:** product redesign ([redesign-plan.md](redesign-plan.md)); advances master Phases 8–11

**Completed:**
- Overview command center: schedule board with date navigation and matchups, league leaders by category, Game Score standouts, held-out model accuracy, data freshness.
- Compare: two-player head to head in `?p1=&p2=&season=`, category leads, season-average form chart with a table equivalent.
- Models: release timeline, accuracy against the baseline, algorithm comparison, prediction-range widths, double-double scores, feature inventory, release history.
- Predictions: player and upcoming-game workflow with real form, rest and opponent context; an explicit "not serving" state instead of a forecast.
- Games: schedule, results and full box scores by date; the last placeholder route is gone.
- Fixed the Linux-only CI layout failures (position filter width, top-bar slack measurement) and a label-in-name accessibility issue on game chips.

**Files changed:** `frontend/src/app/{page.tsx,_overview,compare,models,predict,games,players}`, `frontend/src/components/data/{compare-bar,segmented-control}.tsx`, `frontend/src/lib/{models,api/types}.ts`, `frontend/tests/e2e/**`, docs.

**Tests run:** frontend unit 38 passed; Playwright 204 passed, 4 skipped (4 viewports, both themes); lint and type-check clean.

**Problems encountered:** the real-data reproducibility rerun from the previous session was not repeated; the candidate release was trained from a dirty tree and must be retrained from a clean commit before activation.

**Next step:** Phase 7 inference API, then forecasts, intervals and prediction history in the Predictions and Models screens.

### Session — 2026-10-29 (Phase 7)

**Phase:** 7, plus the Phase 8 forecast display

**Completed:**
- Team logos for all 30 teams, served by the app from `public/logos` (owner request).
- Retrained from a clean commit: release `2026.10.29-2`, metrics identical to `-1`. Activated with the new `activate` CLI command.
- Inference service, `POST /predictions`, `GET /predictions`, `GET /predictions/{id}`, and append-only storage with snapshot reuse and superseding.
- The Predictions page shows stored forecasts with 80% ranges, inputs and the double-double chance, and makes a forecast on request.
- Found and fixed a reproducibility bug: snapshots were stored rounded while the model saw full precision.

**Tests run:** backend 210 passed; frontend lint, type-check and unit tests clean; Playwright 208 passed, 4 skipped; 1,000-request real-data run.

**Next step:** prediction freshness and refresh before tip-off, scoring stored predictions after games (the Phase 3 evaluation handlers), and live accuracy on the Models page.

### Session — 2026-10-29 (Phase 7B)

**Phase:** 7B (owner request)

**Completed:**
- Player photos for current and former players, cached by the API on first view.
- History for every franchise since 1946-47 under each season's name, plus pace and ratings from 1996-97.
- Team comparison at `/compare/teams`, with Players/Teams tabs.
- The Warriors had been shown as "San Francisco" across the app because of nba_api's static list; they now show as Golden State.
- The mobile tab bar is more opaque, so its labels keep contrast over colored content.

**Tests run:** backend 221 passed; frontend lint, type-check and 38 unit tests clean; Playwright 228 passed, 4 skipped; 36 / 36 contrast pairs.

**Next step:** the rest of Phase 7 (forecast refresh and post-game scoring).

### Session — 2026-10-29 (Phase 7 completion)

**Phase:** 7, which also closes Phase 3

**Completed:**
- Prediction freshness (current, stale, invalid, superseded, final pregame) on every prediction response, with a reason.
- A `predictions` worker job (every 15 min): scores finished games, then re-forecasts stale predictions for games in the next 48 h. It runs under its own advisory lock and does not advance `data_version`.
- The `GAME_STATS_FINALIZED` handler scores a game's forecasts as soon as its box score is stable.
- `GET /predictions/{id}/explanation`, `GET /models/{version}/live`, a 4-slot inference limit, and the `app.cli predictions` command.
- The Predictions page shows freshness with an "Update forecast" action and, once scored, the actual results. The Models page shows live accuracy once games are scored.

**Real data:** the job checked 47 stored forecasts for games in the next 48 h in about 5 s. None were stale or scorable yet, since those games haven't been played.

**Tests run:** backend 230 passed; frontend lint, type-check and 38 unit tests clean; Playwright 228 passed, 4 skipped.

**Next step:** Phase 9 analytics that need scored forecasts (actual vs predicted, residuals, history explorer), and the Phase 8 distribution chart and keyboard check.

### Session — 2026-10-29 (game scores and career history)

**Requested:** predict team scores against each other in plain language, and show every season players have played, former players included.

**Completed:**
- Game score model (`app/ml/team_model.py`): each team's points from both teams' form before the game, plus a home win chance calibrated on the predicted margin. Registered in release `2026.10.29-3` (trained from clean commit `d29f491`), now active.
- `POST /predictions/games`: stored, append-only score forecasts for scheduled games (snapshot dedupe, supersede on new data). For a game it can't forecast, it says why.
- Games and Overview show predicted scores on upcoming games, and a plain-language panel: who is favored and by how much, each side's win chance, a typical range, and what the prediction looks at.
- Career history: a `player_seasons` table from PlayerCareerStats (regular season and playoffs, back to 1946-47). The `app.cli ingest careers` command runs in resumable batches, and a daily `careers` worker job refreshes active players. `GET /players/{id}/career` serves it, with `career_history` freshness.
- Player pages have a Career table (sortable, with team logos and a career row). Former players without box scores show career averages in the hero.
- Fixed a sideways page scroll caused by screen-reader text escaping scroll containers (game strip, data tables).

**Real data:**
- Game model, 2025-26 test season: 9.65 points MAE vs 10.51 for the baseline. It picked the winner 66.8% of the time (55.4% for "home team wins"). Brier score 0.208 vs 0.247. 77.8% of scores landed inside the 80% ranges.
- Kareem Abdul-Jabbar's stored career matches the record: 1,560 games, 24.6 / 11.2 / 3.6, 55.9% FG, 38,387 points.
- Steals, blocks, turnovers and threes stay empty before the league recorded them, and career averages for them are labelled with the season they start.

**Tests run:** backend 251 passed; frontend lint, type-check and 38 unit tests clean; Playwright 248 passed, 8 skipped.

**Next step:** finish the all-player career backfill (running) and confirm CI.

### Session — 2026-10-29 (Phase 8)

**Completed:**
- Prediction distribution view: the forecast and its 80% range drawn over the player's last 20 real games, with points, rebounds and assists. It says in plain words how many of those games landed in the range. It uses real game logs only; the model gives a point and an interval, so no distribution is invented.
- A keyboard-only workflow, verified end to end: search, choose a game, switch statistic, open the explanation.

**Real data:** Luka Dončić @ Golden State: forecast 31.2 points, range 22–40. He finished inside that range in 11 of his last 20 games.

**Tests run:** Playwright 255 passed, 9 skipped; the keyboard and forecast workflows passed 200/200 repeated runs; frontend lint and 38 unit tests clean.

**Render time:** p95 8 ms from the forecast response to the forecast on screen, over 20 game switches (`predict.spec.ts`). Phase 8 is complete.

**Next step:** Phase 9 (Model Analytics).

### Session — 2026-10-29 (Phase 9)

**Completed:**
- Backtests: `app.cli backtest 2026.10.29-3` stored and scored 27,999 test-season predictions (1,321 games, 2025-10-21 to 2026-06-13) in 20 s. These come from the held-out models, which never saw that season. For all 7 stats they reproduce the registry's held-out n, MAE and 80% coverage exactly.
- `GET /models/{version}/analytics` (predicted vs actual by tenth, misses, coverage per minutes bin) and `GET /predictions/history` (a player's predictions next to the box score, labelled backtest or pregame).
- Models page:
  - **"Check the predictions":** three charts, each with a table view and a plain-language summary.
  - **"Prediction history":** search any player, then switch between test-season backtests and live forecasts.

**Real data:**
- Points, 2025-26: average miss 4.5, RMSE 5.9, 80.1% inside the range. Coverage by minutes bin: 79.3%, 80.4%, 80.5%. Calibration is within 0.5 points in every tenth.
- Nikola Jokić: points inside the range in 23 of his last 30 backtested games.

**Tests run:** backend 259 passed; Playwright 266 passed, 10 skipped; lint, 38 unit tests and contrast clean.

**Next step:** Phase 10 (Player Comparison: radar chart and a dedicated endpoint).

### Session — 2026-10-29 (Phase 10)

**Completed:**
- `GET /compare/players?p1=&p2=&season=`: both players' season lines (the same aggregation as the player pages), their common seasons, and league percentiles on seven axes. The axes are scoring, rebounding, playmaking, 3-point shooting, steals, blocks and efficiency (true shooting). It refuses the same player twice and an unshared season.
- The Compare page now loads from this endpoint. It adds a "Strengths" panel: a radar chart with a plain-language summary, a table view, and the qualification rule.

**Real data:** Dončić vs Jokić opens on 2025-26 (the latest season both played 10+ games), ranked against 374 qualified players. Dončić leads 3 areas, Jokić 4. The biggest gap is 3-point shooting, where Dončić is in the 100th percentile.

**Tests run:** backend 267 passed; Playwright 273 passed; Compare suite 155/155 repeated; toggle p95 69 ms; lint, unit and contrast clean.

**Next step:** Phase 11 (Overview, Games and supporting screens).

### Session — 2026-10-29 (Phase 11)

**Completed:**
- Prediction shortcuts: every upcoming matchup lists both teams' three leading scorers (`GET /leaders?team_id=`), each linking to that player's forecast for that game.
- A `/games/[id]` page with the matchup, score prediction, shortcuts and full box score, a not-found page, and a "Game page" link from every matchup.
- About rewritten to match what the app does now: data sources, career coverage back to 1946-47, game score predictions, model checking, and stats that weren't recorded yet. It also adds a "Built with" note and a repository link that appears only once `NEXT_PUBLIC_REPOSITORY_URL` is set.

**Real data:** Portland @ Utah (Oct 31): Trail Blazers favored by about 7 (123–115, 74%). Portland's shortcuts are Deni Avdija, Damian Lillard and Ja Morant.

**Career backfill:** stats.nba.com throttled again; the job stopped cleanly at 785 of 5,197 players and was resumed with a 4 s interval.

**Tests run:** backend 268 passed; Playwright 288 passed; 56 internal links crawled with none broken; lint, unit and contrast clean.

**Next step:** Phase 12 (Accessibility & Usability Audit).

### Session — 2026-10-30 (Phase 12)

**Completed:**
- An audit spec covering 15 routes and states at four viewports and in both themes: axe WCAG 2.2 AA, a keyboard focus and trap pass, and 640 px (200% zoom) and 320 px reflow. Results are in `docs/accessibility-report.md`.
- Fixes:
  - visible keyboard focus on the Predictions game list and the Models section rail
  - a 3:1 `--input` token for text-field and control boundaries (was 1.42:1 light, 1.34:1 dark)
  - nested chart headings at level 3
  - screen-reader wording on the Predictions player card, game list and range chart
- The contrast check grew from 36 to 46 pairs, all passing.

**Results:** 0 axe violations of any impact; 0 keyboard traps or invisible focus states; 0 px overflow in 90 reflow runs.

**Not verified:** VoiceOver. An accessibility-tree review of six primary screens was done instead and is recorded as such.

**Next step:** a person runs VoiceOver through Predictions, Compare and Games; then Phase 13.

### Session — 2026-11-02 (visual redesign)

**Phase:** cross-cutting redesign, no new deliverables counted

**Completed:** full-width team-colored features, open sections instead of cards, two-pane schedule, split scoreboards and Compare hero, player dossier with recent games and next-game forecast, new display type and data labels, in both themes. Direction and references are in [frontend.md](frontend.md#design-references). Milestone labels (triple-double) now come from the box score.

**Verified:** lint, types, 39 unit tests, contrast (54 pairs), production build, full Playwright suite including the accessibility audit on 4 viewports (478 passed, 42 skipped by design). Real data inspected at 390, 768 and 1440 px.

**Not verified:** VoiceOver (still open from Phase 12); real-browser zoom.

