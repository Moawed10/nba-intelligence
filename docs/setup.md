# Setup from a fresh checkout

Every step below runs on a machine with nothing but this repository. Commands are run from the repository root unless a `cd` says otherwise. The last clean-room run is recorded in [test-report.md](test-report.md#release-readiness-baseline-2026-11-02).

## Requirements

Python 3.12, Node 22 or newer (CI uses 24), PostgreSQL 16. On macOS:

```bash
brew install postgresql@16 && brew services start postgresql@16
```

## 1. Database

```bash
createdb nba_intelligence
```

The API, worker and CLI all read `NBA_DATABASE_URL` (default `postgresql+psycopg:///nba_intelligence`).

## 2. Backend

Install from the hash-pinned lock files, not from `pyproject.toml`, so every machine gets the same packages. Use `requirements.lock` for a server and `requirements-dev.lock` for development.

```bash
cd backend
python3.12 -m venv .venv
.venv/bin/pip install --require-hashes -r requirements-dev.lock
.venv/bin/pip install --no-deps -e .
.venv/bin/pip check
cp .env.example .env
.venv/bin/alembic upgrade head
```

To change a dependency, edit `pyproject.toml`, raise `LOCK_CUTOFF` in `scripts/lock.sh` if newer releases are needed, and run `sh scripts/lock.sh` (needs `uv` 0.13.6). CI fails when the lock files and `pyproject.toml` disagree.

## 3. Environment variables

Backend settings use the `NBA_` prefix and are read from the environment or `backend/.env`. All are optional locally. Never commit `.env` files.

| Variable | Default | Purpose |
|---|---|---|
| `NBA_DATABASE_URL` | `postgresql+psycopg:///nba_intelligence` | Application database |
| `NBA_DB_POOL_SIZE`, `NBA_DB_MAX_OVERFLOW` | 5, 5 | Connection pool per process |
| `NBA_LOG_LEVEL`, `NBA_LOG_JSON` | `INFO`, `true` | Logging |
| `NBA_CORS_ORIGINS` | `[]` | Leave empty: the browser reaches the API through the frontend's `/api/v1` proxy |
| `NBA_API_DOCS_ENABLED`, `NBA_API_CACHE_ENABLED` | `true`, `true` | Interactive docs; response memoization |
| `NBA_STATS_REQUEST_INTERVAL_SECONDS` | `1.0` | Minimum gap between stats.nba.com requests. Raise to 4 for long backfills |
| `NBA_STATS_TIMEOUT_SECONDS`, `NBA_STATS_MAX_ATTEMPTS` | 30, 5 | Source request limits |
| `NBA_STATS_CACHE_DIR` | `.cache/nba_stats` | On-disk source cache |
| `NBA_ARTIFACTS_DIR` | see `app/config.py` | Where model files live |
| `NBA_PHOTOS_DIR` | see `app/config.py` | Where player photos live |
| `NBA_TEST_DATABASE_URL` | `postgresql+psycopg:///nba_intelligence_test` | Dropped and recreated by the test suite |

Frontend settings (`frontend/.env.local`):

| Variable | Purpose |
|---|---|
| `API_INTERNAL_URL` | Where the Next.js server proxies `/api/v1`. **Fixed at build time**, because rewrites are compiled into the build |
| `NEXT_DIST_DIR` | Optional build directory, used to keep separate builds apart |
| `NEXT_PUBLIC_REPOSITORY_URL` | Optional source-code link on `/about` |

## 4. Data

Test data needs no setup: the test suites build a synthetic league themselves (`backend/tests/fixtures.py`) and never contact the NBA.

Real data comes from stats.nba.com, one request at a time:

```bash
cd backend
.venv/bin/python -m app.cli ingest backfill --from 2018
.venv/bin/python -m app.cli ingest careers
.venv/bin/python -m app.cli integrity
.venv/bin/python -m app.cli data-status
```

The source can refuse requests, especially for long runs and from cloud networks. The career job stops after repeated refusals and picks up where it left off when re-run; use `NBA_STATS_REQUEST_INTERVAL_SECONDS=4` for it.

## 5. Model release

Model files are not in Git. A database has no forecasts until a release is active, and the API answers with a clear "models unavailable" error until then. There are two ways to get one, neither relying on files only one person has.

**Train one** (needs the data from step 4):

```bash
cd backend
.venv/bin/python -m app.cli train
.venv/bin/python -m app.cli backtest <version>
```

`train` prints the new version and registers it as a candidate. `backtest` adds the out-of-sample history shown on the Models page.

**Or import a bundle** made on another machine:

```bash
cd backend
.venv/bin/python -m app.cli artifacts export <version> release.tar.gz
.venv/bin/python -m app.cli artifacts import release.tar.gz
```

A bundle holds the release's registry rows and its model files. Import checks each file's SHA-256 and feature schema before installing anything, and refuses the bundle on any mismatch. Bundles are not committed; keep the current one in durable storage (see [deployment.md](deployment.md#model-artifacts)).

**Verify and activate.** Either route ends the same way. Activation verifies every artifact again and retires the previous release; historical forecasts are never changed.

```bash
cd backend
.venv/bin/python -m app.cli artifacts verify <version>
.venv/bin/python -m app.cli activate <version>
```

## 6. Start the services

Three processes, in separate terminals:

```bash
cd backend && .venv/bin/uvicorn --factory app.main:build --port 8000
```

```bash
cd backend && .venv/bin/python -m app.cli sync-worker
```

```bash
cd frontend && npm ci && cp .env.example .env.local && npm run build && npm start
```

The site is at http://localhost:3000 and the API docs at http://localhost:8000/api/v1/docs. Use `npm run dev` instead of build and start while developing. The worker is the only process that writes NBA data, scores finished games and refreshes forecasts: stop it and the site keeps serving, but its numbers stop moving.

## 7. Check it

```bash
cd backend && .venv/bin/pytest -q
cd frontend && npm run lint && npm run typecheck && npm test && npm run test:e2e
cd frontend && npm run test:fullstack
```

`test:fullstack` runs the prediction workflow against the real API and a real PostgreSQL database. See [test-report.md](test-report.md) for what each suite covers.
