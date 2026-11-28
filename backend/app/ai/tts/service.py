import logging
import math
import threading
import uuid
from collections import OrderedDict
from typing import Any, Literal

from app.ai.tts.providers.dynamic_tts import LocalVietnameseTTS, TTSUnavailableError
from app.ai.tts.providers.static_audio import (
    StaticAudioError,
    StaticAudioPlayer,
    UnknownResponseKey,
)
from app.ai.tts.schemas import VoiceResponseResult, VoiceResponseStatus
from app.core.config import settings
from app.devices.registry import device_registry
from app.services.dashboard_service import dashboard_service

logger = logging.getLogger(__name__)

SensorRequest = Literal["temperature", "humidity", "summary"]

_STATIC_TEXT = {
    "common.ready": "VietHome đã sẵn sàng.",
    "common.understood": "Tôi đã nhận được yêu cầu.",
    "common.action_success": "Đã thực hiện yêu cầu.",
    "common.action_failed": "Xin lỗi, tôi chưa thể thực hiện yêu cầu.",
    "common.device_unavailable": "Thiết bị hiện không khả dụng.",
    "common.partial_success": "Một số thiết bị chưa thể thực hiện yêu cầu.",
    "lights.turned_on": "Đã bật đèn.",
    "lights.turned_off": "Đã tắt đèn.",
    "fans.turned_on": "Đã bật quạt.",
    "fans.turned_off": "Đã tắt quạt.",
    "devices.all_turned_on": "Đã bật tất cả thiết bị.",
    "devices.all_turned_off": "Đã tắt tất cả thiết bị.",
    "sensors.unavailable": "Hiện tại chưa có dữ liệu cảm biến.",
    "sensors.stale": "Dữ liệu cảm biến đã cũ, vui lòng thử lại sau.",
    "sensors.stale": "Dữ liệu cảm biến đã cũ, vui lòng thử lại sau.",
}


class VoiceResponseService:
    def __init__(
        self,
        static_player: StaticAudioPlayer | None = None,
        tts_provider: LocalVietnameseTTS | None = None,
        sensor_source: Any = dashboard_service,
        registry: Any = device_registry,
        idempotency_limit: int = 256,
    ) -> None:
        self.static_player = static_player or StaticAudioPlayer()
        self.tts_provider = tts_provider or LocalVietnameseTTS()
        self.sensor_source = sensor_source
        self.registry = registry
        self._playback_lock = threading.Lock()
        self._state_lock = threading.Lock()
        self._is_playing = False
        self._idempotency_limit = idempotency_limit
        self._completed_requests: OrderedDict[str, VoiceResponseResult] = OrderedDict()

    def _request_id(self, request_id: str | None) -> str:
        return request_id or str(uuid.uuid4())

    def _remember(self, result: VoiceResponseResult) -> None:
        self._completed_requests[result.request_id] = result
        self._completed_requests.move_to_end(result.request_id)
        while len(self._completed_requests) > self._idempotency_limit:
            self._completed_requests.popitem(last=False)

    def _deliver(
        self,
        *,
        request_id: str | None,
        response_mode: Literal["static", "tts"],
        response_key: str,
        text: str,
        data: dict[str, Any] | None = None,
        prior_error: str | None = None,
    ) -> VoiceResponseResult:
        resolved_request_id = self._request_id(request_id)
        with self._playback_lock:
            previous = self._completed_requests.get(resolved_request_id)
            if previous is not None:
                return previous.model_copy(
                    update={"status": "duplicate", "audio_played": False}
                )

            if not settings.VOICE_RESPONSE_ENABLED:
                result = VoiceResponseResult(
                    request_id=resolved_request_id,
                    status="disabled",
                    response_mode="none",
                    response_key=response_key,
                    text=text,
                    audio_played=False,
                    error="Voice responses are disabled.",
                    data=data,
                )
                self._remember(result)
                return result

            with self._state_lock:
                self._is_playing = True
            audio_path: str | None = None
            error = prior_error
            playback_succeeded = True
            try:
                if response_mode == "static":
                    audio_path = self.static_player.play(response_key)
                else:
                    if not settings.VOICE_TTS_ENABLED:
                        raise TTSUnavailableError("TTS is disabled.")
                    self.tts_provider.speak(text)
            except (StaticAudioError, TTSUnavailableError) as playback_error:
                playback_succeeded = False
                error = "; ".join(
                    value for value in (prior_error, str(playback_error)) if value
                )
                logger.warning(
                    "Voice response unavailable request_id=%s key=%s: %s",
                    resolved_request_id,
                    response_key,
                    playback_error,
                )
            except Exception as playback_error:
                playback_succeeded = False
                playback_error_message = "Voice response playback failed."
                error = "; ".join(
                    value
                    for value in (prior_error, playback_error_message)
                    if value
                )
                logger.exception(
                    "Voice response failed request_id=%s key=%s",
                    resolved_request_id,
                    response_key,
                )
            finally:
                with self._state_lock:
                    self._is_playing = False

            result = VoiceResponseResult(
                request_id=resolved_request_id,
                status="played" if playback_succeeded else "unavailable",
                response_mode=response_mode,
                response_key=response_key,
                text=text,
                audio_played=playback_succeeded,
                audio_path=audio_path,
                error=error,
                data=data,
            )
            self._remember(result)
            return result

    def play_static(
        self,
        response_key: str,
        request_id: str | None = None,
    ) -> VoiceResponseResult:
        entry = self.static_player.get_entry(response_key)
        return self._deliver(
            request_id=request_id,
            response_mode="static",
            response_key=response_key,
            text=entry["text"],
        )

    def respond_to_device(
        self,
        device_id: str,
        is_on: bool,
        *,
        success: bool,
        request_id: str | None = None,
        error: str | None = None,
        operation_result: dict[str, Any] | None = None,
    ) -> VoiceResponseResult:
        if not success:
            response_key = (
                "common.device_unavailable"
                if isinstance(error, str) and "not found" in error.lower()
                else "common.action_failed"
            )
        elif device_id in {"light", "light_bed"}:
            response_key = "lights.turned_on" if is_on else "lights.turned_off"
        elif device_id == "fan":
            response_key = "fans.turned_on" if is_on else "fans.turned_off"
        else:
            response_key = "common.action_success"

        try:
            text = self.static_player.get_entry(response_key)["text"]
        except StaticAudioError:
            text = _STATIC_TEXT[response_key]
        data = {"device_id": device_id, "is_on": is_on}
        if operation_result is not None:
            data["device"] = operation_result
        return self._deliver(
            request_id=request_id,
            response_mode="static",
            response_key=response_key,
            text=text,
            data=data,
            prior_error=error if not success else None,
        )

    def respond_to_bulk_operation(
        self,
        *,
        is_on: bool,
        results: list[dict[str, Any]],
        request_id: str | None = None,
    ) -> VoiceResponseResult:
        success_count = sum(bool(result.get("success")) for result in results)
        if success_count == len(results) and results:
            response_key = (
                "devices.all_turned_on" if is_on else "devices.all_turned_off"
            )
            prior_error = None
        elif success_count:
            response_key = "common.partial_success"
            prior_error = "Some device operations failed."
        else:
            response_key = "common.action_failed"
            prior_error = "No device operation succeeded."

        try:
            text = self.static_player.get_entry(response_key)["text"]
        except StaticAudioError:
            text = _STATIC_TEXT[response_key]
        return self._deliver(
            request_id=request_id,
            response_mode="static",
            response_key=response_key,
            text=text,
            data={"is_on": is_on, "results": results},
            prior_error=prior_error,
        )

    @staticmethod
    def _valid_measurement(value: Any, *, humidity: bool = False) -> float | None:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        converted = float(value)
        if not math.isfinite(converted):
            return None
        if humidity and not 0 <= converted <= 100:
            return None
        if not humidity and not -50 <= converted <= 100:
            return None
        return converted

    @staticmethod
    def _format_number(value: float) -> str:
        rounded = round(value, 1)
        if rounded == 0:
            rounded = 0.0
        sign = "âm " if rounded < 0 else ""
        absolute = abs(rounded)
        if absolute.is_integer():
            number = str(int(absolute))
        else:
            whole, fraction = f"{absolute:.1f}".split(".")
            number = f"{whole} phẩy {fraction}"
        return f"{sign}{number}"

    def respond_to_sensor(
        self,
        sensor: SensorRequest,
        request_id: str | None = None,
    ) -> VoiceResponseResult:
        try:
            dashboard = self.sensor_source.get_dashboard()
            readings = getattr(dashboard, "sensors", None)
            status_reader = getattr(
                self.sensor_source,
                "get_sensor_status",
                lambda: "unavailable",
            )
            sensor_status = status_reader()
            temperature = self._valid_measurement(
                getattr(readings, "temperature", None)
            )
            humidity = self._valid_measurement(
                getattr(readings, "humidity", None),
                humidity=True,
            )
        except Exception as error:
            logger.exception("Could not read current sensor values")
            return self._deliver(
                request_id=request_id,
                response_mode="static",
                response_key="sensors.unavailable",
                text=_STATIC_TEXT["sensors.unavailable"],
                data={"sensor": sensor},
                prior_error="Sensor service is unavailable.",
            )

        missing = (
            temperature is None
            if sensor == "temperature"
            else humidity is None
            if sensor == "humidity"
            else temperature is None or humidity is None
        )
        data = {"temperature": temperature, "humidity": humidity}
        if missing:
            response_key = (
                "sensors.stale"
                if sensor_status == "stale"
                else "sensors.unavailable"
            )
            return self._deliver(
                request_id=request_id,
                response_mode="static",
                response_key=response_key,
                text=_STATIC_TEXT[response_key],
                data=data,
                prior_error=(
                    "Sensor data is stale."
                    if response_key == "sensors.stale"
                    else f"No valid current {sensor} reading is available."
                ),
            )

        if sensor == "temperature":
            text = (
                "Nhiệt độ hiện tại là "
                f"{self._format_number(temperature)} độ C."
            )
        elif sensor == "humidity":
            text = f"Độ ẩm hiện tại là {self._format_number(humidity)} phần trăm."
        else:
            text = (
                "Nhiệt độ hiện tại là "
                f"{self._format_number(temperature)} độ C, "
                f"độ ẩm là {self._format_number(humidity)} phần trăm."
            )
        response_key = f"sensors.{sensor}"
        return self._deliver(
            request_id=request_id,
            response_mode="tts",
            response_key=response_key,
            text=text,
            data=data,
        )

    def get_status(self, probe_tts: bool = False) -> VoiceResponseStatus:
        try:
            response_keys = self.static_player.response_keys()
            missing_assets = self.static_player.missing_assets()
        except StaticAudioError:
            logger.exception("Voice response manifest is unavailable")
            response_keys = []
            missing_assets = []

        audio_available = self.static_player.output_available()
        tts_available: bool | None = None
        tts_error: str | None = None
        if not settings.VOICE_TTS_ENABLED:
            tts_available = False
            tts_error = "TTS is disabled."
        elif probe_tts:
            try:
                tts_available = self.tts_provider.check_available()
            except TTSUnavailableError as error:
                tts_available = False
                tts_error = str(error)

        with self._state_lock:
            is_playing = self._is_playing
        return VoiceResponseStatus(
            enabled=settings.VOICE_RESPONSE_ENABLED,
            playback_mode=settings.VOICE_PLAYBACK_MODE,
            is_playing=is_playing,
            static_response_keys=response_keys,
            missing_static_assets=missing_assets,
            audio_output_available=audio_available,
            tts_enabled=settings.VOICE_TTS_ENABLED,
            tts_provider=settings.VOICE_TTS_PROVIDER,
            tts_available=tts_available,
            tts_error=tts_error,
        )


voice_response_service = VoiceResponseService()
