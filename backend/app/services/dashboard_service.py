from app.schemas.dashboard import DashboardResponse, SensorReadings
from app.services.device_service import device_service


class DashboardService:
    def get_dashboard(self) -> DashboardResponse:
        return DashboardResponse(
            devices=device_service.get_devices(),
            sensors=SensorReadings(),
            last_action=device_service.last_action,
        )


dashboard_service = DashboardService()
