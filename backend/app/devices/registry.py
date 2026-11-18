
from app.core.config import settings
from app.devices.base import BaseDevice
from app.devices.mock_device import MockDevice


class DeviceRegistry:
    def __init__(self) -> None:

        # Cua: gia lap tren laptop,
        # servo that tren Raspberry Pi.
        if settings.MOCK_HARDWARE:
            door: BaseDevice = MockDevice(
                "door", "Cửa", "Phòng khách"
            )
        else:
            from app.devices.servo_door import ServoDoor

            door = ServoDoor(
                "door", "Cửa", "Phòng khách"
            )

        # Dang ky cac thiet bi
        self.devices: dict[str, BaseDevice] = {
            "light": MockDevice(
                "light", "Đèn", "Phòng khách"
            ),
            "door": door,
            "light_bed": MockDevice(
                "light_bed", "Đèn ngủ", "Phòng ngủ"
            ),
            "fan": MockDevice(
                "fan", "Quạt", "Phòng ngủ"
            ),
        }

        # Ho tro ten thiet bi cu
        self.legacy_ids = {
            "living_room_light": "light",
            "bedroom_fan": "fan",
        }

    def get_all(self) -> list[BaseDevice]:
        return list(self.devices.values())

    def get(self, device_id: str) -> BaseDevice | None:
        canonical_id = self.legacy_ids.get(
            device_id, device_id
        )
        return self.devices.get(canonical_id)

    def list_devices(self) -> list[dict[str, object]]:
        return [
            device.get_status()
            for device in self.get_all()
        ]


device_registry = DeviceRegistry()
