
import argparse
from pathlib import Path

import numpy as np
import sounddevice as sd
import soundfile as sf
from scipy.signal import resample_poly


SAMPLE_RATE = 16000


def record(duration: int, device_id: int | None):
    device = sd.query_devices(device_id, "input")

    native_rate = int(device["default_samplerate"])

    print(f"Microphone: {device['name']}")
    print(f"Sample rate: {native_rate}")
    print(f"Recording for {duration} seconds...")

    audio = sd.rec(
        int(duration * native_rate),
        samplerate=native_rate,
        channels=1,
        dtype="float32",
        device=device_id,
    )

    sd.wait()

    audio = audio.flatten()

    if native_rate != SAMPLE_RATE:
        divisor = np.gcd(native_rate, SAMPLE_RATE)

        audio = resample_poly(
            audio,
            SAMPLE_RATE // divisor,
            native_rate // divisor,
        ).astype(np.float32)

    output_dir = Path("recordings")
    output_dir.mkdir(exist_ok=True)

    output_file = output_dir / "test.wav"

    sf.write(
        output_file,
        audio,
        SAMPLE_RATE,
        subtype="PCM_16",
    )

    print(f"\nSaved: {output_file.resolve()}")
    print(f"Duration: {len(audio) / SAMPLE_RATE:.2f}s")
    print(f"Peak amplitude: {np.max(np.abs(audio)):.4f}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument("--device", type=int, default=None)
    parser.add_argument("--duration", type=int, default=5)

    args = parser.parse_args()

    record(args.duration, args.device)
