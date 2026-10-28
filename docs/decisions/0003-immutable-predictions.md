# 0003 — Predictions are append-only, with stored feature snapshots

**Status:** Accepted · 2026-10-28

## Context
Predictions must be auditable and reproducible, and pregame predictions must never be confused with backtests or quietly replaced with later, better-informed ones.

## Decision
`predictions` rows are never updated. Each stores the release, feature schema version, the exact feature vector and its hash, and `data_cutoff_at`. `kind` separates `pregame` from `backtest`. Pregame rows can only be created before `tipoff_at`. Outcomes go in a separate `prediction_evaluations` table.

## Consequences
- Identical requests return the stored row (unique on player, game, release, kind and snapshot hash), which also serves as the prediction cache.
- New data produces a new snapshot and a new row. History keeps every version.
- Storage grows with backtests (~180k value rows per release), well within PostgreSQL's comfort zone.
