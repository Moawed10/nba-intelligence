# Architecture Decision Records

| ADR | Decision |
|---|---|
| [0001](0001-season-level-ingestion.md) | Season-level LeagueGameLog ingestion |
| [0002](0002-no-http-admin-operations.md) | Ingestion and training only as CLI jobs |
| [0003](0003-immutable-predictions.md) | Append-only predictions with feature snapshots |
| [0004](0004-in-process-cache.md) | Data-version-keyed in-process cache |
| [0005](0005-same-origin-proxy.md) | Same-origin Next.js proxy to FastAPI |
| [0006](0006-local-postgres-without-docker.md) | Homebrew PostgreSQL locally, containers in CI |

New decisions get the next number. Superseded ADRs stay, marked `Superseded by NNNN`.
