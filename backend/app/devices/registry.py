from app.devices.mock_device import MockDevice


class DeviceRegistry:
    def __init__(self) -> None:
        self.devices: dict[str, MockDevice] = {
            "light": MockDevice("light", "Đèn", "Phòng khách"),
            "door": MockDevice("door", "Cửa", "Phòng khách"),
            "light_bed": MockDevice("light_bed", "Đèn ngủ", "Phòng ngủ"),
            "fan": MockDevice("fan", "Quạt", "Phòng ngủ"),
        }
        self.legacy_ids = {
            "living_room_light": "light",
            "bedroom_fan": "fan",
        }

    def get_all(self) -> list[MockDevice]:
        return list(self.devices.values())

    def get(self, device_id: str) -> MockDevice | None:
        canonical_id = self.legacy_ids.get(device_id, device_id)
        return self.devices.get(canonical_id)

    def list_devices(self) -> list[dict[str, object]]:
        return [device.get_status() for device in self.get_all()]


device_registry = DeviceRegistry()

