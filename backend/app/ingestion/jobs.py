import json
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from nba_api.stats.endpoints import (
    CommonAllPlayers,
    LeagueDashTeamStats,
    LeagueGameLog,
    LeagueStandingsV3,
    PlayerCareerStats,
    PlayerIndex,
    ScheduleLeagueV2,
    TeamYearByYearStats,
)
from nba_api.stats.static import teams as static_teams
from sqlalchemy import Engine, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.config import get_settings
from app.ingestion.client import FetchResult, StatsSource, StatsSourceError
from app.ingestion.lifecycle import resolve_status
from app.ingestion.transforms import (
    ADVANCED_FIRST_SEASON,
    ATYPICAL_SEASONS,
    LOG_SEASON_TYPE,
    Rejection,
    current_season_start_year,
    season_label,
    transform_player_career,
    transform_player_logs,
    transform_players,
    transform_schedule,
    transform_team_advanced,
    transform_team_history,
    transform_team_logs,
    transform_teams,
)
from app.ingestion.writer import UpsertCounts, detect_corrections, provenance, upsert
from app.models import (
    BOX_COLUMNS,
    Game,
    GameStatus,
    IngestionRun,
    Player,
    PlayerGameStats,
    PlayerSeason,
    RunStatus,
    Season,
    SeasonType,
    SyncEvent,
    SyncEventType,
    Team,
    TeamGameStats,
    TeamSeason,
)

log = logging.getLogger(__name__)


class PartialResponseError(Exception):
    """The source returned fewer completed records than are already stored."""


@dataclass
class RunContext:
    session: Session
    run_id: int
    fetched: int = 0
    valid: int = 0
    inserted: int = 0
    updated: int = 0
    rejected: int = 0
    retries: int = 0
    rejection_samples: list[dict[str, Any]] = field(default_factory=list)

    def counted(self, counts: UpsertCounts) -> None:
        self.inserted += counts.inserted
        self.updated += counts.updated

    def fetched_from(self, result: FetchResult) -> Any:
        self.retries += max(0, result.attempts - 1)
        frame = result.frames[0]
        self.fetched += len(frame)
        return frame

    def reject(self, rejections: list[Rejection]) -> None:
        self.rejected += len(rejections)
        for r in rejections[: max(0, 20 - len(self.rejection_samples))]:
            self.rejection_samples.append({"key": r.key, "reason": r.reason})


def _start_run(engine: Engine, job: str, params: dict[str, Any]) -> int:
    with Session(engine) as s, s.begin():
        run = IngestionRun(job=job, params=params, status=RunStatus.running,
                           heartbeat_at=func.now())  # fmt: skip
        s.add(run)
        s.flush()
        return run.id


def _finish_run(engine: Engine, run_id: int, status: RunStatus, ctx: RunContext,
                error: str | None = None) -> None:  # fmt: skip
    with Session(engine) as s, s.begin():
        s.execute(
            update(IngestionRun)
            .where(IngestionRun.id == run_id)
            .values(
                status=status, finished_at=func.now(), heartbeat_at=func.now(),
                rows_fetched=ctx.fetched, rows_valid=ctx.valid, rows_inserted=ctx.inserted,
                rows_updated=ctx.updated, rows_rejected=ctx.rejected, retry_count=ctx.retries,
                error=error,
            )
        )  # fmt: skip
        if status == RunStatus.failed:
            emit_event(s, SyncEventType.INGESTION_FAILED, f"INGESTION_FAILED:{run_id}",
                       {"error": error}, run_id)  # fmt: skip


def run_job(
    engine: Engine, job: str, params: dict[str, Any], body: Callable[[RunContext], None]
) -> IngestionRun | None:
    """Runs body in one transaction under a per-job advisory lock and records the run.

    Returns None without running when another process holds the same job's lock. A failure rolls
    back every write of the body, so previously committed data is untouched.
    """
    lock_key = f"{job}:{json.dumps(params, sort_keys=True)}"
    with Session(engine) as session:
        acquired = session.scalar(
            select(func.pg_try_advisory_xact_lock(func.hashtextextended(lock_key, 0)))
        )
        if not acquired:
            log.info("job already running elsewhere; skipped", extra={"job": job, "params": params})
            session.rollback()
            return None
        run_id = _start_run(engine, job, params)
        ctx = RunContext(session=session, run_id=run_id)
        try:
            body(ctx)
            session.commit()
        except Exception as exc:
            session.rollback()
            message = f"{type(exc).__name__}: {exc}"[:2000]
            _finish_run(engine, run_id, RunStatus.failed, ctx, error=message)
            log.error("ingestion job failed", extra={"job": job, "params": params, "run_id": run_id,
                                                      "error": message})  # fmt: skip
            raise
    _finish_run(engine, run_id, RunStatus.succeeded, ctx)
    log.info("ingestion job succeeded", extra={
        "job": job, "params": params, "run_id": run_id, "fetched": ctx.fetched, "valid": ctx.valid,
        "inserted": ctx.inserted, "updated": ctx.updated, "rejected": ctx.rejected,
        "rejection_samples": ctx.rejection_samples[:5],
    })  # fmt: skip
    with Session(engine) as s:
        return s.get(IngestionRun, run_id)


def emit_event(session: Session, type_: SyncEventType, dedupe_key: str, payload: dict[str, Any],
               run_id: int | None) -> None:  # fmt: skip
    session.execute(
        insert(SyncEvent)
        .values(type=type_, dedupe_key=dedupe_key, payload=payload, ingestion_run_id=run_id)
        .on_conflict_do_nothing(index_elements=["dedupe_key"])
    )


def ensure_season(session: Session, start_year: int) -> None:
    upsert(session, Season, [{
        "id": start_year, "label": season_label(start_year),
        "is_atypical": start_year in ATYPICAL_SEASONS,
    }], ["id"])  # fmt: skip


def _is_completed_season(start_year: int) -> bool:
    return start_year < current_season_start_year()


def ingest_teams(client: StatsSource, season: int) -> Callable[[RunContext], None]:
    def body(ctx: RunContext) -> None:
        standings = ctx.fetched_from(
            client.fetch(LeagueStandingsV3, season=season_label(season),
                         cacheable=_is_completed_season(season))
        )  # fmt: skip
        rows = transform_teams(static_teams.get_teams(), standings)
        ctx.valid += len(rows)
        ctx.counted(upsert(ctx.session, Team, rows, ["id"]))

    return body


def ingest_team_history(client: StatsSource) -> Callable[[RunContext], None]:
    """Every franchise's regular seasons under that year's name, plus pace and ratings from
    1996-97 (the first season the source publishes them)."""

    def body(ctx: RunContext) -> None:
        rows: list[dict[str, Any]] = []
        for team_id in ctx.session.scalars(select(Team.id).order_by(Team.id)).all():
            frame = ctx.fetched_from(
                client.fetch(TeamYearByYearStats, team_id=team_id, per_mode_simple="Totals",
                             season_type_all_star="Regular Season")
            )  # fmt: skip
            rows += transform_team_history(frame)
        for season in sorted({r["season_id"] for r in rows}):
            ensure_season(ctx.session, season)
        advanced: dict[tuple[int, int], dict[str, float | None]] = {}
        for season in range(ADVANCED_FIRST_SEASON, current_season_start_year() + 1):
            frame = ctx.fetched_from(
                client.fetch(LeagueDashTeamStats, season=season_label(season),
                             measure_type_detailed_defense="Advanced", per_mode_detailed="PerGame",
                             cacheable=_is_completed_season(season))
            )  # fmt: skip
            for team_id, values in transform_team_advanced(frame).items():
                advanced[(team_id, season)] = values
        empty = {"pace": None, "off_rating": None, "def_rating": None, "net_rating": None}
        for row in rows:
            row.update(advanced.get((row["team_id"], row["season_id"]), empty))
        ctx.valid += len(rows)
        ctx.counted(
            upsert(ctx.session, TeamSeason, rows, ["team_id", "season_id"],
                   provenance=provenance(ctx.run_id, "TeamYearByYearStats"))
        )  # fmt: skip

    return body


# PlayerCareerStats result sets, in the source's response order.
CAREER_FRAMES = {SeasonType.regular: 0, SeasonType.playoffs: 2}
# This many failed players in a row means the source is refusing requests: stop the batch early.
CAREER_FAILURE_LIMIT = 5


def ingest_player_careers(
    client: StatsSource, player_ids: list[int]
) -> Callable[[RunContext], None]:
    """Every season of each player's career, regular season and playoffs (one request each).
    Finished careers are cached on disk, so re-running a batch only refetches active players.
    A player the source fails on is rejected and the rest of the batch is kept; after
    CAREER_FAILURE_LIMIT failures in a row the batch stops, and a re-run picks up the rest."""

    def body(ctx: RunContext) -> None:
        active = set(ctx.session.scalars(select(Player.id).where(Player.is_active)).all())
        failures = 0
        for player_id in player_ids:
            try:
                result = client.fetch(PlayerCareerStats, player_id=player_id, per_mode36="Totals",
                                      cacheable=player_id not in active)  # fmt: skip
            except StatsSourceError as error:
                ctx.reject(
                    [Rejection({"player_id": player_id}, f"{type(error).__name__}: {error}")]
                )
                failures += 1
                if failures >= CAREER_FAILURE_LIMIT:
                    log.warning("career source refusing requests; batch stopped early",
                                extra={"player_id": player_id})  # fmt: skip
                    return
                continue
            failures = 0
            ctx.retries += max(0, result.attempts - 1)
            rows: list[dict[str, Any]] = []
            for season_type, index in CAREER_FRAMES.items():
                frame = result.frames[index]
                ctx.fetched += len(frame)
                rows += transform_player_career(frame, season_type)
            for season in sorted({r["season_id"] for r in rows}):
                ensure_season(ctx.session, season)
            ctx.valid += len(rows)
            if rows:
                ctx.counted(
                    upsert(ctx.session, PlayerSeason, rows,
                           ["player_id", "season_type", "season_id", "team_abbreviation"],
                           provenance=provenance(ctx.run_id, "PlayerCareerStats"))
                )  # fmt: skip

    return body


def ingest_players(client: StatsSource, season: int) -> Callable[[RunContext], None]:
    def body(ctx: RunContext) -> None:
        label = season_label(season)
        all_players = ctx.fetched_from(
            client.fetch(CommonAllPlayers, is_only_current_season=0, season=label)
        )
        index = client.fetch(PlayerIndex, season=label)
        ctx.retries += max(0, index.attempts - 1)
        rows = transform_players(all_players, index.frames[0])
        team_ids = set(ctx.session.scalars(select(Team.id)))
        for row in rows:
            if row["current_team_id"] not in team_ids:
                row["current_team_id"] = None
        ctx.valid += len(rows)
        ctx.counted(upsert(ctx.session, Player, rows, ["id"],
                           provenance=provenance(ctx.run_id, "CommonAllPlayers")))  # fmt: skip

    return body


def _stored_player_lines(session: Session, season: int, season_type: SeasonType) -> int:
    return (
        session.scalar(
            select(func.count())
            .select_from(PlayerGameStats)
            .join(Game, Game.id == PlayerGameStats.game_id)
            .where(Game.season_id == season, Game.season_type == season_type)
        )
        or 0
    )


def ingest_game_logs(
    client: StatsSource, season: int, season_type: SeasonType
) -> Callable[[RunContext], None]:
    def body(ctx: RunContext) -> None:
        settings = get_settings()
        session, label = ctx.session, season_label(season)
        common = {"season": label, "season_type_all_star": LOG_SEASON_TYPE[season_type],
                  "cacheable": _is_completed_season(season)}  # fmt: skip
        team_df = ctx.fetched_from(
            client.fetch(LeagueGameLog, player_or_team_abbreviation="T", **common)
        )
        player_df = ctx.fetched_from(
            client.fetch(LeagueGameLog, player_or_team_abbreviation="P", **common)
        )
        ensure_season(session, season)
        if team_df.empty:
            return

        log_game_ids = team_df["GAME_ID"].astype(str).unique().tolist()
        scheduled_home = dict(session.execute(
            select(Game.id, Game.home_team_id).where(Game.id.in_(log_game_ids))
        ).all())  # fmt: skip
        team_result = transform_team_logs(team_df, season_type, scheduled_home)
        team_minutes = {(r["game_id"], r["team_id"]): r["minutes"]
                        for r in team_result.team_stats.rows}  # fmt: skip
        player_result = transform_player_logs(
            player_df, team_minutes, settings.team_minutes_tolerance
        )
        game_rows, team_rows = team_result.games.rows, team_result.team_stats.rows
        player_rows = player_result.stats.rows
        ctx.reject(team_result.games.rejections + player_result.stats.rejections)
        ctx.valid += len(team_rows) + len(player_rows)

        stored = _stored_player_lines(session, season, season_type)
        if len(player_rows) < stored:
            raise PartialResponseError(
                f"{label} {season_type}: source returned {len(player_rows)} valid player lines, "
                f"{stored} already stored"
            )

        known = set(session.scalars(
            select(Player.id).where(Player.id.in_([p["id"] for p in player_result.players]))
        ))  # fmt: skip
        stubs = [p for p in player_result.players if p["id"] not in known]
        ctx.counted(upsert(session, Player, stubs, ["id"],
                           provenance=provenance(ctx.run_id, "LeagueGameLog")))  # fmt: skip

        existing = dict(session.execute(
            select(Game.id, Game.status).where(Game.id.in_([g["id"] for g in game_rows]))
        ).all())  # fmt: skip
        accepted_games = []
        for game in game_rows:
            status, ok = resolve_status(existing.get(game["id"]), GameStatus.final)
            if not ok:
                ctx.reject(
                    [
                        Rejection(
                            {"game_id": game["id"]},
                            f"illegal transition {existing[game['id']]} -> final",
                        )
                    ]
                )
                continue
            accepted_games.append({**game, "status": status})
            if existing.get(game["id"]) not in (None, GameStatus.final):
                emit_event(
                    session,
                    SyncEventType.GAME_COMPLETED,
                    f"GAME_COMPLETED:{game['id']}",
                    {"game_id": game["id"]},
                    ctx.run_id,
                )

        accepted_ids = {g["id"] for g in accepted_games}
        team_rows = [r for r in team_rows if r["game_id"] in accepted_ids]
        player_rows = [r for r in player_rows if r["game_id"] in accepted_ids]

        box = (*BOX_COLUMNS, "plus_minus", "minutes")
        detect_corrections(session, Game, accepted_games, ["id"], ["home_score", "away_score"],
                           ctx.run_id)  # fmt: skip
        detect_corrections(session, TeamGameStats, team_rows, ["game_id", "team_id"], box,
                           ctx.run_id)  # fmt: skip
        corrected = detect_corrections(
            session,
            PlayerGameStats,
            player_rows,
            ["game_id", "player_id"],
            (*box, "team_id"),
            ctx.run_id,
        )
        for c in corrected:
            emit_event(
                session,
                SyncEventType.HISTORICAL_DATA_CORRECTED,
                f"CORRECTION:{ctx.run_id}:{c.record_key['game_id']}:"
                f"{c.record_key['player_id']}:{c.column_name}",
                {"record_key": c.record_key, "column": c.column_name},
                ctx.run_id,
            )

        prov = provenance(ctx.run_id, "LeagueGameLog")
        ctx.counted(upsert(session, Game, accepted_games, ["id"], provenance=prov))
        ctx.counted(upsert(session, TeamGameStats, team_rows, ["game_id", "team_id"],
                           provenance=prov))  # fmt: skip
        ctx.counted(upsert(session, PlayerGameStats, player_rows, ["game_id", "player_id"],
                           provenance=prov))  # fmt: skip

        if season_type == SeasonType.regular and accepted_games:
            dates = [g["game_date"] for g in accepted_games]
            session.execute(update(Season).where(Season.id == season).values(
                start_date=func.least(func.coalesce(Season.start_date, min(dates)), min(dates)),
                end_date=func.greatest(func.coalesce(Season.end_date, max(dates)), max(dates)),
            ))  # fmt: skip

    return body


def ingest_schedule(client: StatsSource, season: int) -> Callable[[RunContext], None]:
    def body(ctx: RunContext) -> None:
        session = ctx.session
        df = ctx.fetched_from(client.fetch(ScheduleLeagueV2, season=season_label(season),
                                           cacheable=_is_completed_season(season)))  # fmt: skip
        result = transform_schedule(df, datetime.now(UTC))
        ctx.reject(result.rejections)
        ensure_season(session, season)

        existing = {
            gid: (status, tipoff)
            for gid, status, tipoff in session.execute(
                select(Game.id, Game.status, Game.tipoff_at).where(
                    Game.id.in_([r["id"] for r in result.rows])
                )
            )
        }
        rows = []
        for row in result.rows:
            current, current_tipoff = existing.get(row["id"], (None, None))
            status, ok = resolve_status(current, row["status"])
            if not ok:
                ctx.reject(
                    [
                        Rejection(
                            {"game_id": row["id"]},
                            f"illegal transition {current} -> {row['status']}",
                        )
                    ]
                )
                continue
            rows.append(row)
            if current is None:
                continue
            gid = row["id"]
            if status != current and status == GameStatus.in_progress:
                emit_event(
                    session,
                    SyncEventType.GAME_STARTED,
                    f"GAME_STARTED:{gid}",
                    {"game_id": gid},
                    ctx.run_id,
                )
            elif status != current and status == GameStatus.final:
                emit_event(
                    session,
                    SyncEventType.GAME_COMPLETED,
                    f"GAME_COMPLETED:{gid}",
                    {"game_id": gid},
                    ctx.run_id,
                )
            elif status != current or row["tipoff_at"] != current_tipoff:
                stamp = row["tipoff_at"].isoformat() if row["tipoff_at"] else "none"
                emit_event(
                    session,
                    SyncEventType.GAME_SCHEDULE_UPDATED,
                    f"GAME_SCHEDULE_UPDATED:{gid}:{status}:{stamp}",
                    {"game_id": gid, "status": status, "tipoff_at": stamp},
                    ctx.run_id,
                )
        ctx.valid += len(rows)
        ctx.counted(upsert(session, Game, rows, ["id"],
                           provenance=provenance(ctx.run_id, "ScheduleLeagueV2"),
                           compare_exclude=frozenset({"status_observed_at"})))  # fmt: skip

    return body
