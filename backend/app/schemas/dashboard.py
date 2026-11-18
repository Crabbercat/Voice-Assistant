from pydantic import BaseModel

from app.schemas.device import DeviceResponse


class SensorReadings(BaseModel):
    temperature: float | None = None
    humidity: float | None = None


class DashboardResponse(BaseModel):
    devices: list[DeviceResponse]
    sensors: SensorReadings
    last_action: str | None = None
