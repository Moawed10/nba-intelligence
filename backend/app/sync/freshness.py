"""Per-dataset freshness derived from ingestion_runs.

See docs/data-synchronization.md#freshness-tracking.
"""

from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from enum import StrEnum
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Game, GameStatus, IngestionRun, RunStatus


class Freshness(StrEnum):
    fresh = "fresh"
    aging = "aging"
    stale = "stale"
    unavailable = "unavailable"


@dataclass(frozen=True)
class DatasetPolicy:
    jobs: tuple[str, ...]
    aging_after: timedelta
    stale_after: timedelta


POLICIES: dict[str, DatasetPolicy] = {
    "schedule": DatasetPolicy(("schedule",), timedelta(hours=1), timedelta(hours=2)),
    "final_box_scores": DatasetPolicy(("game_logs",), timedelta(hours=12), timedelta(hours=24)),
    "player_game_logs": DatasetPolicy(("game_logs",), timedelta(hours=12), timedelta(hours=24)),
    "season_stats": DatasetPolicy(("game_logs",), timedelta(hours=12), timedelta(hours=24)),
    "team_stats": DatasetPolicy(("game_logs",), timedelta(hours=12), timedelta(hours=24)),
    "player_metadata": DatasetPolicy(("players", "teams"), timedelta(days=2), timedelta(days=4)),
    "career_history": DatasetPolicy(("player_careers",), timedelta(days=2), timedelta(days=4)),
    "injuries": DatasetPolicy(("injuries",), timedelta(hours=2), timedelta(hours=6)),
}
FAILURES_FOR_UNAVAILABLE = 3


@dataclass
class DatasetFreshness:
    dataset: str
    status: Freshness
    last_successful_sync: datetime | None
    last_attempted_sync: datetime | None
    last_error: str | None
    coverage_start: date | None
    coverage_end: date | None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def classify(
    now: datetime,
    last_success: datetime | None,
    recent_statuses: list[RunStatus],
    policy: DatasetPolicy,
) -> Freshness:
    """recent_statuses is newest first."""
    failing = len(recent_statuses) >= FAILURES_FOR_UNAVAILABLE and all(
        s != RunStatus.succeeded for s in recent_statuses[:FAILURES_FOR_UNAVAILABLE]
    )
    if last_success is None:
        return Freshness.unavailable
    age = now - last_success
    if failing and age > policy.stale_after:
        return Freshness.unavailable
    if age > policy.stale_after:
        return Freshness.stale
    if age > policy.aging_after:
        return Freshness.aging
    return Freshness.fresh


def dataset_freshness(session: Session, now: datetime) -> list[DatasetFreshness]:
    coverage_start, coverage_end = session.execute(
        select(func.min(Game.game_date), func.max(Game.game_date)).where(
            Game.status == GameStatus.final
        )
    ).one()
    result = []
    for dataset, policy in POLICIES.items():
        job_filter = IngestionRun.job.in_(policy.jobs)
        last_success = session.scalar(
            select(func.max(IngestionRun.finished_at)).where(
                job_filter, IngestionRun.status == RunStatus.succeeded
            )
        )
        recent = session.execute(
            select(IngestionRun.status, IngestionRun.started_at, IngestionRun.error)
            .where(job_filter, IngestionRun.status != RunStatus.running)
            .order_by(IngestionRun.id.desc())
            .limit(FAILURES_FOR_UNAVAILABLE)
        ).all()
        last_error = next((r.error for r in recent if r.status != RunStatus.succeeded), None)
        if recent and recent[0].status == RunStatus.succeeded:
            last_error = None
        has_games = dataset not in ("player_metadata", "career_history", "injuries")
        result.append(DatasetFreshness(
            dataset=dataset,
            status=classify(now, last_success, [r.status for r in recent], policy),
            last_successful_sync=last_success,
            last_attempted_sync=recent[0].started_at if recent else None,
            last_error=last_error.split(":")[0] if last_error else None,
            coverage_start=coverage_start if has_games else None,
            coverage_end=coverage_end if has_games else None,
        ))  # fmt: skip
    return result
