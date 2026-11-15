from app.devices.mock_device import MockDevice


class DeviceRegistry:
    def __init__(self) -> None:
        self.devices: dict[str, MockDevice] = {
            "living_room_light": MockDevice("living_room_light", "Living Room Light"),
            "bedroom_fan": MockDevice("bedroom_fan", "Bedroom Fan"),
        }

    def get_all(self) -> list[MockDevice]:
        return list(self.devices.values())

    def get(self, device_id: str) -> MockDevice | None:
        return self.devices.get(device_id)

    def list_devices(self) -> list[dict[str, object]]:
        return [device.get_status() for device in self.get_all()]


device_registry = DeviceRegistry()

