
import argparse
import time
from pathlib import Path

from faster_whisper import WhisperModel


PROJECT_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_AUDIO = PROJECT_ROOT / "recordings" / "stt_test.wav"


def load_model(model_size: str):
    print(f"Loading Whisper model: {model_size}")

    start = time.perf_counter()

    model = WhisperModel(
        model_size,
        device="cpu",
        compute_type="int8",
    )

    load_time = time.perf_counter() - start

    print(f"Model loaded in {load_time:.2f}s")

    return model


def transcribe(model, audio_path: Path):
    print(f"\nAudio: {audio_path}")

    start = time.perf_counter()

    segments, info = model.transcribe(
        str(audio_path),
        language="vi",
        task="transcribe",
        beam_size=5,
        vad_filter=True,
    )

    # Segments are generated lazily, so consume them
    # before measuring the inference time.
    segments = list(segments)

    inference_time = time.perf_counter() - start

    text = " ".join(
        segment.text.strip()
        for segment in segments
    )

    return text, inference_time, info


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--audio",
        type=Path,
        default=DEFAULT_AUDIO,
    )

    parser.add_argument(
        "--model",
        type=str,
        default="tiny",
        choices=["tiny", "base", "small"],
    )

    args = parser.parse_args()

    if not args.audio.exists():
        raise FileNotFoundError(
            f"Audio file not found: {args.audio}"
        )

    model = load_model(args.model)

    text, inference_time, info = transcribe(
        model,
        args.audio,
    )

    print("\n========== WHISPER RESULT ==========")
    print(f"Language: {info.language}")
    print(f"Language probability: {info.language_probability:.4f}")
    print(f"Transcript: {text}")
    print(f"Inference time: {inference_time:.2f}s")
    print(f"Audio duration: {info.duration:.2f}s")
    print(
        f"Real-time factor: "
        f"{inference_time / info.duration:.3f}"
    )
    print("===================================")


if __name__ == "__main__":
    main()

