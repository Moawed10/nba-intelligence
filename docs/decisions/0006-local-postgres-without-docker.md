# 0006 — Homebrew PostgreSQL for local development

**Status:** Accepted · 2026-10-28

## Context
The development machine has no Docker. Production and CI need container images anyway.

## Decision
Local development uses Homebrew `postgresql@16` as a background service. CI uses a `postgres:16` service container. Dockerfiles and `docker-compose.yml` are still provided for deployment and for contributors with Docker.

## Consequences
Local and CI Postgres major versions match (16). Migrations are tested on a clean database in CI.
