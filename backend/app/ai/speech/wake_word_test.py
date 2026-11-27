import argparse
import re
import time
from pathlib import Path

import numpy as np

from faster_whisper import WhisperModel


# =========================================================
# CONFIGURATION
# =========================================================

MODEL_SIZE = "tiny"       # Thử tiny trước, sau đó đổi thành base
DEVICE = "cpu"
COMPUTE_TYPE = "int8"

TARGET_SAMPLE_RATE = 16000

# Mỗi lần lấy âm thanh để kiểm tra Wake Word
WAKE_CHUNK_SECONDS = 3.0

# Thời gian đo nhiễu nền trước khi nhận câu lệnh
COMMAND_CALIBRATION_SECONDS = 1.0

# Thời lượng mỗi đoạn âm thanh khi ghi câu lệnh
COMMAND_CHUNK_SECONDS = 0.25

# Thời gian im lặng để xác định người nói đã kết thúc
SILENCE_DURATION = 1.2

# Ngưỡng RMS tối thiểu và hệ số so với nhiễu nền
MIN_SPEECH_THRESHOLD = 0.001
NOISE_FLOOR_MULTIPLIER = 3.0

# Giới hạn thời gian ghi một câu lệnh
MAX_COMMAND_DURATION = 15

WAKE_WORDS = [
    "hey berry",
    "hey barry",
    "hey very",
    "hey beri",
    "hey be ri",
    "berry",
    "barry",
]


# =========================================================
# AUDIO UTILITIES
# =========================================================

def get_input_sample_rate():
    """Lấy sample rate mặc định của microphone."""

    import sounddevice as sd

    device = sd.query_devices(kind="input")

    sample_rate = int(device["default_samplerate"])

    print(f"[AUDIO] Microphone: {device['name']}")
    print(f"[AUDIO] Native sample rate: {sample_rate} Hz")

    return sample_rate


def record_audio(duration, sample_rate):
    """Thu âm từ microphone."""

    import sounddevice as sd

    frames = int(duration * sample_rate)

    audio = sd.rec(
        frames,
        samplerate=sample_rate,
        channels=1,
        dtype="float32"
    )

    sd.wait()

    return audio.flatten()


def convert_to_16khz(audio, original_rate):
    """Chuyển âm thanh về mono 16 kHz."""

    if original_rate == TARGET_SAMPLE_RATE:
        return audio.astype(np.float32)

    from scipy.signal import resample_poly

    gcd = np.gcd(original_rate, TARGET_SAMPLE_RATE)

    up = TARGET_SAMPLE_RATE // gcd
    down = original_rate // gcd

    converted = resample_poly(audio, up, down)

    return converted.astype(np.float32)


def calculate_rms(audio):
    """Tính mức âm lượng RMS."""

    return float(np.sqrt(np.mean(np.square(audio)) + 1e-10))


def get_speech_threshold(noise_floor):
    """Set a minimum voice threshold relative to the measured noise floor."""

    return max(MIN_SPEECH_THRESHOLD, noise_floor * NOISE_FLOOR_MULTIPLIER)


# =========================================================
# SPEECH RECOGNITION
# =========================================================

def normalize_text(text):
    """Normalize transcript text before checking wake phrases."""

    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def transcribe_audio(model, audio):
    """Transcribe one audio segment with Faster-Whisper in English."""

    segments, info = model.transcribe(
        audio,
        task="transcribe",
        language="en",
        beam_size=1,
        vad_filter=False,
        condition_on_previous_text=False
    )

    text = " ".join(segment.text.strip() for segment in segments)

    return text.strip()


def test_audio_file(model, audio_path):
    """Transcribe one audio file and report whether it contains a wake phrase."""

    path = Path(audio_path).expanduser()
    if not path.is_file():
        raise FileNotFoundError(f"Audio file not found: {path}")

    text = transcribe_audio(model, str(path.resolve()))
    detected = bool(text and detect_wake_word(text))

    print(f"[FILE] {path}")
    print(f"[TRANSCRIPT] {text or '<empty>'}")
    print(f"[WAKE WORD] {'Detected' if detected else 'Not detected'}")
    if detected:
        print("[INFO] Matched one of the configured wake-word variants.")

    return detected


def detect_wake_word(text):
    """Check whether the transcript contains a configured wake phrase."""

    normalized = normalize_text(text)

    for wake_word in WAKE_WORDS:
        if wake_word in normalized:
            return True

    return False


# =========================================================
# WAKE WORD DETECTION
# =========================================================


def wait_for_wake_word(model, sample_rate):

    print("\n[WAKE WORD] Waiting for 'Hey Berry'...")
    print("[INFO] All recognized text will be displayed.\n")

    recognition_count = 0

    while True:

        # Record a short segment.
        raw_audio = record_audio(
            WAKE_CHUNK_SECONDS,
            sample_rate
        )

        audio = convert_to_16khz(
            raw_audio,
            sample_rate
        )

        rms = calculate_rms(audio)

        # Transcribe even quiet segments so possible matches are not skipped.
        text = transcribe_audio(model, audio)

        recognition_count += 1

        timestamp = time.strftime("%H:%M:%S")

        if text:
            print(
                f"[{timestamp}] [RECOGNIZED #{recognition_count}] "
                f"RMS={rms:.4f} | TEXT: {text}",
                flush=True
            )
        else:
            print(
                f"[{timestamp}] [RECOGNIZED #{recognition_count}] "
                f"RMS={rms:.4f} | TEXT: <empty>",
                flush=True
            )

        # Check for a wake phrase.
        if text and detect_wake_word(text):

            print("\n[WAKE WORD] Hey Berry detected!")

            return



# =========================================================
# COMMAND RECORDING
# =========================================================

def record_command(sample_rate):

    print("\n[AUDIO] Keep quiet while the microphone is calibrated...")
    calibration_audio = convert_to_16khz(
        record_audio(COMMAND_CALIBRATION_SECONDS, sample_rate),
        sample_rate
    )
    noise_floor = calculate_rms(calibration_audio)
    speech_threshold = get_speech_threshold(noise_floor)

    print(
        f"[AUDIO] Noise floor RMS={noise_floor:.4f}; "
        f"speech threshold RMS={speech_threshold:.4f}"
    )
    print("\n[COMMAND] Say an English command...")
    print("[INFO] After speaking, remain silent for about 1-2 seconds.\n")

    audio_parts = []

    silence_time = 0.0
    speech_started = False
    total_duration = 0.0
    highest_rms = 0.0

    while total_duration < MAX_COMMAND_DURATION:

        raw_audio = record_audio(
            COMMAND_CHUNK_SECONDS,
            sample_rate
        )

        audio = convert_to_16khz(
            raw_audio,
            sample_rate
        )

        rms = calculate_rms(audio)
        highest_rms = max(highest_rms, rms)

        audio_parts.append(audio)

        total_duration += COMMAND_CHUNK_SECONDS

        if rms >= speech_threshold:
            if not speech_started:
                print(
                    f"[RECORDING] Voice detected "
                    f"(RMS={rms:.4f}, threshold={speech_threshold:.4f})"
                )

            speech_started = True
            silence_time = 0.0

        elif speech_started:

            silence_time += COMMAND_CHUNK_SECONDS

            if silence_time >= SILENCE_DURATION:
                break
        else:
            print(
                f"[LEVEL] RMS={rms:.4f} / threshold={speech_threshold:.4f}",
                flush=True
            )

    if not speech_started:

        print(
            "\n[WARNING] No speech detected "
            f"(highest RMS={highest_rms:.4f}, "
            f"threshold={speech_threshold:.4f})."
        )

        return None

    command_audio = np.concatenate(audio_parts)

    print("\n[COMMAND] Recording finished.")

    return command_audio


# =========================================================
# MAIN
# =========================================================

def main():
    parser = argparse.ArgumentParser(
        description="Test English Hey Berry wake-word detection using a microphone or audio file."
    )
    parser.add_argument(
        "--file",
        type=Path,
        help="Transcribe an audio file offline instead of opening the microphone.",
    )
    args = parser.parse_args()
    if args.file is not None and not args.file.expanduser().is_file():
        parser.error(f"Audio file not found: {args.file}")

    print("=" * 55)
    print("         VIETHOME AI - ENGLISH STT TEST")
    print("=" * 55)

    # Load the model once.
    print(f"\n[MODEL] Loading Faster-Whisper: {MODEL_SIZE}")

    start_time = time.perf_counter()

    model = WhisperModel(
        MODEL_SIZE,
        device=DEVICE,
        compute_type=COMPUTE_TYPE,
        download_root=str(
            Path(__file__).resolve().parents[4] / "models" / "whisper"
        ),
    )

    load_time = time.perf_counter() - start_time

    print(f"[MODEL] Loaded successfully in {load_time:.2f}s")

    try:
        if args.file is not None:
            test_audio_file(model, args.file)
            return

        # Get the microphone sample rate.
        sample_rate = get_input_sample_rate()

        # Phase 1: wait for the wake phrase.
        wait_for_wake_word(model, sample_rate)

        # Give the user a short pause after the wake phrase.
        time.sleep(0.3)

        # Phase 2: record the command.
        command_audio = record_command(sample_rate)

        if command_audio is None:
            return

        # Phase 3: transcribe the command.
        print("\n[STT] Đang xử lý câu lệnh...")

        start_time = time.perf_counter()

        command_text = transcribe_audio(
            model,
            command_audio
        )

        inference_time = time.perf_counter() - start_time

        # Phase 4: print the result.
        print("\n" + "=" * 55)
        print("                 RESULT")
        print("=" * 55)

        print(f"Wake Word: Hey Berry")
        print(f"Command: {command_text}")
        print(f"Inference time: {inference_time:.2f}s")
        print(f"Audio duration: {len(command_audio) / TARGET_SAMPLE_RATE:.2f}s")

        print("=" * 55)
        print("[SYSTEM] STT cycle completed.")

    except KeyboardInterrupt:

        print("\n[SYSTEM] Stopped.")

    except Exception as error:

        print(f"\n[ERROR] {type(error).__name__}: {error}")


if __name__ == "__main__":
    main() 