"""Game score forecasts against the synthetic league, with a 10-game rolling baseline for points
(so the expected score is each team's recent average) and a fixed logistic margin calibrator."""

import numpy as np
import pytest
from fastapi.testclient import TestClient
from sklearn.linear_model import LogisticRegression
from sqlalchemy import Engine, func, select, text
from sqlalchemy.orm import Session

from app.ml.artifacts import save_artifact
from app.ml.models import RollingBaseline
from app.ml.team_model import TEAM_FEATURES
from app.models import Algorithm, GamePrediction, ModelRelease, ModelTarget, ModelVersion
from app.services import game_forecasts
from tests.api.conftest import FINAL, SCHEDULED
from tests.api.test_predictions import CONFORMAL, EXTRA, client, league, serving  # noqa: F401

pytestmark = pytest.mark.integration

NEXT_GAME = SCHEDULED[0]  # 2099-11-11, team 1 hosts team 2
LATER_GAME = SCHEDULED[2]  # 2099-11-25, team 1 hosts team 3
URL = "/api/v1/predictions/games"


@pytest.fixture(autouse=True)
def _small_league(monkeypatch):
    """The fixture league has a handful of games per team, below the production minimum."""
    monkeypatch.setattr(game_forecasts, "MIN_PRIOR_GAMES", 3)


def _add_game_models(engine: Engine, directory) -> None:
    calibrator = LogisticRegression().fit(np.array([[-10.0], [-2.0], [2.0], [10.0]]), [0, 0, 1, 1])
    with Session(engine) as s, s.begin():
        release = s.scalars(select(ModelRelease)).one()
        for target, model, algorithm, conformal in (
            ("team_pts", RollingBaseline("pts"), Algorithm.rolling_baseline, CONFORMAL.to_dict()),
            ("home_win", calibrator, Algorithm.logistic, None),
        ):
            path = f"{release.version}/{target}.joblib"
            digest = save_artifact(directory / path, model, target=target, conformal=conformal)
            s.add(
                ModelVersion(
                    release_id=release.id, target=ModelTarget(target), algorithm=algorithm,
                    is_selected=True, hyperparameters={"fit": "production"},
                    features=list(TEAM_FEATURES), interval_calibration=conformal,
                    artifact_path=path, artifact_sha256=digest, random_seed=0,
                )  # fmt: skip
            )


@pytest.fixture
def scoring(league: Engine, tmp_path, serving: TestClient) -> TestClient:  # noqa: F811
    _add_game_models(league, tmp_path)
    return serving


def _team_points(engine: Engine, team: int) -> list[float]:
    with engine.connect() as conn:
        return conn.scalars(
            text(
                "SELECT t.pts FROM team_game_stats t JOIN games g ON g.id = t.game_id "
                "WHERE t.team_id = :t AND g.status = 'final' ORDER BY g.game_date"
            ),
            {"t": team},
        ).all()


def test_release_without_a_game_model_is_a_named_503(serving):  # noqa: F811
    response = serving.post(URL, json={"game_ids": [NEXT_GAME.id]})
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "model_unavailable"


def test_score_forecast_uses_each_teams_earlier_games(league, scoring):  # noqa: F811
    body = scoring.post(URL, json={"game_ids": [NEXT_GAME.id]}).json()
    forecast = body[0]["forecast"]
    home, away = _team_points(league, 1), _team_points(league, 2)
    assert forecast["home"]["team_id"] == 1 and forecast["away"]["team_id"] == 2
    assert forecast["home"]["points"] == pytest.approx(np.mean(home[-10:]))
    assert forecast["away"]["points"] == pytest.approx(np.mean(away[-10:]))
    assert forecast["home"]["lower"] < forecast["home"]["points"] < forecast["home"]["upper"]
    margin = forecast["home"]["points"] - forecast["away"]["points"]
    assert (forecast["home_win_probability"] > 0.5) == (margin > 0)
    assert forecast["interval_level"] == 0.8


def test_repeating_returns_the_stored_forecast(league, scoring):  # noqa: F811
    first = scoring.post(URL, json={"game_ids": [NEXT_GAME.id]}).json()[0]["forecast"]
    again = scoring.post(URL, json={"game_ids": [NEXT_GAME.id, NEXT_GAME.id]}).json()
    assert len(again) == 1 and again[0]["forecast"]["id"] == first["id"]
    with Session(league) as s:
        assert s.scalar(select(func.count()).select_from(GamePrediction)) == 1


def test_new_results_append_a_superseding_forecast(league, scoring):  # noqa: F811
    first = scoring.post(URL, json={"game_ids": [LATER_GAME.id]}).json()[0]["forecast"]
    with league.begin() as conn:
        conn.execute(
            text("UPDATE team_game_stats SET pts = pts + 30 WHERE game_id = :g AND team_id = 1"),
            {"g": FINAL[-1].id},
        )
    second = scoring.post(URL, json={"game_ids": [LATER_GAME.id]}).json()[0]["forecast"]
    assert second["id"] != first["id"]
    assert second["supersedes_prediction_id"] == first["id"]
    assert second["home"]["points"] > first["home"]["points"]
    with Session(league) as s:
        assert s.scalar(select(func.count()).select_from(GamePrediction)) == 2


def test_games_that_cannot_be_forecast_say_why(scoring, monkeypatch):  # noqa: F811
    monkeypatch.setattr(game_forecasts, "MIN_PRIOR_GAMES", 50)
    final = EXTRA[0].id
    body = scoring.post(URL, json={"game_ids": [NEXT_GAME.id, final, "0099999999"]}).json()
    assert [entry["forecast"] for entry in body] == [None, None, None]
    codes = [entry["unavailable"]["code"] for entry in body]
    assert codes == ["insufficient_data", "game_already_started", "game_not_found"]


@pytest.mark.parametrize("ids", [[], ["123"], [str(i).zfill(10) for i in range(31)]])
def test_invalid_requests_are_refused(scoring, ids):  # noqa: F811
    assert scoring.post(URL, json={"game_ids": ids}).status_code == 422
