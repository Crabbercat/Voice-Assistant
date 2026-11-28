
from app.schemas.dashboard import (
    DashboardResponse,
    SensorReadings,
)

from app.services.device_service import device_service

from app.devices.mock_device import (
    get_temperature_humidity_status,
    read_temperature_humidity,
)


class DashboardService:
    def get_sensor_status(self) -> str:
        return get_temperature_humidity_status()

    def get_dashboard(self) -> DashboardResponse:

        # Lấy nhiệt độ, độ ẩm từ Raspberry Pi
        temperature, humidity = read_temperature_humidity()

        return DashboardResponse(
            devices=device_service.get_devices(),

            sensors=SensorReadings(
                temperature=temperature,
                humidity=humidity,
            ),

            last_action=device_service.last_action,
        )


dashboard_service = DashboardService()
