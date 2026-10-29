"""Phase 7 inference against the synthetic API league (season 2099) with a small active release.

The release uses the 10-game rolling baseline for every statistic, so expected values can be
computed by hand, and a prior-only classifier for the double-double probability.
"""

import uuid
from collections.abc import Iterator
from datetime import UTC, date, datetime

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sklearn.dummy import DummyClassifier
from sqlalchemy import Engine, select, text
from sqlalchemy.orm import Session

from app.ingestion import jobs
from app.ingestion.writer import upsert
from app.main import create_app
from app.ml import inference
from app.ml.artifacts import ArtifactMismatch, save_artifact
from app.ml.conformal import MondrianConformal
from app.ml.dataset import load_dataset
from app.ml.features import FEATURES, TARGETS, feature_schema_version
from app.ml.models import RollingBaseline
from app.models import (
    Algorithm,
    ModelRelease,
    ModelTarget,
    ModelVersion,
    Player,
    PlayerGameStats,
    Prediction,
    ReleaseStatus,
    SeasonType,
    Team,
)
from app.services import prediction_lifecycle
from app.services.prediction_lifecycle import refresh_due, score_game, score_pending
from app.sync.worker import maintain_predictions
from tests.api.conftest import FINAL, NOW, SCHEDULED, _players
from tests.fixtures import SEASON, TEAMS, FakeSource, FixtureGame, player_id, schedule

pytestmark = pytest.mark.integration

# Two more finals give team 1 six games before its next one (eligibility needs five).
EXTRA = [
    FixtureGame(9, "2099-11-08", home=1, away=3),
    FixtureGame(10, "2099-11-09", home=2, away=1),
]
STAR = player_id(1, 0)
TEAM_TWO = player_id(2, 0)
TEAM_THREE = player_id(3, 0)
NEXT_GAME = SCHEDULED[0]  # 2099-11-11, team 1 hosts team 2
CONFORMAL = MondrianConformal(
    alpha=0.2, edges=(10.0, 20.0), quantiles=(1.0, 2.0, 3.0), counts=(9, 9, 9)
)


@pytest.fixture
def league(engine: Engine) -> Engine:
    with Session(engine) as s, s.begin():
        upsert(s, Team, TEAMS, ["id"])
        upsert(s, Player, _players(), ["id"])
    source = FakeSource()
    finals = [*FINAL, *EXTRA]
    source.frames[("ScheduleLeagueV2", None)] = pd.concat(
        [schedule(finals, status=3), schedule(SCHEDULED, status=1)], ignore_index=True
    )
    source.set_logs(finals)
    jobs.run_job(engine, "schedule", {"season": SEASON}, jobs.ingest_schedule(source, SEASON))
    jobs.run_job(
        engine,
        "game_logs",
        {"season": SEASON, "season_type": "regular"},
        jobs.ingest_game_logs(source, SEASON, SeasonType.regular),
    )
    return engine


def _release(engine: Engine, directory, version: str, status: ReleaseStatus) -> None:
    with Session(engine) as s, s.begin():
        release = ModelRelease(
            version=version, feature_schema_version=feature_schema_version(),
            train_start=date(2090, 10, 1), train_end=date(2095, 6, 1), val_start=date(2095, 10, 1),
            val_end=date(2096, 6, 1), test_start=date(2096, 10, 1), test_end=date(2097, 6, 1),
            data_version=1, git_sha=None, status=status,
        )  # fmt: skip
        s.add(release)
        s.flush()
        classifier = DummyClassifier(strategy="prior").fit(
            pd.DataFrame([[0.0] * len(FEATURES)] * 4, columns=list(FEATURES)), [0, 1, 1, 1]
        )
        for target in (*TARGETS, "double_double"):
            regression = target != "double_double"
            path = f"{version}/{target}.joblib"
            model = RollingBaseline(target) if regression else classifier
            calibration = CONFORMAL.to_dict() if regression else None
            digest = save_artifact(directory / path, model, target=target, conformal=calibration)
            s.add(
                ModelVersion(
                    release_id=release.id,
                    target=ModelTarget(target),
                    algorithm=Algorithm.rolling_baseline if regression else Algorithm.logistic,
                    is_selected=True,
                    hyperparameters={"fit": "production"},
                    features=list(FEATURES),
                    interval_calibration=calibration,
                    artifact_path=path,
                    artifact_sha256=digest,
                    random_seed=0,
                )  # fmt: skip
            )


@pytest.fixture
def client(league: Engine, tmp_path) -> Iterator[TestClient]:
    inference.clear_cache()
    app = create_app(league)
    app.state.api.clock = lambda: NOW
    app.state.api.artifacts_dir = tmp_path
    with TestClient(app) as test_client:
        yield test_client
    inference.clear_cache()


@pytest.fixture
def serving(league: Engine, tmp_path, client: TestClient) -> TestClient:
    _release(league, tmp_path, "2099.11.10-1", ReleaseStatus.active)
    return client


def _post(client: TestClient, player: int = STAR, game: FixtureGame = NEXT_GAME):
    return client.post("/api/v1/predictions", json={"player_id": player, "game_id": game.id})


def _star_points(engine: Engine) -> list[float]:
    with engine.connect() as conn:
        return conn.scalars(
            text(
                "SELECT s.pts FROM player_game_stats s JOIN games g ON g.id = s.game_id "
                "WHERE s.player_id = :p ORDER BY g.game_date"
            ),
            {"p": STAR},
        ).all()


def test_no_active_release_is_a_named_503(league, tmp_path, client):
    _release(league, tmp_path, "2099.11.10-1", ReleaseStatus.candidate)
    response = _post(client)
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "model_unavailable"


def test_forecast_uses_pregame_features_and_is_stored(league, serving):
    response = _post(serving)
    assert response.status_code == 201
    body = response.json()
    assert body["release_version"] == "2099.11.10-1"
    assert body["kind"] == "pregame" and body["status"] == "ok"
    assert datetime.fromisoformat(body["data_cutoff_at"]) == NOW

    values = {v["stat"]: v for v in body["values"]}
    assert list(values) == list(TARGETS)
    points = _star_points(league)
    assert len(points) == 6
    assert values["pts"]["point"] == pytest.approx(sum(points) / len(points))
    for v in values.values():
        assert v["lower"] <= v["point"] <= v["upper"]
        assert v["interval_level"] == 0.8
    minutes = values["min"]["point"]
    half = CONFORMAL.quantiles[sum(minutes >= e for e in CONFORMAL.edges)]
    assert values["pts"]["upper"] - values["pts"]["point"] == pytest.approx(half)
    assert body["double_double_probability"] == pytest.approx(0.75)
    inputs = body["explanation"]["inputs"]["pts"]
    assert inputs["pts_avg_10"] == pytest.approx(values["pts"]["point"])


def test_repeating_with_unchanged_data_returns_the_stored_prediction(serving):
    first = _post(serving).json()
    again = _post(serving)
    assert again.status_code == 200
    assert again.json()["id"] == first["id"]


def test_new_data_appends_a_superseding_prediction_and_keeps_the_old_one(league, serving):
    first = _post(serving).json()
    with league.begin() as conn:
        conn.execute(
            text(
                "UPDATE player_game_stats SET pts = pts + 12 WHERE player_id = :p AND game_id = :g"
            ),
            {"p": STAR, "g": EXTRA[1].id},
        )
    second = _post(serving)
    assert second.status_code == 201
    body = second.json()
    assert body["supersedes_prediction_id"] == first["id"]
    assert body["values"][0]["point"] == pytest.approx(first["values"][0]["point"] + 2)

    assert serving.get(f"/api/v1/predictions/{first['id']}").json()["values"] == first["values"]
    history = serving.get("/api/v1/predictions", params={"player_id": STAR}).json()
    assert [h["id"] for h in history] == [body["id"], first["id"]]


@pytest.mark.parametrize(
    ("player", "game", "status", "code"),
    [
        (TEAM_THREE, NEXT_GAME, 422, "invalid_matchup"),
        (STAR, FINAL[0], 409, "game_already_started"),
        (TEAM_TWO, NEXT_GAME, 422, "insufficient_data"),
        (123456, NEXT_GAME, 404, "player_not_found"),
    ],
)
def test_invalid_requests_are_refused_without_storing(league, serving, player, game, status, code):
    response = _post(serving, player, game)
    assert response.status_code == status
    assert response.json()["error"]["code"] == code
    with Session(league) as s:
        assert s.scalar(select(Prediction)) is None


def test_games_at_or_after_tipoff_are_closed(league, serving):
    serving.app.state.api.clock = lambda: datetime(2099, 11, 11, 1, tzinfo=UTC)
    assert _post(serving).json()["error"]["code"] == "game_already_started"


def test_tampered_artifact_stops_serving(league, tmp_path, serving):
    with (tmp_path / "2099.11.10-1" / "pts.joblib").open("ab") as f:
        f.write(b"tampered")
    response = _post(serving)
    assert response.status_code == 503
    assert "verification" in response.json()["error"]["message"]


def test_served_features_match_the_training_row_for_the_same_game(league):
    """Inference and training share build_features; a past game must produce the identical row."""
    frame = load_dataset(league).frame
    game = EXTRA[1]
    expected = frame[(frame["player_id"] == STAR) & (frame["game_id"] == game.id)].iloc[0]
    with Session(league) as s:
        served = inference.pregame_features(
            s, player_id=STAR, team_id=1, opponent_id=2, is_home=False, game_id=game.id,
            game_date=date.fromisoformat(game.date), season_id=SEASON,
        )  # fmt: skip
    for name in FEATURES:
        assert served[name] == pytest.approx(expected[name], nan_ok=True), name


def test_activation_verifies_artifacts_and_retires_the_previous_release(league, tmp_path):
    _release(league, tmp_path, "2099.11.10-1", ReleaseStatus.active)
    _release(league, tmp_path, "2099.11.10-2", ReleaseStatus.candidate)
    with Session(league) as s, s.begin():
        inference.activate(s, "2099.11.10-2", tmp_path, NOW)
    with Session(league) as s:
        statuses = dict(s.execute(select(ModelRelease.version, ModelRelease.status)).all())
    assert statuses == {"2099.11.10-1": ReleaseStatus.retired, "2099.11.10-2": ReleaseStatus.active}

    (tmp_path / "2099.11.10-1" / "reb.joblib").write_bytes(b"broken")
    with Session(league) as s, pytest.raises(ArtifactMismatch):
        inference.activate(s, "2099.11.10-1", tmp_path, NOW)


def test_stored_snapshot_reproduces_the_stored_values_exactly(league, tmp_path, serving):
    body = _post(serving).json()
    with Session(league) as s:
        row = s.get(Prediction, uuid.UUID(body["id"]))
        snapshot = dict(row.feature_snapshot)
        release = inference.active_release(s, tmp_path)
    assert inference.snapshot_hash(snapshot) == row.feature_snapshot_sha256
    values = {n: float("nan") if snapshot[n] is None else snapshot[n] for n in FEATURES}
    features = pd.Series(values, dtype=object)
    features["prior_games"], features["eligible"] = 6, True
    again = inference.predict(release, features)
    stored = {v["stat"]: (v["point"], v["lower"], v["upper"]) for v in body["values"]}
    assert again.values == stored


def _fresh(client: TestClient, prediction_id: str) -> str:
    return client.get(f"/api/v1/predictions/{prediction_id}").json()["freshness"]


def _add_star_game(engine: Engine, game_id: str, pts_bonus: int = 0) -> None:
    """Copy the star's last box score into another game, as if he had played it."""
    with Session(engine) as s, s.begin():
        source = s.scalar(
            select(PlayerGameStats).where(
                PlayerGameStats.player_id == STAR, PlayerGameStats.game_id == EXTRA[1].id
            )
        )
        columns = {c.key: getattr(source, c.key) for c in PlayerGameStats.__table__.columns}
        columns.update(game_id=game_id, pts=columns["pts"] + pts_bonus)
        s.add(PlayerGameStats(**columns))


def test_freshness_follows_new_data_and_refresh_supersedes(league, tmp_path, serving):
    first = _post(serving).json()
    assert first["freshness"] == "current"
    assert _fresh(serving, first["id"]) == "current"

    with league.begin() as conn:
        conn.execute(
            text(
                "UPDATE player_game_stats SET pts = pts + 12 WHERE player_id = :p AND game_id = :g"
            ),
            {"p": STAR, "g": EXTRA[1].id},
        )
    body = serving.get(f"/api/v1/predictions/{first['id']}").json()
    assert body["freshness"] == "stale" and "New games" in body["freshness_reason"]

    with Session(league) as s:
        counts = refresh_due(s, tmp_path, NOW)
    assert counts == {"checked": 1, "refreshed": 1, "skipped": 0}
    assert _fresh(serving, first["id"]) == "superseded"
    latest = serving.get("/api/v1/predictions", params={"player_id": STAR}).json()[0]
    assert latest["supersedes_prediction_id"] == first["id"] and latest["freshness"] == "current"


def test_forecasts_become_final_pregame_at_tipoff(serving):
    first = _post(serving).json()
    serving.app.state.api.clock = lambda: datetime(2099, 11, 11, 1, tzinfo=UTC)
    assert _fresh(serving, first["id"]) == "final_pregame"


@pytest.mark.parametrize(
    "change",
    [
        "UPDATE players SET current_team_id = 3 WHERE id = :p",
        "UPDATE games SET status = 'postponed' WHERE id = :g",
    ],
)
def test_matchup_changes_make_a_forecast_invalid(league, serving, change):
    first = _post(serving).json()
    with league.begin() as conn:
        conn.execute(text(change), {"p": STAR, "g": NEXT_GAME.id})
    assert _fresh(serving, first["id"]) == "invalid"


def test_final_pregame_forecast_is_scored_and_counted_live(league, tmp_path, serving):
    _post(serving)
    with league.begin() as conn:
        conn.execute(
            text(
                "UPDATE player_game_stats SET pts = pts + 12 WHERE player_id = :p AND game_id = :g"
            ),
            {"p": STAR, "g": EXTRA[1].id},
        )
    second = _post(serving).json()
    _add_star_game(league, NEXT_GAME.id, pts_bonus=3)
    with league.begin() as conn:
        conn.execute(
            text("UPDATE games SET status = 'final', stats_finalized_at = now() WHERE id = :g"),
            {"g": NEXT_GAME.id},
        )
    with Session(league) as s, s.begin():
        written = score_pending(s, NOW)
    assert written == 2 * (len(TARGETS) + 1)  # both rows scored; live counts only the final one

    scored = serving.get(f"/api/v1/predictions/{second['id']}").json()
    with Session(league) as s:
        actual = s.scalar(
            select(PlayerGameStats.pts).where(
                PlayerGameStats.player_id == STAR, PlayerGameStats.game_id == NEXT_GAME.id
            )
        )
    assert scored["actuals"]["pts"] == actual
    assert scored["freshness"] == "final_pregame"

    live = serving.get("/api/v1/models/2099.11.10-1/live").json()
    assert live["games"] == 1
    points = next(s for s in live["stats"] if s["stat"] == "pts")
    assert points["n"] == 1
    assert points["mae"] == pytest.approx(abs(second["values"][0]["point"] - actual))
    assert live["double_double"]["n"] == 1


def test_players_who_did_not_play_are_not_scored(league, serving):
    _post(serving)
    with league.begin() as conn:
        conn.execute(text("UPDATE games SET status = 'final' WHERE id = :g"), {"g": NEXT_GAME.id})
    with Session(league) as s, s.begin():
        assert score_game(s, NEXT_GAME.id, NOW) == 0


def test_explanation_lists_every_input(serving):
    first = _post(serving).json()
    body = serving.get(f"/api/v1/predictions/{first['id']}/explanation").json()
    assert set(body["features"]) == set(FEATURES)
    assert body["inputs"]["pts"]["pts_avg_10"] == pytest.approx(first["values"][0]["point"])


def test_inference_is_bounded(serving, monkeypatch):
    monkeypatch.setattr(prediction_lifecycle._inference_slots, "acquire", lambda timeout: False)
    response = _post(serving)
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "inference_busy"


def test_worker_job_scores_and_refreshes(league, tmp_path, serving):
    _post(serving)
    assert maintain_predictions(league, NOW, tmp_path) == {
        "scored": 0,
        "checked": 1,
        "refreshed": 0,
        "skipped": 0,
    }


def test_upcoming_forecasts_every_scheduled_game_once(serving):
    body = serving.post("/api/v1/predictions/upcoming", json={"player_id": STAR}).json()
    assert [entry["game"]["id"] for entry in body] == [NEXT_GAME.id]
    assert body[0]["unavailable"] is None
    first_id = body[0]["prediction"]["id"]
    again = serving.post("/api/v1/predictions/upcoming", json={"player_id": STAR}).json()
    assert again[0]["prediction"]["id"] == first_id


def test_upcoming_explains_games_it_cannot_forecast(serving):
    body = serving.post("/api/v1/predictions/upcoming", json={"player_id": TEAM_TWO}).json()
    assert body and all(entry["prediction"] is None for entry in body)
    assert {entry["unavailable"]["code"] for entry in body} == {"insufficient_data"}
