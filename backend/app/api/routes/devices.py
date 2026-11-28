import asyncio
import logging

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import JSONResponse

from app.schemas.device import DeviceStateRequest
from app.services.device_service import device_service
from app.ai.tts.service import voice_response_service

router = APIRouter(prefix="/devices", tags=["Devices"])
logger = logging.getLogger(__name__)


@router.get("")
@router.get("/")
async def get_devices() -> list[dict[str, object]]:
    return device_service.get_devices()


@router.post("/state/all")
async def update_all_device_states(
    request: DeviceStateRequest,
    request_id: str | None = Header(default=None, alias="X-Request-ID"),
) -> dict[str, object]:
    result = await asyncio.to_thread(
        device_service.set_all_device_states,
        request.is_on,
    )
    voice_response = await asyncio.to_thread(
        voice_response_service.respond_to_bulk_operation,
        is_on=request.is_on,
        results=result["results"],
        request_id=request_id,
    )
    return {**result, "voice_response": voice_response.model_dump(mode="json")}


@router.post("/{device_id}/state", response_model=None)
async def update_device_state(
    device_id: str,
    request: DeviceStateRequest,
    request_id: str | None = Header(default=None, alias="X-Request-ID"),
) -> dict[str, object] | JSONResponse:
    try:
        result = await asyncio.to_thread(
            device_service.set_device_state,
            device_id,
            request.is_on,
        )
    except ValueError as error:
        voice_response = await asyncio.to_thread(
            voice_response_service.respond_to_device,
            device_id,
            request.is_on,
            success=False,
            request_id=request_id,
            error=str(error),
        )
        return JSONResponse(
            status_code=404,
            content={
                "detail": str(error),
                "voice_response": voice_response.model_dump(mode="json"),
            },
        )
    except Exception:
        logger.exception("Device operation failed for %s", device_id)
        voice_response = await asyncio.to_thread(
            voice_response_service.respond_to_device,
            device_id,
            request.is_on,
            success=False,
            request_id=request_id,
        )
        return JSONResponse(
            status_code=500,
            content={
                "detail": "Device operation failed.",
                "voice_response": voice_response.model_dump(mode="json"),
            },
        )

    succeeded = result.get("is_on") is request.is_on
    voice_response = await asyncio.to_thread(
        voice_response_service.respond_to_device,
        device_id,
        request.is_on,
        success=succeeded,
        request_id=request_id,
        operation_result=result,
    )
    if not succeeded:
        return JSONResponse(
            status_code=502,
            content={
                "detail": "Device did not reach the requested state.",
                "device": result,
                "voice_response": voice_response.model_dump(mode="json"),
            },
        )
    return {
        **result,
        "voice_response": voice_response.model_dump(mode="json"),
    }
