# NBA Intelligence

Player performance prediction and analytics for the NBA. It forecasts a player's next-game points, rebounds, assists, threes, steals, blocks and minutes, with calibrated uncertainty ranges and a double-double probability, using machine learning models trained on real NBA box scores. Every number shown comes from ingested data or a trained, versioned model.

> **Status:** architecture and design complete (Phase 1). No application code yet. Progress and verified results: [docs/implementation-status.md](docs/implementation-status.md).

## Stack

Next.js · TypeScript · Tailwind · shadcn/ui · Framer Motion · Recharts · TanStack Query — FastAPI · Pydantic · SQLAlchemy · Alembic · PostgreSQL 16 — pandas · scikit-learn · XGBoost · SHAP — nba_api

## Documentation

| Document | Contents |
|---|---|
| [Architecture](docs/architecture.md) | Five-layer system diagram, data source findings, repository layout |
| [Data ownership](docs/data-ownership.md) | Source of truth, statistic definitions, state boundaries |
| [Data synchronization](docs/data-synchronization.md) | Scheduler, game lifecycle, freshness, prediction refresh |
| [Database](docs/database.md) | Schema and ER diagram |
| [API contracts](docs/api-contracts.md) | Endpoints, errors, caching, per-screen data loading |
| [Model methodology](docs/model-methodology.md) | Features, leakage controls, models, intervals, evaluation |
| [Frontend](docs/frontend.md) | Design system, accessibility, motion, components |
| [Decisions](docs/decisions/) | Architecture decision records |
| [Implementation status](docs/implementation-status.md) | Phase ledger, quality gates, session log |

Model accuracy, dataset sizes, screenshots and setup instructions will be added here as they are produced and verified.
