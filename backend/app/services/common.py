from datetime import date, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.errors import invalid_parameter
from app.ingestion.transforms import NBA_TZ
from app.models import BOX_COLUMNS, Game, PlayerGameStats, Season, Team, TeamGameStats
from app.schemas.common import BoxStats, Shooting, TeamRef
from app.stats import Line, ratio

LIMIT_DEFAULT = 25
LIMIT_MAX = 100

BoxRow = PlayerGameStats | TeamGameStats


def team_ref(team: Team) -> TeamRef:
    return TeamRef(
        id=team.id,
        abbreviation=team.abbreviation,
        city=team.city,
        name=team.name,
        primary_color=team.primary_color,
        secondary_color=team.secondary_color,
    )


def box(row: BoxRow) -> BoxStats:
    return BoxStats(plus_minus=row.plus_minus, **{c: getattr(row, c) for c in BOX_COLUMNS})


def shooting(row: BoxRow) -> Shooting:
    return Shooting.from_rates(
        ratio(row.fgm, row.fga), ratio(row.fg3m, row.fg3a), ratio(row.ftm, row.fta)
    )


def stat_line(game_date: date, row: BoxRow) -> Line:
    return Line(
        game_date=game_date,
        minutes=float(row.minutes),
        **{
            c: getattr(row, c)
            for c in Line.__dataclass_fields__
            if c not in ("game_date", "minutes")
        },
    )


def resolve_season(session: Session, label: str) -> Season:
    season = session.scalar(select(Season).where(Season.label == label))
    if season is None:
        raise invalid_parameter("season", f"Unknown season {label!r}.", "unknown_season")
    return season


def latest_season(session: Session) -> Season | None:
    return session.scalar(
        select(Season).where(Season.id == select(func.max(Game.season_id)).scalar_subquery())
    )


def nba_today(now: datetime) -> date:
    return now.astimezone(NBA_TZ).date()
