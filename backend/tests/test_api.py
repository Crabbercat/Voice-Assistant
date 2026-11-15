from fastapi.testclient import TestClient

from app.main import app

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
