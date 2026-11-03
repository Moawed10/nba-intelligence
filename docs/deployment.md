# Deployment and operations

Nothing has been deployed yet. This guide is ready to follow, and each step says how far it has been tested. Results are in [test-report.md](test-report.md#deployment-and-operations-rehearsal-2026-11-02).

## What runs

| Service | Image | Command | Purpose |
|---|---|---|---|
| `db` | `postgres:16` | | Source of truth. Data in the `db-data` volume |
| `migrate` | `backend/Dockerfile` | `alembic upgrade head` | Runs once before the API and worker start |
| `api` | `backend/Dockerfile` | `uvicorn --factory app.main:build` | Read API and forecasts. Not published outside the Compose network |
| `worker` | `backend/Dockerfile` | `python -m app.cli sync-worker` | The only writer of NBA data. Scores games and refreshes forecasts |
| `web` | `frontend/Dockerfile` | `npm start` | The site, and the `/api/v1` proxy. The only published port |

All are defined in [`docker-compose.yml`](../docker-compose.yml). Services restart unless stopped. CI builds the images and smoke-tests the stack on every pull request. No Docker was available on the development machine, so CI is the only place this has run.

Run a single API process. The rate limiter keeps its counts in memory, so N processes allow N times the configured rate. If you scale out, lower the limits to match or move the counts to a shared store.

## First deployment

1. **Check the host can reach the NBA source** (see [below](#nba-source-access)), before choosing the host:

   ```bash
   docker compose run --rm --no-deps worker python -m app.cli source-check
   ```

2. **Configure.** Create `.env` next to `docker-compose.yml` with a strong `POSTGRES_PASSWORD`. Never commit it. Put TLS and an edge proxy in front of the `web` port. That proxy must **overwrite** `X-Forwarded-For` with the real client address; without this, clients can dodge the per-client limit by sending their own header, and only the global limit protects forecasts.

3. **Start the database and migrate:**

   ```bash
   docker compose up -d db
   docker compose run --rm migrate
   ```

4. **Load data**, if this is a new database. Either restore a backup ([below](#backup-and-restore)) or ingest:

   ```bash
   docker compose run --rm worker python -m app.cli ingest backfill --from 2018
   docker compose run --rm worker python -m app.cli integrity
   ```

5. **Install and activate the model release** ([below](#model-artifacts)).

6. **Start everything and smoke-test:**

   ```bash
   docker compose up -d --wait api worker web
   curl -fsS http://localhost:3000/about > /dev/null
   curl -fsS http://localhost:3000/api/v1/health
   docker compose exec api python -m app.cli ops-check
   ```

   `/api/v1/readiness` must report `database: ok` and `model: ok`.

## Model artifacts

Model files are not in Git or in the images. They live in the `model-data` volume, and their hashes are in the database. A release bundle (`app.cli artifacts export`) holds both the files and the registry rows.

**Durable storage is the owner's step.** Keep each active release's bundle somewhere that outlives the host: private object storage, or an asset on a private GitHub release. No bundle has been uploaded anywhere. The owner can run:

```bash
cd backend && .venv/bin/python -m app.cli artifacts export <version> release.tar.gz
gh release create model-<version> release.tar.gz --draft --title "Model <version>"
```

Install on a host, verify, then activate:

```bash
docker compose cp release.tar.gz api:/tmp/release.tar.gz
docker compose exec api python -m app.cli artifacts import /tmp/release.tar.gz
docker compose exec api python -m app.cli artifacts verify <version>
docker compose exec api python -m app.cli activate <version>
docker compose restart api worker
```

Import refuses any file whose SHA-256 or feature schema differs from the registry. Activation verifies again and retires the previous release; stored forecasts are never changed. If the database already has the release (after a restore), import only puts the files back.

## Migrations

Migrations run automatically through the `migrate` service on `docker compose up`. Take a backup first. A migration that fails leaves the API and worker unstarted, because both wait for it to succeed.

## Deploying a new version

1. Back up the database.
2. `git pull`, then `docker compose build`. Note the previous commit for rollback.
3. `docker compose up -d --wait` runs migrations and replaces the containers.
4. Repeat the smoke test.

## Rollback

| What went wrong | Do this |
|---|---|
| A bad model release | `app.cli activate <previous-version>`, then `docker compose restart api worker`. The previous release's files must still be on the volume |
| A bad application version, no schema change | `git checkout <previous-commit>`, `docker compose up -d --build --wait` |
| A bad version with a schema change | Roll the code back after `docker compose run --rm migrate alembic downgrade -1` (run with the new image, before the checkout). A downgrade drops anything stored in the removed table; for example, removing `game_prediction_evaluations` loses evaluations, which the next maintenance run recreates |
| Data damage | Restore the latest backup ([below](#backup-and-restore)) and reinstall the artifacts from the bundle |

## Backup and restore

```bash
sh backend/scripts/backup.sh <database-or-url> <directory> [keep-days]
sh backend/scripts/restore_check.sh <dump-file> [source-database]
```

`backup.sh` writes a custom-format dump, checks it is readable, stores its SHA-256, and removes backups older than `keep-days` (default 14). `restore_check.sh` restores into a temporary database, compares row counts of the main tables against the source when one is named, and drops the temporary database. Run it regularly; a backup that has never been restored is not a backup.

Schedule the backup daily from the host, and copy the files off the host. Cron example:

```
0 4 * * * cd /srv/nba-intelligence && docker compose exec -T -e PGPASSWORD="$POSTGRES_PASSWORD" api sh scripts/backup.sh postgresql://nba@db:5432/nba_intelligence /data/backups
```

Backups in `/data` stay on the host's volume until you copy them away.

To restore for real: stop `api` and `worker`, drop and recreate the database, `pg_restore --no-owner --dbname=<url> <dump>`, run `migrate`, reinstall artifacts from the bundle if the volume was lost, then start everything and run the smoke test.

## Monitoring

```bash
docker compose exec api python -m app.cli ops-check
```

Prints JSON and exits 1 if any check fails. Schedule it every five minutes and alert on a non-zero exit, using whatever alerting the host offers. No alert destination is configured.

| Check | Fails when |
|---|---|
| `overdue_sync` | A scheduled job is more than 15 minutes late, or the worker has never run |
| `failed_ingestion` | A job's latest run in the last 24 hours failed or was abandoned |
| `stale_data` | A dataset is outside its freshness policy (`docs/data-synchronization.md`) |
| `scoring` | A game finalized more than an hour ago still has unscored forecasts |
| `event_backlog` | A sync event has waited more than 15 minutes |
| `model` | No active release, or its artifacts fail verification |

Also watch `/api/v1/readiness` (503 when the database is down; reports the model state) and the JSON logs. Each log line has a `request_id`, which is also returned in the `X-Request-ID` header and in error bodies. Public errors never contain paths, queries or stack traces.

## NBA source access

stats.nba.com is known to refuse or stall requests from many cloud networks. **It has only been reached from the development Mac** (`app.cli source-check`, 2026-11-02). Do not assume it works from any host until `source-check` passes there, and passes again across several days.

If the host is blocked, use this supported arrangement, which needs no code changes: run the `worker` on a machine that can reach the source, pointed at the hosted database.

```bash
NBA_DATABASE_URL=<hosted-database-url-with-tls> .venv/bin/python -m app.cli sync-worker
```

On the host, leave out the `worker` service. The API only reads NBA data, so it works unchanged. The remote worker needs the model artifacts too (for scoring refreshes), so install the bundle on that machine with `artifacts import`. The database must accept connections from that machine over TLS, and the machine must stay on; supervise it with `launchd`, `systemd` or similar. `overdue_sync` tells you when it stops.

## Release thresholds

These need seven days of evidence from a running deployment and stay **pending** until then: healthy request success of at least 99%, and scheduled ingestion success of at least 95%.
