import asyncio

from fastapi import APIRouter, HTTPException, Query, Request

from app.ai.command.processor import CatalogueConfigurationError
from app.ai.speech.speech_recognizer import (
    SpeechRecognitionError,
    SpeechRecognitionUnavailableError,
)
from app.schemas.voice import CommandRequest, CommandResponse
from app.services.voice_service import (
    VoiceServiceDisabledError,
    VoiceServiceUnavailableError,
    voice_service,
)

router = APIRouter(prefix="/api/voice", tags=["AI command demo"])
_MAX_WAV_BYTES = 10 * 1024 * 1024


@router.get("/commands")
async def get_commands() -> list[dict[str, object]]:
    try:
        return voice_service.get_commands()
    except CatalogueConfigurationError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@router.get("/status")
async def get_voice_status() -> dict[str, object]:
    return voice_service.get_status()


@router.post("/start")
async def start_voice_listener() -> dict[str, object]:
    try:
        return await asyncio.to_thread(voice_service.start)
    except VoiceServiceDisabledError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except VoiceServiceUnavailableError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@router.post("/stop")
async def stop_voice_listener() -> dict[str, object]:
    try:
        return await asyncio.to_thread(voice_service.stop)
    except VoiceServiceUnavailableError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@router.get("/history")
async def get_voice_history(
    limit: int = Query(default=20, ge=1, le=100),
) -> list[dict[str, object]]:
    return voice_service.get_history(limit)


@router.get("/debug")
async def get_voice_debug_log(
    limit: int = Query(default=100, ge=1, le=200),
) -> list[dict[str, object]]:
    return voice_service.get_debug_log(limit)


@router.post("/process", response_model=CommandResponse)
async def process_command(request: CommandRequest) -> dict[str, object]:
    try:
        return await asyncio.to_thread(
            voice_service.process,
            request.text,
            execute=request.execute,
            request_id=request.request_id,
        )
    except CatalogueConfigurationError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@router.post("/transcribe")
async def transcribe_command(request: Request) -> dict[str, object]:
    content_type = request.headers.get("content-type", "").split(";", 1)[0].lower()
    if content_type not in {"audio/wav", "audio/x-wav"}:
        raise HTTPException(status_code=415, detail="Chỉ hỗ trợ audio/wav.")

    audio = bytearray()
    async for chunk in request.stream():
        audio.extend(chunk)
        if len(audio) > _MAX_WAV_BYTES:
            raise HTTPException(status_code=413, detail="Tệp WAV vượt quá 10 MB.")
    if len(audio) < 12 or audio[:4] != b"RIFF" or audio[8:12] != b"WAVE":
        raise HTTPException(status_code=400, detail="Nội dung gửi lên không phải WAV hợp lệ.")

    try:
        transcription = await asyncio.to_thread(
            voice_service.transcribe,
            bytes(audio),
        )
    except SpeechRecognitionUnavailableError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except SpeechRecognitionError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error

    command = voice_service.process(transcription["recognized_text"])
    return {
        **transcription,
        "command": command,
    }
