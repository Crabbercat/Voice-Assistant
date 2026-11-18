import pytest
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
