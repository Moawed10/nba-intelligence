from datetime import datetime

from pydantic import BaseModel

from app.stats import Aggregate, Rate
from app.sync.freshness import Freshness


class DataFreshness(BaseModel):
    dataset: str
    status: Freshness
    last_successful_sync: datetime | None
    data_version: int | None
    is_stale: bool


class Meta(BaseModel):
    data_freshness: DataFreshness


class TeamRef(BaseModel):
    id: int
    abbreviation: str
    city: str
    name: str
    primary_color: str | None = None
    secondary_color: str | None = None


class Page[T](BaseModel):
    items: list[T]
    total: int
    limit: int
    offset: int
    meta: Meta


class Shooting(BaseModel):
    fg_pct: float | None
    fg_pct_status: str | None
    fg3_pct: float | None
    fg3_pct_status: str | None
    ft_pct: float | None
    ft_pct_status: str | None

    @classmethod
    def from_rates(cls, fg: Rate, fg3: Rate, ft: Rate) -> "Shooting":
        return cls(
            fg_pct=fg.value, fg_pct_status=fg.status,
            fg3_pct=fg3.value, fg3_pct_status=fg3.status,
            ft_pct=ft.value, ft_pct_status=ft.status,
        )  # fmt: skip


class BoxStats(BaseModel):
    fgm: int
    fga: int
    fg3m: int
    fg3a: int
    ftm: int
    fta: int
    oreb: int
    dreb: int
    reb: int
    ast: int
    stl: int
    blk: int
    tov: int
    pf: int
    pts: int
    plus_minus: int | None


class PerGame(BaseModel):
    pts: float | None
    reb: float | None
    ast: float | None
    fg3m: float | None
    stl: float | None
    blk: float | None
    tov: float | None
    min: float | None


class Totals(BaseModel):
    pts: int
    reb: int
    ast: int
    fg3m: int
    fg3a: int
    fgm: int
    fga: int
    ftm: int
    fta: int
    oreb: int
    dreb: int
    stl: int
    blk: int
    tov: int
    pf: int
    min: float


class StatSummary(BaseModel):
    games_played: int
    per_game: PerGame
    totals: Totals
    shooting: Shooting
    efg_pct: float | None
    ts_pct: float | None
    double_doubles: int
    pts_consistency: float | None

    @classmethod
    def from_aggregate(cls, agg: Aggregate) -> "StatSummary":
        return cls(
            games_played=agg.games_played,
            per_game=PerGame(**agg.per_game),
            totals=Totals(**agg.totals),
            shooting=Shooting.from_rates(agg.fg_pct, agg.fg3_pct, agg.ft_pct),
            efg_pct=agg.efg_pct.value,
            ts_pct=agg.ts_pct.value,
            double_doubles=agg.double_doubles,
            pts_consistency=agg.pts_consistency,
        )
