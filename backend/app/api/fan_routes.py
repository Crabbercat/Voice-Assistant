
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.config import settings
from app.devices.l298n_fan import get_fan_device

router = APIRouter(
    prefix="/devices/fan",
    tags=["Fan"],
)


class FanSpeedRequest(BaseModel):
    level: int = Field(ge=0, le=3, strict=True)


def get_fan():
    if settings.MOCK_HARDWARE:
        raise HTTPException(
            status_code=503,
            detail="Hardware mode is disabled",
        )

    return get_fan_device()


@router.get("/speed")
def get_speed():
    return get_fan().get_status()


@router.post("/speed")
def set_speed(data: FanSpeedRequest):
    fan = get_fan()
    fan.set_level(data.level)
    return fan.get_status()
