# NBA Intelligence

Player performance prediction and analytics for the NBA. It forecasts a player's next-game points, rebounds, assists, threes, steals, blocks and minutes, with calibrated uncertainty ranges and a double-double probability, using machine learning models trained on real NBA box scores. Every number shown comes from ingested data or a trained, versioned model.

> **Status:** in development.
> - Real box scores from 2018-19 through the current season are ingested, verified and kept in sync automatically.
> - The frontend shell and design system are built.
> - The API, ML models and prediction screens are next.
>
> Progress and verified results: [docs/implementation-status.md](docs/implementation-status.md) and [docs/test-report.md](docs/test-report.md).

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

## Local development

Requirements: Python 3.12, Node 22+, PostgreSQL 16.

```bash
# Database (macOS / Homebrew)
brew install postgresql@16 && brew services start postgresql@16
createdb nba_intelligence

# Backend
cd backend
python3.12 -m venv .venv && .venv/bin/pip install -e ".[dev]"
cp .env.example .env
.venv/bin/alembic upgrade head

# Load real NBA data (about 3 minutes; calls stats.nba.com at ~1 request/s)
.venv/bin/python -m app.cli ingest backfill --from 2018
.venv/bin/python -m app.cli integrity      # integrity and coverage report
.venv/bin/python -m app.cli data-status    # per-dataset freshness

# Keep data current (runs until stopped)
.venv/bin/python -m app.cli sync-worker

# Frontend
cd ../frontend
npm install && cp .env.example .env.local
npm run dev                                # http://localhost:3000
```

## Tests

```bash
cd backend && .venv/bin/pytest            # needs a local PostgreSQL; creates nba_intelligence_test
cd frontend && npm run lint && npm run typecheck && npm test && npm run test:e2e
```

Model accuracy results will be added here once they are produced and verified.
