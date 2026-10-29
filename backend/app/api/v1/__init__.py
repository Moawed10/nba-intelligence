from fastapi import APIRouter

from app.api.errors import ERROR_RESPONSES
from app.api.v1 import games, insights, models, players, predictions, system, teams

router = APIRouter(prefix="/api/v1", responses=ERROR_RESPONSES)
for module in (players, teams, games, insights, models, predictions, system):
    router.include_router(module.router)
