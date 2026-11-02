import pandas as pd
import pytest

from app.ingestion import jobs
from tests.api.conftest import SCHEDULED
from tests.fixtures import SEASON, FakeSource, schedule

pytestmark = pytest.mark.integration


@pytest.fixture
def live_game(client, loaded):
    source = FakeSource()
    source.frames[("ScheduleLeagueV2", None)] = pd.concat(
        [
            schedule(SCHEDULED[:1], status=2).assign(
                homeTeam_score=61, awayTeam_score=58, gameStatusText="Q3 5:12"
            ),
            schedule(SCHEDULED[1:], status=1),
        ],
        ignore_index=True,
    )
    jobs.run_job(loaded, "schedule", {"season": SEASON}, jobs.ingest_schedule(source, SEASON))
    client.app.state.api.reset()
    return SCHEDULED[0]


def test_a_live_game_reports_its_score_and_clock(client, live_game):
    body = client.get(f"/api/v1/games/{live_game.id}").json()
    assert body["status"] == "in_progress" and body["live_status"] == "Q3 5:12"
    assert (body["home"]["score"], body["away"]["score"]) == (61, 58)


def test_the_overview_lists_live_games_apart_from_upcoming_ones(client, live_game):
    body = client.get("/api/v1/overview").json()
    assert [g["id"] for g in body["live"]] == [live_game.id]
    assert live_game.id not in [g["id"] for g in body["upcoming"]]


def test_other_games_have_no_live_status(client):
    body = client.get("/api/v1/overview").json()
    assert body["live"] == []
    assert {g["live_status"] for g in [*body["upcoming"], *body["recent"]]} == {None}
