import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace


def load_wake_word_test(monkeypatch):
    fake_numpy = ModuleType("numpy")
    fake_numpy.concatenate = lambda chunks: list(chunks)
    fake_whisper = ModuleType("faster_whisper")
    fake_whisper.WhisperModel = object
    monkeypatch.setitem(sys.modules, "numpy", fake_numpy)
    monkeypatch.setitem(sys.modules, "faster_whisper", fake_whisper)

    script_path = (
        Path(__file__).parents[1]
        / "app"
        / "ai"
        / "speech"
        / "wake_word_test.py"
    )
    spec = importlib.util.spec_from_file_location(
        "wake_word_test_under_test",
        script_path,
    )
    assert spec is not None and spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_record_command_detects_speech_below_old_fixed_threshold(monkeypatch):
    module = load_wake_word_test(monkeypatch)
    chunks = iter(
        [
            SimpleNamespace(rms=0.0001),  # Calibration noise floor
            SimpleNamespace(rms=0.002),   # Speech below the former 0.012 threshold
            *[SimpleNamespace(rms=0.0) for _ in range(5)],
        ]
    )
    monkeypatch.setattr(module, "record_audio", lambda *_: next(chunks))
    monkeypatch.setattr(module, "convert_to_16khz", lambda audio, _: audio)
    monkeypatch.setattr(module, "calculate_rms", lambda audio: audio.rms)

    command_audio = module.record_command(16000)

    assert command_audio is not None
    assert any(chunk.rms == 0.002 for chunk in command_audio)


def test_speech_threshold_stays_low_when_noise_floor_is_high(monkeypatch):
    module = load_wake_word_test(monkeypatch)

    assert module.get_speech_threshold(0.01) == 0.005
