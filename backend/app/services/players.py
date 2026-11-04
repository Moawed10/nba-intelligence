from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from typing import Literal

from sqlalchemy import Select, and_, case, desc, func, select, text
from sqlalchemy.orm import Session, aliased

from app.api.deps import Context
from app.api.errors import invalid_parameter, not_found
from app.ml.matchups import RATE_DAYS, ROSTER_DAYS
from app.models import (
    Game,
    GameStatus,
    Player,
    PlayerGameStats,
    PlayerInjury,
    PlayerSeason,
    Season,
    SeasonType,
    Team,
)
from app.schemas.common import Page, StatSummary
from app.schemas.resources import (
    CareerLine,
    CareerSeason,
    CareerStint,
    CareerTable,
    DirectoryPlayer,
    InjuryReport,
    MatchupDefender,
    MatchupHistory,
    PlayerCareer,
    PlayerGameLine,
    PlayerIdentity,
    PlayerProfile,
    PlayerSearchResult,
    PlayerSeasonStats,
    PlayerSummary,
    PlayerTrends,
    SeasonLine,
    Split,
    TrendPoint,
    TrendStat,
)
from app.services.common import box, resolve_season, shooting, stat_line, team_ref
from app.services.insights import averages_from_row, season_totals
from app.stats import (
    Line,
    aggregate,
    is_double_double,
    per_game,
    ratio,
    rest_days_series,
    rolling_previous,
)

DATASET = "player_game_logs"
PROFILE_TTL = 1800
IDENTITY_TTL = 86400
SEARCH_THRESHOLD = 0.6
PROFILE_RECENT_GAMES = 5

STAT_SORTS = ("games", "pts", "reb", "ast", "fg3m", "stl", "blk", "min", "tov", "plus_minus")
PlayerSort = Literal[
    "full_name", "-full_name", "last_name", "-last_name", "to_year", "-to_year",
    "games", "-games", "pts", "-pts", "reb", "-reb", "ast", "-ast", "fg3m", "-fg3m",
    "stl", "-stl", "blk", "-blk", "min", "-min", "tov", "-tov", "plus_minus", "-plus_minus",
]  # fmt: skip
GameLogSort = Literal[
    "game_date", "-game_date", "pts", "-pts", "reb", "-reb", "ast", "-ast",
    "fg3m", "-fg3m", "stl", "-stl", "blk", "-blk", "minutes", "-minutes",
]  # fmt: skip

PLAYER_SORTS = {
    "full_name": Player.full_name,
    "last_name": Player.last_name,
    "to_year": Player.to_year,
}


def _order(column, descending: bool):
    return column.desc().nulls_last() if descending else column.asc().nulls_last()


def _summary(player: Player, team: Team | None) -> PlayerSummary:
    return PlayerSummary(
        id=player.id,
        full_name=player.full_name,
        jersey_number=player.jersey_number,
        position=player.position,
        is_active=player.is_active,
        team=team_ref(team) if team else None,
        from_year=player.from_year,
        to_year=player.to_year,
    )


def _player_or_404(session: Session, player_id: int) -> tuple[Player, Team | None]:
    row = session.execute(
        select(Player, Team)
        .outerjoin(Team, Team.id == Player.current_team_id)
        .where(Player.id == player_id)
    ).first()
    if row is None:
        raise not_found("player", player_id)
    return tuple(row)


def list_players(
    ctx: Context, *, team_id: int | None, position: str | None, active: bool | None,
    season: str | None, sort: PlayerSort, limit: int, offset: int,
) -> Page[DirectoryPlayer]:  # fmt: skip
    """With a season, lists players with regular-season games in it, with their averages."""
    stat_sort = sort.lstrip("-") in STAT_SORTS
    if stat_sort and not season:
        raise invalid_parameter("sort", "Sorting by a statistic requires a season.", "needs_season")
    stmt = select(Player, Team).outerjoin(Team, Team.id == Player.current_team_id)
    totals = None
    if season:
        current = resolve_season(ctx.session, season)
        totals = season_totals(current.id).subquery()
        stmt = stmt.add_columns(totals).join(totals, totals.c.player_id == Player.id)
    if team_id is not None:
        stmt = stmt.where(Player.current_team_id == team_id)
    if position:
        stmt = stmt.where(Player.position.ilike(f"%{_escape_like(position)}%", escape="\\"))
    if active is not None:
        stmt = stmt.where(Player.is_active.is_(active))
    total = ctx.session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    descending = sort.startswith("-")
    if totals is not None and stat_sort:
        key = sort.lstrip("-")
        # Players whose only lines are did-not-play have no games; NULLIF sorts them last.
        per_game = getattr(totals.c, key) / func.nullif(totals.c.games, 0)
        column = totals.c.games if key == "games" else per_game
    else:
        column = PLAYER_SORTS[sort.lstrip("-")]
    rows = ctx.session.execute(
        stmt.order_by(_order(column, descending), Player.id).limit(limit).offset(offset)
    ).all()
    items = [
        DirectoryPlayer(
            **_summary(row[0], row[1]).model_dump(),
            season_averages=averages_from_row(row, season) if season else None,
        )
        for row in rows
    ]
    return Page(items=items, total=total, limit=limit, offset=offset, meta=ctx.meta(DATASET))


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


SEARCH_SQL = text("""
    SELECT p.id, p.full_name, p.position, p.is_active, t.id AS team_id,
           t.abbreviation AS team_abbreviation, t.primary_color AS team_primary_color
    FROM players p
    LEFT JOIN teams t ON t.id = p.current_team_id
    CROSS JOIN LATERAL (SELECT search_normalize(:q) AS q) n
    WHERE n.q <% search_normalize(p.full_name)
       OR search_normalize(p.full_name) LIKE '%' || search_normalize(:q_like) || '%' ESCAPE '\\'
    ORDER BY
      (search_normalize(p.full_name) LIKE search_normalize(:q_like) || '%' ESCAPE '\\'
        OR search_normalize(p.full_name) LIKE '% ' || search_normalize(:q_like) || '%' ESCAPE '\\')
        DESC,
      p.is_active DESC,
      word_similarity(n.q, search_normalize(p.full_name)) DESC,
      p.to_year DESC NULLS LAST,
      p.full_name
    LIMIT :limit
""")


def search_players(ctx: Context, q: str, limit: int) -> list[PlayerSearchResult]:
    query = " ".join(q.split())

    def compute() -> list[PlayerSearchResult]:
        ctx.session.execute(
            text("SELECT set_config('pg_trgm.word_similarity_threshold', :t, true)"),
            {"t": str(SEARCH_THRESHOLD)},
        )
        rows = ctx.session.execute(
            SEARCH_SQL, {"q": query, "q_like": _escape_like(query), "limit": limit}
        ).mappings()
        return [PlayerSearchResult(**r) for r in rows]

    return ctx.cached("player_search", IDENTITY_TTL, (query.lower(), limit), compute)


@dataclass(frozen=True)
class GameRow:
    stats: PlayerGameStats
    game: Game
    season: str
    team: Team
    opponent: Team

    @property
    def is_home(self) -> bool:
        return self.game.home_team_id == self.stats.team_id

    @property
    def line(self) -> Line:
        return stat_line(self.game.game_date, self.stats)


def _game_rows_query(player_id: int) -> Select:
    own, opp = aliased(Team), aliased(Team)
    opponent_id = case(
        (Game.home_team_id == PlayerGameStats.team_id, Game.away_team_id),
        else_=Game.home_team_id,
    )
    return (
        select(PlayerGameStats, Game, Season.label, own, opp)
        .join(Game, Game.id == PlayerGameStats.game_id)
        .join(Season, Season.id == Game.season_id)
        .join(own, own.id == PlayerGameStats.team_id)
        .join(opp, opp.id == opponent_id)
        .where(PlayerGameStats.player_id == player_id)
    )


def _rows(session: Session, stmt: Select) -> list[GameRow]:
    return [GameRow(*r) for r in session.execute(stmt)]


def _game_line(row: GameRow) -> PlayerGameLine:
    g = row.game
    team_score, opp_score = (
        (g.home_score, g.away_score) if row.is_home else (g.away_score, g.home_score)
    )
    result = None
    if team_score is not None and opp_score is not None and team_score != opp_score:
        result = "W" if team_score > opp_score else "L"
    return PlayerGameLine(
        game_id=g.id,
        game_date=g.game_date,
        season=row.season,
        season_type=g.season_type,
        team_abbreviation=row.team.abbreviation,
        opponent=team_ref(row.opponent),
        is_home=row.is_home,
        result=result,
        team_score=team_score,
        opponent_score=opp_score,
        minutes=float(row.stats.minutes),
        box=box(row.stats),
        shooting=shooting(row.stats),
        double_double=is_double_double(row.line),
    )


def _chronological(stmt: Select) -> Select:
    return stmt.order_by(Game.game_date, Game.id)


def _season_lines(rows: list[GameRow], season_type: SeasonType | None) -> list[SeasonLine]:
    grouped: dict[tuple[str, SeasonType], list[Line]] = defaultdict(list)
    for row in rows:
        if season_type is None or row.game.season_type == season_type:
            grouped[(row.season, row.game.season_type)].append(row.line)
    ordered = sorted(grouped.items(), key=lambda kv: kv[0][0], reverse=True)
    return [
        SeasonLine(
            season=season,
            season_type=kind,
            **StatSummary.from_aggregate(aggregate(lines)).model_dump(),
        )
        for (season, kind), lines in ordered
    ]


def _latest_season_id(session: Session, player_id: int) -> int | None:
    return session.scalar(
        select(func.max(Game.season_id))
        .join(PlayerGameStats, PlayerGameStats.game_id == Game.id)
        .where(PlayerGameStats.player_id == player_id)
    )


def profile(ctx: Context, player_id: int) -> PlayerProfile:
    def compute() -> PlayerProfile:
        player, team = _player_or_404(ctx.session, player_id)
        season_id = _latest_season_id(ctx.session, player_id)
        rows = []
        if season_id is not None:
            stmt = _game_rows_query(player_id).where(Game.season_id == season_id)
            rows = _rows(ctx.session, _chronological(stmt))
        current = _season_lines(rows, SeasonType.regular) or _season_lines(rows, None)
        identity = PlayerIdentity(
            **_summary(player, team).model_dump(),
            first_name=player.first_name,
            last_name=player.last_name,
            height_inches=player.height_inches,
            weight_lbs=player.weight_lbs,
            birthdate=player.birthdate,
        )
        injury = ctx.session.get(PlayerInjury, player_id)
        return PlayerProfile(
            player=identity,
            injury=InjuryReport.model_validate(injury, from_attributes=True) if injury else None,
            current_season=current[0] if current else None,
            last_games=[_game_line(r) for r in reversed(rows[-PROFILE_RECENT_GAMES:])],
            meta=ctx.meta(DATASET),
        )

    return ctx.cached_model("player_profile", PROFILE_TTL, player_id, DATASET, compute)


SPLIT_LABELS = {
    "home": "Home",
    "away": "Away",
    "rest_0": "No rest (back-to-back)",
    "rest_1": "1 day of rest",
    "rest_2_plus": "2+ days of rest",
}


def _split_key_rest(days: int | None) -> str | None:
    if days is None:
        return None
    return "rest_0" if days == 0 else "rest_1" if days == 1 else "rest_2_plus"


def season_stats(
    ctx: Context, player_id: int, season_type: SeasonType, season: str | None
) -> PlayerSeasonStats:
    def compute() -> PlayerSeasonStats:
        _player_or_404(ctx.session, player_id)
        if season:
            resolve_season(ctx.session, season)
        rows = _rows(ctx.session, _chronological(_game_rows_query(player_id)))
        seasons = _season_lines(rows, season_type)
        split_season = season or (seasons[0].season if seasons else None)
        rest = rest_days_series([r.line for r in rows])
        buckets: dict[str, list[Line]] = defaultdict(list)
        for row, days in zip(rows, rest, strict=True):
            if row.season != split_season or row.game.season_type != season_type:
                continue
            buckets["home" if row.is_home else "away"].append(row.line)
            if key := _split_key_rest(days):
                buckets[key].append(row.line)
        splits = [
            Split(key=key, label=label, summary=StatSummary.from_aggregate(aggregate(buckets[key])))
            for key, label in SPLIT_LABELS.items()
            if buckets[key]
        ]  # fmt: skip
        return PlayerSeasonStats(
            player_id=player_id,
            season_type=season_type,
            seasons=seasons,
            splits_season=split_season,
            splits=splits,
            meta=ctx.meta(DATASET),
        )

    key = (player_id, season_type, season)
    return ctx.cached_model("player_stats", PROFILE_TTL, key, DATASET, compute)


GAME_LOG_SORTS = {
    "game_date": Game.game_date,
    "minutes": PlayerGameStats.minutes,
    **{s: getattr(PlayerGameStats, s) for s in ("pts", "reb", "ast", "fg3m", "stl", "blk")},
}


def game_log(
    ctx: Context, player_id: int, *, season: str | None, season_type: SeasonType | None,
    date_from: date | None, date_to: date | None, sort: GameLogSort, limit: int, offset: int,
) -> Page[PlayerGameLine]:  # fmt: skip
    if date_from and date_to and date_from > date_to:
        raise invalid_parameter("date_from", "date_from must be on or before date_to.")
    _player_or_404(ctx.session, player_id)
    stmt = _game_rows_query(player_id)
    conditions = []
    if season:
        conditions.append(Game.season_id == resolve_season(ctx.session, season).id)
    if season_type:
        conditions.append(Game.season_type == season_type)
    if date_from:
        conditions.append(Game.game_date >= date_from)
    if date_to:
        conditions.append(Game.game_date <= date_to)
    if conditions:
        stmt = stmt.where(and_(*conditions))
    total = ctx.session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    column = GAME_LOG_SORTS[sort.lstrip("-")]
    ordered = stmt.order_by(_order(column, sort.startswith("-")), desc(Game.game_date), Game.id)
    rows = _rows(ctx.session, ordered.limit(limit).offset(offset))
    return Page(
        items=[_game_line(r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
        meta=ctx.meta(DATASET),
    )


def trends(
    ctx: Context, player_id: int, stat: TrendStat, season: str | None,
    season_type: SeasonType | None,
) -> PlayerTrends:  # fmt: skip
    def compute() -> PlayerTrends:
        _player_or_404(ctx.session, player_id)
        if season:
            season_id: int | None = resolve_season(ctx.session, season).id
        else:
            season_id = _latest_season_id(ctx.session, player_id)
        if season_id is None:
            raise invalid_parameter("season", "This player has no recorded games.", "no_games")
        stmt = _game_rows_query(player_id).where(Game.season_id == season_id)
        if season_type:
            stmt = stmt.where(Game.season_type == season_type)
        rows = [r for r in _rows(ctx.session, _chronological(stmt)) if r.line.played]
        values = [r.line.value(stat) for r in rows]
        rolling = {n: rolling_previous(values, n) for n in (3, 5, 10)}
        label = ctx.session.scalar(select(Season.label).where(Season.id == season_id)) or ""
        return PlayerTrends(
            player_id=player_id,
            stat=stat,
            season=label,
            season_type=season_type,
            games_played=len(rows),
            average=round(sum(values) / len(values), 2) if values else None,
            points=[
                TrendPoint(
                    game_id=r.game.id,
                    game_date=r.game.game_date,
                    opponent_abbreviation=r.opponent.abbreviation,
                    is_home=r.is_home,
                    value=v,
                    rolling_3=rolling[3][i],
                    rolling_5=rolling[5][i],
                    rolling_10=rolling[10][i],
                )
                for i, (r, v) in enumerate(zip(rows, values, strict=True))
            ],
            meta=ctx.meta(DATASET),
        )

    key = (player_id, stat, season, season_type)
    return ctx.cached_model("player_trends", PROFILE_TTL, key, DATASET, compute)


MATCHUP_AVERAGES = ("pts", "reb", "ast", "fg3m", "stl", "blk")
MATCHUP_MEETINGS = 10


MATCHUP_DEFENDERS = 4
DEFENDERS_SQL = text("""
    WITH latest AS (
        SELECT DISTINCT ON (m.def_player_id) m.def_player_id, m.def_team_id, g.game_date
        FROM player_matchups m JOIN games g ON g.id = m.game_id
        WHERE m.def_player_id IN (
            SELECT def_player_id FROM player_matchups WHERE off_player_id = :p)
        ORDER BY m.def_player_id, g.game_date DESC
    )
    SELECT m.def_player_id AS player_id, d.full_name, COUNT(DISTINCT m.game_id) AS games,
           SUM(m.partial_possessions)::float AS possessions,
           SUM(m.pts)::float / SUM(m.partial_possessions) * 100 AS pts_per_100
    FROM player_matchups m
    JOIN latest l ON l.def_player_id = m.def_player_id
    JOIN players d ON d.id = m.def_player_id
    WHERE m.off_player_id = :p AND l.def_team_id = :t AND l.game_date >= CURRENT_DATE - :roster
    GROUP BY m.def_player_id, d.full_name
    ORDER BY possessions DESC
    LIMIT :limit""")
USUAL_RATE_SQL = text("""
    SELECT SUM(m.pts)::float / NULLIF(SUM(m.partial_possessions), 0) * 100
    FROM player_matchups m JOIN games g ON g.id = m.game_id
    WHERE m.off_player_id = :p AND g.game_date >= (
        SELECT MAX(g2.game_date) FROM player_matchups m2 JOIN games g2 ON g2.id = m2.game_id
        WHERE m2.off_player_id = :p
    ) - :window""")


def matchup(ctx: Context, player_id: int, team_id: int) -> MatchupHistory:
    """Every stored game the player played against one team (did-not-play lines excluded)."""

    def compute() -> MatchupHistory:
        _player_or_404(ctx.session, player_id)
        opponent = ctx.session.get(Team, team_id)
        if opponent is None:
            raise not_found("team", team_id)
        opponent_id = case(
            (Game.home_team_id == PlayerGameStats.team_id, Game.away_team_id),
            else_=Game.home_team_id,
        )
        stmt = _game_rows_query(player_id).where(
            opponent_id == team_id, PlayerGameStats.minutes > 0, Game.status == GameStatus.final
        )
        rows = _rows(ctx.session, stmt.order_by(desc(Game.game_date), Game.id))
        lines = [_game_line(r) for r in rows]
        games = len(rows)
        totals = {k: sum(getattr(r.stats, k) for r in rows) for k in MATCHUP_AVERAGES}
        minutes = sum(float(r.stats.minutes) for r in rows)
        averages = {k: per_game(float(v), games) for k, v in totals.items()}
        averages["min"] = per_game(minutes, games)
        made = {k: sum(getattr(r.stats, k) for r in rows) for k in ("fgm", "fga", "fg3m", "fg3a")}
        return MatchupHistory(
            player_id=player_id,
            opponent=team_ref(opponent),
            games=games,
            wins=sum(line.result == "W" for line in lines),
            losses=sum(line.result == "L" for line in lines),
            averages=averages,
            fg_pct=ratio(made["fgm"], made["fga"]).value,
            fg3_pct=ratio(made["fg3m"], made["fg3a"]).value,
            first_season=rows[-1].season if rows else None,
            last_season=rows[0].season if rows else None,
            meetings=lines[:MATCHUP_MEETINGS],
            defenders=[
                MatchupDefender(**row._mapping)
                for row in ctx.session.execute(
                    DEFENDERS_SQL,
                    {
                        "p": player_id,
                        "t": team_id,
                        "roster": ROSTER_DAYS,
                        "limit": MATCHUP_DEFENDERS,
                    },
                )
            ],  # fmt: skip
            usual_pts_per_100=ctx.session.scalar(
                USUAL_RATE_SQL, {"p": player_id, "window": RATE_DAYS}
            ),
            meta=ctx.meta(DATASET),
        )

    return ctx.cached_model("player_matchup", 1800, (player_id, team_id), DATASET, compute)


CAREER_DATASET = "career_history"
CAREER_STATS = {"pts": "pts", "reb": "reb", "ast": "ast", "stl": "stl", "blk": "blk",
                "fg3m": "fg3m", "tov": "tov", "min": "minutes"}  # fmt: skip


def _ratio(made: int | None, attempted: int | None) -> float | None:
    return made / attempted if made is not None and attempted else None


def _career_line(rows: list[PlayerSeason]) -> CareerLine:
    """Averages over the given season rows. Each statistic is averaged over the games of the
    seasons that recorded it, so an unrecorded season never counts as zero."""

    def total(column: str) -> tuple[int | None, int]:
        recorded = [r for r in rows if getattr(r, column) is not None]
        if not recorded:
            return None, 0
        return sum(getattr(r, column) for r in recorded), sum(r.games for r in recorded)

    per_game: dict[str, float | None] = {}
    for key, column in CAREER_STATS.items():
        value, games = total(column)
        per_game[key] = None if value is None or not games else value / games

    def pct(made: str, attempted: str) -> float | None:
        recorded = [r for r in rows if getattr(r, made) is not None and getattr(r, attempted)]
        if not recorded:
            return None
        return _ratio(
            sum(getattr(r, made) for r in recorded), sum(getattr(r, attempted) for r in recorded)
        )

    started = [r.games_started for r in rows]
    return CareerLine(
        games=sum(r.games for r in rows),
        games_started=None if any(g is None for g in started) else sum(started),  # type: ignore[arg-type]
        per_game=per_game,
        fg_pct=pct("fgm", "fga"),
        fg3_pct=pct("fg3m", "fg3a"),
        ft_pct=pct("ftm", "fta"),
    )


def _career_table(rows: list[tuple[PlayerSeason, str]], teams: dict[int, Team]) -> CareerTable:
    by_season: dict[int, list[tuple[PlayerSeason, str]]] = defaultdict(list)
    for row, label in rows:
        by_season[row.season_id].append((row, label))
    seasons: list[CareerSeason] = []
    chosen: list[tuple[PlayerSeason, str]] = []
    for season_id in sorted(by_season):
        entries = by_season[season_id]
        combined = [e for e in entries if e[0].team_abbreviation == "TOT"]
        stints = [e[0] for e in entries if e[0].team_abbreviation != "TOT"]
        # A traded player's "TOT" row is the season; without one there is a single team row.
        season_rows = [combined[0][0]] if combined else stints
        chosen += [(r, entries[0][1]) for r in season_rows]
        line = _career_line(season_rows)
        seasons.append(
            CareerSeason(
                **line.model_dump(),
                season=entries[0][1],
                age=season_rows[0].age,
                teams=[
                    CareerStint(
                        abbreviation=r.team_abbreviation,
                        team=team_ref(teams[r.team_id]) if r.team_id in teams else None,
                    )
                    for r in stints
                ],
            )
        )
    partial: dict[str, str] = {}
    for key, column in CAREER_STATS.items():
        recorded = [label for r, label in chosen if getattr(r, column) is not None]
        if recorded and len(recorded) < len(chosen):
            partial[key] = recorded[0]
    return CareerTable(
        seasons=seasons,
        totals=_career_line([r for r, _ in chosen]) if chosen else None,
        partial=partial,
    )


def career(ctx: Context, player_id: int) -> PlayerCareer:
    def compute() -> PlayerCareer:
        _player_or_404(ctx.session, player_id)
        rows = ctx.session.execute(
            select(PlayerSeason, Season.label)
            .join(Season, Season.id == PlayerSeason.season_id)
            .where(PlayerSeason.player_id == player_id)
            .order_by(PlayerSeason.season_id, PlayerSeason.team_abbreviation)
        ).all()
        team_ids = {r.team_id for r, _ in rows if r.team_id is not None}
        teams = {t.id: t for t in ctx.session.scalars(select(Team).where(Team.id.in_(team_ids)))}
        tables = {
            kind: _career_table([(r, label) for r, label in rows if r.season_type == kind], teams)
            for kind in (SeasonType.regular, SeasonType.playoffs)
        }
        return PlayerCareer(
            player_id=player_id,
            regular=tables[SeasonType.regular],
            playoffs=tables[SeasonType.playoffs],
            meta=ctx.meta(CAREER_DATASET),
        )

    return ctx.cached_model("player_career", PROFILE_TTL, player_id, CAREER_DATASET, compute)
