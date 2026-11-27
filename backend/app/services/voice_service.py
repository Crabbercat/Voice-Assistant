import logging
from pathlib import Path
from typing import Any

from app.ai.command.processor import (
    CatalogueConfigurationError,
    CommandProcessor,
    RapidFuzzUnavailableError,
)
from app.ai.speech.speech_recognizer import SpeechRecognizer
from app.core.config import settings
from app.devices.registry import DeviceRegistry, device_registry
from app.services.device_service import DeviceService, device_service

logger = logging.getLogger(__name__)

_REASONS = {
    "MATCH_ACCEPTED": "Đã nhận diện lệnh. Vui lòng xác nhận để thực thi.",
    "EMPTY_TRANSCRIPT": "Vui lòng nhập câu lệnh.",
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


class VoiceService:
    def __init__(
        self,
        device_service_instance: DeviceService = device_service,
        registry: DeviceRegistry = device_registry,
    ) -> None:
        self.device_service = device_service_instance
        self.registry = registry
        self.speech_recognizer = SpeechRecognizer()
        self._processor: CommandProcessor | None = None
        self._catalogue_error: str | None = None

    def _get_processor(self) -> CommandProcessor:
        if self._processor is None and self._catalogue_error is None:
            try:
                project_root = Path(__file__).resolve().parents[3]
                catalogue_path = project_root / "hardware" / "configs" / "commands.json"
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

    def process(self, text: str, execute: bool = False) -> dict[str, Any]:
        try:
            result = self._get_processor().process(text)
        except CatalogueConfigurationError:
            result = {
                "accepted": False,
                "reason": "CATALOGUE_ERROR",
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
        except RapidFuzzUnavailableError:
            result = {
                "accepted": False,
                "reason": "SERVICE_NOT_READY",
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
        result["execution"] = None
        result["execution_status"] = (
            "rejected" if not result["accepted"] else "needs_confirmation"
        )
        result["message"] = _REASONS.get(result["reason"], result["reason"])

        if not result["accepted"] or not execute:
            return result

        device_id = result["device_id"]
        if not isinstance(device_id, str) or self.registry.get(device_id) is None:
            result.update(
                accepted=False,
                reason="TARGET_NOT_FOUND",
                execution_status="rejected",
                message=_REASONS["TARGET_NOT_FOUND"],
            )
            return result

        is_on = result["action"] == "turn_on"
        try:
            execution = self.device_service.set_device_state(device_id, is_on)
        except Exception as error:
            logger.exception("Voice command execution failed for %s", device_id)
            result.update(
                reason="EXECUTION_FAILED",
                execution_status="failed",
                message=f"Không thực thi được lệnh: {error}",
                execution={"success": False, "error": str(error)},
            )
            return result

        result.update(
            execution_status="succeeded",
            message="Đã thực thi lệnh thành công.",
            execution={"success": True, "device": execution},
        )
        return result


voice_service = VoiceService()
