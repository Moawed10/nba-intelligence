from datetime import date
from typing import Annotated

from fastapi import APIRouter, Path, Query

from app.api.deps import Ctx
from app.models import GameStatus, SeasonType
from app.schemas.common import Page
from app.schemas.resources import BoxScore, GameDetail, GameSummary
from app.services import games
from app.services.common import LIMIT_DEFAULT, LIMIT_MAX

router = APIRouter(prefix="/games", tags=["games"])

GameId = Annotated[str, Path(pattern=r"^\d{10}$")]


@router.get("", response_model=Page[GameSummary])
def list_games(
    ctx: Ctx,
    date_from: date | None = None,
    date_to: date | None = None,
    team_id: int | None = None,
    status: GameStatus | None = None,
    season_type: SeasonType | None = None,
    limit: Annotated[int, Query(ge=1, le=LIMIT_MAX)] = LIMIT_DEFAULT,
    offset: Annotated[int, Query(ge=0, le=10_000)] = 0,
) -> Page[GameSummary]:
    ctx.cache_for(60)
    return games.list_games(
        ctx, date_from=date_from, date_to=date_to, team_id=team_id, status=status,
        season_type=season_type, limit=limit, offset=offset,
    )  # fmt: skip


@router.get("/upcoming", response_model=list[GameSummary])
def upcoming_games(
    ctx: Ctx,
    days: Annotated[int, Query(ge=0, le=14)] = 7,
    player_id: Annotated[int | None, Query(ge=1)] = None,
) -> list[GameSummary]:
    ctx.cache_for(300)
    return games.upcoming(ctx, days, player_id)


@router.get("/{game_id}", response_model=GameDetail)
def get_game(ctx: Ctx, game_id: GameId) -> GameDetail:
    return games.game_detail(ctx, game_id)


@router.get("/{game_id}/boxscore", response_model=BoxScore)
def get_boxscore(ctx: Ctx, game_id: GameId) -> BoxScore:
    return games.boxscore(ctx, game_id)
