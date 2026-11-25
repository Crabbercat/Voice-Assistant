
import logging
import threading
import time

from app.core.config import settings
from app.devices.base import BaseDevice
from app.devices.l298n_fan import (
    get_fan_device,
    SPEED_LEVELS,
)

logger = logging.getLogger(__name__)

DHT_PIN = 4
LED_PIN = 18
BED_LED_PIN = 22

_sensor_lock = threading.Lock()
_sensor_start_lock = threading.Lock()
_sensor_started = False

_temperature = None
_humidity = None
_last_success = 0.0

READ_INTERVAL = 3.0
MAX_DATA_AGE = 15.0


def _sensor_worker():
    global _temperature
    global _humidity
    global _last_success

    sensor = None

    while True:
        try:
            if sensor is None:
                from dht_pi import Sensor, DHT11
                sensor = Sensor(DHT11, DHT_PIN)

            reading = sensor.read()

            if reading is not None:
                t = reading.temperature
                h = reading.humidity

                if t is not None and h is not None:
                    with _sensor_lock:
                        _temperature = float(t)
                        _humidity = float(h)
                        _last_success = time.monotonic()

        except Exception:
            logger.exception("DHT11 read error")

        time.sleep(READ_INTERVAL)


def read_temperature_humidity():
    global _sensor_started

    if settings.MOCK_HARDWARE:
        return None, None

    with _sensor_start_lock:
        if not _sensor_started:
            thread = threading.Thread(
                target=_sensor_worker,
                daemon=True,
                name="DHT11Worker",
            )

            thread.start()
            _sensor_started = True

    with _sensor_lock:
        age = time.monotonic() - _last_success

        if _last_success == 0 or age > MAX_DATA_AGE:
            return None, None

        return _temperature, _humidity


class MockDevice(BaseDevice):
    def __init__(
        self,
        device_id: str,
        name: str,
        room: str = "Home",
    ):
        super().__init__(device_id, name, room)

        self._led = None
        self._fan = None
        self._mock_fan_level = 0

        led_pins = {
            "light": LED_PIN,
            "light_bed": BED_LED_PIN,
        }

        if settings.MOCK_HARDWARE:
            return

        if device_id in led_pins:
            from gpiozero import LED

            pin = led_pins[device_id]

            self._led = LED(
                pin,
                active_high=True,
                initial_value=False,
            )

            self.is_on = self._led.is_lit

        elif device_id == "fan":
            self._fan = get_fan_device()
            self.is_on = self._fan.is_on

    def set_level(self, level: int):
        if self.device_id != "fan":
            raise ValueError("Device is not a fan")

        if type(level) is not int or level not in SPEED_LEVELS:
            raise ValueError("Invalid fan level")

        if self._fan is not None:
            self._fan.set_level(level)
            self.is_on = self._fan.is_on
        else:
            self._mock_fan_level = level
            self.is_on = level > 0

    def turn_on(self):
        if self.device_id == "fan":
            self.set_level(1)
        elif self._led is not None:
            self._led.on()
            self.is_on = self._led.is_lit
        else:
            self.is_on = True

    def turn_off(self):
        if self.device_id == "fan":
            self.set_level(0)
        elif self._led is not None:
            self._led.off()
            self.is_on = self._led.is_lit
        else:
            self.is_on = False

    def get_status(self):
        if self._led is not None:
            self.is_on = self._led.is_lit

        if self._fan is not None:
            self.is_on = self._fan.is_on

        status = super().get_status()

        if self.device_id == "fan":
            if self._fan is not None:
                level = self._fan.speed_level
            else:
                level = self._mock_fan_level

            status["is_on"] = level > 0
            status["speed_level"] = level
            status["speed_percent"] = int(
                SPEED_LEVELS[level] * 100
            )

        return status
