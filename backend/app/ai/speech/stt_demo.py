
import argparse
import time
from pathlib import Path

import numpy as np
import sounddevice as sd
import soundfile as sf
import torch
from scipy.signal import resample_poly
from transformers import Wav2Vec2ForCTC, Wav2Vec2Processor


MODEL_ID = "facebook/wav2vec2-base-960h"
TARGET_SAMPLE_RATE = 16000

PROJECT_ROOT = Path(__file__).resolve().parents[4]
RECORDINGS_DIR = PROJECT_ROOT / "recordings"
RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)


def list_microphones():
    """Display available audio input devices."""
    print("\nAvailable audio devices:")
    print(sd.query_devices())


def record_audio(duration: int, device=None):
    """Record mono audio using the microphone's native sample rate."""
    input_info = sd.query_devices(device, "input")

    native_rate = int(input_info["default_samplerate"])
    device_name = input_info["name"]

    print(f"\nMicrophone: {device_name}")
    print(f"Recording rate: {native_rate} Hz")
    print(f"Recording for {duration} seconds...")

    audio = sd.rec(
        int(duration * native_rate),
        samplerate=native_rate,
        channels=1,
        dtype="float32",
        device=device,
    )
    sd.wait()

    audio = audio.flatten()

    if native_rate != TARGET_SAMPLE_RATE:
        divisor = np.gcd(native_rate, TARGET_SAMPLE_RATE)

        audio = resample_poly(
            audio,
            TARGET_SAMPLE_RATE // divisor,
            native_rate // divisor,
        ).astype(np.float32)

    audio = np.clip(audio, -1.0, 1.0)

    output_path = RECORDINGS_DIR / "stt_test.wav"

    sf.write(
        output_path,
        audio,
        TARGET_SAMPLE_RATE,
        subtype="PCM_16",
    )

    print(f"Audio saved: {output_path}")

    return audio


def load_model():
    """Load the English Wav2Vec2 model."""
    print("\nLoading STT model...")
    print(f"Model: {MODEL_ID}")

    processor = Wav2Vec2Processor.from_pretrained(MODEL_ID)
    model = Wav2Vec2ForCTC.from_pretrained(MODEL_ID)

    model.eval()
    model.to("cpu")

    print("Model loaded successfully.")

    return processor, model


def transcribe(audio, processor, model):
    """Convert an audio waveform into English text."""
    inputs = processor(
        audio,
        sampling_rate=TARGET_SAMPLE_RATE,
        return_tensors="pt",
        padding=True,
    )

    with torch.inference_mode():
        logits = model(inputs.input_values).logits

    predicted_ids = torch.argmax(logits, dim=-1)

    transcription = processor.batch_decode(
        predicted_ids
    )[0]

    return transcription.strip()


def main():
    parser = argparse.ArgumentParser(
        description="English microphone STT test"
    )

    parser.add_argument(
        "--list-devices",
        action="store_true",
        help="List available microphones",
    )

    parser.add_argument(
        "--device",
        type=int,
        default=None,
        help="Microphone device index",
    )

    parser.add_argument(
        "--duration",
        type=int,
        default=5,
        help="Recording duration in seconds",
    )

    args = parser.parse_args()

    if args.list_devices:
        list_microphones()
        return

    if args.duration <= 0:
        raise ValueError("Duration must be greater than zero.")

    print("=== VietHome AI: STT Test ===")

    audio = record_audio(
        duration=args.duration,
        device=args.device,
    )

    processor, model = load_model()

    print("\nRecognizing speech...")
    start_time = time.perf_counter()

    text = transcribe(audio, processor, model)

    inference_time = time.perf_counter() - start_time

    print("\n========== RESULT ==========")
    print(f"Transcript: {text}")
    print(f"Inference time: {inference_time:.2f} seconds")
    print(f"Audio duration: {len(audio) / TARGET_SAMPLE_RATE:.2f} seconds")
    print("============================")


if __name__ == "__main__":
    main()
