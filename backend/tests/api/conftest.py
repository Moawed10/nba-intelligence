"""Synthetic API dataset loaded through the real ingestion pipeline (season 2099, teams 1–3)."""

from collections.abc import Iterator
from datetime import UTC, datetime

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, event
from sqlalchemy.orm import Session

from app.ingestion import jobs
from app.ingestion.writer import upsert
from app.main import create_app
from app.models import Player, SeasonType, Team
from tests.fixtures import SEASON, TEAMS, FakeSource, FixtureGame, player_id, schedule

NOW = datetime(2099, 11, 10, 18, tzinfo=UTC)
SEASON_LABEL = "2099-00"
FINAL = [
    FixtureGame(1, "2099-11-01", home=1, away=2),
    FixtureGame(2, "2099-11-02", home=3, away=1),
    FixtureGame(3, "2099-11-05", home=1, away=3),
    FixtureGame(4, "2099-11-06", home=2, away=3),
    FixtureGame(5, "2099-11-07", home=2, away=1),
]
SCHEDULED = [
    FixtureGame(6, "2099-11-11", home=1, away=2),
    FixtureGame(7, "2099-11-12", home=3, away=2),
    FixtureGame(8, "2099-11-25", home=1, away=3),
]
STAR = player_id(1, 0)
NO_SHOTS = player_id(1, 1)
RETIRED = 999
DOUBLE_DOUBLE = {"FGM": 10, "FGA": 15, "FG3M": 2, "FG3A": 4, "FTM": 4, "FTA": 5,
                 "OREB": 2, "DREB": 10, "REB": 12, "AST": 3, "PTS": 26}  # fmt: skip
ZERO_ATTEMPTS = {"FGM": 0, "FGA": 0, "FG3M": 0, "FG3A": 0, "FTM": 0, "FTA": 0, "PTS": 0}


def _players() -> list[dict]:
    rows = [
        {
            "id": player_id(team["id"], slot),
            "full_name": f"Test Player {player_id(team['id'], slot)}",
            "last_name": f"Player {player_id(team['id'], slot)}",
            "position": "G",
            "is_active": True,
            "current_team_id": team["id"],
            "source_endpoint": "fixture",
        }
        for team in TEAMS
        for slot in range(5)
    ]
    rows[0].update(full_name="Nikola Testić", last_name="Testić", position="C")
    rows.append({"id": RETIRED, "full_name": "Retired Testić", "last_name": "Testić",
                 "position": None, "is_active": False, "current_team_id": None,
                 "source_endpoint": "fixture"})  # fmt: skip
    return rows


@pytest.fixture
def loaded(engine: Engine) -> Engine:
    with Session(engine) as s, s.begin():
        upsert(s, Team, TEAMS, ["id"])
        upsert(s, Player, _players(), ["id"])
    source = FakeSource()
    source.frames[("ScheduleLeagueV2", None)] = pd.concat(
        [schedule(FINAL, status=3), schedule(SCHEDULED, status=1)], ignore_index=True
    )
    source.set_logs(
        FINAL,
        {(FINAL[0].id, STAR): DOUBLE_DOUBLE, (FINAL[1].id, NO_SHOTS): ZERO_ATTEMPTS},
    )
    team_log = source.frames[("LeagueGameLog", "T")]
    home = team_log["MATCHUP"].str.contains("vs.", regex=False)
    team_log.loc[home, ["FGM", "PTS"]] += [5, 10]
    jobs.run_job(engine, "schedule", {"season": SEASON}, jobs.ingest_schedule(source, SEASON))
    jobs.run_job(
        engine,
        "game_logs",
        {"season": SEASON, "season_type": "regular"},
        jobs.ingest_game_logs(source, SEASON, SeasonType.regular),
    )
    return engine


@pytest.fixture
def client(loaded: Engine) -> Iterator[TestClient]:
    app = create_app(loaded)
    app.state.api.clock = lambda: NOW
    with TestClient(app) as test_client:
        yield test_client


class QueryCounter:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine
        self.count = 0

    def _on_execute(self, *args: object) -> None:
        self.count += 1

    def __enter__(self) -> "QueryCounter":
        event.listen(self.engine, "before_cursor_execute", self._on_execute)
        return self

    def __exit__(self, *exc: object) -> None:
        event.remove(self.engine, "before_cursor_execute", self._on_execute)


@pytest.fixture
def queries(loaded: Engine):
    return lambda: QueryCounter(loaded)
