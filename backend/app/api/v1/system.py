from typing import Annotated

from fastapi import APIRouter, Depends, Response

from app.api.deps import ApiState, Ctx, get_state
from app.schemas.resources import DataStatus, Health, Readiness
from app.services import system

router = APIRouter(tags=["system"])

NO_STORE = {"Cache-Control": "no-store"}


@router.get("/health", response_model=Health)
def health(response: Response) -> Health:
    response.headers.update(NO_STORE)
    return Health(status="ok")


@router.get("/readiness", response_model=Readiness)
def readiness(state: Annotated[ApiState, Depends(get_state)], response: Response) -> Readiness:
    result = system.readiness(state)
    response.headers.update(NO_STORE)
    if result.status != "ready":
        response.status_code = 503
    return result


@router.get("/data-status", response_model=DataStatus)
def data_status(ctx: Ctx) -> DataStatus:
    return system.data_status(ctx)
