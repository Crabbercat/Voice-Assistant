from fastapi import APIRouter

from app.api.routes.devices import router as devices_router
from app.api.routes.health import router as health_router
from app.api.routes.dashboard import router as dashboard_router

router = APIRouter()
router.include_router(health_router)
router.include_router(devices_router)
router.include_router(dashboard_router)

