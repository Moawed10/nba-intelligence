# NBA Intelligence

Player performance prediction and analytics for the NBA. It forecasts a player's next-game points, rebounds, assists, threes, steals, blocks and minutes, with calibrated uncertainty ranges and a double-double probability, using machine learning models trained on real NBA box scores. Every number shown comes from ingested data or a trained, versioned model.

> **Status:** feature-complete for local use; not deployed. Release gates still open are listed in [docs/release-readiness.md](docs/release-readiness.md).
> - Real box scores from 2018-19 through the current season are ingested and verified. They stay current while the sync worker (`app.cli sync-worker`) is running; nothing syncs when it is stopped.
> - Every player's season-by-season career, regular season and playoffs back to 1946-47, former players included. The career backfill runs one request per player and is resumable; `docs/implementation-status.md` records how far it has run.
> - Forecasts for a player's next game (with uncertainty ranges and a double-double probability) and predicted final scores and win chances for upcoming games.
> - Screens: Overview, Players, player profiles, Predictions, Compare, Models, Games, game pages, About.
> - Model accuracy on the held-out 2025-26 season is published on the Models page and in [docs/test-report.md](docs/test-report.md#phase-6-machine-learning-pipeline). Live accuracy appears only once real forecasts have been scored.
>
> Progress and verified results: [docs/implementation-status.md](docs/implementation-status.md) and [docs/test-report.md](docs/test-report.md).

## Stack

Next.js · TypeScript · Tailwind · shadcn/ui · Framer Motion · Recharts · TanStack Query — FastAPI · Pydantic · SQLAlchemy · Alembic · PostgreSQL 16 — pandas · scikit-learn · XGBoost — nba_api

## Documentation

| Document | Contents |
|---|---|
| [Setup](docs/setup.md) | Clean setup from a fresh checkout: database, environment, model release, startup |
| [Deployment](docs/deployment.md) | Packaging, migrations, model artifacts, backups, monitoring, rollback |
| [Release readiness](docs/release-readiness.md) | Release gates, evidence and open blockers |
| [Architecture](docs/architecture.md) | Five-layer system diagram, data source findings, repository layout |
| [Data ownership](docs/data-ownership.md) | Source of truth, statistic definitions, state boundaries |
| [Data synchronization](docs/data-synchronization.md) | Scheduler, game lifecycle, freshness, prediction refresh |
| [Database](docs/database.md) | Schema and ER diagram |
| [API contracts](docs/api-contracts.md) | Endpoints, errors, caching, per-screen data loading |
| [Model methodology](docs/model-methodology.md) | Features, leakage controls, models, intervals, evaluation |
| [Frontend](docs/frontend.md) | Design system, accessibility, motion, components |
| [Decisions](docs/decisions/) | Architecture decision records |
| [Implementation status](docs/implementation-status.md) | Phase ledger, quality gates, session log |
| [Redesign plan](docs/redesign-plan.md) | Product redesign audit and phases |

## Local development

Full instructions, including how to get a model release, are in [docs/setup.md](docs/setup.md). Requirements: Python 3.12, Node 22+, PostgreSQL 16.

## Tests

```bash
cd backend && .venv/bin/pytest            # needs a local PostgreSQL; recreates nba_intelligence_test
cd frontend && npm run lint && npm run typecheck && npm test && npm run test:e2e
```

`test:e2e` uses a synthetic stub API, so it runs without a database. Live checks compare pages with the real API (backend running on port 8000):

```bash
cd frontend && npx playwright test -c playwright.live.config.ts
```

After changing an API model, regenerate the contract and frontend types (CI checks both):

```bash
cd backend && .venv/bin/python -m app.cli openapi > openapi.json
cd ../frontend && npm run api:types
```
