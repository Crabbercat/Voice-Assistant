from pydantic import BaseModel


class DeviceStateRequest(BaseModel):
    is_on: bool


class DeviceResponse(BaseModel):
    device_id: str
    name: str
    room: str
    is_on: bool
