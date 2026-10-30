from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import Ctx
from app.schemas.resources import Leaders, LeaderStat, Overview, Standouts
from app.services import insights

router = APIRouter(tags=["insights"])

SeasonLabel = Annotated[str | None, Query(pattern=r"^\d{4}-\d{2}$")]


@router.get("/overview", response_model=Overview)
def get_overview(ctx: Ctx) -> Overview:
    ctx.always_revalidate()
    return insights.overview(ctx)


@router.get("/leaders", response_model=Leaders)
def get_leaders(
    ctx: Ctx,
    stat: LeaderStat = "pts",
    season: SeasonLabel = None,
    limit: Annotated[int, Query(ge=1, le=25)] = 10,
    team_id: Annotated[int | None, Query(ge=1)] = None,
) -> Leaders:
    """League leaders per game; with `team_id`, the leaders on that team's current roster."""
    ctx.always_revalidate()
    return insights.leaders(ctx, stat, season, limit, team_id)


@router.get("/standouts", response_model=Standouts)
def get_standouts(ctx: Ctx, limit: Annotated[int, Query(ge=1, le=25)] = 8) -> Standouts:
    ctx.always_revalidate()
    return insights.standouts(ctx, limit)
