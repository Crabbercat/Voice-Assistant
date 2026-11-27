from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.services.voice_service import VoiceServiceUnavailableError, voice_service

client = TestClient(app)


def test_voice_status_reports_disabled_stopped_state(monkeypatch) -> None:
    monkeypatch.setattr(settings, "VOICE_ENABLED", False)

    response = client.get("/api/voice/status")

    assert response.status_code == 200
    result = response.json()
    assert result["enabled"] is False
    assert result["running"] is False
    assert result["state"] == "STOPPED"
    assert result["microphone_available"] is False


def test_voice_start_requires_opt_in(monkeypatch) -> None:
    monkeypatch.setattr(settings, "VOICE_ENABLED", False)

    response = client.post("/api/voice/start")

    assert response.status_code == 409
    assert "VOICE_ENABLED=true" in response.json()["detail"]


def test_voice_start_returns_service_error_for_unavailable_microphone(
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "VOICE_ENABLED", True)

    def fail_to_start() -> dict[str, object]:
        raise VoiceServiceUnavailableError("No input device.")

    monkeypatch.setattr(voice_service, "start", fail_to_start)
    response = client.post("/api/voice/start")

    assert response.status_code == 503
    assert response.json()["detail"] == "No input device."


def test_voice_history_validates_limit() -> None:
    response = client.get("/api/voice/history?limit=0")

    assert response.status_code == 422
