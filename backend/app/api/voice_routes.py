import asyncio

from fastapi import APIRouter, HTTPException
from fastapi import Request

from app.ai.command.processor import CatalogueConfigurationError
from app.ai.speech.speech_recognizer import (
    SpeechRecognitionError,
    SpeechRecognitionUnavailableError,
)
from app.schemas.voice import CommandRequest, CommandResponse
from app.services.voice_service import voice_service

router = APIRouter(prefix="/api/voice", tags=["AI command demo"])
_MAX_WAV_BYTES = 10 * 1024 * 1024


@router.get("/commands")
async def get_commands() -> list[dict[str, object]]:
    try:
        return voice_service.get_commands()
    except CatalogueConfigurationError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@router.post("/process", response_model=CommandResponse)
async def process_command(request: CommandRequest) -> dict[str, object]:
    try:
        return voice_service.process(request.text, execute=request.execute)
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
