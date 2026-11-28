
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.ai.tts.service import voice_response_service
from app.core.config import settings
from app.devices.l298n_fan import get_fan_device
from app.devices.registry import device_registry

router = APIRouter(
    prefix="/devices/fan",
    tags=["Fan"],
)


class FanSpeedRequest(BaseModel):
    level: int = Field(ge=0, le=3, strict=True)


def get_fan():
    if settings.MOCK_HARDWARE:
        fan = device_registry.get("fan")
        if fan is None or not callable(getattr(fan, "set_level", None)):
            raise HTTPException(status_code=503, detail="Fan device is unavailable.")
        return fan

    return get_fan_device()


@router.get("/speed")
def get_speed():
    return get_fan().get_status()


@router.post("/speed")
def set_speed(data: FanSpeedRequest):
    fan = get_fan()
    was_on = bool(fan.get_status().get("is_on"))
    set_level = getattr(fan, "set_level", None)
    if not callable(set_level):
        raise HTTPException(status_code=503, detail="Fan speed control is unavailable.")
    try:
        set_level(data.level)
    except Exception as error:
        response = voice_response_service.respond_to_device(
            "fan",
            data.level > 0,
            success=False,
            error=str(error),
        )
        raise HTTPException(
            status_code=503,
            detail={
                "message": "Fan operation failed.",
                "voice_response": response.model_dump(mode="json"),
            },
        ) from error
    status = fan.get_status()
    is_on = bool(status.get("is_on"))
    response = None
    if was_on != is_on:
        response = voice_response_service.respond_to_device(
            "fan",
            is_on,
            success=True,
            operation_result=status,
        )
    return {
        **status,
        "voice_response": response.model_dump(mode="json") if response else None,
    }
