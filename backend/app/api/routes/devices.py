from fastapi import APIRouter, HTTPException

from app.schemas.device import DeviceStateRequest
from app.services.device_service import device_service

router = APIRouter(prefix="/devices", tags=["Devices"])


@router.get("")
@router.get("/")
async def get_devices() -> list[dict[str, object]]:
    return device_service.get_devices()


@router.post("/{device_id}/state")
async def update_device_state(device_id: str, request: DeviceStateRequest) -> dict[str, object]:
    try:
        return device_service.set_device_state(device_id, request.is_on)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
