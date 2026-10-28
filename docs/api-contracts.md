# API Contracts

FastAPI, versioned under `/api/v1`. OpenAPI is served at `/api/v1/openapi.json`, with interactive docs at `/api/v1/docs`. Frontend TypeScript types are generated from that schema with `openapi-typescript`, so the contract has one source of truth.

## Conventions

- **Timestamps:** ISO 8601 with explicit offset (`2026-10-28T23:30:00Z`). Game dates (no time) are `YYYY-MM-DD`.
- **Missing values** are `null` and accompanied by a status field, never `0`. Example: `"fg3_pct": null, "fg3_pct_status": "no_attempts"`.
- **Pagination:** `limit` (default 25, max 100) and `cursor`, or `offset` for directory pages. List responses include `{ items, total, limit, next_cursor }`. Every list query is bounded.
- **Sorting:** `sort=field` or `sort=-field`, validated against an allow-list per endpoint.
- **Seasons** are accepted as labels (`2025-26`) and validated against the `seasons` table.
- **Freshness:** responses built from NBA data include `meta.data_freshness = { last_successful_sync, data_version, is_stale }`. `is_stale` is true when the relevant job has not succeeded within its expected interval.
- **Request id:** every response carries an `X-Request-ID` header (generated if the client did not send one), which is also logged.

### Error envelope

```json
{
  "error": {
    "code": "player_not_found",
    "message": "No player with id 9999999.",
    "request_id": "6f1c2a0e-...",
    "details": [{ "field": "player_id", "issue": "not_found" }]
  }
}
```

| HTTP | `code` examples | When |
|---|---|---|
| 400 | `invalid_parameter` | Semantically invalid input (e.g. `date_from > date_to`) |
| 404 | `player_not_found`, `game_not_found`, `prediction_not_found` | Missing resource |
| 409 | `game_already_started` | Pregame prediction requested after tip-off |
| 413 | `payload_too_large` | Body over 16 KB |
| 422 | `validation_error` | Pydantic validation failure, with field-level `details` |
| 422 | `insufficient_data`, `invalid_matchup` | Prediction cannot be made reliably (body explains why) |
| 429 | `rate_limited` | Includes `Retry-After` |
| 503 | `model_unavailable`, `database_unavailable` | Dependency down; readiness fails |
| 500 | `internal_error` | Generic message only; detail is in logs under the request id |

## Endpoint contract table

Module = file under `backend/app/api/v1/`. Response models live in `backend/app/schemas/`.

| Method | Path | Module | Response model | Purpose | Cache |
|---|---|---|---|---|---|
| GET | `/players` | players.py | `Page[PlayerSummary]` | Directory; filters `team_id`, `position`, `active`, `season`; sort | 24 h identity · data_version |
| GET | `/players/search?q=` | players.py | `list[PlayerSearchResult]` | Trigram fuzzy search, `q` 2–64 chars, `limit` ≤ 20 | 24 h · data_version |
| GET | `/players/{player_id}` | players.py | `PlayerProfile` | Identity, current team, season summary, last 5 games | 15–60 min |
| GET | `/players/{player_id}/stats` | players.py | `PlayerSeasonStats` | Per-season averages and totals, splits (home/away, rest) | 15–60 min |
| GET | `/players/{player_id}/games` | players.py | `Page[PlayerGameLine]` | Game log; `season`, `date_from`, `date_to`, `limit` | Completed games: long-lived |
| GET | `/players/{player_id}/trends` | players.py | `PlayerTrends` | Per-game series plus rolling 3/5/10 for a `stat`, bounded range | 15–60 min |
| GET | `/teams` | teams.py | `list[Team]` | All 30 teams | 24 h |
| GET | `/teams/{team_id}` | teams.py | `TeamDetail` | Identity, record, roster | 15–60 min |
| GET | `/teams/{team_id}/stats` | teams.py | `TeamSeasonStats` | Pace, offensive/defensive rating computed from team logs | 15–60 min |
| GET | `/games` | games.py | `Page[GameSummary]` | `date_from`/`date_to` (≤ 31 days), `team_id`, `status` | by status |
| GET | `/games/upcoming` | games.py | `list[GameSummary]` | Scheduled games, `days` ≤ 14, optional `player_id` (their team's games) | 5–15 min |
| GET | `/games/{game_id}` | games.py | `GameDetail` | Matchup, status, score | by status: live 30 s, final long |
| GET | `/games/{game_id}/boxscore` | games.py | `BoxScore` | Team and player lines for a final game | Long-lived |
| POST | `/predictions` | predictions.py | `Prediction` (201) or existing (200) | Body `{ player_id, game_id }` only | Keyed by model release + feature snapshot |
| GET | `/predictions/{prediction_id}` | predictions.py | `Prediction` | Stored prediction plus evaluation if the game is final | Immutable |
| GET | `/predictions/history` | predictions.py | `Page[PredictionWithOutcome]` | `player_id`, `kind=pregame\|backtest`, `release`, date range | data_version |
| GET | `/predictions/{prediction_id}/explanation` | predictions.py | `PredictionExplanation` | Feature contributions and plain-language factors | Immutable |
| GET | `/compare/players?player1=&player2=&season=` | compare.py | `PlayerComparison` | Side-by-side season metrics with league percentiles | 15–60 min |
| GET | `/models` | models.py | `list[ModelRelease]` | Releases and their per-target models | Until activation |
| GET | `/models/active` | models.py | `ModelRelease` | Active release | Until activation |
| GET | `/models/metrics` | models.py | `ModelMetrics` | Test MAE/RMSE/R², baseline, coverage per target; `release` param | Per release |
| GET | `/models/evaluations` | models.py | `Page[EvaluationPoint]` | Actual-vs-predicted points and residuals; `target`, `release`, `season`, `limit` ≤ 5000 | Per release |
| GET | `/overview` | overview.py | `Overview` | Featured players, recent standout lines, upcoming games, model summary in one call | 5 min · data_version |
| GET | `/health` | system.py | `Health` | Liveness only, no dependencies | none |
| GET | `/readiness` | system.py | `Readiness` | DB reachable, active model artifact loaded and hash-verified | none |
| GET | `/data-status` | system.py | `DataStatus` | Last successful sync per job, seasons covered, row counts | 1 min |

`/overview` is the one aggregate endpoint. The home page would otherwise make four requests.

## Prediction contract

`POST /api/v1/predictions` accepts only identifiers. Opponent, date, home/away and every feature come from stored data:

```json
{ "player_id": 201939, "game_id": "0022600123" }
```

Server-side validation, in order:

1. Player exists → else 404 `player_not_found`.
2. Game exists and `status = scheduled` → else 404 or 409 `game_already_started`.
3. The player's current team is one of the two teams → else 422 `invalid_matchup`.
4. An active model release exists and its artifacts loaded → else 503 `model_unavailable`.
5. The player has at least the minimum history (see model-methodology.md) → else 422 `insufficient_data`, recorded with `status = insufficient_data`.
6. Build the feature snapshot with `cutoff = min(now, tipoff_at)`. If an identical snapshot was already predicted by this release, return it with 200. Otherwise run inference, persist and return 201.

Response (`Prediction`). The values below are schema placeholders, not model output:

```json
{
  "id": "uuid",
  "kind": "pregame",
  "player": { "id": 0, "full_name": "string", "team_abbreviation": "string" },
  "game": { "id": "string", "tipoff_at": "2026-10-30T23:30:00Z", "opponent": { "id": 0, "abbreviation": "string" }, "is_home": true },
  "model": { "release": "2026.10.28-1", "feature_schema_version": "string" },
  "created_at": "2026-10-28T19:02:11Z",
  "data_cutoff_at": "2026-10-28T06:10:00Z",
  "status": "ok",
  "values": [
    { "stat": "pts", "point": 0.0, "lower": 0.0, "upper": 0.0, "interval_level": 0.8, "recent_avg_5": 0.0, "season_avg": 0.0 }
  ],
  "double_double_probability": 0.0,
  "top_factors": [{ "feature": "pts_avg_last_5", "label": "Points, last 5 games", "value": 0.0, "effect": 0.0, "target": "pts" }],
  "conditional_on_playing": true,
  "meta": { "data_freshness": { "last_successful_sync": "...", "data_version": 0, "is_stale": false } }
}
```

## Caching and invalidation

All caching starts in-process (`cachetools.TTLCache`, bounded size) plus HTTP headers. Redis would only be added if the API runs as more than one replica and measurements show cache misses dominate latency.

| Data | Policy | Key includes | Invalidation |
|---|---|---|---|
| Player / team identity | TTL 24 h | id, `data_version` | New ingestion run changes `data_version` |
| Completed games, box scores | Long-lived; `Cache-Control: public, max-age=86400` | game id, `data_version` | Source correction re-ingested → new `data_version` |
| Current-season stats, trends | TTL 30 min | player, season, stat, range, `data_version` | `data_version` |
| Upcoming schedule | TTL 10 min | date range, team | `data_version` |
| Game status | live 30 s, scheduled 10 min, final long | game id | Status change via ingestion |
| Model metadata | Until activation | `release.version` | Activation changes the active release id |
| Model evaluation metrics | Per release, immutable | `release.version`, target, season | Never changes for a given release |
| Predictions | Persisted in `predictions` (the database is the cache) | player, game, release, snapshot hash | New data → new snapshot hash → new prediction |

Rules:

- Only successful (2xx) results are cached. Errors and `insufficient_data` responses are not.
- `data_version` is read once per request from a 30-second in-process memo of `max(ingestion_runs.id WHERE status = 'succeeded')`.
- Next.js Server Components use `fetch(..., { next: { revalidate } })` with the same TTLs. TanStack Query `staleTime` mirrors them on the client.

## Screen-by-screen data loading

| Screen | Server-rendered (RSC) | Client (TanStack Query) | Deferred / on demand |
|---|---|---|---|
| Overview `/` | `GET /overview` | none | none |
| Players `/players` | First page of `GET /players` from URL filters, `GET /teams` | Search `GET /players/search` (debounced 250 ms, `AbortSignal` cancels stale requests), pagination | No game logs on the directory |
| Player profile `/players/[id]` | `GET /players/{id}` (identity, season summary, last 5) | `GET /players/{id}/trends` when season/stat changes | Full game log `GET /players/{id}/games` paged when the log tab opens; splits on expand |
| Predictions `/predict` | `GET /models/active`, player from `?player=` when present | Player search, `GET /games/upcoming?player_id=`, `POST /predictions` on explicit submit | `GET /predictions/{id}/explanation` when the explanation panel opens |
| Compare `/compare` | Both summaries via `GET /compare/players` from `?p1=&p2=&season=` | Swapping or reselecting players or season | Trend overlays via `/players/{id}/trends` when that chart is shown |
| Model analytics `/models` | `GET /models`, `GET /models/metrics` | Release and target selection | `GET /models/evaluations` (scatter, residuals) when charts scroll into view; `/predictions/history` paged |
| Games `/games` | `GET /games` for the URL date window (≤ 31 days) | Date navigation | `GET /games/{id}/boxscore` only when a final game is opened |
| About `/about` | `GET /data-status`, `GET /models/active` | none | none |

## Rate limits and request controls

| Scope | Limit |
|---|---|
| `POST /predictions` | 10/min and 100/day per client IP |
| `/players/search` | 60/min per IP |
| Everything else | 120/min per IP |
| Request body | 16 KB max |
| CORS | Disabled in production (same-origin through the Next.js proxy); `localhost:3000` in development |

Rate limiting uses `slowapi` keyed by client IP behind the trusted proxy header. Inference runs in a bounded thread pool (default 2 workers), so concurrent predictions cannot exhaust CPU.
