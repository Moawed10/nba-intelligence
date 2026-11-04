from typing import Annotated

from fastapi import APIRouter, Path, Query

from app.api.deps import Ctx
from app.models import SeasonType
from app.schemas.resources import (
    FanPosts,
    HomeCourt,
    Team,
    TeamDetail,
    TeamHistory,
    TeamSeasonStats,
)
from app.services import teams

router = APIRouter(prefix="/teams", tags=["teams"])

TeamId = Annotated[int, Path(ge=1, le=2_147_483_647)]
SeasonLabel = Annotated[str | None, Query(pattern=r"^\d{4}-\d{2}$")]


@router.get("", response_model=list[Team])
def list_teams(ctx: Ctx) -> list[Team]:
    ctx.always_revalidate()
    return teams.list_teams(ctx)


@router.get("/{team_id}", response_model=TeamDetail)
def get_team(ctx: Ctx, team_id: TeamId, season: SeasonLabel = None) -> TeamDetail:
    ctx.always_revalidate()
    return teams.team_detail(ctx, team_id, season)


@router.get("/{team_id}/stats", response_model=TeamSeasonStats)
def get_team_stats(
    ctx: Ctx,
    team_id: TeamId,
    season: SeasonLabel = None,
    season_type: SeasonType = SeasonType.regular,
) -> TeamSeasonStats:
    ctx.always_revalidate()
    return teams.team_stats(ctx, team_id, season, season_type)


@router.get("/{team_id}/home-court", response_model=HomeCourt)
def get_home_court(ctx: Ctx, team_id: TeamId, season: SeasonLabel = None) -> HomeCourt:
    ctx.always_revalidate()
    return teams.home_court(ctx, team_id, season)


@router.get("/{team_id}/fan-posts", response_model=FanPosts)
def get_fan_posts(ctx: Ctx, team_id: TeamId) -> FanPosts:
    ctx.always_revalidate()
    return teams.fan_posts(ctx, team_id)


@router.get("/{team_id}/history", response_model=TeamHistory)
def get_team_history(ctx: Ctx, team_id: TeamId) -> TeamHistory:
    ctx.always_revalidate()
    return teams.team_history(ctx, team_id)
