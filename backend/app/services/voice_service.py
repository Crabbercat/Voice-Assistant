import logging
import math
import queue
import threading
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from app.ai.command.processor import (
    CatalogueConfigurationError,
    CommandProcessor,
    RapidFuzzUnavailableError,
)
from app.ai.speech.microphone_capture import (
    MicrophoneCapture,
)
from app.ai.speech.speech_recognizer import (
    SpeechRecognitionError,
    SpeechRecognizer,
)
from app.ai.speech.wake_word_detector import WakeWordDetector
from app.ai.tts.service import VoiceResponseService, voice_response_service
from app.core.config import settings
from app.devices.registry import DeviceRegistry, device_registry
from app.services.device_service import DeviceService, device_service

logger = logging.getLogger(__name__)

_REASONS = {
    "MATCH_ACCEPTED": "Đã nhận diện lệnh. Vui lòng xác nhận để thực thi.",
    "EMPTY_TRANSCRIPT": "Vui lòng nhập câu lệnh.",
    "NO_SPEECH": "Không phát hiện giọng nói sau Wake Word.",
    "NO_MATCH": "Không nhận diện được hành động hoặc thiết bị.",
    "BELOW_THRESHOLD": "Câu lệnh chưa đủ rõ để thực thi.",
    "NEGATION_DETECTED": "Phát hiện câu phủ định; lệnh không được thực thi.",
    "CONFLICTING_ACTION": "Câu lệnh chứa cả hành động bật và tắt.",
    "AMBIGUOUS_COMMAND": "Câu lệnh có nhiều cách hiểu.",
    "AMBIGUOUS_TARGET": "Có nhiều thiết bị phù hợp; hãy chỉ rõ phòng.",
    "TARGET_REQUIRED": "Cần chỉ rõ thiết bị hoặc phòng.",
    "TARGET_NOT_FOUND": "Không tìm thấy thiết bị phù hợp với phòng đã nêu.",
    "CATALOGUE_ERROR": "Cấu hình lệnh AI không hợp lệ.",
    "SERVICE_NOT_READY": "Chưa cài thư viện AI cần thiết để xử lý lệnh.",
}


class VoiceServiceDisabledError(RuntimeError):
    """Raised when microphone voice control is disabled by configuration."""


class VoiceServiceUnavailableError(RuntimeError):
    """Raised when the voice listener cannot start or stop cleanly."""


class VoiceService:
    def __init__(
        self,
        device_service_instance: DeviceService = device_service,
        registry: DeviceRegistry = device_registry,
        speech_recognizer: SpeechRecognizer | None = None,
        capture_factory: Callable[[], Any] | None = None,
        response_service: VoiceResponseService | None = None,
    ) -> None:
        self.device_service = device_service_instance
        self.registry = registry
        self.speech_recognizer = speech_recognizer or SpeechRecognizer()
        self._capture_factory = capture_factory
        self.response_service = response_service or voice_response_service
        self._processor: CommandProcessor | None = None
        self._catalogue_error: str | None = None
        self._state = "STOPPED"
        self._last_error: str | None = None
        self._last_transcript: str | None = None
        self._microphone_available = False
        self._microphone_name: str | None = None
        self._capture: Any | None = None
        self._listener_thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._state_lock = threading.RLock()
        self._lifecycle_lock = threading.Lock()
        self._history: deque[dict[str, Any]] = deque(
            maxlen=settings.VOICE_HISTORY_LIMIT
        )
        self._wake_detector: WakeWordDetector | None = None

    def _get_processor(self) -> CommandProcessor:
        if self._processor is None and self._catalogue_error is None:
            try:
                project_root = Path(__file__).resolve().parents[3]
                catalogue_path = Path(settings.COMMAND_CATALOG_PATH)
                if not catalogue_path.is_absolute():
                    catalogue_path = project_root / catalogue_path
                self._processor = CommandProcessor(
                    catalogue_path=catalogue_path,
                    registry=self.registry,
                    similarity_threshold=settings.COMMAND_SIMILARITY_THRESHOLD,
                )
            except CatalogueConfigurationError as error:
                self._catalogue_error = str(error)
        if self._catalogue_error is not None:
            raise CatalogueConfigurationError(self._catalogue_error)
        if self._processor is None:
            raise RuntimeError("Command processor is not available.")
        return self._processor

    def get_commands(self) -> list[dict[str, Any]]:
        processor = self._get_processor()
        return [
            {
                "id": command["id"],
                "intent": command["intent"],
                "action": command["action"],
                "device_type": command["device_type"],
                "aliases": command["aliases"],
            }
            for command in processor.catalogue["commands"]
            if command.get("enabled", True)
        ]

    def transcribe(self, audio: bytes) -> dict[str, Any]:
        return self.speech_recognizer.transcribe(audio)

    def process(
        self,
        text: str,
        execute: bool = False,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        try:
            result = self._get_processor().process(text)
        except CatalogueConfigurationError:
            result = self._empty_result(text, "CATALOGUE_ERROR")
        except RapidFuzzUnavailableError:
            result = self._empty_result(text, "SERVICE_NOT_READY")

        result["execution"] = None
        result["execution_status"] = (
            "rejected" if not result["accepted"] else "needs_confirmation"
        )
        result["message"] = _REASONS.get(result["reason"], result["reason"])
        if execute:
            return self._execute_result(result, request_id=request_id)
        return result

    def _empty_result(self, text: str, reason: str) -> dict[str, Any]:
        return {
            "accepted": False,
            "reason": reason,
            "recognized_text": text,
            "normalized_text": "",
            "command_id": None,
            "intent": None,
            "action": None,
            "device_type": None,
            "target": None,
            "device_id": None,
            "confidence": None,
            "threshold": settings.COMMAND_SIMILARITY_THRESHOLD,
        }

    def _execute_result(
        self,
        result: dict[str, Any],
        request_id: str | None = None,
    ) -> dict[str, Any]:
        if not result["accepted"]:
            return result

        device_id = result["device_id"]
        is_on = result["action"] == "turn_on"
        if not isinstance(device_id, str) or self.registry.get(device_id) is None:
            response = self.response_service.respond_to_device(
                device_id if isinstance(device_id, str) else "",
                is_on,
                success=False,
                request_id=request_id,
                error="Device not found.",
            )
            result.update(
                accepted=False,
                reason="TARGET_NOT_FOUND",
                execution_status="rejected",
                message=_REASONS["TARGET_NOT_FOUND"],
                voice_response=response.model_dump(mode="json"),
            )
            return result

        try:
            execution = self.device_service.set_device_state(device_id, is_on)
        except Exception as error:
            logger.exception("Voice command execution failed for %s", device_id)
            response = self.response_service.respond_to_device(
                device_id,
                is_on,
                success=False,
                request_id=request_id,
                error=str(error),
            )
            result.update(
                reason="EXECUTION_FAILED",
                execution_status="failed",
                message=f"Không thực thi được lệnh: {error}",
                execution={"success": False, "error": str(error)},
                voice_response=response.model_dump(mode="json"),
            )
            return result

        succeeded = execution.get("is_on") is is_on
        response = self.response_service.respond_to_device(
            device_id,
            is_on,
            success=succeeded,
            request_id=request_id,
            operation_result=execution,
        )
        if not succeeded:
            result.update(
                reason="EXECUTION_FAILED",
                execution_status="failed",
                message="Thiết bị không chuyển sang trạng thái được yêu cầu.",
                execution={"success": False, "device": execution},
                voice_response=response.model_dump(mode="json"),
            )
            return result

        result.update(
            execution_status="succeeded",
            message="Đã thực thi lệnh thành công.",
            execution={"success": True, "device": execution},
            voice_response=response.model_dump(mode="json"),
        )
        return result

    def get_status(self) -> dict[str, Any]:
        with self._state_lock:
            return {
                "enabled": settings.VOICE_ENABLED,
                "running": self._listener_thread is not None
                and self._listener_thread.is_alive(),
                "state": self._state,
                "model_loaded": self.speech_recognizer.is_loaded,
                "microphone_available": self._microphone_available,
                "microphone": self._microphone_name,
                "last_transcript": self._last_transcript,
                "last_error": self._last_error,
                "wake_word": next(
                    (
                        word.strip()
                        for word in settings.WAKE_WORDS.split(",")
                        if word.strip()
                    ),
                    None,
                ),
            }

    def get_history(self, limit: int = 20) -> list[dict[str, Any]]:
        with self._state_lock:
            return [dict(entry) for entry in list(self._history)[-limit:][::-1]]

    def start(self) -> dict[str, Any]:
        if not settings.VOICE_ENABLED:
            raise VoiceServiceDisabledError(
                "Voice control is disabled. Set VOICE_ENABLED=true to start it."
            )

        with self._lifecycle_lock:
            with self._state_lock:
                if (
                    self._listener_thread is not None
                    and self._listener_thread.is_alive()
                ):
                    return {
                        "success": True,
                        "state": self._state,
                        "message": "Voice listener is already running.",
                    }
                self._state = "STARTING"
                self._last_error = None

            capture: Any | None = None
            try:
                self._wake_detector = WakeWordDetector(
                    word.strip()
                    for word in settings.WAKE_WORDS.split(",")
                    if word.strip()
                )
                self.speech_recognizer.load()
                capture = self._new_capture()
                capture.start()
                self._stop_event.clear()
                listener = threading.Thread(
                    target=self._listen_loop,
                    name="VietHomeVoiceListener",
                    daemon=True,
                )
                with self._state_lock:
                    self._capture = capture
                    self._listener_thread = listener
                    self._microphone_available = True
                    self._microphone_name = getattr(
                        capture,
                        "device_name",
                        None,
                    )
                    self._state = "WAITING_WAKE_WORD"
                listener.start()
            except Exception as error:
                logger.exception("Could not start voice listener")
                if capture is not None:
                    try:
                        capture.stop()
                    except Exception:
                        logger.exception("Could not close failed microphone stream")
                try:
                    self.speech_recognizer.unload()
                except Exception:
                    logger.exception("Could not unload speech model after start failure")
                with self._state_lock:
                    self._capture = None
                    self._listener_thread = None
                    self._microphone_available = False
                    self._microphone_name = None
                    self._state = "ERROR"
                    self._last_error = str(error)
                raise VoiceServiceUnavailableError(str(error)) from error

        logger.info("Voice listener started")
        return {
            "success": True,
            "state": "WAITING_WAKE_WORD",
            "message": "Voice listener started.",
        }

    def _new_capture(self) -> Any:
        if self._capture_factory is not None:
            return self._capture_factory()
        return MicrophoneCapture(
            sample_rate=settings.AUDIO_SAMPLE_RATE,
            input_device=settings.AUDIO_INPUT_DEVICE,
            block_seconds=settings.AUDIO_BLOCK_SECONDS,
        )

    def stop(self) -> dict[str, Any]:
        with self._lifecycle_lock:
            with self._state_lock:
                listener = self._listener_thread
                capture = self._capture
                if (
                    self._state == "STOPPED"
                    and (listener is None or not listener.is_alive())
                ):
                    return {
                        "success": True,
                        "state": "STOPPED",
                        "message": "Voice listener is already stopped.",
                    }
                self._state = "STOPPING"
                self._stop_event.set()

            stop_error: Exception | None = None
            if capture is not None:
                try:
                    capture.stop()
                except Exception as error:
                    logger.exception("Could not close microphone stream")
                    stop_error = error
            if listener is not None and listener is not threading.current_thread():
                listener.join()
            try:
                self.speech_recognizer.unload()
            except Exception as error:
                logger.exception("Could not unload speech model")
                stop_error = stop_error or error

            with self._state_lock:
                self._capture = None
                self._listener_thread = None
                self._microphone_available = False
                self._microphone_name = None
                self._state = "ERROR" if stop_error else "STOPPED"
                self._last_error = str(stop_error) if stop_error else None
            if stop_error is not None:
                raise VoiceServiceUnavailableError(str(stop_error)) from stop_error

        logger.info("Voice listener stopped")
        return {
            "success": True,
            "state": "STOPPED",
            "message": "Voice listener stopped.",
        }

    def _listen_loop(self) -> None:
        try:
            self._run_listener()
        except Exception as error:
            logger.exception("Voice listener failed")
            with self._state_lock:
                self._state = "ERROR"
                self._last_error = str(error)
                capture = self._capture
                self._microphone_available = False
            if capture is not None:
                try:
                    capture.stop()
                except Exception:
                    logger.exception("Could not close microphone after listener failure")

    def _run_listener(self) -> None:
        capture = self._capture
        wake_detector = self._wake_detector
        if capture is None or wake_detector is None:
            raise VoiceServiceUnavailableError("Voice listener was not initialized.")

        wake_chunk_count = max(
            1,
            math.ceil(
                settings.WAKE_CHUNK_SECONDS / settings.AUDIO_BLOCK_SECONDS
            ),
        )
        preroll_chunk_count = max(1, math.ceil(0.5 / settings.AUDIO_BLOCK_SECONDS))
        wake_frames: deque[Any] = deque(maxlen=wake_chunk_count)
        preroll_frames: deque[Any] = deque(maxlen=preroll_chunk_count)
        command_frames: list[Any] = []
        last_wake_check = 0.0
        last_wake_at = -settings.WAKE_WORD_COOLDOWN_SECONDS
        command_duration = 0.0
        speech_duration = 0.0
        silence_duration = 0.0
        speech_started = False

        while not self._stop_event.is_set():
            try:
                frame = capture.read(timeout=0.5)
            except queue.Empty:
                continue

            if not frame:
                continue

            frame_duration = len(frame) / settings.AUDIO_SAMPLE_RATE
            state = self.get_status()["state"]
            if state == "WAITING_WAKE_WORD":
                wake_frames.append(frame)
                preroll_frames.append(frame)
                timestamp = time.monotonic()
                if timestamp - last_wake_at < settings.WAKE_WORD_COOLDOWN_SECONDS:
                    continue
                if len(wake_frames) < wake_chunk_count:
                    continue
                if (
                    timestamp - last_wake_check
                    < settings.WAKE_DETECTION_INTERVAL_SECONDS
                ):
                    continue
                last_wake_check = timestamp
                try:
                    wake_audio = self._join_audio(wake_frames)
                    transcription = self.speech_recognizer.transcribe_samples(
                        wake_audio,
                        settings.AUDIO_SAMPLE_RATE,
                    )
                except SpeechRecognitionError as error:
                    self._set_last_error(str(error))
                    logger.warning("Wake-word transcription failed: %s", error)
                    continue

                transcript = transcription["recognized_text"]
                if not wake_detector.detect(transcript):
                    continue

                logger.info("Wake word detected")
                with self._state_lock:
                    self._state = "LISTENING_COMMAND"
                    self._last_transcript = transcript
                last_wake_at = timestamp
                command_frames = list(preroll_frames)
                command_duration = 0.0
                speech_duration = 0.0
                silence_duration = 0.0
                speech_started = False
                wake_frames.clear()
                preroll_frames.clear()
                continue

            if state != "LISTENING_COMMAND":
                continue

            command_frames.append(frame)
            command_duration += frame_duration
            rms = self._calculate_rms(frame)
            if rms >= settings.AUDIO_SILENCE_THRESHOLD:
                speech_started = True
                speech_duration += frame_duration
                silence_duration = 0.0
            elif speech_started:
                silence_duration += frame_duration

            if (
                speech_started
                and speech_duration >= settings.COMMAND_MIN_DURATION
                and silence_duration >= settings.COMMAND_SILENCE_DURATION
            ):
                self._process_command_audio(self._join_audio(command_frames))
                command_frames = []
                command_duration = 0.0
                speech_duration = 0.0
                silence_duration = 0.0
                speech_started = False
                wake_frames.clear()
                preroll_frames.clear()
                continue

            if command_duration >= settings.COMMAND_START_TIMEOUT_SECONDS and not speech_started:
                self._record_no_speech()
                command_frames = []
                command_duration = 0.0
                speech_duration = 0.0
                silence_duration = 0.0
                wake_frames.clear()
                preroll_frames.clear()
                with self._state_lock:
                    self._state = "WAITING_WAKE_WORD"
                continue

            if command_duration >= settings.COMMAND_MAX_DURATION:
                if speech_started and speech_duration >= settings.COMMAND_MIN_DURATION:
                    self._process_command_audio(self._join_audio(command_frames))
                else:
                    self._record_no_speech()
                command_frames = []
                command_duration = 0.0
                speech_duration = 0.0
                silence_duration = 0.0
                speech_started = False
                wake_frames.clear()
                preroll_frames.clear()
                with self._state_lock:
                    self._state = "WAITING_WAKE_WORD"

    @staticmethod
    def _join_audio(frames: Any) -> Any:
        from array import array

        joined = array("f")
        for frame in frames:
            joined.extend(frame)
        return joined

    @staticmethod
    def _calculate_rms(frame: Any) -> float:
        if not frame:
            return 0.0
        return math.sqrt(sum(sample * sample for sample in frame) / len(frame))

    def _process_command_audio(self, audio: Any) -> None:
        with self._state_lock:
            self._state = "PROCESSING"
        try:
            transcription = self.speech_recognizer.transcribe_samples(
                audio,
                settings.AUDIO_SAMPLE_RATE,
            )
        except SpeechRecognitionError as error:
            self._set_last_error(str(error))
            logger.exception("Command speech recognition failed")
            self._record_stt_error(str(error))
        else:
            transcript = transcription["recognized_text"]
            result = self.process(transcript)
            if result["accepted"] and settings.VOICE_AUTO_EXECUTE:
                with self._state_lock:
                    self._state = "EXECUTING"
                result = self._execute_result(result)
            self._add_history(transcription, result)
            logger.info(
                "Voice command processed: accepted=%s reason=%s execution=%s",
                result["accepted"],
                result["reason"],
                result["execution_status"],
            )
        finally:
            if not self._stop_event.is_set():
                with self._state_lock:
                    self._state = "WAITING_WAKE_WORD"

    def _record_no_speech(self) -> None:
        result = self._empty_result("", "NO_SPEECH")
        result.update(
            execution=None,
            execution_status="rejected",
            message=_REASONS["NO_SPEECH"],
        )
        self._add_history({}, result)
        logger.info("No speech detected after Wake Word")

    def _record_stt_error(self, message: str) -> None:
        result = self._empty_result("", "STT_ERROR")
        result.update(
            execution=None,
            execution_status="failed",
            message=message,
        )
        self._add_history({}, result)

    def _add_history(
        self,
        transcription: dict[str, Any],
        result: dict[str, Any],
    ) -> None:
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "recognized_text": result["recognized_text"],
            "accepted": result["accepted"],
            "reason": result["reason"],
            "intent": result["intent"],
            "action": result["action"],
            "target": result["target"],
            "device_id": result["device_id"],
            "confidence": result["confidence"],
            "execution_status": result["execution_status"],
            "execution": result["execution"],
            "language": transcription.get("language"),
        }
        with self._state_lock:
            self._last_transcript = result["recognized_text"]
            self._history.append(entry)

    def _set_last_error(self, error: str) -> None:
        with self._state_lock:
            self._last_error = error


voice_service = VoiceService()
