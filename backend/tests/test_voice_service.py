import queue
import threading
import time
from array import array
from collections import deque

import pytest

from app.core.config import settings
from app.services.voice_service import (
    VoiceService,
    VoiceServiceDisabledError,
    VoiceServiceUnavailableError,
)


class FakeDevice:
    def __init__(self) -> None:
        self.device_id = "light"
        self.name = "Đèn"
        self.room = "Phòng khách"


class FakeRegistry:
    def __init__(self) -> None:
        self.device = FakeDevice()

    def get_all(self) -> list[FakeDevice]:
        return [self.device]

    def get(self, device_id: str) -> FakeDevice | None:
        return self.device if device_id == self.device.device_id else None


class FakeDeviceService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, bool]] = []

    def set_device_state(self, device_id: str, is_on: bool) -> dict[str, object]:
        self.calls.append((device_id, is_on))
        return {"device_id": device_id, "is_on": is_on}


class FakeRecognizer:
    def __init__(self, command_text: str) -> None:
        self.command_text = command_text
        self.loaded = False
        self.transcription_count = 0

    @property
    def is_loaded(self) -> bool:
        return self.loaded

    def load(self) -> None:
        self.loaded = True

    def unload(self) -> None:
        self.loaded = False

    def transcribe_samples(self, audio: array, sample_rate: int) -> dict[str, object]:
        assert sample_rate == 16000
        self.transcription_count += 1
        text = "Hey Berry" if self.transcription_count == 1 else self.command_text
        return {
            "recognized_text": text,
            "language": "en",
            "language_probability": 0.99,
            "duration_seconds": len(audio) / sample_rate,
        }


class FakeCapture:
    def __init__(self, frames: list[array]) -> None:
        self.frames = deque(frames)
        self.device_name = "fake microphone"
        self.started = False
        self.stopped = threading.Event()

    def start(self) -> None:
        self.started = True

    def read(self, timeout: float = 1.0) -> array:
        if self.frames:
            return self.frames.popleft()
        if self.stopped.wait(timeout):
            raise queue.Empty
        raise queue.Empty

    def stop(self) -> None:
        self.stopped.set()


def _voice_test_frames() -> list[array]:
    wake_audio = [array("f", [0.002] * 4000) for _ in range(12)]
    command_audio = [array("f", [0.02] * 4000) for _ in range(4)]
    silence = [array("f", [0.0] * 4000) for _ in range(5)]
    return wake_audio + command_audio + silence


def _make_service(command_text: str) -> tuple[VoiceService, FakeDeviceService, FakeRecognizer]:
    device_service = FakeDeviceService()
    recognizer = FakeRecognizer(command_text)
    capture = FakeCapture(_voice_test_frames())
    service = VoiceService(
        device_service_instance=device_service,
        registry=FakeRegistry(),
        speech_recognizer=recognizer,
        capture_factory=lambda: capture,
    )
    return service, device_service, recognizer


def _wait_for_history(service: VoiceService) -> list[dict[str, object]]:
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        history = service.get_history()
        if history:
            return history
        time.sleep(0.01)
    return []


def test_voice_listener_requires_explicit_enable(monkeypatch) -> None:
    monkeypatch.setattr(settings, "VOICE_ENABLED", False)
    service, _, recognizer = _make_service("Turn on the living room light")

    try:
        service.start()
    except VoiceServiceDisabledError:
        pass
    else:
        raise AssertionError("Starting a disabled voice listener must fail.")

    assert recognizer.loaded is False


def test_microphone_start_failure_is_reported_in_service_status(monkeypatch) -> None:
    monkeypatch.setattr(settings, "VOICE_ENABLED", True)

    class FailingCapture:
        device_name = None

        def start(self) -> None:
            raise RuntimeError("no input device")

        def stop(self) -> None:
            pass

    recognizer = FakeRecognizer("Turn on the living room light")
    service = VoiceService(
        speech_recognizer=recognizer,
        capture_factory=FailingCapture,
    )

    with pytest.raises(VoiceServiceUnavailableError, match="no input device"):
        service.start()

    status = service.get_status()
    assert status["state"] == "ERROR"
    assert status["microphone_available"] is False
    assert status["last_error"] == "no input device"
    assert recognizer.loaded is False


def test_live_voice_command_executes_through_device_service(monkeypatch) -> None:
    monkeypatch.setattr(settings, "VOICE_ENABLED", True)
    monkeypatch.setattr(settings, "VOICE_AUTO_EXECUTE", True)
    monkeypatch.setattr(settings, "WAKE_WORDS", "hey berry")
    monkeypatch.setattr(settings, "WAKE_CHUNK_SECONDS", 3.0)
    monkeypatch.setattr(settings, "AUDIO_BLOCK_SECONDS", 0.25)
    monkeypatch.setattr(settings, "AUDIO_SAMPLE_RATE", 16000)
    monkeypatch.setattr(settings, "AUDIO_SILENCE_THRESHOLD", 0.005)
    monkeypatch.setattr(settings, "COMMAND_MIN_DURATION", 0.4)
    monkeypatch.setattr(settings, "COMMAND_SILENCE_DURATION", 1.2)
    monkeypatch.setattr(settings, "COMMAND_START_TIMEOUT_SECONDS", 5.0)
    monkeypatch.setattr(settings, "COMMAND_MAX_DURATION", 15.0)
    monkeypatch.setattr(settings, "WAKE_DETECTION_INTERVAL_SECONDS", 0.01)
    monkeypatch.setattr(settings, "WAKE_WORD_COOLDOWN_SECONDS", 0.0)

    service, device_service, recognizer = _make_service(
        "Turn on the living room light"
    )
    try:
        started = service.start()
        assert started["state"] == "WAITING_WAKE_WORD"
        assert service.start()["message"] == "Voice listener is already running."

        history = _wait_for_history(service)
        assert history
        assert history[0]["recognized_text"] == "Turn on the living room light"
        assert history[0]["accepted"], f"Unexpected command result: {history[0]!r}"
        assert history[0]["intent"] == "LIGHT_ON"
        assert history[0]["device_id"] == "light"
        assert history[0]["execution_status"] == "succeeded"
        assert device_service.calls == [("light", True)]
        assert recognizer.transcription_count == 2
    finally:
        service.stop()

    assert service.get_status()["state"] == "STOPPED"
    assert recognizer.loaded is False


def test_live_voice_negation_never_executes(monkeypatch) -> None:
    monkeypatch.setattr(settings, "VOICE_ENABLED", True)
    monkeypatch.setattr(settings, "VOICE_AUTO_EXECUTE", True)
    monkeypatch.setattr(settings, "WAKE_WORDS", "hey berry")
    monkeypatch.setattr(settings, "WAKE_CHUNK_SECONDS", 3.0)
    monkeypatch.setattr(settings, "AUDIO_BLOCK_SECONDS", 0.25)
    monkeypatch.setattr(settings, "AUDIO_SAMPLE_RATE", 16000)
    monkeypatch.setattr(settings, "AUDIO_SILENCE_THRESHOLD", 0.005)
    monkeypatch.setattr(settings, "COMMAND_MIN_DURATION", 0.4)
    monkeypatch.setattr(settings, "COMMAND_SILENCE_DURATION", 1.2)
    monkeypatch.setattr(settings, "COMMAND_START_TIMEOUT_SECONDS", 5.0)
    monkeypatch.setattr(settings, "COMMAND_MAX_DURATION", 15.0)
    monkeypatch.setattr(settings, "WAKE_DETECTION_INTERVAL_SECONDS", 0.01)
    monkeypatch.setattr(settings, "WAKE_WORD_COOLDOWN_SECONDS", 0.0)

    service, device_service, _ = _make_service(
        "Don't turn on the living room light"
    )
    try:
        service.start()
        history = _wait_for_history(service)
        assert history
        assert history[0]["reason"] == "NEGATION_DETECTED"
        assert history[0]["execution_status"] == "rejected"
        assert device_service.calls == []
    finally:
        service.stop()
