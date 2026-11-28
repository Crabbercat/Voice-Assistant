import json
import logging
import wave
from pathlib import Path, PurePosixPath, PureWindowsPath
from threading import RLock
from typing import Callable

from app.core.config import settings

logger = logging.getLogger(__name__)


class StaticAudioError(RuntimeError):
    """Raised when a registered static response cannot be played."""


class UnknownResponseKey(StaticAudioError):
    """Raised when a response key is not present in the manifest."""


class StaticAudioPlayer:
    def __init__(
        self,
        asset_dir: str | Path | None = None,
        playback: Callable[[bytes, int], None] | None = None,
    ) -> None:
        configured_dir = Path(asset_dir or settings.VOICE_STATIC_AUDIO_DIR)
        if not configured_dir.is_absolute():
            project_root = Path(__file__).resolve().parents[5]
            configured_dir = project_root / configured_dir
        self.asset_dir = configured_dir.resolve()
        self.manifest_path = self.asset_dir.parent / "manifest.json"
        self._playback = playback or self._play_with_sounddevice
        self._manifest: dict[str, object] | None = None
        self._manifest_lock = RLock()

    def _load_responses(self) -> dict[str, dict[str, str]]:
        with self._manifest_lock:
            if self._manifest is not None:
                responses = self._manifest.get("responses")
                if isinstance(responses, dict):
                    return responses  # type: ignore[return-value]

            try:
                document = json.loads(self.manifest_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as error:
                raise StaticAudioError(
                    "Could not read the voice response manifest."
                ) from error

            if (
                not isinstance(document, dict)
                or type(document.get("version")) is not int
                or document["version"] != 1
                or not isinstance(document.get("responses"), dict)
            ):
                raise StaticAudioError("Unsupported voice response manifest.")

            responses: dict[str, dict[str, str]] = {}
            for key, entry in document["responses"].items():
                if (
                    not isinstance(key, str)
                    or not isinstance(entry, dict)
                    or entry.get("type") != "static"
                    or not isinstance(entry.get("path"), str)
                    or not isinstance(entry.get("text"), str)
                    or not entry["text"].strip()
                ):
                    raise StaticAudioError(
                        "The voice response manifest contains an invalid entry."
                    )
                self._resolve_asset_path(entry["path"])
                responses[key] = entry

            self._manifest = document
            return responses

    def _resolve_asset_path(self, relative_path: str) -> Path:
        posix_path = PurePosixPath(relative_path)
        windows_path = PureWindowsPath(relative_path)
        if (
            not relative_path
            or "\\" in relative_path
            or posix_path.is_absolute()
            or windows_path.is_absolute()
            or windows_path.drive
            or ".." in posix_path.parts
        ):
            raise StaticAudioError("The manifest contains an unsafe audio path.")

        candidate = (self.asset_dir / Path(*posix_path.parts)).resolve()
        try:
            candidate.relative_to(self.asset_dir)
        except ValueError as error:
            raise StaticAudioError(
                "The manifest contains an unsafe audio path."
            ) from error
        return candidate

    def get_entry(self, response_key: str) -> dict[str, str]:
        responses = self._load_responses()
        entry = responses.get(response_key)
        if entry is None:
            raise UnknownResponseKey(f"Unknown voice response key: {response_key}")
        return dict(entry)

    def response_keys(self) -> list[str]:
        return sorted(self._load_responses())

    def missing_assets(self) -> list[str]:
        responses = self._load_responses()
        return sorted(
            key
            for key, entry in responses.items()
            if not self._resolve_asset_path(entry["path"]).is_file()
        )

    def play(self, response_key: str) -> str:
        entry = self.get_entry(response_key)
        asset_path = self._resolve_asset_path(entry["path"])
        if not asset_path.is_file():
            raise StaticAudioError(
                f"No recording has been supplied for '{response_key}'."
            )

        try:
            with wave.open(str(asset_path), "rb") as audio_file:
                if (
                    audio_file.getcomptype() != "NONE"
                    or audio_file.getnchannels() != 1
                    or audio_file.getsampwidth() != 2
                    or audio_file.getframerate() != settings.AUDIO_SAMPLE_RATE
                ):
                    raise StaticAudioError(
                        f"Recording '{response_key}' must be mono, 16-bit PCM "
                        f"WAV at {settings.AUDIO_SAMPLE_RATE} Hz."
                    )
                frames = audio_file.readframes(audio_file.getnframes())
        except (OSError, wave.Error, EOFError) as error:
            raise StaticAudioError(
                f"Recording '{response_key}' is not a valid WAV file."
            ) from error

        if not frames:
            raise StaticAudioError(f"Recording '{response_key}' is empty.")

        try:
            self._playback(frames, settings.AUDIO_SAMPLE_RATE)
        except Exception as error:
            logger.exception("Static voice response playback failed: %s", response_key)
            raise StaticAudioError(
                f"Audio output is unavailable for '{response_key}'."
            ) from error
        return entry["path"]

    @staticmethod
    def _play_with_sounddevice(frames: bytes, sample_rate: int) -> None:
        try:
            import sounddevice as sd
            import numpy as np
        except ImportError as error:
            raise StaticAudioError(
                "Install audio dependencies with "
                "'pip install -r backend/requirements/voice.txt'."
            ) from error

        samples = np.frombuffer(frames, dtype="<i2")
        sd.play(samples, samplerate=sample_rate, blocking=True)

    def output_available(self) -> bool:
        try:
            import sounddevice as sd
        except ImportError:
            return False
        try:
            devices = sd.query_devices()
        except Exception:
            logger.exception("Could not query audio output devices")
            return False
        return any(device.get("max_output_channels", 0) > 0 for device in devices)
