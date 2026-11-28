import logging
import re
import threading
from typing import Any, Callable

from app.core.config import settings

logger = logging.getLogger(__name__)


class TTSUnavailableError(RuntimeError):
    """Raised when a local Vietnamese TTS engine or voice is unavailable."""


class LocalVietnameseTTS:
    def __init__(
        self,
        engine_factory: Callable[[], Any] | None = None,
        voice_name: str | None = None,
        rate: float | None = None,
    ) -> None:
        self._engine_factory = engine_factory
        self.voice_name = (
            settings.VOICE_TTS_VOICE if voice_name is None else voice_name
        )
        self.rate = settings.VOICE_TTS_RATE if rate is None else rate
        self._engine: Any | None = None
        self._lock = threading.Lock()

    @staticmethod
    def _is_vietnamese_voice(voice: Any) -> bool:
        values = [getattr(voice, "id", ""), getattr(voice, "name", "")]
        languages = getattr(voice, "languages", [])
        if isinstance(languages, (list, tuple)):
            values.extend(languages)
        for value in values:
            if isinstance(value, bytes):
                text = value.decode("latin-1", errors="ignore").lower()
            else:
                text = str(value).lower()
            compact = re.sub(r"[^a-z]", "", text)
            if (
                text.strip() in {"vi", "vi-vn", "vi_vn"}
                or "vietnam" in text
                or "vi-vn" in text
                or "vi_vn" in text
                or "vivn" in compact
            ):
                return True
        return False

    def _create_engine(self) -> Any:
        if self._engine_factory is not None:
            try:
                return self._engine_factory()
            except Exception as error:
                raise TTSUnavailableError(
                    "Could not initialize the local speech engine."
                ) from error
        try:
            import pyttsx3
        except ImportError as error:
            raise TTSUnavailableError(
                "Install local TTS with "
                "'pip install -r backend/requirements/tts.txt'."
            ) from error
        try:
            return pyttsx3.init()
        except Exception as error:
            raise TTSUnavailableError(
                "Could not initialize the local speech engine."
            ) from error

    def _get_engine(self) -> Any:
        if self._engine is not None:
            return self._engine

        engine = self._create_engine()
        try:
            voices = engine.getProperty("voices") or []
        except Exception as error:
            raise TTSUnavailableError(
                "Could not inspect voices in the local speech engine."
            ) from error

        if self.voice_name:
            selected = next(
                (
                    voice
                    for voice in voices
                    if self.voice_name in {
                        str(getattr(voice, "id", "")),
                        str(getattr(voice, "name", "")),
                    }
                    and self._is_vietnamese_voice(voice)
                ),
                None,
            )
        else:
            selected = next(
                (voice for voice in voices if self._is_vietnamese_voice(voice)),
                None,
            )

        if selected is None:
            raise TTSUnavailableError(
                "No Vietnamese voice is available. Install a vi-VN system voice "
                "and optionally set VOICE_TTS_VOICE to its exact name or ID."
            )

        try:
            engine.setProperty("voice", selected.id)
            self._engine = engine
        except Exception as error:
            raise TTSUnavailableError(
                "Could not select the configured Vietnamese voice."
            ) from error
        return engine

    def check_available(self) -> bool:
        with self._lock:
            self._get_engine()
        return True

    def speak(self, text: str) -> None:
        if not text.strip():
            raise ValueError("TTS text cannot be empty.")
        with self._lock:
            engine = self._get_engine()
            try:
                engine.setProperty("rate", round(200 * self.rate))
                engine.say(text)
                engine.runAndWait()
            except Exception as error:
                logger.exception("Local Vietnamese TTS playback failed")
                raise TTSUnavailableError(
                    "The local Vietnamese speech engine could not play audio."
                ) from error
