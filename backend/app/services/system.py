from sqlalchemy import func, select, text
from sqlalchemy.exc import SQLAlchemyError

from app.api.deps import ApiState, Context
from app.models import Game, GameStatus, Player, PlayerGameStats, Season, Team, TeamGameStats
from app.schemas.resources import DatasetStatus, DataStatus, Readiness, SeasonCoverage
from app.sync.freshness import dataset_freshness

DATA_STATUS_TTL = 60
NOT_REMAINING = (GameStatus.final, GameStatus.cancelled)


def readiness(state: ApiState) -> Readiness:
    try:
        with state.engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        database = "ok"
    except SQLAlchemyError:
        database = "unavailable"
    return Readiness(
        status="ready" if database == "ok" else "not_ready",
        checks={"database": database, "model": "not_configured"},
    )


def data_status(ctx: Context) -> DataStatus:
    def compute() -> DataStatus:
        session = ctx.session
        games = session.execute(
            select(
                Season.label,
                func.count().filter(Game.status == GameStatus.final),
                func.count().filter(Game.status.not_in(NOT_REMAINING)),
            )
            .join(Game, Game.season_id == Season.id)
            .group_by(Season.id)
            .order_by(Season.id.desc())
        ).all()
        lines = dict(
            session.execute(
                select(Game.season_id, func.count())
                .join(PlayerGameStats, PlayerGameStats.game_id == Game.id)
                .group_by(Game.season_id)
            ).all()
        )
        season_ids = dict(session.execute(select(Season.label, Season.id)).all())
        counts = {
            name: session.scalar(select(func.count()).select_from(model)) or 0
            for name, model in (("games", Game), ("players", Player), ("teams", Team),
                                ("team_game_lines", TeamGameStats),
                                ("player_game_lines", PlayerGameStats))
        }  # fmt: skip
        return DataStatus(
            generated_at=ctx.now,
            data_version=ctx.data_version,
            datasets=[
                DatasetStatus(**d.as_dict()) for d in dataset_freshness(session, ctx.now)
            ],
            seasons=[
                SeasonCoverage(
                    season=label, final_games=final, remaining_games=remaining,
                    player_lines=lines.get(season_ids[label], 0),
                )
                for label, final, remaining in games
            ],
            row_counts=counts,
        )  # fmt: skip

    ctx.cache_for(DATA_STATUS_TTL)
    return ctx.cached("data_status", DATA_STATUS_TTL, None, compute)
