from typing import Annotated, Literal

from fastapi import APIRouter, Path

from app.api.deps import Ctx
from app.models.predictions import PredictedStat
from app.schemas.resources import (
    LiveAccuracy,
    ModelAnalytics,
    ModelReleaseDetail,
    ModelReleaseSummary,
)
from app.services import registry

router = APIRouter(prefix="/models", tags=["models"])


@router.get("", response_model=list[ModelReleaseSummary])
def list_models(ctx: Ctx) -> list[ModelReleaseSummary]:
    ctx.cache_for(300)
    return registry.list_releases(ctx)


@router.get("/{version}", response_model=ModelReleaseDetail)
def get_model(
    ctx: Ctx, version: Annotated[str, Path(pattern=r"^\d{4}\.\d{2}\.\d{2}-\d{1,3}$")]
) -> ModelReleaseDetail:
    ctx.cache_for(300)
    return registry.release_detail(ctx, version)


@router.get("/{version}/live", response_model=LiveAccuracy)
def get_live_accuracy(
    ctx: Ctx, version: Annotated[str, Path(pattern=r"^\d{4}\.\d{2}\.\d{2}-\d{1,3}$")]
) -> LiveAccuracy:
    ctx.cache_for(120)
    return registry.live(ctx, version)


@router.get("/{version}/analytics", response_model=ModelAnalytics)
def get_analytics(
    ctx: Ctx,
    version: Annotated[str, Path(pattern=r"^\d{4}\.\d{2}\.\d{2}-\d{1,3}$")],
    stat: PredictedStat = PredictedStat.pts,
    kind: Literal["backtest", "pregame"] = "backtest",
) -> ModelAnalytics:
    """Stored predictions scored against box scores: predicted vs actual by tenth, the spread of
    misses, and interval coverage per predicted-minutes bin."""
    ctx.cache_for(300)
    return registry.analytics(ctx, version, stat.value, kind)
