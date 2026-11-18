from app.devices.registry import device_registry


class DeviceService:
    def __init__(self) -> None:
        self.last_action: str | None = None

    def get_devices(self) -> list[dict[str, object]]:
        return [device.get_status() for device in device_registry.get_all()]

    def set_device_state(self, device_id: str, is_on: bool) -> dict[str, object]:
        device = device_registry.get(device_id)
        if device is None:
            raise ValueError(f"Device not found: {device_id}")

        if is_on:
            device.turn_on()
        else:
            device.turn_off()

        verb = ("Mở" if is_on else "Đóng") if device_id == "door" else ("Bật" if is_on else "Tắt")
        self.last_action = f"{verb} {device.name}"
        return device.get_status()


device_service = DeviceService()
