from app.devices.base import BaseDevice


class MockDevice(BaseDevice):
    def turn_on(self) -> None:
        self.is_on = True

    def turn_off(self) -> None:
        self.is_on = False
