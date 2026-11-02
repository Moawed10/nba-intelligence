"""Operational entry points. Nothing here is reachable over HTTP (ADR 0002)."""

import argparse
import json
import sys
import time
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_engine, session_scope
from app.ingestion import jobs
from app.ingestion.client import NBAStatsClient
from app.ingestion.integrity import integrity_report, recent_runs
from app.ingestion.transforms import current_season_start_year
from app.logging import configure_logging
from app.models import IngestionRun, Player, PlayerSeason, SeasonType
from app.sync import worker
from app.sync.freshness import dataset_freshness


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


def _last_run_stopped_early() -> bool:
    with session_scope(get_engine()) as s:
        rejected = s.scalar(
            select(IngestionRun.rows_rejected)
            .where(IngestionRun.job == "player_careers")
            .order_by(IngestionRun.id.desc())
            .limit(1)
        )
    return (rejected or 0) >= jobs.CAREER_FAILURE_LIMIT


def ingest_careers(client: NBAStatsClient, player_ids: list[int] | None) -> bool:
    """Career seasons in batches of worker.CAREER_BATCH players, each its own run, so an interrupted
    backfill keeps finished batches. Without ids: players with nothing stored, plus every active
    player (their current season keeps changing)."""
    if player_ids is None:
        with session_scope(get_engine()) as s:
            player_ids = s.scalars(
                select(Player.id)
                .where(Player.is_active | ~exists().where(PlayerSeason.player_id == Player.id))
                .order_by(Player.is_active.desc(), Player.id)
            ).all()
    print(f"career history for {len(player_ids)} players")
    ok = True
    for start in range(0, len(player_ids), worker.CAREER_BATCH):
        batch = list(player_ids[start : start + worker.CAREER_BATCH])
        ok &= _run("player_careers", {"first": batch[0], "count": len(batch)},
                   jobs.ingest_player_careers(client, batch))  # fmt: skip
        if ok and _last_run_stopped_early():
            print("the source is refusing requests; stopped. Re-run later to continue.")
            return False
    return ok


def train_command(args: argparse.Namespace) -> int:
    from app.ml.features import TARGETS
    from app.ml.models import FAST_CONFIG, TrainConfig
    from app.ml.train import run

    configure_logging()
    targets = tuple(args.targets.split(",")) if args.targets else TARGETS
    unknown = set(targets) - set(TARGETS)
    if unknown:
        print(f"Unknown targets: {sorted(unknown)}", file=sys.stderr)
        return 2
    summary = run(
        get_engine(),
        get_settings().artifacts_dir,
        FAST_CONFIG if args.fast else TrainConfig(),
        targets=targets,
        register=args.targets is None,
    )
    print(json.dumps(summary, indent=2, default=str))
    return 0


def activate_command(version: str) -> int:
    from app.ml.artifacts import ArtifactMismatch
    from app.ml.inference import activate

    try:
        with session_scope(get_engine()) as session:
            release = activate(session, version, get_settings().artifacts_dir, datetime.now(UTC))
            print(f"{release.version} is active")
    except (LookupError, ArtifactMismatch, FileNotFoundError) as error:
        print(f"Not activated: {error}", file=sys.stderr)
        return 1
    return 0


def artifacts_command(args: argparse.Namespace) -> int:
    from app.ml.artifacts import ArtifactMismatch
    from app.ml.release_bundle import export_release, import_release, verify_release

    artifacts_dir = get_settings().artifacts_dir
    try:
        with session_scope(get_engine()) as session:
            if args.action == "verify":
                problems = verify_release(session, artifacts_dir, args.target)
                for problem in problems:
                    print(problem, file=sys.stderr)
                print(f"{args.target}: {'FAILED' if problems else 'all artifacts verified'}")
                return 1 if problems else 0
            if args.action == "export":
                count = export_release(session, artifacts_dir, args.target, Path(args.file))
                print(f"{args.target}: {count} artifacts written to {args.file}")
                return 0
            version = import_release(session, artifacts_dir, Path(args.target))
            session.commit()
            print(
                f"{version} imported as a candidate; activate it with: app.cli activate {version}"
            )
            return 0
    except (LookupError, ArtifactMismatch, FileNotFoundError, KeyError) as error:
        print(f"{args.action} failed: {error}", file=sys.stderr)
        return 1


def ops_check_command() -> int:
    from app.ops import run_checks

    with Session(get_engine()) as session:
        checks = run_checks(session, datetime.now(UTC), get_settings().artifacts_dir)
    print(json.dumps([asdict(c) for c in checks], indent=2))
    return 1 if any(c.status == "fail" for c in checks) else 0


def source_check_command() -> int:
    from nba_api.stats.endpoints import CommonTeamYears

    started = time.perf_counter()
    try:
        result = NBAStatsClient(max_attempts=1).fetch(CommonTeamYears)
    except Exception as error:
        print(json.dumps({"reachable": False, "error": type(error).__name__}))
        return 1
    elapsed = round(time.perf_counter() - started, 2)
    print(json.dumps({"reachable": True, "rows": len(result.frames[0]), "seconds": elapsed}))
    return 0


def openapi_json() -> str:
    from app.main import create_app

    return json.dumps(create_app().openapi(), indent=2, sort_keys=True) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="command", required=True)

    ingest = sub.add_parser("ingest", help="Fetch NBA data into PostgreSQL")
    isub = ingest.add_subparsers(dest="target", required=True)
    current = current_season_start_year()
    isub.add_parser("teams")
    isub.add_parser("team-history", help="All seasons of every franchise (about 60 requests)")
    isub.add_parser("players")
    careers = isub.add_parser("careers", help="Every season of every player (one request each)")
    careers.add_argument("--players", help="Comma-separated player ids (default: all due)")
    for name in ("schedule", "season"):
        p = isub.add_parser(name)
        p.add_argument("--season", type=int, default=current, help="Start year, e.g. 2025")
    backfill = isub.add_parser("backfill")
    backfill.add_argument("--from", dest="start", type=int, required=True)
    backfill.add_argument("--to", dest="end", type=int, default=current)

    sub.add_parser("sync-worker", help="Run scheduled synchronization until stopped")
    sub.add_parser("sync-once", help="Run every currently due sync job once")
    sub.add_parser("data-status", help="Show per-dataset freshness")
    sub.add_parser("integrity", help="Run integrity and coverage checks")
    runs = sub.add_parser("runs", help="Show recent ingestion runs")
    runs.add_argument("--limit", type=int, default=20)
    sub.add_parser("openapi", help="Print the API's OpenAPI schema")
    train = sub.add_parser("train", help="Train, evaluate and register a candidate model release")
    train.add_argument("--targets", help="Comma-separated subset of targets (no registration)")
    train.add_argument("--fast", action="store_true", help="Small search grids, for smoke runs")
    sub.add_parser("predictions", help="Score finished games and refresh stale forecasts once")
    activate = sub.add_parser("activate", help="Verify a release's artifacts and make it serve")
    activate.add_argument("version")
    artifacts = sub.add_parser("artifacts", help="Verify, export or import a model release")
    asub = artifacts.add_subparsers(dest="action", required=True)
    asub.add_parser(
        "verify", help="Check every artifact's SHA-256 and feature schema"
    ).add_argument("target", metavar="version")
    export = asub.add_parser("export", help="Write a release bundle (registry + artifacts)")
    export.add_argument("target", metavar="version")
    export.add_argument("file")
    asub.add_parser("import", help="Install a release bundle as a candidate").add_argument(
        "target", metavar="bundle"
    )
    sub.add_parser(
        "ops-check", help="Check sync, data, scoring and model health; exit 1 on failure"
    )
    sub.add_parser("source-check", help="Check that this host can reach stats.nba.com")
    backtest = sub.add_parser(
        "backtest", help="Store and score a release's held-out test-season predictions"
    )
    backtest.add_argument("version")

    args = parser.parse_args(argv)
    if args.command == "openapi":
        sys.stdout.write(openapi_json())
        return 0
    if args.command == "train":
        return train_command(args)
    if args.command == "activate":
        return activate_command(args.version)
    if args.command == "artifacts":
        return artifacts_command(args)
    if args.command == "ops-check":
        configure_logging()
        return ops_check_command()
    if args.command == "source-check":
        configure_logging()
        return source_check_command()
    if args.command == "backtest":
        from app.ml.backtest import run_backtest

        configure_logging()
        print(json.dumps(run_backtest(get_engine(), get_settings().artifacts_dir, args.version)))
        return 0
    if args.command == "predictions":
        result = worker.maintain_predictions(
            get_engine(), datetime.now(UTC), get_settings().artifacts_dir
        )
        print(json.dumps(result if result is not None else "skipped: running elsewhere"))
        return 0
    configure_logging()
    client = NBAStatsClient()
    all_types = list(SeasonType)

    if args.command == "ingest":
        if args.target == "team-history":
            ok = _run("team_history", {}, jobs.ingest_team_history(client))
        elif args.target == "teams":
            ok = _run("teams", {"season": current}, jobs.ingest_teams(client, current))
        elif args.target == "careers":
            ids = [int(i) for i in args.players.split(",")] if args.players else None
            ok = ingest_careers(client, ids)
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

    if args.command == "sync-worker":
        worker.run_forever(get_engine(), client)
        return 0
    if args.command == "sync-once":
        print(json.dumps(worker.run_due(get_engine(), client), indent=2))
        return 0

    with session_scope() as session:
        if args.command == "data-status":
            now = datetime.now(UTC)
            rows = [d.as_dict() for d in dataset_freshness(session, now)]
            print(json.dumps(rows, indent=2, default=str))
        elif args.command == "integrity":
            print(json.dumps(integrity_report(session), indent=2, default=str))
        else:
            print(json.dumps(recent_runs(session, args.limit), indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
