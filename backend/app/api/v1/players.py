from datetime import date
from typing import Annotated

from fastapi import APIRouter, Path, Query
from fastapi.responses import FileResponse

from app.api.deps import Ctx
from app.api.errors import ApiError, not_found
from app.models import Player, SeasonType
from app.schemas.common import Page
from app.schemas.resources import (
    DirectoryPlayer,
    PlayerGameLine,
    PlayerProfile,
    PlayerSearchResult,
    PlayerSeasonStats,
    PlayerTrends,
    TrendStat,
)
from app.services import players
from app.services.common import LIMIT_DEFAULT, LIMIT_MAX
from app.services.photos import PhotoSourceError

router = APIRouter(prefix="/players", tags=["players"])

PlayerId = Annotated[int, Path(ge=1, le=2_147_483_647)]
SeasonLabel = Annotated[str | None, Query(pattern=r"^\d{4}-\d{2}$")]
Limit = Annotated[int, Query(ge=1, le=LIMIT_MAX)]
Offset = Annotated[int, Query(ge=0, le=100_000)]


@router.get("", response_model=Page[DirectoryPlayer])
def list_players(
    ctx: Ctx,
    team_id: int | None = None,
    position: Annotated[str | None, Query(max_length=16)] = None,
    active: bool | None = None,
    season: SeasonLabel = None,
    sort: players.PlayerSort = "full_name",
    limit: Limit = LIMIT_DEFAULT,
    offset: Offset = 0,
) -> Page[DirectoryPlayer]:
    ctx.cache_for(300)
    return players.list_players(
        ctx, team_id=team_id, position=position, active=active, season=season,
        sort=sort, limit=limit, offset=offset,
    )  # fmt: skip


@router.get("/search", response_model=list[PlayerSearchResult])
def search_players(
    ctx: Ctx,
    q: Annotated[str, Query(min_length=2, max_length=64)],
    limit: Annotated[int, Query(ge=1, le=20)] = 10,
) -> list[PlayerSearchResult]:
    ctx.cache_for(300)
    return players.search_players(ctx, q, limit)


@router.get("/{player_id}", response_model=PlayerProfile)
def get_player(ctx: Ctx, player_id: PlayerId) -> PlayerProfile:
    ctx.cache_for(300)
    return players.profile(ctx, player_id)


@router.get(
    "/{player_id}/photo",
    response_class=FileResponse,
    responses={200: {"content": {"image/png": {}}, "description": "The player's photo"}},
)
def get_player_photo(ctx: Ctx, player_id: PlayerId) -> FileResponse:
    """Copied once from the NBA's image server and then served locally; 404 when none exists."""
    if ctx.session.get(Player, player_id) is None:
        raise not_found("player", player_id)
    try:
        path = ctx.state.photos.path(player_id)
    except PhotoSourceError:
        raise ApiError(503, "photo_unavailable", "The photo service is unavailable.") from None
    if path is None:
        raise ApiError(404, "photo_not_found", "No photo is available for this player.")
    return FileResponse(
        path, media_type="image/png", headers={"Cache-Control": "public, max-age=604800"}
    )


@router.get("/{player_id}/stats", response_model=PlayerSeasonStats)
def get_player_stats(
    ctx: Ctx,
    player_id: PlayerId,
    season_type: SeasonType = SeasonType.regular,
    season: SeasonLabel = None,
) -> PlayerSeasonStats:
    ctx.cache_for(300)
    return players.season_stats(ctx, player_id, season_type, season)


@router.get("/{player_id}/games", response_model=Page[PlayerGameLine])
def get_player_games(
    ctx: Ctx,
    player_id: PlayerId,
    season: SeasonLabel = None,
    season_type: SeasonType | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    sort: players.GameLogSort = "-game_date",
    limit: Limit = LIMIT_DEFAULT,
    offset: Offset = 0,
) -> Page[PlayerGameLine]:
    ctx.cache_for(300)
    return players.game_log(
        ctx, player_id, season=season, season_type=season_type, date_from=date_from,
        date_to=date_to, sort=sort, limit=limit, offset=offset,
    )  # fmt: skip


@router.get("/{player_id}/trends", response_model=PlayerTrends)
def get_player_trends(
    ctx: Ctx,
    player_id: PlayerId,
    stat: TrendStat = "pts",
    season: SeasonLabel = None,
    season_type: SeasonType | None = None,
) -> PlayerTrends:
    ctx.cache_for(300)
    return players.trends(ctx, player_id, stat, season, season_type)
