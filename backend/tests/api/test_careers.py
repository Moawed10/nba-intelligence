"""Career history: PlayerCareerStats rows through the ingestion job to GET /players/{id}/career."""

from dataclasses import dataclass, field
from typing import Any

import pandas as pd
import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ingestion import jobs
from app.ingestion.client import FetchResult, RetryableSourceError
from app.ingestion.transforms import transform_player_career
from app.models import PlayerSeason, RunStatus, Season, SeasonType
from tests.api.conftest import RETIRED, STAR
from tests.fixtures import player_id

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


def test_all_time_directory_ranks_career_totals_and_counts_trades_once(client, career):
    params = {"season": "all", "sort": "-pts", "active": "false"}
    body = client.get("/api/v1/players", params=params).json()
    assert [p["id"] for p in body["items"]] == [RETIRED]
    totals = body["items"][0]["totals"]
    # 1970-71 plus both 1985-86 team rows; the combined TOT row is not counted again.
    assert totals["games_played"] == 150 and totals["pts"] == 3200
    assert totals["stl"] == 80  # sums the seasons that recorded steals
    assert body["meta"]["data_freshness"]["dataset"] == "career_history"


def test_all_time_with_a_team_counts_only_that_franchise(client, career):
    params = {"season": "all", "team_id": 2, "active": "false"}
    totals = client.get("/api/v1/players", params=params).json()["items"][0]["totals"]
    assert totals["games_played"] == 40 and totals["pts"] == 1000


def test_all_time_has_no_plus_minus(client, career):
    response = client.get("/api/v1/players", params={"season": "all", "sort": "-plus_minus"})
    assert response.status_code == 400
    assert response.json()["error"]["details"][0]["issue"] == "unavailable_sort"


def test_career_for_one_team_keeps_only_that_teams_part_of_a_traded_season(client, career):
    body = client.get(f"/api/v1/players/{RETIRED}/career", params={"team": "BBB"}).json()
    regular = body["regular"]
    assert [s["season"] for s in regular["seasons"]] == ["1985-86"]
    assert regular["totals"]["games"] == 40
    assert regular["totals"]["per_game"]["pts"] == 25.0
    assert [s["season"] for s in body["playoffs"]["seasons"]] == ["1985-86"]
    combined = client.get(f"/api/v1/players/{RETIRED}/career", params={"team": "TOT"})
    assert combined.status_code == 400


def _final_team(client) -> str | None:
    params = {"season": "all", "active": "false"}
    return client.get("/api/v1/players", params=params).json()["items"][0]["final_team"]


def test_a_final_season_split_by_a_trade_without_box_scores_leaves_the_team_unknown(client, career):
    assert _final_team(client) is None  # 1985-86 was split between AAA and BBB


def test_former_players_show_the_team_they_finished_with(client, career):
    with Session(career) as s, s.begin():
        later = s.scalar(select(func.max(Season.id)))  # any season after the 1985-86 trade
        s.add(PlayerSeason(player_id=RETIRED, season_type=SeasonType.regular, season_id=later,
                           team_abbreviation="BBB", team_id=2, games=10, pts=100,
                           source_endpoint="PlayerCareerStats"))  # fmt: skip
    assert _final_team(client) == "BBB"


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


@dataclass
class FlakySource(CareerSource):
    """Fails for the listed players, as stats.nba.com does when it starts timing out."""

    failing: set[int] = field(default_factory=set)

    def fetch(self, endpoint_cls: type, *, cacheable: bool = False, **params: Any) -> FetchResult:
        if params["player_id"] in self.failing:
            raise RetryableSourceError("ReadTimeout")
        return super().fetch(endpoint_cls, cacheable=cacheable, **params)


def test_a_failing_player_is_rejected_and_the_rest_of_the_batch_is_kept(loaded):
    source = FlakySource(failing={STAR})
    run = jobs.run_job(loaded, "player_careers", {"first": STAR, "count": 2},
                       jobs.ingest_player_careers(source, [STAR, RETIRED]))  # fmt: skip
    assert run is not None and run.status == RunStatus.succeeded
    assert run.rows_rejected == 1 and run.rows_valid == 5


def test_repeated_failures_stop_the_batch_early(loaded):
    ids = [player_id(1, slot) for slot in range(5)] + [RETIRED]
    source = FlakySource(failing=set(ids[:5]))
    run = jobs.run_job(loaded, "player_careers", {"first": ids[0], "count": len(ids)},
                       jobs.ingest_player_careers(source, ids))  # fmt: skip
    assert run is not None and run.rows_rejected == jobs.CAREER_FAILURE_LIMIT
    assert len(source.calls) == 0  # stopped before reaching the player who would have worked
