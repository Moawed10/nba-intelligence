# Data Ownership & Source of Truth

Every piece of information in NBA Intelligence has exactly one authoritative owner. Other components may cache, transform or display it, but they never redefine it.

## Source-of-truth matrix

| Information | Authoritative source | Written by | Read by |
|---|---|---|---|
| Official NBA statistics | stats.nba.com (via `nba_api`) | NBA | Ingestion only |
| Player and team records | PostgreSQL `players`, `teams` | Ingestion | API, ML |
| Historical game logs | PostgreSQL `player_game_stats`, `team_game_stats` | Ingestion | API, ML |
| Schedules and results | PostgreSQL `games` | Ingestion | API, ML |
| Data freshness | PostgreSQL `ingestion_runs` | Ingestion | API (`/data-status`, `meta.data_freshness`) |
| Source corrections | PostgreSQL `source_corrections` | Ingestion | API, audits |
| Application statistic definitions | `backend/app/stats/` | Backend | API services, ML features |
| Model features | `backend/app/ml/features.py`, versioned by `feature_schema_version` | ML pipeline | Training, inference |
| Model artifacts | `ARTIFACTS_DIR`, verified by SHA-256 | ML pipeline | Inference |
| Model metadata, active model | PostgreSQL `model_releases`, `model_versions` | ML pipeline | API |
| Evaluation results | PostgreSQL `model_evaluations`, `prediction_evaluations` | ML pipeline | API |
| Generated predictions | PostgreSQL `predictions`, `prediction_values` (append-only) | API (pregame), ML (backtest) | API |
| API contracts | FastAPI Pydantic schemas → generated OpenAPI | Backend | Frontend (generated types) |
| Frontend server data | API responses through `frontend/src/lib/api` | API | Components |
| Shareable selections and filters | URL query parameters | Frontend | Frontend |
| Transient UI state | Local React state | Frontend | Same component tree |
| Development progress | [implementation-status.md](implementation-status.md), backed by evidence | Developer | Everyone |
| Test results | Actual command output recorded in `docs/test-report.md` and CI | Test runs | Status ledger |
| Deployment status | Hosting platform and `/health`, `/readiness` | Platform | Status ledger |
| Architecture decisions | [decisions/](decisions/) | Developer | Everyone |

PostgreSQL is authoritative for the application's ingested dataset. It is not the original source of NBA statistics.

## Layer ownership

| Concern | Ingestion | PostgreSQL | ML pipeline | FastAPI | Next.js |
|---|:-:|:-:|:-:|:-:|:-:|
| NBA API requests, throttling, retries | **owns** | | | | |
| Cleaning, normalization, dedup, provenance | **owns** | | | | |
| Freshness tracking | writes | **stores** | | reads, exposes | displays |
| Players, teams, seasons, games, box scores | writes | **stores** | reads | reads | displays |
| Feature generation, training datasets | | | **owns** | | |
| Training, evaluation, calibration | | | **owns** | | |
| Model artifact files | | | **owns** | loads read-only | |
| Model registry rows | | **stores** | writes | reads | displays |
| Inference (features → prediction) | | | code | **orchestrates** | |
| Prediction records, feature snapshots | | **stores** | backtests | pregame (append-only) | displays |
| Post-game evaluation | | **stores** | **owns** job | reads | displays |
| Validation, business rules, errors, cache | | | | **owns** | |
| Rendering, navigation, filters, URL state, charts | | | | | **owns** |

## NBA data provenance and reconciliation

Every ingested row in `players`, `games`, `team_game_stats` and `player_game_stats` carries:

- `ingestion_run_id`: the run that last wrote it
- `source_endpoint`: e.g. `LeagueGameLog`
- `first_ingested_at`, `updated_at`

Reconciliation rules, applied per row:

1. **Validation before write.** Rows that fail validation (missing keys, negative counts, `fgm > fga`, a player-minutes total for a team far from 240 + 25·OT) are rejected and counted in `ingestion_runs.rows_rejected`. A rejected row never overwrites a stored valid row.
2. **Partial responses.** If a season response has fewer rows than already stored for completed games in that season, the run fails without writing, because the source returned an incomplete set.
3. **Corrections.** When a stored final game's stat differs from a valid source row, the row is updated and the change is logged in `source_corrections` (table, key, column, old value, new value, run id, detected time). The new `data_version` invalidates caches and the dependent features.
4. **Predictions are never recomputed** because of a correction. Their stored feature snapshots stay as they were. Evaluation rows for affected games are re-scored against the corrected actuals, and that change is also logged.
5. **Schedule changes** (postponements, time changes) update `games` in place. A pregame prediction for a postponed game keeps its original `data_cutoff_at`, and the UI marks the game as postponed.

## Statistic definitions

One implementation per derived statistic, in `backend/app/stats/`. API services and the ML feature pipeline both import from it, and consistency tests check both against independent fixtures.

| Statistic | Definition |
|---|---|
| Per-game average | Sum over games played ÷ games played (games with `minutes > 0`) |
| FG%, 3P%, FT% | Σ made ÷ Σ attempted over the window; `null` with status `no_attempts` when attempts are 0. Never the mean of per-game percentages |
| eFG% | (FGM + 0.5·3PM) ÷ FGA |
| TS% | PTS ÷ (2·(FGA + 0.44·FTA)) |
| Rolling *n* average | Mean of the previous *n* games played, excluding the current game; `null` when fewer than *n* are available (the ML pipeline adds explicit fallbacks) |
| Rest days | Days between this game's date and the player's previous game date, minus 1; capped at 7; `null` for the first game of a career |
| Back-to-back | The team played on the previous calendar day |
| Home/away | From `games.home_team_id` vs. the player's team for that game |
| Possessions | FGA − OREB + TOV + 0.44·FTA (team) |
| Defensive rating | Opponent points ÷ possessions × 100 |
| Consistency | Coefficient of variation (std ÷ mean) of points over the window |
| Double-double | ≥ 10 in at least two of PTS, REB, AST, STL, BLK |

The frontend formats these values. It never computes them.

## Frontend state boundaries

| State | Owner | Examples | Rules |
|---|---|---|---|
| Server state | FastAPI via `frontend/src/lib/api` | Players, games, predictions, metrics | Server Components for first paint; TanStack Query in the client with stable keys `[resource, id, params]`; no copies in global stores |
| URL state | Query parameters | `?season=2025-26&stat=pts`, `?p1=&p2=`, `?player=&game=` | The single copy of any shareable filter; components read it, not a mirror |
| Local UI state | `useState` in the owning component | Open dialog, autocomplete highlight index, unsent input | Never persisted as data |
| Preferences | `localStorage` | Theme override, collapsed panels | Convenience only, never data |

## Conflict resolution

When two representations disagree:

1. Identify both values and the authoritative owner from the matrix above.
2. Classify the cause: stale cache, transformation defect, source correction or ingestion defect.
3. Re-derive the value from the authoritative source.
4. Fix the dependent representation and invalidate its cache.
5. Add a regression test.
6. Log material corrections (data corrections in `source_corrections`, development corrections in the status ledger session log).

If the authoritative source itself is uncertain, the value is shown as unverified until reconciled.

## Evidence hierarchy for progress claims

1. Executed verification results (test output, measurements, CI runs)
2. Current repository contents
3. Recorded acceptance measurements
4. Phase documentation
5. Earlier summaries from people or assistants

When documentation conflicts with executable evidence, the evidence wins and the documentation is corrected.

## Consistency tests

| Check | Phase |
|---|---|
| Stored box scores match recorded source fixtures for sampled games | 3 |
| Re-running ingestion three times yields identical row counts and no duplicates | 3 |
| Profile averages equal an independent SQL aggregate | 4 |
| Comparison metrics equal profile metrics for the same player and season | 10 |
| `app/stats` rolling averages equal ML rolling features on shared fixtures | 6 |
| Every prediction's release and feature schema exist in the registry | 7 |
| Evaluation rows match stored predictions and final box scores | 9 |
| Generated frontend types match the committed OpenAPI (CI diff) | 2, 14 |
| Every "Pass" in the status ledger cites evidence | every phase |
