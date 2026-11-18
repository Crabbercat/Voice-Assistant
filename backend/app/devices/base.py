from abc import ABC, abstractmethod


class BaseDevice(ABC):
    def __init__(self, device_id: str, name: str, room: str = "Nhà") -> None:
        self.device_id = device_id
        self.name = name
        self.room = room
        self.is_on = False

    @abstractmethod
    def turn_on(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def turn_off(self) -> None:
        raise NotImplementedError

    def get_status(self) -> dict[str, object]:
        return {
            "device_id": self.device_id,
            "name": self.name,
            "room": self.room,
            "is_on": self.is_on,
        }
