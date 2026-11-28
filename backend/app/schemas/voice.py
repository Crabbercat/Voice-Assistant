from typing import Any

from pydantic import BaseModel, Field

from app.ai.tts.schemas import VoiceResponseResult


class CommandRequest(BaseModel):
    text: str = Field(min_length=1, max_length=500)
    execute: bool = False
    request_id: str | None = Field(default=None, min_length=1, max_length=128)


class CommandResponse(BaseModel):
    accepted: bool
    reason: str
    recognized_text: str
    normalized_text: str
    command_id: str | None = None
    intent: str | None = None
    action: str | None = None
    device_type: str | None = None
    target: str | None = None
    device_id: str | None = None
    confidence: float | None = None
    threshold: float
    execution_status: str
    message: str
    execution: dict[str, Any] | None = None
    voice_response: VoiceResponseResult | None = None
