from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel

from app.models import GameStatus, SeasonType
from app.schemas.common import BoxStats, Meta, Shooting, StatSummary, TeamRef
from app.sync.freshness import Freshness

TrendStat = Literal["pts", "reb", "ast", "fg3m", "stl", "blk", "min"]


class Team(TeamRef):
    conference: str | None
    division: str | None


class PlayerSummary(BaseModel):
    id: int
    full_name: str
    position: str | None
    is_active: bool
    team: TeamRef | None
    from_year: int | None
    to_year: int | None


class PlayerSearchResult(BaseModel):
    id: int
    full_name: str
    position: str | None
    is_active: bool
    team_abbreviation: str | None
    team_primary_color: str | None = None


class PlayerIdentity(PlayerSummary):
    first_name: str | None
    last_name: str | None
    height_inches: int | None
    weight_lbs: int | None
    birthdate: date | None


class PlayerGameLine(BaseModel):
    game_id: str
    game_date: date
    season: str
    season_type: SeasonType
    team_abbreviation: str
    opponent: TeamRef
    is_home: bool
    result: Literal["W", "L"] | None
    team_score: int | None
    opponent_score: int | None
    minutes: float
    box: BoxStats
    shooting: Shooting
    double_double: bool


class SeasonLine(StatSummary):
    season: str
    season_type: SeasonType


class PlayerProfile(BaseModel):
    player: PlayerIdentity
    current_season: SeasonLine | None
    last_games: list[PlayerGameLine]
    meta: Meta


class Split(BaseModel):
    key: Literal["home", "away", "rest_0", "rest_1", "rest_2_plus"]
    label: str
    summary: StatSummary


class PlayerSeasonStats(BaseModel):
    player_id: int
    season_type: SeasonType
    seasons: list[SeasonLine]
    splits_season: str | None
    splits: list[Split]
    meta: Meta


class TrendPoint(BaseModel):
    game_id: str
    game_date: date
    opponent_abbreviation: str
    is_home: bool
    value: float
    rolling_3: float | None
    rolling_5: float | None
    rolling_10: float | None


class PlayerTrends(BaseModel):
    player_id: int
    stat: TrendStat
    season: str
    season_type: SeasonType | None
    games_played: int
    average: float | None
    points: list[TrendPoint]
    meta: Meta


class Record(BaseModel):
    wins: int
    losses: int


class TeamDetail(BaseModel):
    team: Team
    season: str
    record: Record
    roster: list[PlayerSummary]
    meta: Meta


class TeamSeasonStats(BaseModel):
    team_id: int
    season: str
    season_type: SeasonType
    games: int
    record: Record
    pts_per_game: float | None
    opp_pts_per_game: float | None
    possessions_per_game: float | None
    pace: float | None
    offensive_rating: float | None
    defensive_rating: float | None
    net_rating: float | None
    shooting: Shooting
    meta: Meta


class GameTeam(BaseModel):
    team: TeamRef
    score: int | None


class GameSummary(BaseModel):
    id: str
    game_date: date
    tipoff_at: datetime | None
    status: GameStatus
    season: str
    season_type: SeasonType
    home: GameTeam
    away: GameTeam
    arena: str | None


class GameDetail(GameSummary):
    status_observed_at: datetime | None
    stats_finalized: bool
    meta: Meta


class BoxScorePlayer(BaseModel):
    player_id: int
    full_name: str
    minutes: float
    box: BoxStats
    shooting: Shooting
    double_double: bool


class BoxScoreTeam(BaseModel):
    team: TeamRef
    is_home: bool
    minutes: int
    totals: BoxStats
    shooting: Shooting
    players: list[BoxScorePlayer]


class BoxScore(BaseModel):
    game: GameSummary
    stats_finalized: bool
    teams: list[BoxScoreTeam]
    meta: Meta


class Health(BaseModel):
    status: Literal["ok"]


class Readiness(BaseModel):
    status: Literal["ready", "not_ready"]
    checks: dict[str, str]


class DatasetStatus(BaseModel):
    dataset: str
    status: Freshness
    last_successful_sync: datetime | None
    last_attempted_sync: datetime | None
    last_error: str | None
    coverage_start: date | None
    coverage_end: date | None


class SeasonCoverage(BaseModel):
    season: str
    final_games: int
    remaining_games: int
    player_lines: int


class DataStatus(BaseModel):
    generated_at: datetime
    data_version: int | None
    datasets: list[DatasetStatus]
    seasons: list[SeasonCoverage]
    row_counts: dict[str, int]


LeaderStat = Literal["pts", "reb", "ast", "fg3m", "stl", "blk", "min"]


class SeasonAverages(BaseModel):
    season: str
    games_played: int
    min: float | None
    pts: float | None
    reb: float | None
    ast: float | None
    fg3m: float | None
    stl: float | None
    blk: float | None
    fg_pct: float | None
    fg_pct_status: str | None


class DirectoryPlayer(PlayerSummary):
    season_averages: SeasonAverages | None


class Leader(BaseModel):
    rank: int
    player_id: int
    full_name: str
    team: TeamRef | None
    games_played: int
    value: float


class Leaders(BaseModel):
    stat: LeaderStat
    season: str
    minimum_games: int
    qualified_players: int
    leaders: list[Leader]
    meta: Meta


class Performance(BaseModel):
    player_id: int
    full_name: str
    game_id: str
    game_date: date
    team: TeamRef
    opponent: TeamRef
    is_home: bool
    result: Literal["W", "L"] | None
    minutes: float
    box: BoxStats
    shooting: Shooting
    game_score: float
    double_double: bool


class Standouts(BaseModel):
    window_start: date | None
    window_end: date | None
    criterion: str
    performances: list[Performance]
    meta: Meta


class TargetMetrics(BaseModel):
    target: str
    algorithm: str
    n: int
    mae: float | None
    rmse: float | None
    r2: float | None
    baseline_mae: float | None
    interval_coverage: float | None
    brier: float | None
    log_loss: float | None


class AlgorithmMetrics(BaseModel):
    target: str
    algorithm: str
    selected: bool
    validation_mae: float | None
    test_mae: float | None
    test_rmse: float | None
    test_r2: float | None


class ModelReleaseSummary(BaseModel):
    version: str
    status: str
    created_at: datetime
    activated_at: datetime | None
    data_version: int
    feature_schema_version: str
    train_start: date
    train_end: date
    val_start: date
    val_end: date
    test_start: date
    test_end: date
    git_sha: str | None
    selected: dict[str, str]


class ModelReleaseDetail(ModelReleaseSummary):
    features: list[str]
    test_season: str | None
    selected_metrics: list[TargetMetrics]
    algorithms: list[AlgorithmMetrics]
    interval_calibration: dict[str, dict]


class ModelSnapshot(BaseModel):
    release: ModelReleaseSummary
    test_season: str | None
    metrics: list[TargetMetrics]


class Overview(BaseModel):
    generated_at: datetime
    today: date
    upcoming: list[GameSummary]
    recent: list[GameSummary]
    standouts: Standouts
    leaders: Leaders | None
    model: ModelSnapshot | None
    datasets: list[DatasetStatus]
