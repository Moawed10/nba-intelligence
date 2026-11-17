"""Prediction API: create through the lifecycle service, read back with derived freshness."""

import uuid

from sqlalchemy import exists, select
from sqlalchemy.orm import aliased

from app.api.deps import Context
from app.api.errors import ApiError, not_found
from app.ml.artifacts import ArtifactMismatch
from app.ml.inference import ActiveRelease, active_release
from app.models import (
    Game,
    ModelRelease,
    Player,
    PlayerGameStats,
    Prediction,
    PredictionEvaluation,
    PredictionKind,
    PredictionValue,
    Season,
    Team,
    TeamSeason,
)
from app.models.predictions import PredictedStat
from app.schemas.predictions import (
    PredictedValue,
    PredictionExplanation,
    Unavailable,
    UpcomingForecast,
)
from app.schemas.predictions import Prediction as PredictionOut
from app.schemas.resources import HistoryEntry, HistoryValue, PredictionHistory
from app.services import games as games_service
from app.services.common import team_ref
from app.services.prediction_lifecycle import Freshness, FreshnessState, forecast, freshness

HISTORY_LIMIT = 20


def _release(ctx: Context) -> ActiveRelease | None:
    try:
        return active_release(ctx.session, ctx.state.artifacts_dir)
    except (ArtifactMismatch, LookupError, FileNotFoundError):
        return None


def _out(ctx: Context, row: Prediction, state: FreshnessState | None = None) -> PredictionOut:
    session = ctx.session
    values = session.scalars(
        select(PredictionValue).where(PredictionValue.prediction_id == row.id)
    ).all()
    order = list(PredictedStat)
    version = session.scalar(select(ModelRelease.version).where(ModelRelease.id == row.release_id))
    actuals = {
        e.stat.value: e.actual
        for e in session.scalars(
            select(PredictionEvaluation).where(PredictionEvaluation.prediction_id == row.id)
        )
    }
    state = state or freshness(session, row, ctx.now, _release(ctx))
    return PredictionOut(
        id=row.id,
        player_id=row.player_id,
        game_id=row.game_id,
        release_version=version or "",
        kind=row.kind.value,
        status=row.status.value,
        created_at=row.created_at,
        data_cutoff_at=row.data_cutoff_at,
        feature_schema_version=row.feature_schema_version,
        double_double_probability=row.double_double_probability,
        supersedes_prediction_id=row.supersedes_prediction_id,
        freshness=state.state.value,
        freshness_reason=state.reason,
        values=[
            PredictedValue(
                stat=v.stat.value,
                point=v.point,
                lower=v.lower,
                upper=v.upper,
                interval_level=float(v.interval_level),
            )  # fmt: skip
            for v in sorted(values, key=lambda v: order.index(v.stat))
        ],
        actuals=actuals or None,
        explanation=row.explanation,
    )


def create_prediction(ctx: Context, player_id: int, game_id: str) -> tuple[PredictionOut, bool]:
    """Returns the stored prediction and whether it was created by this call."""
    row, created = forecast(ctx.session, ctx.state.artifacts_dir, ctx.now, player_id, game_id)
    return _out(ctx, row, FreshnessState(Freshness.current) if created else None), created


def _row(ctx: Context, prediction_id: uuid.UUID) -> Prediction:
    row = ctx.session.get(Prediction, prediction_id)
    if row is None:
        raise not_found("prediction", prediction_id)
    return row


def get_prediction(ctx: Context, prediction_id: uuid.UUID) -> PredictionOut:
    return _out(ctx, _row(ctx, prediction_id))


def explanation(ctx: Context, prediction_id: uuid.UUID) -> PredictionExplanation:
    """The inputs a forecast received: highlighted averages and the full stored feature snapshot."""
    row = _row(ctx, prediction_id)
    stored = row.explanation or {}
    return PredictionExplanation(
        prediction_id=row.id,
        method=stored.get("method", "inputs"),
        inputs=stored.get("inputs", {}),
        context=stored.get("context", {}),
        features=row.feature_snapshot,
    )


def history(ctx: Context, player_id: int, game_id: str | None) -> list[PredictionOut]:
    """Newest first, superseded rows included, so every stored forecast stays visible."""
    query = select(Prediction).where(Prediction.player_id == player_id)
    if game_id:
        query = query.where(Prediction.game_id == game_id)
    rows = ctx.session.scalars(
        query.order_by(Prediction.created_at.desc()).limit(HISTORY_LIMIT)
    ).all()
    return [_out(ctx, r) for r in rows]


NOTABLE_RANK = 5  # league top or bottom five
NOTABLE_ABSENCE_PTS = 8.0
NOTES_PER_GAME = 2


def _ordinal(n: int) -> str:
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def _extreme(rank: int, teams: int, best: str, worst: str) -> str | None:
    if rank <= NOTABLE_RANK:
        return f"{best}" if rank == 1 else f"{_ordinal(rank)}-{best}"
    if rank > teams - NOTABLE_RANK:
        bottom = teams - rank + 1
        return f"{worst}" if bottom == 1 else f"{_ordinal(bottom)}-{worst}"
    return None


def _league_ranks(ctx: Context, season: str) -> dict[int, tuple[int, int, int]]:
    """Per team: defensive rating rank (1 = fewest points allowed per 100 possessions), pace rank
    (1 = fastest) and the number of teams ranked, from the source's season team stats."""
    rows = ctx.session.execute(
        select(TeamSeason.team_id, TeamSeason.def_rating, TeamSeason.pace)
        .join(Season, Season.id == TeamSeason.season_id)
        .where(Season.label == season, TeamSeason.def_rating.is_not(None))
    ).all()
    defense = sorted(rows, key=lambda r: r.def_rating)
    pace = sorted((r for r in rows if r.pace is not None), key=lambda r: -r.pace)
    n = len(rows)
    pace_rank = {r.team_id: i + 1 for i, r in enumerate(pace)}
    return {r.team_id: (i + 1, pace_rank.get(r.team_id, 0), n) for i, r in enumerate(defense)}


def _notes(snapshot: dict, opponent: str, ranks: tuple[int, int, int] | None) -> list[str]:
    """Plain-language reasons this game's forecast differs, most telling first. Only inputs the
    forecast read are used, so a note never claims something the model did not see."""
    notes: list[str] = []
    if snapshot.get("is_back_to_back") == 1:
        notes.append("Second night of a back-to-back")
    own_out, opp_out = snapshot.get("absent_pts") or 0, snapshot.get("opp_absent_pts") or 0
    if own_out >= NOTABLE_ABSENCE_PTS:
        notes.append(f"Teammates out who score about {round(own_out)} points a game")
    if opp_out >= NOTABLE_ABSENCE_PTS:
        notes.append(f"{opponent} missing about {round(opp_out)} points a game")
    if ranks is not None:
        defense, pace, teams = ranks
        if label := _extreme(defense, teams, "best defense", "worst defense"):
            notes.append(f"{opponent}: {label}")
        if pace and (label := _extreme(pace, teams, "fastest pace", "slowest pace")):
            notes.append(f"{opponent}: {label}")
    rest = snapshot.get("team_rest_days")
    if rest is not None and rest >= 3 and snapshot.get("is_back_to_back") != 1:
        notes.append(f"{round(rest)} days of rest")
    return notes[:NOTES_PER_GAME]


def upcoming(ctx: Context, player_id: int, days: int) -> list[UpcomingForecast]:
    """Forecasts for every game the player has in the next `days` days. Each stored forecast is
    reused while its inputs are unchanged, so repeating the call never duplicates rows."""
    player = ctx.session.get(Player, player_id)
    if player is None:
        raise not_found("player", player_id)
    out: list[UpcomingForecast] = []
    ranks: dict[str, dict[int, tuple[int, int, int]]] = {}
    for game in games_service.upcoming(ctx, days, player_id):
        try:
            row, _ = forecast(ctx.session, ctx.state.artifacts_dir, ctx.now, player_id, game.id)
        except ApiError as error:
            ctx.session.rollback()
            if error.status == 503 and error.code == "model_unavailable":
                raise
            reason = Unavailable(code=error.code, message=error.message)
            out.append(UpcomingForecast(game=game, prediction=None, unavailable=reason))
            continue
        current = FreshnessState(Freshness.current)
        home = game.home.team.id == player.current_team_id
        opponent = (game.away if home else game.home).team
        if game.season not in ranks:
            ranks[game.season] = _league_ranks(ctx, game.season)
        notes = _notes(row.feature_snapshot, opponent.name, ranks[game.season].get(opponent.id))
        out.append(
            UpcomingForecast(
                game=game, prediction=_out(ctx, row, current), unavailable=None, notes=notes
            )
        )
    return out


def explorer(ctx: Context, player_id: int, kind: PredictionKind, limit: int) -> PredictionHistory:
    """A player's stored predictions of one kind, newest game first, each next to the result."""
    player = ctx.session.get(Player, player_id)
    if player is None:
        raise not_found("player", player_id)
    newer = aliased(Prediction)  # a later forecast replacing this one
    team_in_game = (
        select(PlayerGameStats.team_id)
        .where(
            PlayerGameStats.game_id == Prediction.game_id,
            PlayerGameStats.player_id == Prediction.player_id,
        )  # fmt: skip
        .scalar_subquery()
    )
    rows = ctx.session.execute(
        select(Prediction, Game, ModelRelease.version, team_in_game)
        .join(Game, Game.id == Prediction.game_id)
        .join(ModelRelease, ModelRelease.id == Prediction.release_id)
        .where(
            Prediction.player_id == player_id,
            Prediction.kind == kind,
            ~exists().where(newer.supersedes_prediction_id == Prediction.id),
        )  # fmt: skip
        .order_by(Game.game_date.desc(), Prediction.created_at.desc())
        .limit(limit)
    ).all()
    ids = [r[0].id for r in rows]
    values = ctx.session.scalars(
        select(PredictionValue).where(PredictionValue.prediction_id.in_(ids))
    )
    evaluations = {
        (e.prediction_id, e.stat.value): e
        for e in ctx.session.scalars(
            select(PredictionEvaluation).where(PredictionEvaluation.prediction_id.in_(ids))
        )
    }
    by_prediction: dict[uuid.UUID, dict[str, HistoryValue]] = {}
    for v in values:
        e = evaluations.get((v.prediction_id, v.stat.value))
        by_prediction.setdefault(v.prediction_id, {})[v.stat.value] = HistoryValue(
            point=v.point, lower=v.lower, upper=v.upper,
            actual=e.actual if e else None, within_interval=e.within_interval if e else None,
        )  # fmt: skip
    teams = {t.id: t for t in ctx.session.scalars(select(Team))}
    entries = []
    for prediction, game, version, team_id in rows:
        own = team_id or player.current_team_id
        is_home = own == game.home_team_id
        opponent = teams[game.away_team_id if is_home else game.home_team_id]
        entries.append(
            HistoryEntry(
                prediction_id=str(prediction.id),
                kind=prediction.kind.value,
                release_version=version,
                game_id=game.id,
                game_date=game.game_date,
                opponent=team_ref(opponent),
                is_home=is_home,
                values=by_prediction.get(prediction.id, {}),
            )  # fmt: skip
        )
    return PredictionHistory(player_id=player_id, kind=kind.value, entries=entries)
