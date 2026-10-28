# 0004 — Data-version-keyed in-process cache instead of Redis

**Status:** Accepted · 2026-10-28

## Context
NBA data changes only when ingestion runs (a few times a day). One API instance is expected initially.

## Decision
Bounded `cachetools.TTLCache` in the API process. Keys include `data_version` (the latest successful ingestion run id), so any committed ingestion invalidates dependent entries. HTTP `Cache-Control` and Next.js `revalidate` mirror the same TTLs.

## Consequences
- No extra service to deploy or secure.
- Each replica keeps its own cache. Revisit if the API scales out and measured cache misses dominate latency.
