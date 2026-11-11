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


class InjuryReport(BaseModel):
    """Current listing from the source. `return_date` is its rough estimate, not a promise."""

    status: str
    injury: str | None
    detail: str | None
    side: str | None
    return_date: date | None
    reported_at: datetime
    source: str = "ESPN"


class PlayerSummary(BaseModel):
    id: int
    full_name: str
    jersey_number: str | None = None
    position: str | None
    is_active: bool
    team: TeamRef | None
    from_year: int | None
    to_year: int | None
    # Former players only: the team they last played for, as listed that season (e.g. "SEA").
    final_team: str | None = None


class PlayerSearchResult(BaseModel):
    id: int
    full_name: str
    position: str | None
    is_active: bool
    team_id: int | None = None
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
    injury: InjuryReport | None = None
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


class RosterPlayer(PlayerSummary):
    injury: InjuryReport | None = None


class TeamDetail(BaseModel):
    team: Team
    season: str
    record: Record
    roster: list[RosterPlayer]
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
    live_status: str | None
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
    tov: float | None
    plus_minus: float | None
    fg_pct: float | None
    fg_pct_status: str | None
    fg3_pct: float | None
    ft_pct: float | None
    ts_pct: float | None


class CareerTotals(BaseModel):
    """Regular-season totals as published by the source. None means the league recorded that
    statistic in none of the seasons counted (steals and blocks begin 1973-74, threes 1979-80).
    """

    games_played: int
    min: int | None
    pts: int
    reb: int | None
    ast: int | None
    fg3m: int | None
    stl: int | None
    blk: int | None
    tov: int | None


class DirectoryPlayer(PlayerSummary):
    season_averages: SeasonAverages | None
    # Only for all-time listings: career totals, or with a team, totals for that franchise.
    totals: CareerTotals | None = None


class Leader(BaseModel):
    rank: int
    player_id: int
    full_name: str
    team: TeamRef | None
    games_played: int
    value: float
    total: float


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
    live: list[GameSummary]
    upcoming: list[GameSummary]
    recent: list[GameSummary]
    standouts: Standouts
    leaders: Leaders | None
    model: ModelSnapshot | None
    datasets: list[DatasetStatus]


class HistoricSeason(BaseModel):
    """One regular season of a franchise as published by the source. None means not recorded."""

    season: str
    city: str
    name: str
    games: int
    wins: int
    losses: int
    win_pct: float
    conference_rank: int | None
    division_rank: int | None
    playoff_wins: int | None
    playoff_losses: int | None
    finals: Literal["finals", "champion"] | None
    per_game: dict[str, float | None]
    fg_pct: float | None
    fg3_pct: float | None
    ft_pct: float | None
    pace: float | None
    off_rating: float | None
    def_rating: float | None
    net_rating: float | None


class VenueSplit(BaseModel):
    """A team's results in one setting; a point-margin gap is an association, not a cause."""

    games: int
    wins: int
    losses: int
    pts_per_game: float | None
    opp_pts_per_game: float | None
    margin_per_game: float | None


class PlayerVenueSplit(BaseModel):
    player_id: int
    full_name: str
    home_games: int
    away_games: int
    home: dict[str, float | None]
    away: dict[str, float | None]


class HomeCourt(BaseModel):
    team_id: int
    season: str
    home: VenueSplit
    away: VenueSplit
    average_attendance: int | None
    attendance_games: int
    players: list[PlayerVenueSplit]
    meta: Meta


class FanPostOut(BaseModel):
    url: str
    author_handle: str
    author_name: str | None
    text: str
    posted_at: datetime
    likes: int
    reposts: int
    replies: int


class FanPosts(BaseModel):
    team_id: int
    source: str
    posts: list[FanPostOut]
    meta: Meta


class TeamHistory(BaseModel):
    team: TeamRef
    seasons: list[HistoricSeason]
    meta: Meta


class LiveStat(BaseModel):
    stat: str
    n: int
    mae: float | None
    interval_coverage: float | None


class LiveDoubleDouble(BaseModel):
    n: int
    brier: float | None


class LiveGameScores(BaseModel):
    games: int
    points_mae: float
    interval_coverage: float
    brier: float
    winner_accuracy: float


class LiveAccuracy(BaseModel):
    """Final pregame forecasts of this release scored against box scores after the games."""

    version: str
    status: str
    activated_at: datetime | None
    games: int
    stats: list[LiveStat]
    double_double: LiveDoubleDouble | None
    game_scores: LiveGameScores | None


class MatchupDefender(BaseModel):
    """Someone now on the opponent who has guarded this player in past games. Not a prediction of
    tonight's matchup: the NBA's tracking data is only published after a game."""

    player_id: int
    full_name: str
    games: int
    possessions: float
    pts_per_100: float


class MatchupHistory(BaseModel):
    """A player's games against one opponent, every season stored (2018-19 onward)."""

    player_id: int
    opponent: TeamRef
    games: int
    wins: int
    losses: int
    averages: dict[str, float | None]
    fg_pct: float | None
    fg3_pct: float | None
    first_season: str | None
    last_season: str | None
    meetings: list[PlayerGameLine]
    defenders: list[MatchupDefender] = []
    usual_pts_per_100: float | None = None
    meta: Meta


class CareerStint(BaseModel):
    """A team the player appeared for that season; `team` is null for defunct franchises."""

    abbreviation: str
    team: TeamRef | None


class CareerLine(BaseModel):
    """Per-game averages and shooting percentages. A statistic the league did not record yet
    (e.g. steals before 1973-74, 3-pointers before 1979-80) is null."""

    games: int
    games_started: int | None
    per_game: dict[str, float | None]
    fg_pct: float | None
    fg3_pct: float | None
    ft_pct: float | None


class CareerSeason(CareerLine):
    season: str
    age: int | None
    teams: list[CareerStint]


class CareerTable(BaseModel):
    seasons: list[CareerSeason]
    totals: CareerLine | None
    # Statistics whose career average leaves out seasons before the league recorded them.
    partial: dict[str, str]


class PlayerCareer(BaseModel):
    """Every season of a player's career as published by the league, oldest first."""

    player_id: int
    regular: CareerTable
    playoffs: CareerTable
    meta: Meta


class CalibrationPoint(BaseModel):
    """One tenth of the predictions, ordered by predicted value: average predicted vs actual."""

    predicted: float
    actual: float
    n: int


class ResidualBin(BaseModel):
    """Games whose miss (actual minus predicted) fell in [lower, upper)."""

    lower: float
    upper: float
    n: int


class CoverageBin(BaseModel):
    """Interval coverage for predictions in one predicted-minutes bin of the calibration."""

    minutes_from: float | None
    minutes_to: float | None
    n: int
    coverage: float | None


class ModelAnalytics(BaseModel):
    """Stored predictions of one release and kind for one statistic, scored against box scores.
    Backtests come from the held-out models on the test season; pregame rows are live forecasts."""

    version: str
    kind: Literal["backtest", "pregame"]
    stat: str
    algorithm: str | None
    n: int
    first_game: date | None
    last_game: date | None
    mae: float | None
    rmse: float | None
    bias: float | None
    interval_level: float
    coverage: float | None
    calibration: list[CalibrationPoint]
    residuals: list[ResidualBin]
    coverage_by_bin: list[CoverageBin]


class HistoryValue(BaseModel):
    point: float
    lower: float
    upper: float
    actual: float | None
    within_interval: bool | None


class HistoryEntry(BaseModel):
    """A stored prediction for one game next to what happened."""

    prediction_id: str
    kind: Literal["backtest", "pregame"]
    release_version: str
    game_id: str
    game_date: date
    opponent: TeamRef
    is_home: bool
    values: dict[str, HistoryValue]


class PredictionHistory(BaseModel):
    player_id: int
    kind: Literal["backtest", "pregame"]
    entries: list[HistoryEntry]


class PercentileAxis(BaseModel):
    """One radar axis: each player's season value and league percentile (0–100, higher is
    better). A percentile is null when the player has no value for it."""

    key: str
    label: str
    values: list[float | None]
    percentiles: list[float | None]


class PlayerComparison(BaseModel):
    """Two players in the same regular season. `season` is null when they never shared one."""

    players: list[PlayerSummary]
    season: str | None
    common_seasons: list[str]
    lines: list[SeasonLine]
    axes: list[PercentileAxis]
    qualified_players: int
    qualification: str
    # Whether each player met the qualification themselves (they are ranked either way).
    qualified: list[bool]
    meta: Meta
