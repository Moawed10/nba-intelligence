"""Two players side by side in one regular season, with league percentiles for a radar chart."""

import pandas as pd
from sqlalchemy import case, func, select

from app.api.deps import Context
from app.api.errors import ApiError, invalid_parameter
from app.models import Game, GameStatus, PlayerGameStats, Season, SeasonType
from app.schemas.resources import PercentileAxis, PlayerComparison, SeasonLine
from app.services.insights import max_team_games
from app.services.players import DATASET, PROFILE_TTL, _player_or_404, _summary, season_stats

# Without a season, open on the latest regular season where both played this many games.
MIN_DEFAULT_GAMES = 10
# Percentiles rank players who played this share of their team's games, at this many minutes.
QUALIFY_SHARE = 0.4
QUALIFY_MINUTES = 10.0
AXES = (
    ("pts", "Scoring"),
    ("reb", "Rebounding"),
    ("ast", "Playmaking"),
    ("fg3m", "3-point shooting"),
    ("stl", "Steals"),
    ("blk", "Blocks"),
    ("ts_pct", "Efficiency"),
)
SUMMED = ("min", "pts", "reb", "ast", "fg3m", "stl", "blk", "fga", "fta")
PER_GAME = ("min", "pts", "reb", "ast", "fg3m", "stl", "blk")


def _league(ctx: Context, season_id: int) -> pd.DataFrame:
    """Per-game averages and true shooting for every player in the season (games played only)."""
    played = PlayerGameStats.minutes > 0

    def total(stat: str):
        column = PlayerGameStats.minutes if stat == "min" else getattr(PlayerGameStats, stat)
        return func.sum(case((played, column), else_=0)).label(stat)

    rows = ctx.session.execute(
        select(
            PlayerGameStats.player_id,
            func.count().filter(played).label("games"),
            *(total(s) for s in SUMMED),
        )
        .join(Game, Game.id == PlayerGameStats.game_id)
        .where(
            Game.season_id == season_id,
            Game.season_type == SeasonType.regular,
            Game.status == GameStatus.final,
        )  # fmt: skip
        .group_by(PlayerGameStats.player_id)
    ).all()
    frame = pd.DataFrame(rows, columns=["player_id", "games", *SUMMED]).astype(float)
    frame = frame[frame["games"] > 0].set_index(frame["player_id"].astype(int))
    attempts = 2 * (frame["fga"] + 0.44 * frame["fta"])
    frame["ts_pct"] = (frame["pts"] / attempts).where(attempts > 0)
    for stat in PER_GAME:
        frame[stat] = frame[stat] / frame["games"]
    return frame


def _percentile(values: pd.Series, value: float | None) -> float | None:
    """Share of the qualified players below this value, counting ties as half (0–100)."""
    if value is None or pd.isna(value) or values.empty:
        return None
    below = (values < value).sum()
    equal = (values == value).sum()
    return float((below + 0.5 * equal) / len(values) * 100)


def compare(ctx: Context, p1: int, p2: int, season: str | None) -> PlayerComparison:
    if p1 == p2:
        raise invalid_parameter("p2", "Pick two different players.", "same_player")

    def compute() -> PlayerComparison:
        players = [_player_or_404(ctx.session, pid) for pid in (p1, p2)]
        stats = [season_stats(ctx, pid, SeasonType.regular, None) for pid in (p1, p2)]
        lines = [{line.season: line for line in s.seasons} for s in stats]
        common = [label for label in lines[0] if label in lines[1]]  # newest first
        if season is not None and season not in common:
            raise ApiError(422, "no_common_season", f"These players did not both play in {season}.")
        qualifying = (
            c for c in common if all(lines[i][c].games_played >= MIN_DEFAULT_GAMES for i in (0, 1))
        )
        chosen = season or next(qualifying, common[0] if common else None)
        summaries = [_summary(player, team) for player, team in players]
        if chosen is None:
            return PlayerComparison(
                players=summaries, season=None, common_seasons=[], lines=[], axes=[],
                qualified_players=0, qualification="", qualified=[False, False],
                meta=ctx.meta(DATASET),
            )  # fmt: skip
        season_id = ctx.session.scalar(select(Season.id).where(Season.label == chosen))
        league = _league(ctx, season_id)
        min_games = max(1, round(QUALIFY_SHARE * max_team_games(ctx.session, season_id)))
        pool = league[(league["games"] >= min_games) & (league["min"] >= QUALIFY_MINUTES)]

        def value(pid: int, key: str) -> float | None:
            if pid not in league.index or pd.isna(league.at[pid, key]):
                return None
            return float(league.at[pid, key])

        axes = [
            PercentileAxis(
                key=key,
                label=label,
                values=[value(pid, key) for pid in (p1, p2)],
                percentiles=[_percentile(pool[key].dropna(), value(pid, key)) for pid in (p1, p2)],
            )
            for key, label in AXES
        ]
        season_lines: list[SeasonLine] = [lines[0][chosen], lines[1][chosen]]
        return PlayerComparison(
            players=summaries,
            season=chosen,
            common_seasons=common,
            lines=season_lines,
            axes=axes,
            qualified_players=len(pool),
            qualification=(
                f"Ranked against the {len(pool)} players with at least {min_games} games and "
                f"{QUALIFY_MINUTES:g} minutes per game in {chosen}."
            ),
            qualified=[pid in pool.index for pid in (p1, p2)],
            meta=ctx.meta(DATASET),
        )

    return ctx.cached_model("compare_players", PROFILE_TTL, (p1, p2, season), DATASET, compute)
