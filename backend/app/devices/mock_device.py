
import logging
import threading
import time

from app.core.config import settings
from app.devices.base import BaseDevice

logger = logging.getLogger(__name__)

# GPIO theo chuẩn BCM
DHT_PIN = 4
LED_PIN = 18

# Dữ liệu cảm biến
_sensor_lock = threading.Lock()
_dht = None
_last_read_time = None
_last_success_time = None
_temperature = None
_humidity = None

READ_INTERVAL = 2.5
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

        # Chỉ thiết bị "light" dùng GPIO18.
        # Các thiết bị còn lại giữ nguyên chế độ mock.
        if device_id == "light" and not settings.MOCK_HARDWARE:
            from gpiozero import LED

            self._led = LED(
                LED_PIN,
                active_high=True,
                initial_value=False
            )

            self.is_on = self._led.is_lit
            logger.info("LED khoi tao tai GPIO%d", LED_PIN)

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
    """
    Doc DHT11 tai GPIO4.

    Tra ve:
        (temperature, humidity)

    Trong che do mock:
        (None, None)
    """
    global _dht
    global _last_read_time
    global _last_success_time
    global _temperature
    global _humidity

    if settings.MOCK_HARDWARE:
        return None, None

    with _sensor_lock:
        now = time.monotonic()

        # Không đọc DHT11 liên tục
        if (
            _last_read_time is not None
            and now - _last_read_time < READ_INTERVAL
        ):
            return _get_cached_sensor(now)

        _last_read_time = now

        try:
            # Chỉ khởi tạo một lần
            if _dht is None:
                import board
                import adafruit_dht

                _dht = adafruit_dht.DHT11(
                    board.D4,
                    use_pulseio=False
                )

                logger.info(
                    "DHT11 khoi tao tai GPIO%d",
                    DHT_PIN
                )

            temperature = _dht.temperature
            humidity = _dht.humidity

            if temperature is None or humidity is None:
                raise RuntimeError(
                    "DHT11 chua tra ve du lieu"
                )

            _temperature = float(temperature)
            _humidity = float(humidity)
            _last_success_time = now

        except RuntimeError as error:
            # DHT11 thường có lỗi đọc tạm thời
            logger.warning("DHT11: %s", error)

        except Exception:
            logger.exception("Loi doc cam bien DHT11")

        return _get_cached_sensor(now)


def _get_cached_sensor(now):
    # Không hiển thị số đo quá cũ
    if (
        _last_success_time is None
        or now - _last_success_time > MAX_DATA_AGE
    ):
        return None, None

    return _temperature, _humidity
