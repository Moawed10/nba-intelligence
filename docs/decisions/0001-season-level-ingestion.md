# 0001 — Ingest box scores with season-level LeagueGameLog

**Status:** Accepted · 2026-10-28

## Context
Per-player `PlayerGameLog` needs ~500 requests per season. stats.nba.com has no published rate limit and is known to throttle or block heavy clients.

## Decision
Use `LeagueGameLog` with `player_or_team_abbreviation=P` and `T`: one request per season and season type each. Verified on 2026-10-28: 26,651 player rows for 2025-26 in 6.2 s.

## Consequences
- ~40 requests backfill 2018-19 through 2026-27, instead of ~4,500.
- Players who did not play are absent, so DNPs are inferred from team games.
- No per-game advanced box score; usage rate is a box-score proxy.

## Alternatives considered
Per-player `PlayerGameLog` (too many requests); `BoxScoreAdvancedV3` per game (~1,230 requests per season; deferred until a feature needs it and its value is measured).
