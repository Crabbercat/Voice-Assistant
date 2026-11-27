import logging
import math
import queue
from array import array
from typing import Any

logger = logging.getLogger(__name__)


class MicrophoneUnavailableError(RuntimeError):
    """Raised when an input device cannot be opened for audio capture."""


class MicrophoneCapture:
    def __init__(
        self,
        sample_rate: int = 16000,
        input_device: str | None = None,
        block_seconds: float = 0.25,
        queue_size: int = 16,
    ) -> None:
        self.sample_rate = sample_rate
        self.input_device = self._parse_device(input_device)
        self.block_seconds = block_seconds
        self._chunks: queue.Queue[array] = queue.Queue(maxsize=queue_size)
        self._stream: Any | None = None
        self._sounddevice: Any | None = None
        self._source_sample_rate = sample_rate
        self.device_name: str | None = None

    @staticmethod
    def _parse_device(device: str | None) -> int | str | None:
        if device is None or not device.strip():
            return None
        device = device.strip()
        if device.isdecimal():
            return int(device)
        return device

    def start(self) -> None:
        try:
            import sounddevice as sd
        except ImportError as error:
            raise MicrophoneUnavailableError(
                "Install microphone dependencies with "
                "'pip install -r backend/requirements/voice.txt'."
            ) from error

        self._sounddevice = sd
        try:
            device_info = sd.query_devices(
                device=self.input_device,
                kind="input",
            )
        except Exception as error:
            raise MicrophoneUnavailableError(
                f"Could not find microphone input device "
                f"{self.input_device!r}: {error}"
            ) from error

        if device_info["max_input_channels"] < 1:
            raise MicrophoneUnavailableError(
                f"Audio device '{device_info['name']}' has no input channels."
            )

        self.device_name = str(device_info["name"])
        native_rate = int(device_info["default_samplerate"])
        sample_rates = [self.sample_rate]
        if native_rate != self.sample_rate:
            sample_rates.append(native_rate)

        last_error: Exception | None = None
        for sample_rate in sample_rates:
            stream: Any | None = None
            try:
                self._source_sample_rate = sample_rate
                block_size = max(1, math.ceil(sample_rate * self.block_seconds))
                stream = sd.InputStream(
                    device=self.input_device,
                    channels=1,
                    samplerate=sample_rate,
                    blocksize=block_size,
                    dtype="float32",
                    callback=self._audio_callback,
                )
                stream.start()
                self._stream = stream
                if sample_rate != self.sample_rate:
                    logger.info(
                        "Microphone %s uses %s Hz; resampling to %s Hz",
                        self.device_name,
                        sample_rate,
                        self.sample_rate,
                    )
                return
            except Exception as error:
                last_error = error
                if stream is not None:
                    try:
                        stream.close()
                    except Exception:
                        logger.exception("Could not close failed microphone stream")

        raise MicrophoneUnavailableError(
            f"Could not open microphone '{self.device_name}' at "
            f"{self.sample_rate} Hz or its native {native_rate} Hz rate: "
            f"{last_error}"
        ) from last_error

    def _audio_callback(
        self,
        input_data: Any,
        frame_count: int,
        time_info: Any,
        status: Any,
    ) -> None:
        del frame_count, time_info
        if status:
            logger.warning("Microphone stream status: %s", status)

        chunk = array("f", (float(value) for value in input_data[:, 0]))
        try:
            self._chunks.put_nowait(chunk)
        except queue.Full:
            try:
                self._chunks.get_nowait()
            except queue.Empty:
                pass
            try:
                self._chunks.put_nowait(chunk)
            except queue.Full:
                logger.warning("Dropping microphone audio chunk from full queue.")

    def read(self, timeout: float = 1.0) -> array:
        chunk = self._chunks.get(timeout=timeout)
        if self._source_sample_rate == self.sample_rate:
            return chunk

        try:
            import numpy as np
            from scipy.signal import resample_poly
        except ImportError as error:
            raise MicrophoneUnavailableError(
                "Install numpy and scipy to resample microphone audio."
            ) from error

        divisor = math.gcd(self._source_sample_rate, self.sample_rate)
        resampled = resample_poly(
            np.asarray(chunk, dtype=np.float32),
            self.sample_rate // divisor,
            self._source_sample_rate // divisor,
        )
        return array("f", (float(value) for value in resampled))

    def stop(self) -> None:
        stream = self._stream
        self._stream = None
        if stream is None:
            return
        try:
            stream.stop()
        finally:
            stream.close()
