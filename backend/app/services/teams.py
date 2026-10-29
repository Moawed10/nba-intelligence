from sqlalchemy import select
from sqlalchemy.orm import Session, aliased

from app.api.deps import Context
from app.api.errors import not_found
from app.models import (
    Game,
    GameStatus,
    Player,
    Season,
    SeasonType,
    Team,
    TeamGameStats,
    TeamSeason,
)
from app.schemas.common import Shooting
from app.schemas.resources import (
    HistoricSeason,
    PlayerSummary,
    Record,
    TeamDetail,
    TeamHistory,
    TeamSeasonStats,
)
from app.schemas.resources import Team as TeamSchema
from app.services.common import latest_season, resolve_season, team_ref
from app.stats import pace, per_100, possessions, ratio

DATASET = "team_stats"
TEAM_TTL = 1800
IDENTITY_TTL = 86400
SHOT_COLUMNS = ("fgm", "fga", "fg3m", "fg3a", "ftm", "fta")


def _team_schema(team: Team) -> TeamSchema:
    return TeamSchema(
        **team_ref(team).model_dump(),
        conference=team.conference,
        division=team.division,
    )


def list_teams(ctx: Context) -> list[TeamSchema]:
    def compute() -> list[TeamSchema]:
        teams = ctx.session.scalars(select(Team).order_by(Team.city, Team.name))
        return [_team_schema(t) for t in teams]

    return ctx.cached("teams", IDENTITY_TTL, None, compute)


def _team_or_404(session: Session, team_id: int) -> Team:
    team = session.get(Team, team_id)
    if team is None:
        raise not_found("team", team_id)
    return team


def _season(ctx: Context, label: str | None) -> Season | None:
    return resolve_season(ctx.session, label) if label else latest_season(ctx.session)


def _lines(
    session: Session, team_id: int, season_id: int, season_type: SeasonType
) -> list[tuple[TeamGameStats, TeamGameStats]]:
    opp = aliased(TeamGameStats)
    stmt = (
        select(TeamGameStats, opp)
        .join(Game, Game.id == TeamGameStats.game_id)
        .join(opp, (opp.game_id == TeamGameStats.game_id) & (opp.team_id != TeamGameStats.team_id))
        .where(
            TeamGameStats.team_id == team_id,
            Game.season_id == season_id,
            Game.season_type == season_type,
            Game.status == GameStatus.final,
        )
    )
    return list(session.execute(stmt))


def _record(lines: list[tuple[TeamGameStats, TeamGameStats]]) -> Record:
    return Record(
        wins=sum(own.pts > opp.pts for own, opp in lines),
        losses=sum(own.pts < opp.pts for own, opp in lines),
    )


def team_detail(ctx: Context, team_id: int, season: str | None) -> TeamDetail:
    def compute() -> TeamDetail:
        team = _team_or_404(ctx.session, team_id)
        current = _season(ctx, season)
        lines = _lines(ctx.session, team_id, current.id, SeasonType.regular) if current else []
        roster = ctx.session.scalars(
            select(Player)
            .where(Player.current_team_id == team_id, Player.is_active.is_(True))
            .order_by(Player.last_name, Player.full_name)
        )
        ref = team_ref(team)
        return TeamDetail(
            team=_team_schema(team),
            season=current.label if current else "",
            record=_record(lines),
            roster=[
                PlayerSummary(
                    id=p.id, full_name=p.full_name, position=p.position, is_active=p.is_active,
                    team=ref, from_year=p.from_year, to_year=p.to_year,
                )
                for p in roster
            ],
            meta=ctx.meta(DATASET),
        )  # fmt: skip

    return ctx.cached_model("team_detail", TEAM_TTL, (team_id, season), DATASET, compute)


def _per_game(total: float, games: int) -> float | None:
    return round(total / games, 1) if games else None


def team_stats(
    ctx: Context, team_id: int, season: str | None, season_type: SeasonType
) -> TeamSeasonStats:
    def compute() -> TeamSeasonStats:
        _team_or_404(ctx.session, team_id)
        current = _season(ctx, season)
        lines = _lines(ctx.session, team_id, current.id, season_type) if current else []
        games = len(lines)
        pts = sum(own.pts for own, _ in lines)
        opp_pts = sum(opp.pts for _, opp in lines)
        poss = sum(possessions(o.fga, o.oreb, o.tov, o.fta) for o, _ in lines)
        minutes = sum(own.minutes for own, _ in lines)
        off = per_100(pts, poss)
        dfn = per_100(opp_pts, poss)
        total = {c: sum(getattr(own, c) for own, _ in lines) for c in SHOT_COLUMNS}
        return TeamSeasonStats(
            team_id=team_id,
            season=current.label if current else "",
            season_type=season_type,
            games=games,
            record=_record(lines),
            pts_per_game=_per_game(pts, games),
            opp_pts_per_game=_per_game(opp_pts, games),
            possessions_per_game=_per_game(poss, games),
            pace=pace(poss, minutes),
            offensive_rating=off,
            defensive_rating=dfn,
            net_rating=round(off - dfn, 1) if off is not None and dfn is not None else None,
            shooting=Shooting.from_rates(
                ratio(total["fgm"], total["fga"]),
                ratio(total["fg3m"], total["fg3a"]),
                ratio(total["ftm"], total["fta"]),
            ),
            meta=ctx.meta(DATASET),
        )

    key = (team_id, season, season_type)
    return ctx.cached_model("team_stats", TEAM_TTL, key, DATASET, compute)


HISTORY_PER_GAME = ("pts", "reb", "oreb", "ast", "stl", "blk", "tov", "fg3m", "pf")


def _historic(row: TeamSeason, label: str) -> HistoricSeason:
    def per_game(column: str) -> float | None:
        total = getattr(row, column)
        return None if total is None else round(total / row.games, 1)

    def pct(made: int | None, attempted: int | None) -> float | None:
        return None if made is None or not attempted else round(made / attempted, 4)

    return HistoricSeason(
        season=label, city=row.city, name=row.name, games=row.games, wins=row.wins,
        losses=row.losses, win_pct=round(row.wins / row.games, 4),
        conference_rank=row.conference_rank, division_rank=row.division_rank,
        playoff_wins=row.playoff_wins, playoff_losses=row.playoff_losses, finals=row.finals,
        per_game={c: per_game(c) for c in HISTORY_PER_GAME},
        fg_pct=pct(row.fgm, row.fga), fg3_pct=pct(row.fg3m, row.fg3a), ft_pct=pct(row.ftm, row.fta),
        pace=row.pace, off_rating=row.off_rating, def_rating=row.def_rating,
        net_rating=row.net_rating,
    )  # fmt: skip


def team_history(ctx: Context, team_id: int) -> TeamHistory:
    """Every season of a franchise, newest first, under the name it had that year."""

    def compute() -> TeamHistory:
        team = _team_or_404(ctx.session, team_id)
        rows = ctx.session.execute(
            select(TeamSeason, Season.label)
            .join(Season, Season.id == TeamSeason.season_id)
            .where(TeamSeason.team_id == team_id)
            .order_by(TeamSeason.season_id.desc())
        ).all()
        return TeamHistory(
            team=team_ref(team),
            seasons=[_historic(row, label) for row, label in rows],
            meta=ctx.meta(DATASET),
        )

    return ctx.cached_model("team_history", TEAM_TTL, team_id, DATASET, compute)
