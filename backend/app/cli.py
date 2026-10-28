"""Operational entry points. Nothing here is reachable over HTTP (ADR 0002)."""

import argparse
import json
import sys

from app.db import get_engine, session_scope
from app.ingestion import jobs
from app.ingestion.client import NBAStatsClient
from app.ingestion.integrity import integrity_report, recent_runs
from app.ingestion.transforms import current_season_start_year
from app.logging import configure_logging
from app.models import SeasonType


def _run(job: str, params: dict, body) -> bool:
    try:
        run = jobs.run_job(get_engine(), job, params, body)
    except Exception:
        return False
    if run is None:
        print(f"skipped {job} {params}: already running")
        return True
    print(f"{job} {params}: fetched={run.rows_fetched} valid={run.rows_valid} "
          f"inserted={run.rows_inserted} updated={run.rows_updated} "
          f"rejected={run.rows_rejected} retries={run.retry_count}")  # fmt: skip
    return True


def ingest_season(client: NBAStatsClient, season: int, types: list[SeasonType]) -> bool:
    ok = _run("schedule", {"season": season}, jobs.ingest_schedule(client, season))
    for st in types:
        ok &= _run("game_logs", {"season": season, "season_type": st.value},
                   jobs.ingest_game_logs(client, season, st))  # fmt: skip
    return ok


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="command", required=True)

    ingest = sub.add_parser("ingest", help="Fetch NBA data into PostgreSQL")
    isub = ingest.add_subparsers(dest="target", required=True)
    current = current_season_start_year()
    isub.add_parser("teams")
    isub.add_parser("players")
    for name in ("schedule", "season"):
        p = isub.add_parser(name)
        p.add_argument("--season", type=int, default=current, help="Start year, e.g. 2025")
    backfill = isub.add_parser("backfill")
    backfill.add_argument("--from", dest="start", type=int, required=True)
    backfill.add_argument("--to", dest="end", type=int, default=current)

    sub.add_parser("integrity", help="Run integrity and coverage checks")
    runs = sub.add_parser("runs", help="Show recent ingestion runs")
    runs.add_argument("--limit", type=int, default=20)

    args = parser.parse_args(argv)
    configure_logging()
    client = NBAStatsClient()
    all_types = list(SeasonType)

    if args.command == "ingest":
        if args.target == "teams":
            ok = _run("teams", {"season": current}, jobs.ingest_teams(client, current))
        elif args.target == "players":
            ok = _run("players", {"season": current}, jobs.ingest_players(client, current))
        elif args.target == "schedule":
            ok = _run("schedule", {"season": args.season},
                      jobs.ingest_schedule(client, args.season))  # fmt: skip
        elif args.target == "season":
            ok = ingest_season(client, args.season, all_types)
        else:
            ok = _run("teams", {"season": current}, jobs.ingest_teams(client, current))
            ok &= _run("players", {"season": current}, jobs.ingest_players(client, current))
            for season in range(args.start, args.end + 1):
                ok &= ingest_season(client, season, all_types)
        return 0 if ok else 1

    with session_scope() as session:
        if args.command == "integrity":
            print(json.dumps(integrity_report(session), indent=2, default=str))
        else:
            print(json.dumps(recent_runs(session, args.limit), indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
