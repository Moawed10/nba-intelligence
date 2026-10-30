"""Career history: PlayerCareerStats rows through the ingestion job to GET /players/{id}/career."""

from dataclasses import dataclass, field
from typing import Any

import pandas as pd
import pytest

from app.ingestion import jobs
from app.ingestion.client import FetchResult
from app.ingestion.transforms import transform_player_career
from app.models import SeasonType
from tests.api.conftest import RETIRED

pytestmark = pytest.mark.integration

ZERO = {"FGM": 0, "FGA": 0, "FG3M": 0, "FG3A": 0, "FTM": 0, "FTA": 0, "OREB": 0, "DREB": 0,
        "REB": 0, "AST": 0, "STL": 0, "BLK": 0, "TOV": 0, "PF": 0}  # fmt: skip
UNRECORDED = {"FG3M": None, "FG3A": None, "OREB": None, "DREB": None, "STL": None, "BLK": None,
              "TOV": None}  # fmt: skip


def _season(season: str, team_id: int, abbreviation: str, gp: int, pts: int, **stats) -> dict:
    return {"PLAYER_ID": RETIRED, "SEASON_ID": season, "LEAGUE_ID": "00", "TEAM_ID": team_id,
            "TEAM_ABBREVIATION": abbreviation, "PLAYER_AGE": 25.0, "GP": gp, "GS": gp,
            "MIN": gp * 30, "PTS": pts, **ZERO, **stats}  # fmt: skip


REGULAR = pd.DataFrame(
    [
        # 1970-71: before steals, blocks, turnovers and the 3-point line were recorded.
        _season("1970-71", 1610610023, "BAL", 80, 1600, FGM=640, FGA=1400, REB=800, **UNRECORDED),
        # 1985-86: traded mid-season, so two team rows plus the combined "TOT" row.
        _season("1985-86", 1, "AAA", 30, 600, FGM=240, FGA=500, FG3M=10, FG3A=30, STL=30),
        _season("1985-86", 2, "BBB", 40, 1000, FGM=400, FGA=800, FG3M=20, FG3A=50, STL=50),
        _season("1985-86", 0, "TOT", 70, 1600, FGM=640, FGA=1300, FG3M=30, FG3A=80, STL=80),
        _season("1986-87", 2, "BBB", 0, 0),
    ]
)
PLAYOFFS = pd.DataFrame([_season("1985-86", 2, "BBB", 5, 150, FGM=60, FGA=120)])


@dataclass
class CareerSource:
    """Serves PlayerCareerStats in the source's result-set order (regular first, playoffs third)."""

    calls: list[dict[str, Any]] = field(default_factory=list)

    def fetch(self, endpoint_cls: type, *, cacheable: bool = False, **params: Any) -> FetchResult:
        self.calls.append({"endpoint": endpoint_cls.__name__, "cacheable": cacheable, **params})
        empty = REGULAR.iloc[0:0]
        return FetchResult(frames=[REGULAR.copy(), empty, PLAYOFFS.copy(), empty], attempts=1)


def test_unrecorded_statistics_stay_null_and_unplayed_rows_are_skipped():
    rows = transform_player_career(REGULAR, SeasonType.regular)
    assert [(r["season_id"], r["team_abbreviation"]) for r in rows] == [
        (1970, "BAL"), (1985, "AAA"), (1985, "BBB"), (1985, "TOT"),
    ]  # fmt: skip
    early = rows[0]
    assert early["stl"] is None and early["tov"] is None and early["fg3a"] is None
    assert early["team_id"] == 1610610023
    assert rows[3]["team_id"] is None and rows[3]["games"] == 70


@pytest.fixture
def career(loaded):
    source = CareerSource()
    run = jobs.run_job(loaded, "player_careers", {"first": RETIRED, "count": 1},
                       jobs.ingest_player_careers(source, [RETIRED]))  # fmt: skip
    assert run is not None and run.rows_valid == 5
    assert source.calls == [{"endpoint": "PlayerCareerStats", "cacheable": True,
                             "player_id": RETIRED, "per_mode36": "Totals"}]  # fmt: skip
    return loaded


def test_career_lists_every_season_oldest_first(client, career):
    body = client.get(f"/api/v1/players/{RETIRED}/career").json()
    regular = body["regular"]
    assert [s["season"] for s in regular["seasons"]] == ["1970-71", "1985-86"]
    early, traded = regular["seasons"]
    assert early["per_game"]["pts"] == pytest.approx(20.0)
    assert early["per_game"]["stl"] is None and early["fg3_pct"] is None
    assert early["teams"] == [{"abbreviation": "BAL", "team": None}]  # defunct franchise
    assert traded["games"] == 70 and traded["per_game"]["pts"] == pytest.approx(1600 / 70)
    assert [t["abbreviation"] for t in traded["teams"]] == ["AAA", "BBB"]
    assert traded["teams"][0]["team"]["name"] == "Ants"


def test_career_totals_count_a_traded_season_once_and_skip_unrecorded_seasons(client, career):
    regular = client.get(f"/api/v1/players/{RETIRED}/career").json()["regular"]
    totals = regular["totals"]
    assert totals["games"] == 150
    assert totals["per_game"]["pts"] == pytest.approx(3200 / 150)
    assert totals["per_game"]["stl"] == pytest.approx(80 / 70)  # 1985-86 only
    assert totals["fg_pct"] == pytest.approx(1280 / 2700)
    assert regular["partial"] == {"stl": "1985-86", "blk": "1985-86", "fg3m": "1985-86",
                                  "tov": "1985-86"}  # fmt: skip


def test_playoffs_are_listed_separately(client, career):
    playoffs = client.get(f"/api/v1/players/{RETIRED}/career").json()["playoffs"]
    assert [s["season"] for s in playoffs["seasons"]] == ["1985-86"]
    assert playoffs["totals"]["per_game"]["pts"] == pytest.approx(30.0)


def test_player_without_stored_seasons_has_an_empty_career(client, loaded):
    body = client.get(f"/api/v1/players/{RETIRED}/career").json()
    assert body["regular"] == {"seasons": [], "totals": None, "partial": {}}
    assert body["meta"]["data_freshness"]["dataset"] == "career_history"


def test_unknown_player_is_404(client, loaded):
    response = client.get("/api/v1/players/123456789/career")
    assert response.json()["error"]["code"] == "player_not_found"
