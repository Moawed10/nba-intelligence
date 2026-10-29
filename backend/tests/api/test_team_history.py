import pandas as pd
import pytest
from sqlalchemy.orm import Session

from app.ingestion.jobs import ensure_season
from app.ingestion.transforms import transform_team_advanced, transform_team_history
from app.ingestion.writer import upsert
from app.models import TeamSeason

pytestmark = pytest.mark.integration

COUNTS = {"FGM": 3000, "FGA": 7000, "FG3M": 0, "FG3A": 0, "FTM": 1500, "FTA": 2000,
          "OREB": 0, "DREB": 0, "REB": 4000, "AST": 1800, "STL": 0, "BLK": 0, "TOV": 0,
          "PF": 2000}  # fmt: skip


def _year(year: str, city: str, name: str, **overrides) -> dict:
    return {"TEAM_ID": 1, "YEAR": year, "TEAM_CITY": city, "TEAM_NAME": name, "GP": 82,
            "WINS": 41, "LOSSES": 41, "CONF_RANK": 0, "DIV_RANK": 3, "PO_WINS": 0, "PO_LOSSES": 0,
            "NBA_FINALS_APPEARANCE": "N/A", "PTS": 9000, **COUNTS, **overrides}  # fmt: skip


FRAME = pd.DataFrame(
    [
        _year("1970-71", "Seattle", "SuperSonics"),
        _year(
            "2007-08",
            "Seattle",
            "SuperSonics",
            FG3M=500,
            FG3A=1400,
            OREB=900,
            DREB=2600,
            STL=600,
            BLK=400,
            TOV=1200,
            NBA_FINALS_APPEARANCE="LEAGUE CHAMPION",
            PO_WINS=16,
            PO_LOSSES=6,
        ),  # fmt: skip
        _year("2008-09", "Oklahoma City", "Thunder", GP=0),
    ]
)


def test_unrecorded_columns_become_null_and_unplayed_seasons_are_skipped():
    rows = transform_team_history(FRAME)
    assert [r["season_id"] for r in rows] == [1970, 2007]
    early, late = rows
    assert early["name"] == "SuperSonics" and early["city"] == "Seattle"
    assert early["tov"] is None and early["oreb"] is None and early["stl"] is None
    assert early["fg3m"] is None and early["fg3a"] is None  # no 3-point line yet
    assert early["conference_rank"] is None and early["finals"] is None
    assert late["tov"] == 1200 and late["fg3a"] == 1400
    assert late["finals"] == "champion" and late["playoff_wins"] == 16


def test_advanced_rows_are_keyed_by_team():
    frame = pd.DataFrame([{"TEAM_ID": 1, "PACE": 91.5, "OFF_RATING": 110.2, "DEF_RATING": None,
                           "NET_RATING": 3.1}])  # fmt: skip
    assert transform_team_advanced(frame) == {
        1: {"pace": 91.5, "off_rating": 110.2, "def_rating": None, "net_rating": 3.1}
    }


@pytest.fixture
def history(loaded):
    rows = transform_team_history(FRAME)
    rows[1].update(pace=91.5, off_rating=110.2, def_rating=104.0, net_rating=6.2)
    rows[0].update(pace=None, off_rating=None, def_rating=None, net_rating=None)
    with Session(loaded) as s, s.begin():
        for r in rows:
            ensure_season(s, r["season_id"])
        key = ["team_id", "season_id"]
        upsert(s, TeamSeason, rows, key, provenance={"source_endpoint": "test"})
    return loaded


def test_history_lists_seasons_newest_first_with_that_years_name(client, history):
    body = client.get("/api/v1/teams/1/history").json()
    assert [s["season"] for s in body["seasons"]] == ["2007-08", "1970-71"]
    latest, early = body["seasons"]
    assert latest["per_game"]["pts"] == pytest.approx(round(9000 / 82, 1))
    assert latest["fg3_pct"] == pytest.approx(round(500 / 1400, 4))
    assert latest["off_rating"] == 110.2 and latest["finals"] == "champion"
    assert early["per_game"]["tov"] is None and early["fg3_pct"] is None and early["pace"] is None
    assert body["team"]["id"] == 1


def test_unknown_team_is_404(client, history):
    assert client.get("/api/v1/teams/99/history").json()["error"]["code"] == "team_not_found"
