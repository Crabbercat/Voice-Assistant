import asyncio

from fastapi import APIRouter, Header, HTTPException

from app.ai.tts.providers.static_audio import StaticAudioError, UnknownResponseKey
from app.ai.tts.schemas import VoiceResponseResult, VoiceResponseStatus
from app.ai.tts.service import SensorRequest, voice_response_service

router = APIRouter(prefix="/api/voice/response", tags=["Voice responses"])


@router.get("/status", response_model=VoiceResponseStatus)
async def get_voice_response_status() -> VoiceResponseStatus:
    return await asyncio.to_thread(voice_response_service.get_status, True)


@router.post("/play/{response_key}", response_model=VoiceResponseResult)
async def play_static_response(
    response_key: str,
    request_id: str | None = Header(default=None, alias="X-Request-ID"),
) -> VoiceResponseResult:
    try:
        return await asyncio.to_thread(
            voice_response_service.play_static,
            response_key,
            request_id,
        )
    except UnknownResponseKey as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except StaticAudioError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@router.post("/sensors/temperature", response_model=VoiceResponseResult)
async def speak_temperature(
    request_id: str | None = Header(default=None, alias="X-Request-ID"),
) -> VoiceResponseResult:
    return await asyncio.to_thread(
        voice_response_service.respond_to_sensor,
        "temperature",
        request_id,
    )


@router.post("/sensors/humidity", response_model=VoiceResponseResult)
async def speak_humidity(
    request_id: str | None = Header(default=None, alias="X-Request-ID"),
) -> VoiceResponseResult:
    return await asyncio.to_thread(
        voice_response_service.respond_to_sensor,
        "humidity",
        request_id,
    )


@router.post("/sensors/summary", response_model=VoiceResponseResult)
async def speak_sensor_summary(
    request_id: str | None = Header(default=None, alias="X-Request-ID"),
) -> VoiceResponseResult:
    return await asyncio.to_thread(
        voice_response_service.respond_to_sensor,
        "summary",
        request_id,
    )
