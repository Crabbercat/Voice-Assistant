
import logging

from app.devices.base import BaseDevice

logger = logging.getLogger(__name__)

# Cau hinh servo
SERVO_PIN = 27
DOOR_OPEN_ANGLE = 120
DOOR_CLOSE_ANGLE = 0


class ServoDoor(BaseDevice):
    def __init__(
        self,
        device_id: str = "door",
        name: str = "Cửa",
        room: str = "Phòng khách",
    ) -> None:
        super().__init__(device_id, name, room)

        # Chi import khi chay phan cung that tren Pi
        from gpiozero import AngularServo

        self._servo = AngularServo(
            SERVO_PIN,
            min_angle=0,
            max_angle=180,
            min_pulse_width=0.0009,
            max_pulse_width=0.0021,
            initial_angle=None,
        )

        # Trang thai ban dau cua app
        # Chua co cam bien xac nhan vi tri cua
        self.is_on = False

        logger.info(
            "Da khoi tao servo cua tai GPIO%d",
            SERVO_PIN,
        )

    def turn_on(self) -> None:
        # Mo cua
        self._servo.angle = DOOR_OPEN_ANGLE
        self.is_on = True
        logger.info("GUI LENH MO CUA - 90 DO")

    def turn_off(self) -> None:
        # Dong cua
        self._servo.angle = DOOR_CLOSE_ANGLE
        self.is_on = False
        logger.info("GUI LENH DONG CUA - 0 DO")

    def close(self) -> None:
        self._servo.close()
