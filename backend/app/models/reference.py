import enum
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, Provenance, pg_enum


class SeasonType(enum.StrEnum):
    regular = "regular"
    playin = "playin"
    playoffs = "playoffs"


class GameStatus(enum.StrEnum):
    scheduled = "scheduled"
    delayed = "delayed"
    in_progress = "in_progress"
    final = "final"
    postponed = "postponed"
    cancelled = "cancelled"


class Season(Base):
    __tablename__ = "seasons"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, autoincrement=False)
    label: Mapped[str] = mapped_column(String(7), unique=True)
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    is_atypical: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")


class Team(Base):
    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    abbreviation: Mapped[str] = mapped_column(String(3), unique=True)
    city: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(64))
    conference: Mapped[str | None] = mapped_column(String(8))
    division: Mapped[str | None] = mapped_column(String(16))
    primary_color: Mapped[str | None] = mapped_column(String(7))
    secondary_color: Mapped[str | None] = mapped_column(String(7))


class Player(Provenance, Base):
    __tablename__ = "players"
    __table_args__ = (
        Index(
            "ix_players_full_name_trgm",
            "full_name",
            postgresql_using="gin",
            postgresql_ops={"full_name": "gin_trgm_ops"},
        ),
        Index("ix_players_current_team_id", "current_team_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    full_name: Mapped[str] = mapped_column(String(96))
    first_name: Mapped[str | None] = mapped_column(String(64))
    last_name: Mapped[str | None] = mapped_column(String(64))
    position: Mapped[str | None] = mapped_column(String(16))
    height_inches: Mapped[int | None] = mapped_column(SmallInteger)
    weight_lbs: Mapped[int | None] = mapped_column(SmallInteger)
    birthdate: Mapped[date | None] = mapped_column(Date)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    current_team_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id", ondelete="RESTRICT"))
    from_year: Mapped[int | None] = mapped_column(SmallInteger)
    to_year: Mapped[int | None] = mapped_column(SmallInteger)


class Game(Provenance, Base):
    __tablename__ = "games"
    __table_args__ = (
        CheckConstraint("home_team_id <> away_team_id", name="distinct_teams"),
        Index("ix_games_game_date", "game_date"),
        Index("ix_games_season_type", "season_id", "season_type"),
        Index("ix_games_home_date", "home_team_id", "game_date"),
        Index("ix_games_away_date", "away_team_id", "game_date"),
        Index(
            "ix_games_scheduled_tipoff",
            "tipoff_at",
            postgresql_where="status = 'scheduled'",
        ),
    )

    id: Mapped[str] = mapped_column(String(10), primary_key=True)
    season_id: Mapped[int] = mapped_column(ForeignKey("seasons.id", ondelete="RESTRICT"))
    season_type: Mapped[SeasonType] = mapped_column(pg_enum(SeasonType, "season_type"))
    game_date: Mapped[date] = mapped_column(Date)
    tipoff_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    home_team_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="RESTRICT"))
    away_team_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="RESTRICT"))
    status: Mapped[GameStatus] = mapped_column(pg_enum(GameStatus, "game_status"))
    provider_status: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    status_observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    stats_finalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    home_score: Mapped[int | None] = mapped_column(SmallInteger)
    away_score: Mapped[int | None] = mapped_column(SmallInteger)
    arena: Mapped[str | None] = mapped_column(String(96))


BOX_COLUMNS = (
    "fgm", "fga", "fg3m", "fg3a", "ftm", "fta",
    "oreb", "dreb", "reb", "ast", "stl", "blk", "tov", "pf", "pts",
)  # fmt: skip


def _box_checks() -> tuple[CheckConstraint, ...]:
    nonneg = " AND ".join(f"{c} >= 0" for c in BOX_COLUMNS)
    return (
        CheckConstraint(nonneg, name="nonnegative"),
        CheckConstraint(
            "fgm <= fga AND fg3m <= fg3a AND ftm <= fta AND fg3m <= fgm AND fg3a <= fga",
            name="made_le_attempted",
        ),
    )


class _BoxScore:
    fgm: Mapped[int] = mapped_column(SmallInteger)
    fga: Mapped[int] = mapped_column(SmallInteger)
    fg3m: Mapped[int] = mapped_column(SmallInteger)
    fg3a: Mapped[int] = mapped_column(SmallInteger)
    ftm: Mapped[int] = mapped_column(SmallInteger)
    fta: Mapped[int] = mapped_column(SmallInteger)
    oreb: Mapped[int] = mapped_column(SmallInteger)
    dreb: Mapped[int] = mapped_column(SmallInteger)
    reb: Mapped[int] = mapped_column(SmallInteger)
    ast: Mapped[int] = mapped_column(SmallInteger)
    stl: Mapped[int] = mapped_column(SmallInteger)
    blk: Mapped[int] = mapped_column(SmallInteger)
    tov: Mapped[int] = mapped_column(SmallInteger)
    pf: Mapped[int] = mapped_column(SmallInteger)
    pts: Mapped[int] = mapped_column(SmallInteger)
    plus_minus: Mapped[int | None] = mapped_column(SmallInteger)


class TeamGameStats(_BoxScore, Provenance, Base):
    __tablename__ = "team_game_stats"
    __table_args__ = (*_box_checks(), Index("ix_tgs_team", "team_id", "game_id"))

    game_id: Mapped[str] = mapped_column(
        ForeignKey("games.id", ondelete="RESTRICT"), primary_key=True
    )
    team_id: Mapped[int] = mapped_column(
        ForeignKey("teams.id", ondelete="RESTRICT"), primary_key=True
    )
    is_home: Mapped[bool] = mapped_column(Boolean)
    minutes: Mapped[int] = mapped_column(SmallInteger)


class PlayerGameStats(_BoxScore, Provenance, Base):
    __tablename__ = "player_game_stats"
    __table_args__ = (
        *_box_checks(),
        CheckConstraint("minutes >= 0", name="minutes_nonnegative"),
        Index("ix_pgs_player_game", "player_id", "game_id"),
        Index("ix_pgs_team_game", "team_id", "game_id"),
    )

    game_id: Mapped[str] = mapped_column(
        ForeignKey("games.id", ondelete="RESTRICT"), primary_key=True
    )
    player_id: Mapped[int] = mapped_column(
        ForeignKey("players.id", ondelete="RESTRICT"), primary_key=True
    )
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="RESTRICT"))
    minutes: Mapped[Decimal] = mapped_column(Numeric(5, 2))
