
import argparse
import time
from pathlib import Path

from faster_whisper import WhisperModel


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--audio",
        default="recordings/test.wav",
    )

    parser.add_argument(
        "--model",
        default="tiny",
        choices=["tiny", "base", "small"],
    )

    args = parser.parse_args()

    audio_path = Path(args.audio)

    if not audio_path.exists():
        raise FileNotFoundError(audio_path)

    print(f"Loading Whisper {args.model}...")

    load_start = time.perf_counter()

    model = WhisperModel(
        args.model,
        device="cpu",
        compute_type="int8",
    )

    load_time = time.perf_counter() - load_start

    print(f"Load time: {load_time:.2f}s")

    print("\nRecognizing...")

    inference_start = time.perf_counter()

    segments, info = model.transcribe(
        str(audio_path),
        language="en",
        task="transcribe",
        beam_size=5,
        vad_filter=False,
    )

    segments = list(segments)

    inference_time = time.perf_counter() - inference_start

    transcript = " ".join(
        segment.text.strip()
        for segment in segments
    )

    print("\n========== RESULT ==========")
    print(f"Model: Whisper {args.model}")
    print(f"Language: {info.language}")
    print(f"Transcript: {transcript}")
    print(f"Audio duration: {info.duration:.2f}s")
    print(f"Load time: {load_time:.2f}s")
    print(f"Inference time: {inference_time:.2f}s")

    if info.duration > 0:
        print(
            f"Real-time factor: "
            f"{inference_time / info.duration:.3f}"
        )

    print("============================")


if __name__ == "__main__":
    main()
