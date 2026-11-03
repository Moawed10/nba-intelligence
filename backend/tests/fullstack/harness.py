import argparse
import json
import os
import shutil
import sys
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from alembic import command
from sklearn.dummy import DummyClassifier
from sklearn.linear_model import LogisticRegression
from sqlalchemy import Engine, create_engine, make_url, select, text
from sqlalchemy.orm import Session

from app.ingestion import jobs
from app.ingestion.writer import upsert
from app.ml import inference
from app.ml.artifacts import save_artifact
from app.ml.backtest import run_backtest
from app.ml.conformal import MondrianConformal
from app.ml.features import FEATURES, TARGETS, feature_schema_version
from app.ml.models import RollingBaseline
from app.ml.team_model import TEAM_FEATURES
from app.models import (
    Algorithm,
    ModelRelease,
    ModelTarget,
    ModelVersion,
    Player,
    ReleaseStatus,
    SeasonType,
    Team,
)
from app.services import prediction_lifecycle
from app.sync import worker
from tests.conftest import _recreate_database, alembic_config
from tests.fixtures import BOX, SEASON, TEAMS, FakeSource, FixtureGame, player_id, team_log

SCENARIO = json.loads((Path(__file__).parent / "scenario.json").read_text())
ROOT = Path(os.environ["NBA_FULLSTACK_DIR"])
CLOCK = Path(os.environ["NBA_FULLSTACK_CLOCK"])
ARTIFACTS = Path(os.environ["NBA_ARTIFACTS_DIR"])
URL = os.environ["NBA_DATABASE_URL"]
VERSION = SCENARIO["version"]


def now() -> datetime:
    return datetime.fromisoformat(CLOCK.read_text().strip())


def set_clock(value: str) -> None:
    CLOCK.write_text(value)


def engine() -> Engine:
    if "fullstack" not in (make_url(URL).database or ""):
        raise SystemExit("refusing to run: the database name must contain 'fullstack'")
    return create_engine(URL, connect_args={"options": "-c timezone=UTC"})


def _fixture(game: dict[str, Any]) -> FixtureGame:
    return FixtureGame(game["number"], game["date"], home=game["home"], away=game["away"])


def _box(line: dict[str, int]) -> dict[str, int]:
    made, free = line["pts"] // 2, line["pts"] % 2
    return {
        **BOX,
        "FGM": made,
        "FGA": made,
        "FG3M": 0,
        "FG3A": 0,
        "FTM": free,
        "FTA": free,
        "OREB": 0,
        "DREB": line["reb"],
        "REB": line["reb"],
        "AST": line["ast"],
        "PTS": line["pts"],
    }


def _player_log(finals: list[dict[str, Any]]) -> pd.DataFrame:
    rows = []
    default = SCENARIO["default_line"]
    for game in finals:
        fixture = _fixture(game)
        for team in (game["home"], game["away"]):
            for slot in range(5):
                pid = player_id(team, slot)
                rows.append(
                    {
                        "SEASON_ID": f"2{SEASON}",
                        "PLAYER_ID": pid,
                        "PLAYER_NAME": _name(pid),
                        "TEAM_ID": team,
                        "GAME_ID": fixture.id,
                        "GAME_DATE": game["date"],
                        "MIN": 48,
                        "PLUS_MINUS": 0,
                        **_box(game["lines"].get(str(pid), default)),
                    }
                )
    return pd.DataFrame(rows)


def _team_log(finals: list[dict[str, Any]]) -> pd.DataFrame:
    frame = team_log([_fixture(g) for g in finals])
    for game in finals:
        for team, score, other in (
            (game["home"], game["home_score"], game["away_score"]),
            (game["away"], game["away_score"], game["home_score"]),
        ):
            row = (frame["GAME_ID"] == _fixture(game).id) & (frame["TEAM_ID"] == team)
            extra = score - BOX["PTS"] * 5
            frame.loc[row, "PTS"] = score
            frame.loc[row, "FGM"] += extra // 2
            frame.loc[row, "WL"] = "W" if score > other else "L"
    return frame


def _schedule(finals: list[dict[str, Any]], scheduled: list[dict[str, Any]]) -> pd.DataFrame:
    def row(game: dict[str, Any], status: int) -> dict[str, Any]:
        return {
            "gameId": _fixture(game).id,
            "gameStatus": status,
            "gameStatusText": {1: "7:30 pm ET", 3: "Final"}[status],
            "gameDateEst": f"{game['date']}T00:00:00Z",
            "gameDateTimeUTC": f"{game['date']}T00:30:00Z",
            "homeTeam_teamId": game["home"],
            "awayTeam_teamId": game["away"],
            "arenaName": "Fixture Arena",
            "postponedStatus": "N",
        }

    return pd.DataFrame([row(g, 3) for g in finals] + [row(g, 1) for g in scheduled])


def ingest(db: Engine, finals: list[dict[str, Any]], scheduled: list[dict[str, Any]]) -> None:
    source = FakeSource()
    source.frames[("ScheduleLeagueV2", None)] = _schedule(finals, scheduled)
    source.frames[("LeagueGameLog", "T")] = _team_log(finals)
    source.frames[("LeagueGameLog", "P")] = _player_log(finals)
    jobs.run_job(db, "schedule", {"season": SEASON}, jobs.ingest_schedule(source, SEASON))
    jobs.run_job(
        db,
        "game_logs",
        {"season": SEASON, "season_type": "regular"},
        jobs.ingest_game_logs(source, SEASON, SeasonType.regular),
    )


def _name(pid: int) -> str:
    return "Nikola Testić" if pid == SCENARIO["star"] else f"Test Player {pid}"


def _players() -> list[dict[str, Any]]:
    return [
        {
            "id": player_id(team["id"], slot),
            "full_name": _name(player_id(team["id"], slot)),
            "last_name": _name(player_id(team["id"], slot)).split(" ", 1)[1],
            "position": "G",
            "is_active": True,
            "current_team_id": team["id"],
            "source_endpoint": "fixture",
        }
        for team in TEAMS
        for slot in range(5)
    ]


def _add_version(
    session: Session,
    release: ModelRelease,
    target: str,
    model: Any,
    algorithm: Algorithm,
    features: tuple[str, ...],
    calibration: dict | None,
    held_out: bool,
) -> None:
    path = f"{VERSION}/{'held_out_' if held_out else ''}{target}.joblib"
    digest = save_artifact(ARTIFACTS / path, model, target=target, conformal=calibration)
    session.add(
        ModelVersion(
            release_id=release.id,
            target=ModelTarget(target),
            algorithm=algorithm,
            is_selected=not held_out,
            hyperparameters={"fit": "held_out" if held_out else "production"},
            features=list(features),
            interval_calibration=calibration,
            artifact_path=path,
            artifact_sha256=digest,
            random_seed=0,
        )
    )


def register_release(db: Engine) -> None:
    window = SCENARIO["backtest_window"]
    calibration = MondrianConformal(
        alpha=SCENARIO["conformal"]["alpha"],
        edges=tuple(SCENARIO["conformal"]["edges"]),
        quantiles=tuple(SCENARIO["conformal"]["quantiles"]),
        counts=tuple(SCENARIO["conformal"]["counts"]),
    ).to_dict()
    positive = int(SCENARIO["double_double_prior"] * 4)
    classifier = DummyClassifier(strategy="prior").fit(
        pd.DataFrame([[0.0] * len(FEATURES)] * 4, columns=list(FEATURES)),
        [1] * positive + [0] * (4 - positive),
    )
    winner = LogisticRegression().fit(np.array([[-10.0], [-2.0], [2.0], [10.0]]), [0, 0, 1, 1])
    with Session(db) as s, s.begin():
        release = ModelRelease(
            version=VERSION,
            feature_schema_version=feature_schema_version(),
            train_start=date(2090, 10, 1),
            train_end=date(2095, 6, 1),
            val_start=date(2095, 10, 1),
            val_end=date(2096, 6, 1),
            test_start=date.fromisoformat(window["start"]),
            test_end=date.fromisoformat(window["end"]),
            data_version=1,
            git_sha=None,
            status=ReleaseStatus.candidate,
        )
        s.add(release)
        s.flush()
        for held_out in (False, True):
            for target in TARGETS:
                baseline = RollingBaseline(target)
                _add_version(s, release, target, baseline, Algorithm.rolling_baseline, FEATURES,
                             calibration, held_out)  # fmt: skip
            _add_version(s, release, "double_double", classifier, Algorithm.logistic, FEATURES,
                         None, held_out)  # fmt: skip
        _add_version(s, release, "team_pts", RollingBaseline("pts"), Algorithm.rolling_baseline,
                     TEAM_FEATURES, calibration, False)  # fmt: skip
        _add_version(s, release, "home_win", winner, Algorithm.logistic, TEAM_FEATURES, None, False)
    with Session(db) as s, s.begin():
        inference.activate(s, VERSION, ARTIFACTS, now())
    run_backtest(db, ARTIFACTS, VERSION, now())


def seed() -> dict[str, Any]:
    db = engine()
    _recreate_database(URL)
    command.upgrade(alembic_config(URL), "head")
    shutil.rmtree(ROOT, ignore_errors=True)
    ARTIFACTS.mkdir(parents=True)
    set_clock(SCENARIO["clock"]["start"])
    with Session(db) as s, s.begin():
        upsert(s, Team, TEAMS, ["id"])
        upsert(s, Player, _players(), ["id"])
    ingest(db, SCENARIO["finals"], [SCENARIO["target"], *SCENARIO["later"]])
    register_release(db)
    return {"seeded": VERSION, "clock": now().isoformat()}


def add_game() -> dict[str, Any]:
    ingest(
        engine(),
        [*SCENARIO["finals"], SCENARIO["added_final"]],
        [SCENARIO["target"], *SCENARIO["later"]],
    )
    return {"added": _fixture(SCENARIO["added_final"]).id}


def maintain() -> dict[str, Any]:
    result = worker.maintain_predictions(engine(), now(), ARTIFACTS)
    if result is None:
        raise SystemExit("prediction maintenance is running elsewhere")
    return result


def finalize() -> dict[str, Any]:
    db = engine()
    finals = [*SCENARIO["finals"], SCENARIO["added_final"], SCENARIO["target"]]
    ingest(db, finals, SCENARIO["later"])
    started = datetime.now(UTC)
    ingest(db, finals, SCENARIO["later"])
    return {
        "finalized": worker.finalize_stable_box_scores(db, started, now()),
        "events": worker.drain_events(db, now()),
    }


def score() -> dict[str, Any]:
    db = engine()
    game = _fixture(SCENARIO["target"]).id
    with Session(db) as s, s.begin():
        pending = prediction_lifecycle.score_pending(s, now())
        rewritten = prediction_lifecycle.score_game(s, game, now())
    return {"pending": pending, "rewritten": rewritten, "maintenance": maintain()}


def state() -> dict[str, Any]:
    sql = """
        SELECT p.id::text AS id, p.player_id, p.game_id, p.created_at::text AS created_at,
               p.supersedes_prediction_id::text AS supersedes, p.feature_snapshot_sha256 AS sha,
               p.double_double_probability AS dd,
               (SELECT json_object_agg(v.stat, json_build_object(
                    'point', v.point, 'lower', v.lower, 'upper', v.upper))
                FROM prediction_values v WHERE v.prediction_id = p.id) AS values,
               (SELECT json_object_agg(e.stat, json_build_object(
                    'actual', e.actual, 'abs_error', e.abs_error, 'within', e.within_interval))
                FROM prediction_evaluations e WHERE e.prediction_id = p.id) AS evaluations
        FROM predictions p WHERE p.kind = 'pregame'
        ORDER BY p.created_at, p.player_id, p.game_id
    """
    with engine().connect() as conn:
        rows = [dict(r._mapping) for r in conn.execute(text(sql))]
        status = conn.execute(
            select(text("status::text, stats_finalized_at::text"))
            .select_from(text("games"))
            .where(text("id = :id")),
            {"id": _fixture(SCENARIO["target"]).id},
        ).one()
    return {
        "predictions": rows,
        "target": {"status": status[0], "stats_finalized_at": status[1]},
        "clock": now().isoformat(),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("seed", "add-game", "maintain", "finalize", "score", "state"):
        sub.add_parser(name)
    sub.add_parser("clock").add_argument("value")
    args = parser.parse_args()
    if args.command == "clock":
        set_clock(args.value)
        result: dict[str, Any] = {"clock": now().isoformat()}
    else:
        commands = {"seed": seed, "add-game": add_game, "maintain": maintain,
                    "finalize": finalize, "score": score, "state": state}  # fmt: skip
        result = commands[args.command]()
    json.dump(result, sys.stdout, default=str)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
