"""Pure transformations from nba_api DataFrames to validated table rows."""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd

from app.models import BOX_COLUMNS, GameStatus, SeasonType

NBA_TZ = ZoneInfo("America/New_York")
ATYPICAL_SEASONS = {2019, 2020}

SEASON_TYPE_BY_PREFIX = {
    "002": SeasonType.regular,
    "005": SeasonType.playin,
    "004": SeasonType.playoffs,
}
LOG_SEASON_TYPE = {
    SeasonType.regular: "Regular Season",
    SeasonType.playin: "PlayIn",
    SeasonType.playoffs: "Playoffs",
}
SCHEDULE_STATUS = {1: GameStatus.scheduled, 2: GameStatus.in_progress, 3: GameStatus.final}


@dataclass
class Rejection:
    key: dict[str, Any]
    reason: str


@dataclass
class Transformed:
    rows: list[dict[str, Any]] = field(default_factory=list)
    rejections: list[Rejection] = field(default_factory=list)
    scores: dict[str, tuple[int, int]] = field(default_factory=dict)


def season_label(start_year: int) -> str:
    return f"{start_year}-{(start_year + 1) % 100:02d}"


def season_from_game_id(game_id: str) -> int:
    return 2000 + int(game_id[3:5])


def current_season_start_year(now: datetime | None = None) -> int:
    local = (now or datetime.now(UTC)).astimezone(NBA_TZ)
    return local.year if local.month >= 8 else local.year - 1


def parse_matchup(matchup: str) -> tuple[bool, str]:
    """'GSW vs. LAL' -> (True, 'LAL'); 'GSW @ LAL' -> (False, 'LAL')."""
    if " vs. " in matchup:
        return True, matchup.split(" vs. ")[1].strip()
    if " @ " in matchup:
        return False, matchup.split(" @ ")[1].strip()
    raise ValueError(f"Unrecognized matchup: {matchup!r}")


def parse_height(value: Any) -> int | None:
    if not isinstance(value, str) or "-" not in value:
        return None
    feet, inches = value.split("-", 1)
    try:
        return int(feet) * 12 + int(inches)
    except ValueError:
        return None


def to_int(value: Any) -> int | None:
    if value is None or (isinstance(value, float) and pd.isna(value)) or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def validate_box(row: dict[str, Any]) -> str | None:
    """Returns a rejection reason, or None when the box-score line is internally consistent."""
    for col in BOX_COLUMNS:
        value = row.get(col)
        if value is None:
            return f"missing {col}"
        if value < 0:
            return f"negative {col}"
    if row["fgm"] > row["fga"] or row["fg3m"] > row["fg3a"] or row["ftm"] > row["fta"]:
        return "made exceeds attempted"
    if row["fg3m"] > row["fgm"] or row["fg3a"] > row["fga"]:
        return "three-pointers exceed field goals"
    if row["reb"] != row["oreb"] + row["dreb"]:
        return "reb != oreb + dreb"
    if row["pts"] != 2 * row["fgm"] + row["fg3m"] + row["ftm"]:
        return "pts != 2*fgm + fg3m + ftm"
    return None


def _box_values(record: dict[str, Any]) -> dict[str, Any]:
    values = {col: to_int(record.get(col.upper())) for col in BOX_COLUMNS}
    values["plus_minus"] = to_int(record.get("PLUS_MINUS"))
    return values


def _game_date(value: Any) -> date:
    return date.fromisoformat(str(value)[:10])


@dataclass
class TeamLogResult:
    games: Transformed
    team_stats: Transformed


def transform_team_logs(
    df: pd.DataFrame,
    season_type: SeasonType,
    scheduled_home: dict[str, int] | None = None,
) -> TeamLogResult:
    """Neutral-site games list both teams as away ('@'); scheduled_home (game id -> designated
    home team id, from the schedule) resolves them. Without it such games are rejected."""
    games, team_stats = Transformed(), Transformed()
    by_game: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in df.to_dict("records"):
        by_game[str(record["GAME_ID"])].append(record)

    for game_id, records in by_game.items():
        if SEASON_TYPE_BY_PREFIX.get(game_id[:3]) != season_type:
            games.rejections.append(Rejection({"game_id": game_id}, "unexpected game id prefix"))
            continue
        if len(records) != 2:
            games.rejections.append(Rejection({"game_id": game_id}, f"{len(records)} team rows"))
            continue
        try:
            sides = {parse_matchup(r["MATCHUP"])[0]: r for r in records}
        except ValueError as exc:
            games.rejections.append(Rejection({"game_id": game_id}, str(exc)))
            continue
        if set(sides) != {True, False}:
            home_id = (scheduled_home or {}).get(game_id)
            if home_id not in {int(r["TEAM_ID"]) for r in records}:
                games.rejections.append(Rejection({"game_id": game_id}, "no distinct home/away"))
                continue
            sides = {int(r["TEAM_ID"]) == home_id: r for r in records}
        if any(pd.isna(r.get("WL")) or not r.get("WL") for r in records):
            games.rejections.append(Rejection({"game_id": game_id}, "game not final"))
            continue

        lines = []
        for is_home, record in sides.items():
            line = {
                "game_id": game_id,
                "team_id": int(record["TEAM_ID"]),
                "is_home": is_home,
                "minutes": to_int(record["MIN"]),
                **_box_values(record),
            }
            reason = validate_box(line) or (None if line["minutes"] else "missing minutes")
            if reason:
                break
            lines.append(line)
        if reason:
            games.rejections.append(Rejection({"game_id": game_id}, reason))
            continue

        home, away = sides[True], sides[False]
        games.rows.append({
            "id": game_id,
            "season_id": season_from_game_id(game_id),
            "season_type": season_type,
            "game_date": _game_date(home["GAME_DATE"]),
            "home_team_id": int(home["TEAM_ID"]),
            "away_team_id": int(away["TEAM_ID"]),
            "status": GameStatus.final,
            "home_score": to_int(home["PTS"]),
            "away_score": to_int(away["PTS"]),
        })  # fmt: skip
        team_stats.rows.extend(lines)
    return TeamLogResult(games=games, team_stats=team_stats)


@dataclass
class PlayerLogResult:
    stats: Transformed
    players: list[dict[str, Any]]


def transform_player_logs(
    df: pd.DataFrame,
    team_minutes: dict[tuple[str, int], int],
    minutes_tolerance: int,
) -> PlayerLogResult:
    """Player box-score lines; a team-game whose player minutes disagree with the team total by more
    than the tolerance is rejected as a whole, as are lines for games missing from team_minutes."""
    stats = Transformed()
    players: dict[int, dict[str, Any]] = {}
    pending: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)

    for record in df.to_dict("records"):
        game_id, team_id = str(record["GAME_ID"]), int(record["TEAM_ID"])
        player_id = int(record["PLAYER_ID"])
        key = {"game_id": game_id, "player_id": player_id}
        line = {
            "game_id": game_id,
            "player_id": player_id,
            "team_id": team_id,
            "minutes": to_int(record["MIN"]),
            **_box_values(record),
        }
        if (game_id, team_id) not in team_minutes:
            stats.rejections.append(Rejection(key, "game not in validated team logs"))
            continue
        reason = validate_box(line)
        if reason is None and line["minutes"] is None:
            reason = "missing minutes"
        if reason:
            stats.rejections.append(Rejection(key, reason))
            continue
        pending[(game_id, team_id)].append(line)
        players.setdefault(player_id, {"id": player_id, "full_name": str(record["PLAYER_NAME"])})

    for (game_id, team_id), lines in pending.items():
        total = sum(line["minutes"] for line in lines)
        if abs(total - team_minutes[(game_id, team_id)]) > minutes_tolerance:
            stats.rejections.extend(
                Rejection({"game_id": game_id, "player_id": line["player_id"]},
                          f"team minutes mismatch ({total} vs {team_minutes[(game_id, team_id)]})")
                for line in lines
            )  # fmt: skip
            continue
        stats.rows.extend(lines)
    return PlayerLogResult(stats=stats, players=list(players.values()))


def transform_schedule(df: pd.DataFrame, observed_at: datetime) -> Transformed:
    result = Transformed()
    for record in df.to_dict("records"):
        game_id = str(record["gameId"])
        season_type = SEASON_TYPE_BY_PREFIX.get(game_id[:3])
        if season_type is None:
            continue
        home_id = to_int(record.get("homeTeam_teamId"))
        away_id = to_int(record.get("awayTeam_teamId"))
        if not home_id or not away_id:
            result.rejections.append(Rejection({"game_id": game_id}, "teams not yet determined"))
            continue
        status = SCHEDULE_STATUS.get(to_int(record.get("gameStatus")) or 0)
        if str(record.get("postponedStatus", "N")).upper() == "Y":
            status = GameStatus.postponed
        if status is None:
            result.rejections.append(Rejection({"game_id": game_id}, "unknown game status"))
            continue
        tipoff = pd.to_datetime(record.get("gameDateTimeUTC"), utc=True, errors="coerce")
        home_score = to_int(record.get("homeTeam_score"))
        away_score = to_int(record.get("awayTeam_score"))
        if home_score is not None and away_score is not None and min(home_score, away_score) >= 0:
            result.scores[game_id] = (home_score, away_score)
        result.rows.append({
            "id": game_id,
            "season_id": season_from_game_id(game_id),
            "season_type": season_type,
            "game_date": _game_date(record.get("gameDateEst") or record.get("gameDate")),
            "tipoff_at": None if pd.isna(tipoff) else tipoff.to_pydatetime(),
            "home_team_id": home_id,
            "away_team_id": away_id,
            "status": status,
            "provider_status": {
                "gameStatus": to_int(record.get("gameStatus")),
                "gameStatusText": str(record.get("gameStatusText", "")).strip(),
                "postponedStatus": record.get("postponedStatus"),
            },
            "status_observed_at": observed_at,
            "arena": str(record.get("arenaName") or "").strip() or None,
        })  # fmt: skip
    return result


@dataclass(frozen=True)
class LiveGame:
    status: GameStatus
    status_text: str
    scores: dict[int, int]


def transform_scoreboard(games: pd.DataFrame, teams: pd.DataFrame) -> dict[str, LiveGame]:
    scores: dict[str, dict[int, int]] = defaultdict(dict)
    for record in teams.to_dict("records"):
        team, score = to_int(record.get("teamId")), to_int(record.get("score"))
        if team and score is not None and score >= 0:
            scores[str(record["gameId"])][team] = score
    live = {}
    for record in games.to_dict("records"):
        status = SCHEDULE_STATUS.get(to_int(record.get("gameStatus")) or 0)
        if status is None:
            continue
        game_id = str(record["gameId"])
        text = str(record.get("gameStatusText", "")).strip()
        live[game_id] = LiveGame(status, text, scores[game_id])
    return live


def transform_players(
    all_players: pd.DataFrame, index: pd.DataFrame | None
) -> list[dict[str, Any]]:
    bio = {}
    if index is not None:
        for r in index.to_dict("records"):
            bio[int(r["PERSON_ID"])] = r
    rows = []
    for r in all_players.to_dict("records"):
        pid = int(r["PERSON_ID"])
        b = bio.get(pid, {})
        team_id = to_int(r.get("TEAM_ID")) or None
        rows.append({
            "id": pid,
            "full_name": str(r["DISPLAY_FIRST_LAST"]).strip(),
            "first_name": (str(b["PLAYER_FIRST_NAME"]).strip() or None) if b else None,
            "last_name": (str(b["PLAYER_LAST_NAME"]).strip() or None) if b else None,
            "position": (str(b.get("POSITION") or "").strip() or None) if b else None,
            "height_inches": parse_height(b.get("HEIGHT")) if b else None,
            "weight_lbs": to_int(b.get("WEIGHT")) if b else None,
            "jersey_number": (str(b.get("JERSEY_NUMBER") or "").strip() or None) if b else None,
            "is_active": to_int(r.get("ROSTERSTATUS")) == 1,
            "current_team_id": team_id,
            "from_year": to_int(r.get("FROM_YEAR")),
            "to_year": to_int(r.get("TO_YEAR")),
        })  # fmt: skip
    return rows


# Primary and secondary brand colors (hex), used only as identity accents in the UI.
TEAM_COLORS: dict[str, tuple[str, str]] = {
    "ATL": ("#C8102E", "#FDB927"), "BOS": ("#007A33", "#BA9653"), "BKN": ("#000000", "#FFFFFF"),
    "CHA": ("#1D1160", "#00788C"), "CHI": ("#CE1141", "#000000"), "CLE": ("#860038", "#FDBB30"),
    "DAL": ("#00538C", "#002B5E"), "DEN": ("#0E2240", "#FEC524"), "DET": ("#C8102E", "#1D42BA"),
    "GSW": ("#1D428A", "#FFC72C"), "HOU": ("#CE1141", "#000000"), "IND": ("#002D62", "#FDBB30"),
    "LAC": ("#C8102E", "#1D428A"), "LAL": ("#552583", "#FDB927"), "MEM": ("#5D76A9", "#12173F"),
    "MIA": ("#98002E", "#F9A01B"), "MIL": ("#00471B", "#EEE1C6"), "MIN": ("#0C2340", "#78BE20"),
    "NOP": ("#0C2340", "#C8102E"), "NYK": ("#006BB6", "#F58426"), "OKC": ("#007AC1", "#EF3B24"),
    "ORL": ("#0077C0", "#C4CED4"), "PHI": ("#006BB6", "#ED174C"), "PHX": ("#1D1160", "#E56020"),
    "POR": ("#E03A3E", "#000000"), "SAC": ("#5A2D81", "#63727A"), "SAS": ("#C4CED4", "#000000"),
    "TOR": ("#CE1141", "#000000"), "UTA": ("#002B5C", "#F9A01B"), "WAS": ("#002B5C", "#E31837"),
}  # fmt: skip


# nba_api's static list moved the Warriors to "San Francisco"; the league still calls them
# Golden State (TeamYearByYearStats, schedules, broadcasts).
CITY_OVERRIDES = {"GSW": "Golden State"}


def transform_teams(
    static_teams: list[dict[str, Any]], standings: pd.DataFrame | None
) -> list[dict[str, Any]]:
    conf = {}
    if standings is not None:
        for r in standings.to_dict("records"):
            conf[int(r["TeamID"])] = (r.get("Conference"), r.get("Division"))
    return [
        {
            "id": int(t["id"]),
            "abbreviation": t["abbreviation"],
            "city": CITY_OVERRIDES.get(t["abbreviation"], t["city"]),
            "name": t["nickname"],
            "conference": conf.get(int(t["id"]), (None, None))[0],
            "division": conf.get(int(t["id"]), (None, None))[1],
            "primary_color": TEAM_COLORS.get(t["abbreviation"], (None, None))[0],
            "secondary_color": TEAM_COLORS.get(t["abbreviation"], (None, None))[1],
        }
        for t in static_teams
    ]


# A season total of zero in these columns means the source did not record them that year.
UNRECORDED_WHEN_ZERO = ("oreb", "dreb", "stl", "blk", "tov")
ADVANCED_FIRST_SEASON = 1996
FINALS = {"FINALS APPEARANCE": "finals", "LEAGUE CHAMPION": "champion"}


def _optional_int(value: Any) -> int | None:
    return None if value is None or pd.isna(value) else int(value)


def transform_team_history(frame: pd.DataFrame) -> list[dict[str, Any]]:
    """TeamYearByYearStats (regular season totals) to team_seasons rows, one per played season."""
    rows = []
    for r in frame.to_dict("records"):
        if not r.get("GP"):
            continue
        row: dict[str, Any] = {
            "team_id": int(r["TEAM_ID"]),
            "season_id": int(str(r["YEAR"])[:4]),
            "city": r["TEAM_CITY"],
            "name": r["TEAM_NAME"],
            "games": int(r["GP"]),
            "wins": int(r["WINS"]),
            "losses": int(r["LOSSES"]),
            "conference_rank": _optional_int(r.get("CONF_RANK")) or None,
            "division_rank": _optional_int(r.get("DIV_RANK")) or None,
            "playoff_wins": _optional_int(r.get("PO_WINS")),
            "playoff_losses": _optional_int(r.get("PO_LOSSES")),
            "finals": FINALS.get(str(r.get("NBA_FINALS_APPEARANCE", "")).upper()),
            "pts": int(r["PTS"]),
        }
        for column in ("fgm", "fga", "fg3m", "fg3a", "ftm", "fta", "oreb", "dreb", "reb", "ast",
                       "stl", "blk", "tov", "pf"):  # fmt: skip
            row[column] = _optional_int(r.get(column.upper()))
        for column in UNRECORDED_WHEN_ZERO:
            if row[column] == 0:
                row[column] = None
        if not row["fg3a"]:
            row["fg3m"] = row["fg3a"] = None
        rows.append(row)
    return rows


def transform_team_advanced(frame: pd.DataFrame) -> dict[int, dict[str, float | None]]:
    """LeagueDashTeamStats (Advanced, per game) to pace and ratings by team id."""
    return {
        int(r["TEAM_ID"]): {
            "pace": _optional_float(r.get("PACE")),
            "off_rating": _optional_float(r.get("OFF_RATING")),
            "def_rating": _optional_float(r.get("DEF_RATING")),
            "net_rating": _optional_float(r.get("NET_RATING")),
        }
        for r in frame.to_dict("records")
    }


def _optional_float(value: Any) -> float | None:
    return None if value is None or pd.isna(value) else float(value)


# The 3-point line arrived in 1979-80; earlier zeros mean "no such shot", not "none made".
THREE_POINT_FIRST_SEASON = 1979
CAREER_COUNTS = ("fgm", "fga", "fg3m", "fg3a", "ftm", "fta", "oreb", "dreb", "reb", "ast", "stl",
                 "blk", "tov", "pf")  # fmt: skip


def transform_player_career(frame: pd.DataFrame, season_type: SeasonType) -> list[dict[str, Any]]:
    """PlayerCareerStats season totals (one row per team, plus "TOT" after a mid-season trade) to
    player_seasons rows. Statistics the league did not record that season stay NULL."""
    rows = []
    for r in frame.to_dict("records"):
        games = _optional_int(r.get("GP"))
        if not games:
            continue
        team_id = _optional_int(r.get("TEAM_ID")) or None
        row: dict[str, Any] = {
            "player_id": int(r["PLAYER_ID"]),
            "season_type": season_type,
            "season_id": int(str(r["SEASON_ID"])[:4]),
            "team_abbreviation": "TOT" if team_id is None else str(r["TEAM_ABBREVIATION"]),
            "team_id": team_id,
            "age": _optional_int(r.get("PLAYER_AGE")),
            "games": games,
            "games_started": _optional_int(r.get("GS")),
            "minutes": _optional_int(r.get("MIN")) or None,
            "pts": int(r["PTS"]),
        }
        for column in CAREER_COUNTS:
            row[column] = _optional_int(r.get(column.upper()))
        if row["season_id"] < THREE_POINT_FIRST_SEASON:
            row["fg3m"] = row["fg3a"] = None
        rows.append(row)
    return rows


def transform_matchups(
    frame: pd.DataFrame, game_id: str, teams: tuple[int, int], known_players: set[int]
) -> Transformed:
    """BoxScoreMatchupsV3 to player_matchups rows. `teamId` is the offensive player's team.

    A pair the tracking data credits with no possessions carries no information and is dropped.
    """
    out = Transformed()
    for r in frame.to_dict("records"):
        key = {"game_id": game_id, "off": r.get("personIdOff"), "def": r.get("personIdDef")}
        try:
            off_team = int(r["teamId"])
            off_player, def_player = int(r["personIdOff"]), int(r["personIdDef"])
            possessions = float(r["partialPossessions"])
            seconds = float(r["matchupMinutesSort"])
            numbers = {
                "pts": int(r["playerPoints"]),
                "ast": int(r["matchupAssists"]),
                "tov": int(r["matchupTurnovers"]),
                "fgm": int(r["matchupFieldGoalsMade"]),
                "fga": int(r["matchupFieldGoalsAttempted"]),
                "fg3m": int(r["matchupThreePointersMade"]),
                "fg3a": int(r["matchupThreePointersAttempted"]),
            }
        except (KeyError, TypeError, ValueError) as error:
            out.rejections.append(Rejection(key, f"unreadable matchup row: {error}"))
            continue
        if possessions <= 0:
            continue
        if off_team not in teams:
            out.rejections.append(Rejection(key, f"team {off_team} is not in this game"))
        elif not {off_player, def_player} <= known_players:
            out.rejections.append(Rejection(key, "player not in the players table"))
        elif seconds < 0 or min(numbers.values()) < 0:
            out.rejections.append(Rejection(key, "negative matchup value"))
        else:
            out.rows.append({
                "game_id": game_id,
                "off_player_id": off_player,
                "def_player_id": def_player,
                "off_team_id": off_team,
                "def_team_id": teams[0] if off_team == teams[1] else teams[1],
                "seconds": round(seconds, 1),
                "partial_possessions": round(possessions, 2),
                **numbers,
            })  # fmt: skip
    return out


def transform_attendance(frames: list[pd.DataFrame]) -> int | None:
    """The reported crowd from a box-score summary; zero means not reported (a closed arena reads
    the same as a missing figure, so neither is stored as a real number)."""
    for frame in frames:
        if "attendance" in frame.columns and not frame.empty:
            value = to_int(frame["attendance"].iloc[0])
            return value if value else None
    return None

