import logging

from app.devices.registry import device_registry

logger = logging.getLogger(__name__)


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

    def set_all_device_states(self, is_on: bool) -> dict[str, object]:
        results: list[dict[str, object]] = []
        for device in device_registry.get_all():
            try:
                status = self.set_device_state(device.device_id, is_on)
                succeeded = status.get("is_on") is is_on
                results.append(
                    {
                        "device_id": device.device_id,
                        "success": succeeded,
                        "device": status,
                        "error": None
                        if succeeded
                        else "Device did not reach the requested state.",
                    }
                )
            except Exception:
                logger.exception(
                    "Bulk device operation failed for %s",
                    device.device_id,
                )
                results.append(
                    {
                        "device_id": device.device_id,
                        "success": False,
                        "device": None,
                        "error": "Device operation failed.",
                    }
                )

        succeeded_count = sum(bool(result["success"]) for result in results)
        failed_count = len(results) - succeeded_count
        if succeeded_count == len(results) and results:
            self.last_action = f"{'Bật' if is_on else 'Tắt'} tất cả thiết bị"
        elif succeeded_count:
            self.last_action = f"{'Bật' if is_on else 'Tắt'} một số thiết bị"

        return {
            "success": bool(results) and failed_count == 0,
            "partial": succeeded_count > 0 and failed_count > 0,
            "is_on": is_on,
            "results": results,
        }


device_service = DeviceService()
