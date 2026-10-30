from datetime import date, timedelta

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session, aliased

from app.api.deps import Context
from app.api.errors import ApiError, invalid_parameter, not_found
from app.models import (
    Game,
    GameStatus,
    Player,
    PlayerGameStats,
    Season,
    SeasonType,
    Team,
    TeamGameStats,
)
from app.schemas.common import Page
from app.schemas.resources import (
    BoxScore,
    BoxScorePlayer,
    BoxScoreTeam,
    GameDetail,
    GameSummary,
    GameTeam,
)
from app.services.common import box, nba_today, shooting, stat_line, team_ref
from app.stats import is_double_double

DATASET = "schedule"
BOX_DATASET = "final_box_scores"
MAX_WINDOW_DAYS = 31
UPCOMING_STATUSES = (GameStatus.scheduled, GameStatus.delayed)
UPCOMING_LIMIT = 100


def _summary_query() -> Select:
    home, away = aliased(Team), aliased(Team)
    return (
        select(Game, Season.label, home, away)
        .join(Season, Season.id == Game.season_id)
        .join(home, home.id == Game.home_team_id)
        .join(away, away.id == Game.away_team_id)
    )


def _summary(game: Game, season: str, home: Team, away: Team) -> GameSummary:
    return GameSummary(
        id=game.id,
        game_date=game.game_date,
        tipoff_at=game.tipoff_at,
        status=game.status,
        season=season,
        season_type=game.season_type,
        home=GameTeam(team=team_ref(home), score=game.home_score),
        away=GameTeam(team=team_ref(away), score=game.away_score),
        arena=game.arena,
    )


def _ordered(stmt: Select) -> Select:
    return stmt.order_by(Game.game_date, Game.tipoff_at.asc().nulls_last(), Game.id)


def list_games(
    ctx: Context, *, date_from: date | None, date_to: date | None, team_id: int | None,
    status: GameStatus | None, season_type: SeasonType | None, limit: int, offset: int,
) -> Page[GameSummary]:  # fmt: skip
    start = date_from or (date_to if date_to else nba_today(ctx.now))
    end = date_to or start
    if start > end:
        raise invalid_parameter("date_from", "date_from must be on or before date_to.")
    if (end - start).days >= MAX_WINDOW_DAYS:
        raise invalid_parameter(
            "date_to", f"The date window is limited to {MAX_WINDOW_DAYS} days.", "window_too_large"
        )
    stmt = _summary_query().where(Game.game_date.between(start, end))
    if team_id is not None:
        stmt = stmt.where(or_(Game.home_team_id == team_id, Game.away_team_id == team_id))
    if status:
        stmt = stmt.where(Game.status == status)
    if season_type:
        stmt = stmt.where(Game.season_type == season_type)
    total = ctx.session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = ctx.session.execute(_ordered(stmt).limit(limit).offset(offset))
    return Page(
        items=[_summary(*r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
        meta=ctx.meta(DATASET),
    )


def upcoming(ctx: Context, days: int, player_id: int | None) -> list[GameSummary]:
    today = nba_today(ctx.now)
    stmt = _summary_query().where(
        Game.status.in_(UPCOMING_STATUSES),
        Game.game_date.between(today, today + timedelta(days=days)),
    )
    if player_id is not None:
        player = ctx.session.get(Player, player_id)
        if player is None:
            raise not_found("player", player_id)
        if player.current_team_id is None:
            return []
        team = player.current_team_id
        stmt = stmt.where(or_(Game.home_team_id == team, Game.away_team_id == team))
    rows = ctx.session.execute(_ordered(stmt).limit(UPCOMING_LIMIT))
    return [_summary(*r) for r in rows]


def _game_or_404(session: Session, game_id: str) -> tuple[Game, str, Team, Team]:
    row = session.execute(_summary_query().where(Game.id == game_id)).first()
    if row is None:
        raise not_found("game", game_id)
    return tuple(row)


def game_detail(ctx: Context, game_id: str) -> GameDetail:
    row = _game_or_404(ctx.session, game_id)
    game = row[0]
    ctx.always_revalidate()
    return GameDetail(
        **_summary(*row).model_dump(),
        status_observed_at=game.status_observed_at,
        stats_finalized=game.stats_finalized_at is not None,
        meta=ctx.meta(DATASET),
    )


def boxscore(ctx: Context, game_id: str) -> BoxScore:
    def compute() -> BoxScore:
        row = _game_or_404(ctx.session, game_id)
        game = row[0]
        if game.status != GameStatus.final:
            raise ApiError(
                409, "game_not_final", f"Game {game_id} is {game.status.value}; no box score yet."
            )
        team_rows = ctx.session.execute(
            select(TeamGameStats, Team)
            .join(Team, Team.id == TeamGameStats.team_id)
            .where(TeamGameStats.game_id == game_id)
            .order_by(TeamGameStats.is_home.desc())
        )
        player_rows = ctx.session.execute(
            select(PlayerGameStats, Player.full_name)
            .join(Player, Player.id == PlayerGameStats.player_id)
            .where(PlayerGameStats.game_id == game_id)
            .order_by(PlayerGameStats.minutes.desc(), Player.full_name)
        )
        by_team: dict[int, list[BoxScorePlayer]] = {}
        for stats, name in player_rows:
            by_team.setdefault(stats.team_id, []).append(
                BoxScorePlayer(
                    player_id=stats.player_id,
                    full_name=name,
                    minutes=float(stats.minutes),
                    box=box(stats),
                    shooting=shooting(stats),
                    double_double=is_double_double(stat_line(game.game_date, stats)),
                )
            )
        return BoxScore(
            game=_summary(*row),
            stats_finalized=game.stats_finalized_at is not None,
            teams=[
                BoxScoreTeam(
                    team=team_ref(team),
                    is_home=stats.is_home,
                    minutes=stats.minutes,
                    totals=box(stats),
                    shooting=shooting(stats),
                    players=by_team.get(team.id, []),
                )
                for stats, team in team_rows
            ],
            meta=ctx.meta(BOX_DATASET),
        )

    result = ctx.cached_model("boxscore", 3600, game_id, BOX_DATASET, compute)
    ctx.always_revalidate()
    return result
