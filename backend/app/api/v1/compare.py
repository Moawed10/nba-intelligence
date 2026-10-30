from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import Ctx
from app.schemas.resources import PlayerComparison
from app.services import compare

router = APIRouter(prefix="/compare", tags=["compare"])

PlayerParam = Annotated[int, Query(ge=1, le=2_147_483_647)]


@router.get("/players", response_model=PlayerComparison)
def compare_players(
    ctx: Ctx,
    p1: PlayerParam,
    p2: PlayerParam,
    season: Annotated[str | None, Query(pattern=r"^\d{4}-\d{2}$")] = None,
) -> PlayerComparison:
    """Two players in one regular season with league percentiles. Without a season, the latest
    regular season in which both played at least 10 games (or their latest shared one)."""
    ctx.cache_for(300)
    return compare.compare(ctx, p1, p2, season)
