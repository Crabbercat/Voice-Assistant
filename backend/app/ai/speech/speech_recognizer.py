import io
import logging
import threading
from pathlib import Path
from typing import Any, Callable

from app.core.config import settings

logger = logging.getLogger(__name__)


class SpeechRecognitionUnavailableError(RuntimeError):
    """Raised when optional Faster-Whisper dependencies are unavailable."""


class SpeechRecognitionError(RuntimeError):
    """Raised when the model cannot load or transcribe audio."""


class SpeechRecognizer:
    def __init__(self, model_factory: Callable[..., Any] | None = None) -> None:
        self._model_factory = model_factory
        self._model: Any | None = None
        self._load_error: Exception | None = None
        self._model_lock = threading.Lock()
        self._inference_lock = threading.Lock()

    @property
    def is_loaded(self) -> bool:
        with self._model_lock:
            return self._model is not None

    def load(self) -> None:
        with self._inference_lock:
            self._get_model()

    def unload(self) -> None:
        with self._inference_lock:
            with self._model_lock:
                self._model = None
                self._load_error = None

    def _get_model(self) -> Any:
        if self._model is not None:
            return self._model
        if self._load_error is not None:
            raise self._load_error
        with self._model_lock:
            if self._model is not None:
                return self._model
            if self._load_error is not None:
                raise self._load_error
            factory = self._model_factory
            if factory is None:
                try:
                    from faster_whisper import WhisperModel
                except ImportError as error:
                    self._load_error = SpeechRecognitionUnavailableError(
                        "Cài Faster-Whisper bằng "
                        "'pip install -r backend/requirements/stt.txt'."
                    )
                    raise self._load_error from error
                factory = WhisperModel

            project_root = Path(__file__).resolve().parents[4]
            cache_path = Path(settings.STT_MODEL_CACHE_DIR)
            if not cache_path.is_absolute():
                cache_path = project_root / cache_path
            try:
                cache_path.mkdir(parents=True, exist_ok=True)
                self._model = factory(
                    settings.STT_MODEL,
                    device=settings.STT_DEVICE,
                    compute_type=settings.STT_COMPUTE_TYPE,
                    download_root=str(cache_path),
                )
            except Exception as error:
                logger.exception("Could not load Faster-Whisper model")
                self._load_error = SpeechRecognitionError(
                    f"Không tải được model STT '{settings.STT_MODEL}': {error}"
                )
                raise self._load_error from error
            return self._model

    def transcribe(self, audio: bytes) -> dict[str, Any]:
        if len(audio) < 12 or audio[:4] != b"RIFF" or audio[8:12] != b"WAVE":
            raise ValueError("Chỉ chấp nhận tệp WAV hợp lệ.")

        return self._transcribe_input(io.BytesIO(audio))

    def transcribe_samples(
        self,
        audio: Any,
        sample_rate: int,
    ) -> dict[str, Any]:
        if sample_rate <= 0:
            raise ValueError("Sample rate must be positive.")

        try:
            import numpy as np
        except ImportError as error:
            raise SpeechRecognitionUnavailableError(
                "Cài numpy bằng 'pip install -r backend/requirements/voice.txt'."
            ) from error

        samples = np.asarray(audio, dtype=np.float32).reshape(-1)
        if samples.size == 0:
            return {
                "recognized_text": "",
                "language": None,
                "language_probability": None,
                "duration_seconds": 0.0,
            }

        duration_seconds = samples.size / sample_rate
        if sample_rate != 16000:
            try:
                from scipy.signal import resample_poly
            except ImportError as error:
                raise SpeechRecognitionUnavailableError(
                    "Cài scipy để đổi sample rate microphone: "
                    "'pip install -r backend/requirements/voice.txt'."
                ) from error
            import math

            divisor = math.gcd(sample_rate, 16000)
            samples = resample_poly(
                samples,
                16000 // divisor,
                sample_rate // divisor,
            ).astype(np.float32)

        return self._transcribe_input(samples, duration_seconds)

    def _transcribe_input(
        self,
        audio: Any,
        duration_seconds: float | None = None,
    ) -> dict[str, Any]:
        try:
            with self._inference_lock:
                model = self._get_model()
                segments, info = model.transcribe(
                    audio,
                    language=settings.STT_LANGUAGE,
                    beam_size=settings.STT_BEAM_SIZE,
                    vad_filter=settings.STT_VAD_FILTER,
                    condition_on_previous_text=False,
                )
                transcript = " ".join(
                    segment.text.strip()
                    for segment in segments
                    if segment.text.strip()
                ).strip()
        except (SpeechRecognitionUnavailableError, SpeechRecognitionError):
            raise
        except Exception as error:
            logger.exception("Faster-Whisper transcription failed")
            raise SpeechRecognitionError(
                f"Không nhận diện được âm thanh: {error}"
            ) from error

        return {
            "recognized_text": transcript,
            "language": getattr(info, "language", None),
            "language_probability": getattr(info, "language_probability", None),
            "duration_seconds": getattr(info, "duration", duration_seconds),
        }
