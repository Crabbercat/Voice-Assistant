from fastapi import APIRouter

from . import devices, health

router = APIRouter()
router.include_router(health.router)
router.include_router(devices.router)
