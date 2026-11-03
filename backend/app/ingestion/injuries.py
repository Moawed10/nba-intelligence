"""The current injury report from ESPN's public feed; player ids come from our own roster.

The NBA's official report carries no expected return date, and ESPN's does. Names are matched only
when exactly one active player has them; anything else is rejected rather than guessed.
"""

import re
import unicodedata
from collections.abc import Iterable, Mapping
from datetime import date, datetime
from typing import Any

import requests

from app.config import get_settings
from app.ingestion.transforms import Rejection

INJURIES_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/injuries"
SOURCE = "espn_injuries"
SUFFIXES = re.compile(r"\b(jr|sr|ii|iii|iv|v)\b")


def fetch_injury_report() -> dict[str, Any]:
    response = requests.get(INJURIES_URL, timeout=get_settings().stats_timeout_seconds)
    response.raise_for_status()
    return response.json()


def normalize_name(name: str) -> str:
    plain = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    plain = SUFFIXES.sub("", plain.replace(".", "").replace("'", "").replace("-", " "))
    return " ".join(plain.split())


def name_index(players: Iterable[tuple[int, str]]) -> dict[str, int | None]:
    """Normalized name to player id; None when two active players share the name."""
    index: dict[str, int | None] = {}
    for player_id, name in players:
        key = normalize_name(name)
        index[key] = None if key in index else player_id
    return index


def _text(value: Any) -> str | None:
    text = str(value).strip() if value else ""
    return text if text and text.lower() != "not specified" else None


def _day(value: Any) -> date | None:
    try:
        return date.fromisoformat(str(value)[:10]) if value else None
    except ValueError:
        return None


def transform_injuries(
    payload: Mapping[str, Any], names: Mapping[str, int | None]
) -> tuple[list[dict[str, Any]], list[Rejection]]:
    rows: dict[int, dict[str, Any]] = {}
    rejections: list[Rejection] = []
    for team in payload.get("injuries") or []:
        for entry in team.get("injuries") or []:
            name = (entry.get("athlete") or {}).get("displayName") or ""
            player_id = names.get(normalize_name(name))
            status = _text(entry.get("status"))
            if player_id is None or status is None:
                rejections.append(
                    Rejection({"player": name}, "no single active player by this name")
                )
                continue
            details = entry.get("details") or {}
            reported = datetime.fromisoformat(str(entry["date"]).replace("Z", "+00:00"))
            row = {
                "player_id": player_id,
                "status": status,
                "injury": _text(details.get("type")) or _text(details.get("location")),
                "detail": _text(details.get("detail")),
                "side": _text(details.get("side")),
                "return_date": _day(details.get("returnDate")),
                "reported_at": reported,
            }
            if player_id not in rows or reported > rows[player_id]["reported_at"]:
                rows[player_id] = row
    return list(rows.values()), rejections
