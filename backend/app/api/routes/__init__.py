from fastapi import APIRouter

from . import dashboard, devices, health

router = APIRouter()
router.include_router(health.router)
router.include_router(devices.router)
router.include_router(dashboard.router)
