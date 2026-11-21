
import logging
import threading
import time

from dht_pi import Sensor, DHT11
from app.core.config import settings
from app.devices.base import BaseDevice

logger = logging.getLogger(__name__)

DHT_PIN = 4
LED_PIN = 18
BED_LED_PIN = 22

_sensor_lock = threading.Lock()
_dht = None
_last_read_time = None
_last_success_time = None
_temperature = None
_humidity = None

READ_INTERVAL = 3.0
MAX_DATA_AGE = 15.0


class MockDevice(BaseDevice):
    def __init__(
        self,
        device_id: str,
        name: str,
        room: str = "Nhà"
    ) -> None:
        super().__init__(device_id, name, room)

        self._led = None

        led_pins = {
            "light": LED_PIN,
            "light_bed": BED_LED_PIN,
        }

        if device_id in led_pins and not settings.MOCK_HARDWARE:
            from gpiozero import LED

            pin = led_pins[device_id]

            self._led = LED(
                pin,
                active_high=True,
                initial_value=False
            )

            self.is_on = self._led.is_lit

            logger.info(
                "Initialized %s on GPIO%d",
                device_id,
                pin
            )

    def turn_on(self) -> None:
        if self._led is not None:
            self._led.on()
            self.is_on = self._led.is_lit
        else:
            self.is_on = True

    def turn_off(self) -> None:
        if self._led is not None:
            self._led.off()
            self.is_on = self._led.is_lit
        else:
            self.is_on = False

    def get_status(self) -> dict[str, object]:
        if self._led is not None:
            self.is_on = self._led.is_lit

        return super().get_status()


def read_temperature_humidity():
    global _dht
    global _last_read_time
    global _last_success_time
    global _temperature
    global _humidity

    if settings.MOCK_HARDWARE:
        return None, None

    with _sensor_lock:
        now = time.monotonic()

        if (
            _last_read_time is not None
            and now - _last_read_time < READ_INTERVAL
        ):
            return _get_cached_sensor(now)

        _last_read_time = now

        try:
            if _dht is None:
                _dht = Sensor(DHT11, DHT_PIN)

                logger.info(
                    "DHT11 initialized on GPIO%d",
                    DHT_PIN
                )

            reading = _dht.read()

            if reading is None:
                logger.warning("DHT11 read failed")
                return _get_cached_sensor(now)

            temperature = reading.temperature
            humidity = reading.humidity

            if temperature is None or humidity is None:
                logger.warning("DHT11 returned no data")
                return _get_cached_sensor(now)

            _temperature = float(temperature)
            _humidity = float(humidity)
            _last_success_time = time.monotonic()

            logger.info(
                "Temperature: %.1f C | Humidity: %.1f %%",
                _temperature,
                _humidity
            )

        except Exception:
            logger.exception("DHT11 sensor error")

        return _get_cached_sensor(time.monotonic())


def _get_cached_sensor(now):
    if (
        _last_success_time is None
        or now - _last_success_time > MAX_DATA_AGE
    ):
        return None, None

    return _temperature, _humidity
