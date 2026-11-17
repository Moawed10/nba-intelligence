"""Live box scores for games in progress, from the cdn.nba.com live feed (nba_api's live BoxScore).

The latest snapshot per game is stored in live_box_scores and replaced on every poll. It never
touches player_game_stats: those hold only the official box score, written by the game-log jobs
once a game is final.
"""

import re
from collections.abc import Callable
from datetime import datetime
from typing import Any

from sqlalchemy import Engine, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models import Game, GameStatus, LiveBoxScore

SOURCE = "BoxScore (live)"
LIVE_STATUS = 2  # the feed's gameStatus: 1 scheduled, 2 in progress, 3 final
DURATION = re.compile(r"^PT(?:(\d+)M)?(?:([\d.]+)S)?$")

# Feed statistic -> our box score column.
STATS = {
    "fgm": "fieldGoalsMade", "fga": "fieldGoalsAttempted",
    "fg3m": "threePointersMade", "fg3a": "threePointersAttempted",
    "ftm": "freeThrowsMade", "fta": "freeThrowsAttempted",
    "oreb": "reboundsOffensive", "dreb": "reboundsDefensive", "reb": "reboundsTotal",
    "ast": "assists", "stl": "steals", "blk": "blocks", "tov": "turnovers",
    "pf": "foulsPersonal", "pts": "points",
}  # fmt: skip


def minutes(value: str | None) -> float:
    """ISO 8601 duration as the feed writes it ("PT22M27.00S") to minutes."""
    match = DURATION.match(value or "")
    if not match:
        return 0.0
    whole, seconds = match.groups()
    return int(whole or 0) + float(seconds or 0) / 60


def clock(value: str | None) -> str | None:
    """Game clock as shown on a scoreboard ("PT05M12.00S" -> "5:12"); None when not running."""
    match = DURATION.match(value or "")
    if not match or not value:
        return None
    whole, seconds = match.groups()
    return f"{int(whole or 0)}:{int(float(seconds or 0)):02d}"


def _line(statistics: dict[str, Any]) -> dict[str, int]:
    return {ours: int(statistics.get(theirs) or 0) for ours, theirs in STATS.items()}


def box_snapshot(payload: dict[str, Any]) -> dict[str, Any]:
    """The feed's game object to {"status", "period", "clock", "teams": [...]}. Only players who
    have been on the floor are kept; plus-minus is the feed's own."""
    game = payload["game"]
    teams = []
    for side, is_home in (("awayTeam", False), ("homeTeam", True)):
        team = game[side]
        players = [
            {
                "player_id": int(p["personId"]),
                "name": p["name"],
                "starter": p.get("starter") == "1",
                "on_court": p.get("oncourt") == "1",
                "minutes": minutes(p["statistics"].get("minutes")),
                "plus_minus": int(p["statistics"].get("plusMinusPoints") or 0),
                **_line(p["statistics"]),
            }
            for p in team.get("players", [])
            if p.get("played") == "1"
        ]
        totals = team.get("statistics", {})
        teams.append(
            {
                "team_id": int(team["teamId"]),
                "is_home": is_home,
                "minutes": round(minutes(totals.get("minutes"))),
                "totals": _line(totals),
                "players": players,
            }
        )
    return {
        "status": int(game["gameStatus"]),
        "period": int(game.get("period") or 0),
        "clock": clock(game.get("gameClock")),
        "teams": teams,
    }


def store(engine: Engine, game_id: str, snapshot: dict[str, Any], now: datetime) -> None:
    row = {
        "game_id": game_id,
        "observed_at": now,
        "period": snapshot["period"],
        "clock": snapshot["clock"],
        "data": {"teams": snapshot["teams"]},
        "source_endpoint": SOURCE,
        "updated_at": now,
    }
    stmt = insert(LiveBoxScore).values(row)
    stmt = stmt.on_conflict_do_update(
        index_elements=["game_id"], set_={k: v for k, v in row.items() if k != "game_id"}
    )
    with Session(engine) as session, session.begin():
        session.execute(stmt)


def record(engine: Engine, game_id: str, payload: dict[str, Any], now: datetime) -> bool:
    """Stores the snapshot from a live box score already fetched (the live score poll reads the
    same reply). A feed that no longer says live keeps the last snapshot until the official one."""
    snapshot = box_snapshot(payload)
    if snapshot["status"] != LIVE_STATUS or not any(t["players"] for t in snapshot["teams"]):
        return False
    store(engine, game_id, snapshot, now)
    return True


def poll_live_box_scores(
    engine: Engine, fetch: Callable[[str], dict[str, Any]], now: datetime
) -> int:
    """Refreshes the stored snapshot of every game in progress; returns how many were stored. A
    game the feed no longer reports as live keeps its last snapshot until the official one lands."""
    with Session(engine) as session:
        live = session.scalars(select(Game.id).where(Game.status == GameStatus.in_progress)).all()
    return sum(record(engine, game_id, fetch(game_id), now) for game_id in live)
