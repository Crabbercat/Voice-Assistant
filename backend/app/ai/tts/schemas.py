from typing import Any, Literal

from pydantic import BaseModel


class VoiceResponseResult(BaseModel):
    request_id: str
    status: Literal["played", "unavailable", "failed", "disabled", "duplicate"]
    response_mode: Literal["static", "tts", "none"]
    response_key: str | None = None
    text: str | None = None
    audio_played: bool = False
    audio_path: str | None = None
    error: str | None = None
    data: dict[str, Any] | None = None


class VoiceResponseStatus(BaseModel):
    enabled: bool
    playback_mode: str
    is_playing: bool
    static_response_keys: list[str]
    missing_static_assets: list[str]
    audio_output_available: bool | None
    tts_enabled: bool
    tts_provider: str
    tts_available: bool | None
    tts_error: str | None = None
