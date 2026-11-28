from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.services.device_service import device_service
from app.ai.tts.service import voice_response_service
from app.services.voice_service import voice_service

client = TestClient(app)


def test_voice_response_status_is_available_without_audio_hardware() -> None:
    response = client.get("/api/voice/response/status")

    assert response.status_code == 200
    result = response.json()
    assert result["playback_mode"] == "server"
    assert result["is_playing"] is False
    assert "lights.turned_on" in result["static_response_keys"]
    assert result["audio_output_available"] in (True, False)


def test_voice_monitor_localhost_origin_is_allowed() -> None:
    response = client.options(
        "/api/voice/status",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_voice_debug_endpoint_returns_listener_diagnostics(monkeypatch) -> None:
    expected = [{"stage": "wake_window", "text": "Hey Berry"}]
    monkeypatch.setattr(
        voice_service,
        "get_debug_log",
        lambda limit: expected if limit == 1 else [],
    )

    response = client.get("/api/voice/debug?limit=1")

    assert response.status_code == 200
    assert response.json() == expected


def test_static_response_endpoint_rejects_unknown_key() -> None:
    response = client.post("/api/voice/response/play/unknown.key")

    assert response.status_code == 404


def test_known_static_response_returns_controlled_missing_output_result(
    monkeypatch,
) -> None:
    def unavailable_output(frames: bytes, sample_rate: int) -> None:
        raise RuntimeError("Speaker unavailable for test.")

    monkeypatch.setattr(
        voice_response_service.static_player,
        "_playback",
        unavailable_output,
    )
    response = client.post("/api/voice/response/play/common.ready")

    assert response.status_code == 200
    result = response.json()
    assert result["response_key"] == "common.ready"
    assert result["audio_played"] is False
    assert result["status"] == "unavailable"
    assert "audio output" in result["error"].lower()


def test_sensor_summary_uses_current_dashboard_readings(
    monkeypatch,
) -> None:
    class FakeTTS:
        spoken: list[str] = []

        def speak(self, text: str) -> None:
            self.spoken.append(text)

    fake_tts = FakeTTS()
    monkeypatch.setattr(settings, "VOICE_RESPONSE_ENABLED", True)
    monkeypatch.setattr(settings, "VOICE_TTS_ENABLED", True)
    monkeypatch.setattr(voice_response_service, "tts_provider", fake_tts)
    monkeypatch.setattr(
        voice_response_service,
        "sensor_source",
        SimpleNamespace(
            get_dashboard=lambda: SimpleNamespace(
                sensors=SimpleNamespace(temperature=28.6, humidity=75)
            )
        ),
    )
    response = client.post("/api/voice/response/sensors/summary")

    assert response.status_code == 200
    result = response.json()
    assert result["response_mode"] == "tts"
    assert result["audio_played"] is True
    assert result["text"] == (
        "Nhiệt độ hiện tại là 28 phẩy 6 độ C, độ ẩm là 75 phần trăm."
    )
    assert result["data"] == {"temperature": 28.6, "humidity": 75.0}
    assert fake_tts.spoken == [result["text"]]


def test_bulk_device_endpoint_returns_operation_details_and_response() -> None:
    response = client.post("/devices/state/all", json={"is_on": True})

    assert response.status_code == 200
    result = response.json()
    assert result["success"] is True
    assert result["partial"] is False
    assert len(result["results"]) == len(device_service.get_devices())
    assert result["voice_response"]["response_key"] == "devices.all_turned_on"

    reset = client.post("/devices/state/all", json={"is_on": False})
    assert reset.status_code == 200


def test_failed_device_route_returns_unavailable_voice_response(
    monkeypatch,
) -> None:
    def fail_device(device_id: str, is_on: bool) -> dict[str, object]:
        raise ValueError(f"Device not found: {device_id}")

    monkeypatch.setattr(device_service, "set_device_state", fail_device)
    response = client.post(
        "/devices/not-a-device/state",
        json={"is_on": True},
    )

    assert response.status_code == 404
    result = response.json()
    assert result["voice_response"]["response_key"] == "common.device_unavailable"
    assert result["voice_response"]["audio_played"] is False


def test_mock_fan_speed_transition_returns_voice_response() -> None:
    off_response = client.post("/devices/fan/speed", json={"level": 0})
    assert off_response.status_code == 200

    on_response = client.post("/devices/fan/speed", json={"level": 2})

    assert on_response.status_code == 200
    result = on_response.json()
    assert result["is_on"] is True
    assert result["voice_response"]["response_key"] == "fans.turned_on"

    reset = client.post("/devices/fan/speed", json={"level": 0})
    assert reset.status_code == 200
