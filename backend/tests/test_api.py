import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.device_service import device_service
from app.services.voice_service import voice_service

client = TestClient(app)


def test_root() -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert response.json()["message"] == "Welcome to VietHome AI"


def test_health() -> None:
    response = client.get("/health/")

    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_get_devices() -> None:
    response = client.get("/devices/")

    assert response.status_code == 200
    assert len(response.json()) >= 1


def test_turn_on_device() -> None:
    response = client.post("/devices/living_room_light/state", json={"is_on": True})

    assert response.status_code == 200
    assert response.json()["is_on"] is True


def test_dashboard_returns_devices_and_unavailable_sensors() -> None:
    action_response = client.post("/devices/door/state", json={"is_on": True})
    assert action_response.status_code == 200

    response = client.get("/dashboard")

    assert response.status_code == 200
    dashboard = response.json()
    assert {device["device_id"] for device in dashboard["devices"]} == {
        "light",
        "door",
        "light_bed",
        "fan",
    }
    assert dashboard["sensors"] == {"temperature": None, "humidity": None}
    assert dashboard["last_action"] == "Mở Cửa"

    reset_response = client.post("/devices/door/state", json={"is_on": False})
    assert reset_response.status_code == 200


@pytest.mark.parametrize("device_id", ["light", "door", "light_bed", "fan"])
def test_control_supported_device(device_id: str) -> None:
    response = client.post(f"/devices/{device_id}/state", json={"is_on": True})

    assert response.status_code == 200
    assert response.json()["is_on"] is True

    reset_response = client.post(f"/devices/{device_id}/state", json={"is_on": False})
    assert reset_response.status_code == 200
    assert reset_response.json()["is_on"] is False


def test_text_command_preview_requires_confirmation(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, bool]] = []
    original = device_service.set_device_state

    def track_execution(device_id: str, is_on: bool) -> dict[str, object]:
        calls.append((device_id, is_on))
        return original(device_id, is_on)

    monkeypatch.setattr(device_service, "set_device_state", track_execution)
    original("light", False)
    calls.clear()

    response = client.post(
        "/api/voice/process",
        json={"text": "Turn on the living room light"},
    )

    assert response.status_code == 200
    result = response.json()
    assert result["accepted"] is True
    assert result["intent"] == "LIGHT_ON"
    assert result["device_id"] == "light"
    assert result["action"] == "turn_on"
    assert result["execution_status"] == "needs_confirmation"
    assert result["confidence"] >= result["threshold"]
    assert calls == []


def test_text_command_executes_only_after_explicit_confirmation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, bool]] = []
    original = device_service.set_device_state

    def track_execution(device_id: str, is_on: bool) -> dict[str, object]:
        calls.append((device_id, is_on))
        return original(device_id, is_on)

    monkeypatch.setattr(device_service, "set_device_state", track_execution)
    response = client.post(
        "/api/voice/process",
        json={"text": "Turn on the living room light", "execute": True},
    )

    assert response.status_code == 200
    result = response.json()
    assert result["execution_status"] == "succeeded"
    assert result["execution"]["success"] is True
    assert calls == [("light", True)]

    original("light", False)


@pytest.mark.parametrize(
    ("text", "reason"),
    [
        ("Tắt quạt phòng ngủ", "MATCH_ACCEPTED"),
        ("Bật đèn", "AMBIGUOUS_TARGET"),
        ("Không bật đèn", "NEGATION_DETECTED"),
        ("Bật đèn phòng khách hay tắt đèn?", "AMBIGUOUS_COMMAND"),
        ("Bật đèn phòng bếp", "TARGET_NOT_FOUND"),
        ("Turn off the bedroom fan", "MATCH_ACCEPTED"),
        ("Turn on the light", "AMBIGUOUS_TARGET"),
        ("Don't turn on the light", "NEGATION_DETECTED"),
        ("Turn on the living room light or turn it off", "AMBIGUOUS_COMMAND"),
        ("Turn on the kitchen light", "TARGET_NOT_FOUND"),
    ],
)
def test_text_command_validation(text: str, reason: str) -> None:
    response = client.post(
        "/api/voice/process",
        json={"text": text, "execute": True},
    )

    assert response.status_code == 200
    result = response.json()
    assert result["reason"] == reason
    if reason != "MATCH_ACCEPTED":
        assert result["execution_status"] == "rejected"


def test_transcribe_wav_returns_command_preview_without_execution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeRecognizer:
        def transcribe(self, audio: bytes) -> dict[str, object]:
            return {
                "recognized_text": "Turn on the living room light",
                "language": "vi",
                "language_probability": 0.97,
                "duration_seconds": 1.0,
            }

    calls: list[tuple[str, bool]] = []
    original = device_service.set_device_state

    def track_execution(device_id: str, is_on: bool) -> dict[str, object]:
        calls.append((device_id, is_on))
        return original(device_id, is_on)

    monkeypatch.setattr(voice_service, "speech_recognizer", FakeRecognizer())
    monkeypatch.setattr(device_service, "set_device_state", track_execution)
    wav = b"RIFF\x00\x00\x00\x00WAVE"

    response = client.post(
        "/api/voice/transcribe",
        content=wav,
        headers={"content-type": "audio/wav"},
    )

    assert response.status_code == 200
    result = response.json()
    assert result["recognized_text"] == "Turn on the living room light"
    assert result["command"]["intent"] == "LIGHT_ON"
    assert result["command"]["execution_status"] == "needs_confirmation"
    assert calls == []


def test_transcribe_rejects_non_wav_content() -> None:
    response = client.post(
        "/api/voice/transcribe",
        content=b"not audio",
        headers={"content-type": "audio/wav"},
    )

    assert response.status_code == 400
