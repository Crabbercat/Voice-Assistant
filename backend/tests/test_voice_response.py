import json
import threading
import time
import wave
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.ai.tts.providers.dynamic_tts import LocalVietnameseTTS, TTSUnavailableError
from app.ai.tts.providers.static_audio import (
    StaticAudioError,
    StaticAudioPlayer,
    UnknownResponseKey,
)
from app.ai.tts.service import VoiceResponseService
from app.core.config import settings


_TEXTS = {
    "common.action_failed": "Xin lỗi, tôi chưa thể thực hiện yêu cầu.",
    "common.device_unavailable": "Thiết bị hiện không khả dụng.",
    "common.partial_success": "Một số thiết bị chưa thể thực hiện yêu cầu.",
    "lights.turned_on": "Đã bật đèn.",
    "lights.turned_off": "Đã tắt đèn.",
    "fans.turned_on": "Đã bật quạt.",
    "fans.turned_off": "Đã tắt quạt.",
    "devices.all_turned_on": "Đã bật tất cả thiết bị.",
    "devices.all_turned_off": "Đã tắt tất cả thiết bị.",
    "common.action_success": "Đã thực hiện yêu cầu.",
    "sensors.unavailable": "Hiện tại chưa có dữ liệu cảm biến.",
    "sensors.stale": "Dữ liệu cảm biến đã cũ, vui lòng thử lại sau.",
}


def _write_manifest(root: Path, path: str = "common/test.wav") -> Path:
    asset_dir = root / "assets" / "static"
    asset_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = asset_dir.parent / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "version": 1,
                "default_locale": "vi-VN",
                "responses": {
                    "common.test": {
                        "path": path,
                        "type": "static",
                        "text": "Đã kiểm tra.",
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    return asset_dir


def _write_test_wav(path: Path, *, sample_width: int = 2) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as audio_file:
        audio_file.setnchannels(1)
        audio_file.setsampwidth(sample_width)
        audio_file.setframerate(16000)
        audio_file.writeframes(b"\x00" * 320)


class FakeStaticPlayer:
    def __init__(self) -> None:
        self.played_keys: list[str] = []
        self.active = 0
        self.maximum_active = 0
        self._counter_lock = threading.Lock()

    def get_entry(self, response_key: str) -> dict[str, str]:
        if response_key not in _TEXTS:
            raise UnknownResponseKey(response_key)
        return {
            "path": response_key.replace(".", "/") + ".wav",
            "text": _TEXTS[response_key],
            "type": "static",
        }

    def play(self, response_key: str) -> str:
        with self._counter_lock:
            self.active += 1
            self.maximum_active = max(self.maximum_active, self.active)
        time.sleep(0.02)
        self.played_keys.append(response_key)
        with self._counter_lock:
            self.active -= 1
        return response_key.replace(".", "/") + ".wav"

    def response_keys(self) -> list[str]:
        return sorted(_TEXTS)

    def missing_assets(self) -> list[str]:
        return []

    def output_available(self) -> bool:
        return True


class FakeTTS:
    def __init__(self) -> None:
        self.spoken: list[str] = []

    def speak(self, text: str) -> None:
        self.spoken.append(text)

    def check_available(self) -> bool:
        return True


class FakeSensorSource:
    def __init__(
        self,
        temperature: object,
        humidity: object,
        status: str = "available",
    ) -> None:
        self.readings = SimpleNamespace(
            temperature=temperature,
            humidity=humidity,
        )
        self.status = status

    def get_dashboard(self) -> SimpleNamespace:
        return SimpleNamespace(sensors=self.readings)

    def get_sensor_status(self) -> str:
        return self.status


def test_static_audio_player_plays_registered_pcm_wav(tmp_path: Path) -> None:
    asset_dir = _write_manifest(tmp_path)
    wav_path = asset_dir / "common" / "test.wav"
    _write_test_wav(wav_path)
    played: list[tuple[bytes, int]] = []
    player = StaticAudioPlayer(
        asset_dir,
        playback=lambda frames, rate: played.append((frames, rate)),
    )

    result = player.play("common.test")

    assert result == "common/test.wav"
    assert played == [(b"\x00" * 320, 16000)]


def test_static_audio_rejects_unknown_key_and_missing_recording(
    tmp_path: Path,
) -> None:
    asset_dir = _write_manifest(tmp_path)
    player = StaticAudioPlayer(asset_dir, playback=lambda *_: None)

    with pytest.raises(UnknownResponseKey):
        player.play("common.unknown")
    with pytest.raises(StaticAudioError, match="No recording"):
        player.play("common.test")


def test_static_audio_rejects_manifest_path_traversal(tmp_path: Path) -> None:
    asset_dir = _write_manifest(tmp_path, "../escape.wav")
    player = StaticAudioPlayer(asset_dir, playback=lambda *_: None)

    with pytest.raises(StaticAudioError, match="unsafe audio path"):
        player.response_keys()


def test_static_audio_validates_pcm_format(tmp_path: Path) -> None:
    asset_dir = _write_manifest(tmp_path)
    _write_test_wav(asset_dir / "common" / "test.wav", sample_width=1)
    player = StaticAudioPlayer(asset_dir, playback=lambda *_: None)

    with pytest.raises(StaticAudioError, match="mono, 16-bit PCM"):
        player.play("common.test")


def test_response_playback_is_serialized_and_idempotent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "VOICE_RESPONSE_ENABLED", True)
    player = FakeStaticPlayer()
    service = VoiceResponseService(static_player=player, tts_provider=FakeTTS())
    threads = [
        threading.Thread(
            target=service.play_static,
            args=("lights.turned_on", f"request-{index}"),
        )
        for index in range(4)
    ]

    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    duplicate = service.play_static("lights.turned_on", "request-0")

    assert player.maximum_active == 1
    assert len(player.played_keys) == 4
    assert duplicate.status == "duplicate"
    assert duplicate.audio_played is False


@pytest.mark.parametrize(
    ("device_id", "is_on", "expected_key"),
    [
        ("light", True, "lights.turned_on"),
        ("light_bed", False, "lights.turned_off"),
        ("fan", True, "fans.turned_on"),
        ("door", False, "common.action_success"),
    ],
)
def test_device_response_mapping(
    monkeypatch: pytest.MonkeyPatch,
    device_id: str,
    is_on: bool,
    expected_key: str,
) -> None:
    monkeypatch.setattr(settings, "VOICE_RESPONSE_ENABLED", True)
    player = FakeStaticPlayer()
    service = VoiceResponseService(static_player=player, tts_provider=FakeTTS())

    response = service.respond_to_device(
        device_id,
        is_on,
        success=True,
        operation_result={"device_id": device_id, "is_on": is_on},
    )

    assert player.played_keys == [expected_key]
    assert response.status == "played"


def test_failed_device_action_never_selects_success_clip(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "VOICE_RESPONSE_ENABLED", True)
    player = FakeStaticPlayer()
    service = VoiceResponseService(static_player=player, tts_provider=FakeTTS())

    response = service.respond_to_device(
        "light",
        True,
        success=False,
        error="GPIO error",
    )

    assert player.played_keys == ["common.action_failed"]
    assert response.text == _TEXTS["common.action_failed"]
    assert response.audio_played is True
    assert response.error == "GPIO error"


def test_bulk_partial_failure_selects_partial_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "VOICE_RESPONSE_ENABLED", True)
    player = FakeStaticPlayer()
    service = VoiceResponseService(static_player=player, tts_provider=FakeTTS())

    response = service.respond_to_bulk_operation(
        is_on=True,
        results=[
            {"device_id": "light", "success": True},
            {"device_id": "fan", "success": False},
        ],
    )

    assert player.played_keys == ["common.partial_success"]
    assert response.audio_played is True
    assert response.data["results"][1]["success"] is False


@pytest.mark.parametrize(
    ("sensor", "temperature", "humidity", "expected_text"),
    [
        (
            "temperature",
            28.6,
            75,
            "Nhiệt độ hiện tại là 28 phẩy 6 độ C.",
        ),
        ("humidity", 28, 75, "Độ ẩm hiện tại là 75 phần trăm."),
        (
            "summary",
            28,
            75,
            "Nhiệt độ hiện tại là 28 độ C, độ ẩm là 75 phần trăm.",
        ),
    ],
)
def test_sensor_values_are_formatted_and_spoken(
    monkeypatch: pytest.MonkeyPatch,
    sensor: str,
    temperature: float,
    humidity: float,
    expected_text: str,
) -> None:
    monkeypatch.setattr(settings, "VOICE_RESPONSE_ENABLED", True)
    monkeypatch.setattr(settings, "VOICE_TTS_ENABLED", True)
    tts = FakeTTS()
    service = VoiceResponseService(
        static_player=FakeStaticPlayer(),
        tts_provider=tts,
        sensor_source=FakeSensorSource(temperature, humidity),
    )

    response = service.respond_to_sensor(sensor)

    assert response.status == "played"
    assert response.response_mode == "tts"
    assert response.text == expected_text
    assert tts.spoken == [expected_text]
    assert response.data == {
        "temperature": float(temperature),
        "humidity": float(humidity),
    }


def test_missing_or_invalid_sensor_data_uses_static_unavailable_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "VOICE_RESPONSE_ENABLED", True)
    tts = FakeTTS()
    player = FakeStaticPlayer()
    service = VoiceResponseService(
        static_player=player,
        tts_provider=tts,
        sensor_source=FakeSensorSource(float("nan"), 101),
    )

    response = service.respond_to_sensor("summary")

    assert player.played_keys == ["sensors.unavailable"]
    assert tts.spoken == []
    assert response.response_key == "sensors.unavailable"
    assert response.text == _TEXTS["sensors.unavailable"]
    assert response.audio_played is True
    assert response.error is not None


def test_stale_sensor_data_uses_static_stale_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "VOICE_RESPONSE_ENABLED", True)
    player = FakeStaticPlayer()
    service = VoiceResponseService(
        static_player=player,
        tts_provider=FakeTTS(),
        sensor_source=FakeSensorSource(None, None, status="stale"),
    )

    response = service.respond_to_sensor("temperature")

    assert player.played_keys == ["sensors.stale"]
    assert response.response_key == "sensors.stale"
    assert response.text == _TEXTS["sensors.stale"]
    assert response.error == "Sensor data is stale."


def test_sensor_service_failure_is_returned_as_structured_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class BrokenSensorSource:
        def get_dashboard(self) -> None:
            raise RuntimeError("sensor unavailable")

    monkeypatch.setattr(settings, "VOICE_RESPONSE_ENABLED", True)
    player = FakeStaticPlayer()
    service = VoiceResponseService(
        static_player=player,
        tts_provider=FakeTTS(),
        sensor_source=BrokenSensorSource(),
    )

    response = service.respond_to_sensor("temperature")

    assert player.played_keys == ["sensors.unavailable"]
    assert response.error == "Sensor service is unavailable."
    assert response.data == {"sensor": "temperature"}


def test_local_tts_selects_and_reuses_vietnamese_voice() -> None:
    class FakeEngine:
        def __init__(self) -> None:
            self.properties: dict[str, object] = {}
            self.spoken: list[str] = []
            self.voices = [
                SimpleNamespace(id="en-US", name="English", languages=["en-US"]),
                SimpleNamespace(id="vi-VN", name="Vietnamese", languages=["vi-VN"]),
            ]

        def getProperty(self, name: str) -> object:
            return self.voices if name == "voices" else self.properties.get(name)

        def setProperty(self, name: str, value: object) -> None:
            self.properties[name] = value

        def say(self, text: str) -> None:
            self.spoken.append(text)

        def runAndWait(self) -> None:
            return None

    engine = FakeEngine()
    factory_calls = 0

    def create_engine() -> FakeEngine:
        nonlocal factory_calls
        factory_calls += 1
        return engine

    provider = LocalVietnameseTTS(engine_factory=create_engine)

    assert provider.check_available() is True
    provider.speak("Nhiệt độ hiện tại là 28 độ C.")
    provider.speak("Độ ẩm hiện tại là 75 phần trăm.")
    assert engine.properties["voice"] == "vi-VN"
    assert factory_calls == 1
    assert len(engine.spoken) == 2


def test_local_tts_does_not_fall_back_to_english_voice() -> None:
    class EnglishEngine:
        def getProperty(self, name: str) -> object:
            return [SimpleNamespace(id="en-US", name="English", languages=["en-US"])]

        def setProperty(self, name: str, value: object) -> None:
            return None

    provider = LocalVietnameseTTS(engine_factory=EnglishEngine)

    with pytest.raises(TTSUnavailableError, match="No Vietnamese voice"):
        provider.check_available()
