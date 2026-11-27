from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "VietHome AI"
    APP_VERSION: str = "0.1.0"
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = True
    MOCK_HARDWARE: bool = True
    AUDIO_SAMPLE_RATE: int = Field(default=16000, gt=0)
    AUDIO_CHANNELS: int = 1
    AUDIO_INPUT_DEVICE: str | None = None
    AUDIO_BLOCK_SECONDS: float = Field(default=0.25, gt=0, le=2)
    AUDIO_SILENCE_THRESHOLD: float = Field(default=0.005, gt=0, le=1)
    WAKE_WORDS: str = "hey berry,hey barry,hey beri,hey very,hey be ri"
    WAKE_CHUNK_SECONDS: float = Field(default=3.0, gt=0, le=10)
    WAKE_DETECTION_INTERVAL_SECONDS: float = Field(default=1.0, gt=0, le=10)
    WAKE_WORD_COOLDOWN_SECONDS: float = Field(default=2.0, ge=0, le=30)
    COMMAND_SILENCE_DURATION: float = Field(default=1.2, gt=0, le=10)
    COMMAND_MIN_DURATION: float = Field(default=0.4, gt=0, le=10)
    COMMAND_START_TIMEOUT_SECONDS: float = Field(default=5.0, gt=0, le=60)
    COMMAND_MAX_DURATION: float = Field(default=15.0, gt=0, le=120)
    VOICE_ENABLED: bool = False
    VOICE_AUTO_START: bool = False
    VOICE_AUTO_EXECUTE: bool = False
    VOICE_HISTORY_LIMIT: int = Field(default=50, ge=1, le=500)
    COMMAND_CATALOG_PATH: str = "hardware/configs/commands.json"
    DATABASE_URL: str = "sqlite+aiosqlite:///./viethome.db"
    API_PREFIX: str = "/api/v1"
    COMMAND_SIMILARITY_THRESHOLD: float = Field(default=80, ge=0, le=100)
    STT_MODEL: str = "tiny"
    STT_DEVICE: str = "cpu"
    STT_COMPUTE_TYPE: str = "int8"
    STT_LANGUAGE: str = "en"
    STT_BEAM_SIZE: int = Field(default=1, ge=1, le=5)
    STT_VAD_FILTER: bool = False
    STT_MODEL_CACHE_DIR: str = "models/whisper"

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[2] / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def app_name(self) -> str:
        return self.APP_NAME

    @property
    def app_version(self) -> str:
        return self.APP_VERSION

    @property
    def api_prefix(self) -> str:
        return self.API_PREFIX

    @property
    def debug(self) -> bool:
        return self.DEBUG

    @property
    def host(self) -> str:
        return self.HOST

    @property
    def port(self) -> int:
        return self.PORT


settings = Settings()

