# 0002 — Ingestion and training run only as CLI jobs

**Status:** Accepted · 2026-10-28

## Context
Ingestion and training are expensive and change shared state. Exposing them over HTTP needs authentication, quotas and abuse handling.

## Decision
`python -m app.cli ingest|train|evaluate|activate` are the only entry points, run by a scheduler or a developer. The public API has no endpoint that starts them.

## Consequences
- The public attack surface is read endpoints plus rate-limited prediction creation.
- Scheduling is external (cron, GitHub Actions or the host's scheduler).
- Ingestion can run on a machine stats.nba.com does not block and write to the production database.
