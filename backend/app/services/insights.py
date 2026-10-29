"""Season averages, leaders and standout performances built on the shared stat definitions."""

from datetime import timedelta

from sqlalchemy import Select, and_, case, func, select
from sqlalchemy.orm import Session, aliased

from app.api.deps import Context
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
from app.schemas.resources import (
    DatasetStatus,
    Leader,
    Leaders,
    LeaderStat,
    Overview,
    Performance,
    SeasonAverages,
    Standouts,
)
from app.services import games, registry
from app.services.common import (
    box,
    latest_season,
    nba_today,
    resolve_season,
    shooting,
    stat_line,
    team_ref,
)
from app.stats import game_score, is_double_double, leader_minimum_games, per_game, ratio
from app.sync.freshness import dataset_freshness

DATASET = "season_stats"
INSIGHT_TTL = 1800
STANDOUT_WINDOW_DAYS = 7
STANDOUT_CRITERION = "Highest Game Score (Hollinger) in final games from the last 7 days with data"
AVERAGED = ("min", "pts", "reb", "ast", "fg3m", "stl", "blk")


def season_totals(season_id: int) -> Select:
    """Per-player regular-season sums over games played (minutes > 0) in final games."""
    played = PlayerGameStats.minutes > 0

    def total(stat: str):
        column = PlayerGameStats.minutes if stat == "min" else getattr(PlayerGameStats, stat)
        return func.sum(case((played, column), else_=0)).label(stat)

    return (
        select(
            PlayerGameStats.player_id.label("player_id"),
            func.count().filter(played).label("games"),
            *(total(s) for s in (*AVERAGED, "fgm", "fga")),
        )
        .join(Game, Game.id == PlayerGameStats.game_id)
        .where(
            Game.season_id == season_id,
            Game.season_type == SeasonType.regular,
            Game.status == GameStatus.final,
        )
        .group_by(PlayerGameStats.player_id)
    )


def averages_from_row(row, season: str) -> SeasonAverages:
    games = int(row.games or 0)
    fg = ratio(float(row.fgm or 0), float(row.fga or 0))
    values = {s: per_game(float(getattr(row, s) or 0), games) for s in AVERAGED}
    return SeasonAverages(
        season=season, games_played=games, fg_pct=fg.value, fg_pct_status=fg.status, **values
    )


def max_team_games(session: Session, season_id: int) -> int:
    per_team = (
        select(TeamGameStats.team_id, func.count().label("n"))
        .join(Game, Game.id == TeamGameStats.game_id)
        .where(Game.season_id == season_id, Game.season_type == SeasonType.regular)
        .group_by(TeamGameStats.team_id)
        .subquery()
    )
    return session.scalar(select(func.max(per_team.c.n))) or 0


def season_with_games(session: Session, label: str | None) -> Season | None:
    if label:
        return resolve_season(session, label)
    with_games = (
        select(func.max(Game.season_id))
        .where(Game.status == GameStatus.final, Game.season_type == SeasonType.regular)
        .scalar_subquery()
    )
    return session.scalar(select(Season).where(Season.id == with_games)) or latest_season(session)


def leaders(ctx: Context, stat: LeaderStat, season: str | None, limit: int) -> Leaders:
    def compute() -> Leaders:
        current = season_with_games(ctx.session, season)
        if current is None:
            return Leaders(
                stat=stat, season="", minimum_games=0, qualified_players=0, leaders=[],
                meta=ctx.meta(DATASET),
            )  # fmt: skip
        minimum = leader_minimum_games(max_team_games(ctx.session, current.id))
        totals = season_totals(current.id).subquery()
        qualified = select(totals).where(totals.c.games >= minimum).subquery()
        count = ctx.session.scalar(select(func.count()).select_from(qualified)) or 0
        value = getattr(qualified.c, stat) / qualified.c.games
        rows = ctx.session.execute(
            select(qualified, Player.full_name, Team)
            .join(Player, Player.id == qualified.c.player_id)
            .outerjoin(Team, Team.id == Player.current_team_id)
            .order_by(value.desc(), qualified.c.games.desc(), Player.full_name)
            .limit(limit)
        ).all()
        return Leaders(
            stat=stat,
            season=current.label,
            minimum_games=minimum,
            qualified_players=count,
            leaders=[
                Leader(
                    rank=i + 1,
                    player_id=r.player_id,
                    full_name=r.full_name,
                    team=team_ref(r.Team) if r.Team else None,
                    games_played=int(r.games),
                    value=per_game(float(getattr(r, stat)), int(r.games)) or 0.0,
                )
                for i, r in enumerate(rows)
            ],
            meta=ctx.meta(DATASET),
        )

    return ctx.cached_model("leaders", INSIGHT_TTL, (stat, season, limit), DATASET, compute)


def _performance(score: float, stats, game, name: str, team, opponent) -> Performance:
    is_home = game.home_team_id == stats.team_id
    mine, theirs = (
        (game.home_score, game.away_score) if is_home else (game.away_score, game.home_score)
    )
    result = (
        None
        if mine is None or theirs is None or mine == theirs
        else ("W" if mine > theirs else "L")
    )
    return Performance(
        player_id=stats.player_id, full_name=name, game_id=game.id, game_date=game.game_date,
        team=team_ref(team), opponent=team_ref(opponent), is_home=is_home, result=result,
        minutes=float(stats.minutes), box=box(stats), shooting=shooting(stats), game_score=score,
        double_double=is_double_double(stat_line(game.game_date, stats)),
    )  # fmt: skip


def standouts(ctx: Context, limit: int) -> Standouts:
    def compute() -> Standouts:
        latest = ctx.session.scalar(
            select(func.max(Game.game_date)).where(Game.status == GameStatus.final)
        )
        if latest is None:
            return Standouts(
                window_start=None, window_end=None, criterion=STANDOUT_CRITERION,
                performances=[], meta=ctx.meta(DATASET),
            )  # fmt: skip
        start = latest - timedelta(days=STANDOUT_WINDOW_DAYS - 1)
        own, opp = aliased(Team), aliased(Team)
        opponent_id = case(
            (Game.home_team_id == PlayerGameStats.team_id, Game.away_team_id),
            else_=Game.home_team_id,
        )
        rows = ctx.session.execute(
            select(PlayerGameStats, Game, Player.full_name, own, opp)
            .join(Game, Game.id == PlayerGameStats.game_id)
            .join(Player, Player.id == PlayerGameStats.player_id)
            .join(own, own.id == PlayerGameStats.team_id)
            .join(opp, opp.id == opponent_id)
            .where(
                and_(Game.status == GameStatus.final, Game.game_date.between(start, latest)),
                PlayerGameStats.minutes > 0,
            )
        ).all()
        scored = [(game_score(stat_line(r[1].game_date, r[0])), *r) for r in rows]
        scored.sort(key=lambda r: (-r[0], r[2].game_date, r[3]))
        return Standouts(
            window_start=start,
            window_end=latest,
            criterion=STANDOUT_CRITERION,
            performances=[_performance(*r) for r in scored[:limit]],
            meta=ctx.meta(DATASET),
        )

    return ctx.cached_model("standouts", INSIGHT_TTL, limit, DATASET, compute)


RECENT_LIMIT = 15


def overview(ctx: Context) -> Overview:
    latest_final = ctx.session.scalar(
        select(func.max(Game.game_date)).where(Game.status == GameStatus.final)
    )
    recent = (
        games.list_games(
            ctx, date_from=latest_final, date_to=latest_final, team_id=None,
            status=GameStatus.final, season_type=None, limit=RECENT_LIMIT, offset=0,
        ).items
        if latest_final
        else []
    )  # fmt: skip
    return Overview(
        generated_at=ctx.now,
        today=nba_today(ctx.now),
        upcoming=games.upcoming(ctx, days=7, player_id=None)[:RECENT_LIMIT],
        recent=recent,
        standouts=standouts(ctx, limit=6),
        leaders=leaders(ctx, "pts", None, 5),
        model=registry.snapshot(ctx),
        datasets=[DatasetStatus(**d.as_dict()) for d in dataset_freshness(ctx.session, ctx.now)],
    )
