
import atexit
import threading

from gpiozero import DigitalOutputDevice, PWMOutputDevice
from app.devices.base import BaseDevice

ENB_PIN = 25
IN3_PIN = 23
IN4_PIN = 24

PWM_FREQUENCY = 1000

SPEED_LEVELS = {
    0: 0.00,
    1: 0.55,
    2: 0.75,
    3: 1.00,
}


class L298NFan(BaseDevice):
    def __init__(
        self,
        device_id="fan",
        name="Fan",
        room="Bedroom",
    ):
        super().__init__(device_id, name, room)

        self._lock = threading.RLock()

        self._in3 = DigitalOutputDevice(
            IN3_PIN, initial_value=False
        )

        try:
            self._in4 = DigitalOutputDevice(
                IN4_PIN, initial_value=False
            )
        except Exception:
            self._in3.close()
            raise

        try:
            self._enb = PWMOutputDevice(
                ENB_PIN,
                frequency=PWM_FREQUENCY,
                initial_value=0,
            )
        except Exception:
            self._in4.close()
            self._in3.close()
            raise

        self.speed_level = 0
        self.is_on = False

    def set_level(self, level: int):
        if type(level) is not int or level not in SPEED_LEVELS:
            raise ValueError("Invalid fan level")

        with self._lock:
            self._enb.value = 0

            if level == 0:
                self._in3.off()
                self._in4.off()
            else:
                self._in4.off()
                self._in3.on()
                self._enb.value = SPEED_LEVELS[level]

            self.speed_level = level
            self.is_on = level > 0

            print(
                f"Fan level: {level}, "
                f"PWM: {SPEED_LEVELS[level] * 100:.0f}%"
            )

    def turn_on(self):
        self.set_level(1)

    def turn_off(self):
        self.set_level(0)

    def get_status(self):
        with self._lock:
            status = super().get_status()

            status["is_on"] = self.is_on
            status["speed_level"] = self.speed_level
            status["speed_percent"] = int(
                SPEED_LEVELS[self.speed_level] * 100
            )

            return status

    def close(self):
        with self._lock:
            self._enb.value = 0
            self._in3.off()
            self._in4.off()

            self.speed_level = 0
            self.is_on = False

            self._enb.close()
            self._in3.close()
            self._in4.close()


_fan_instance = None
_fan_lock = threading.Lock()


def get_fan_device():
    global _fan_instance

    with _fan_lock:
        if _fan_instance is None:
            _fan_instance = L298NFan()
            atexit.register(_fan_instance.close)

        return _fan_instance


if __name__ == "__main__":
    fan = get_fan_device()

    try:
        while True:
            value = input(
                "Fan level [0/1/2/3/q]: "
            ).strip().lower()

            if value == "q":
                break

            if value not in ("0", "1", "2", "3"):
                print("Invalid level")
                continue

            fan.set_level(int(value))

    except KeyboardInterrupt:
        pass

    finally:
        fan.turn_off()
