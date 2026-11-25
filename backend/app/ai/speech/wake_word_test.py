import re
import time
import numpy as np
import sounddevice as sd

from faster_whisper import WhisperModel
from scipy.signal import resample_poly


# =========================================================
# CONFIGURATION
# =========================================================

MODEL_SIZE = "tiny"       # Thử tiny trước, sau đó đổi thành base
DEVICE = "cpu"
COMPUTE_TYPE = "int8"

TARGET_SAMPLE_RATE = 16000

# Mỗi lần lấy âm thanh để kiểm tra Wake Word
WAKE_CHUNK_SECONDS = 3.0

# Thời lượng mỗi đoạn âm thanh khi ghi câu lệnh
COMMAND_CHUNK_SECONDS = 0.25

# Thời gian im lặng để xác định người nói đã kết thúc
SILENCE_DURATION = 1.2

# Ngưỡng âm lượng để phát hiện giọng nói
SILENCE_THRESHOLD = 0.012

# Giới hạn thời gian ghi một câu lệnh
MAX_COMMAND_DURATION = 15

WAKE_WORDS = [
    "hey berry",
    "hey barry",
    "hey very",
    "hey beri",
    "hey be ri",
]


# =========================================================
# AUDIO UTILITIES
# =========================================================

def get_input_sample_rate():
    """Lấy sample rate mặc định của microphone."""

    device = sd.query_devices(kind="input")

    sample_rate = int(device["default_samplerate"])

    print(f"[AUDIO] Microphone: {device['name']}")
    print(f"[AUDIO] Native sample rate: {sample_rate} Hz")

    return sample_rate


def record_audio(duration, sample_rate):
    """Thu âm từ microphone."""

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

    gcd = np.gcd(original_rate, TARGET_SAMPLE_RATE)

    up = TARGET_SAMPLE_RATE // gcd
    down = original_rate // gcd

    converted = resample_poly(audio, up, down)

    return converted.astype(np.float32)


def calculate_rms(audio):
    """Tính mức âm lượng RMS."""

    return float(np.sqrt(np.mean(np.square(audio)) + 1e-10))


# =========================================================
# SPEECH RECOGNITION
# =========================================================

def normalize_text(text):
    """Chuẩn hóa văn bản để kiểm tra Wake Word."""

    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def transcribe_audio(model, audio):
    """Nhận dạng một đoạn âm thanh bằng Faster-Whisper."""

    segments, info = model.transcribe(
        audio,
        task="transcribe",
        language="vi",
        beam_size=1,
        vad_filter=False,
        condition_on_previous_text=False
    )

    text = " ".join(segment.text.strip() for segment in segments)

    return text.strip()


def detect_wake_word(text):
    """Kiểm tra câu nhận dạng có chứa Hey Berry không."""

    normalized = normalize_text(text)

    for wake_word in WAKE_WORDS:
        if wake_word in normalized:
            return True

    return False


# =========================================================
# WAKE WORD DETECTION
# =========================================================


def wait_for_wake_word(model, sample_rate):

    print("\n[WAKE WORD] Đang chờ 'Hey Berry'...")
    print("[INFO] Toàn bộ kết quả nhận dạng sẽ được hiển thị.\n")

    recognition_count = 0

    while True:

        # Thu âm một đoạn ngắn
        raw_audio = record_audio(
            WAKE_CHUNK_SECONDS,
            sample_rate
        )

        audio = convert_to_16khz(
            raw_audio,
            sample_rate
        )

        rms = calculate_rms(audio)

        # Không bỏ qua âm thanh nhỏ.
        # Vẫn đưa vào model để ghi nhận mọi kết quả có thể nhận dạng.
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

        # Kiểm tra Wake Word
        if text and detect_wake_word(text):

            print("\n[WAKE WORD] Đã phát hiện Hey Berry!")

            return



# =========================================================
# COMMAND RECORDING
# =========================================================

def record_command(sample_rate):

    print("\n[COMMAND] Hãy nói câu lệnh...")
    print("[INFO] Nói xong hãy giữ im lặng khoảng 1-2 giây.\n")

    audio_parts = []

    silence_time = 0.0
    speech_started = False
    total_duration = 0.0

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

        audio_parts.append(audio)

        total_duration += COMMAND_CHUNK_SECONDS

        if rms >= SILENCE_THRESHOLD:

            speech_started = True
            silence_time = 0.0

            print("[RECORDING] Đang nhận giọng nói...", end="\r")

        elif speech_started:

            silence_time += COMMAND_CHUNK_SECONDS

            if silence_time >= SILENCE_DURATION:
                break

    if not speech_started:

        print("\n[WARNING] Không phát hiện được giọng nói.")

        return None

    command_audio = np.concatenate(audio_parts)

    print("\n[COMMAND] Đã kết thúc ghi âm.")

    return command_audio


# =========================================================
# MAIN
# =========================================================

def main():

    print("=" * 55)
    print("             VIETHOME AI - STT TEST")
    print("=" * 55)

    # Lấy sample rate của microphone
    sample_rate = get_input_sample_rate()

    # Load model duy nhất một lần
    print(f"\n[MODEL] Loading Faster-Whisper: {MODEL_SIZE}")

    start_time = time.perf_counter()

    model = WhisperModel(
        MODEL_SIZE,
        device=DEVICE,
        compute_type=COMPUTE_TYPE
    )

    load_time = time.perf_counter() - start_time

    print(f"[MODEL] Loaded successfully in {load_time:.2f}s")

    try:

        # Giai đoạn 1: Chờ Wake Word
        wait_for_wake_word(model, sample_rate)

        # Cho người dùng một khoảng nghỉ sau Wake Word
        time.sleep(0.3)

        # Giai đoạn 2: Ghi nhận câu lệnh
        command_audio = record_command(sample_rate)

        if command_audio is None:
            return

        # Giai đoạn 3: Nhận dạng câu lệnh
        print("\n[STT] Đang xử lý câu lệnh...")

        start_time = time.perf_counter()

        command_text = transcribe_audio(
            model,
            command_audio
        )

        inference_time = time.perf_counter() - start_time

        # Giai đoạn 4: Trả kết quả
        print("\n" + "=" * 55)
        print("                 RESULT")
        print("=" * 55)

        print(f"Wake Word: Hey Berry")
        print(f"Command: {command_text}")
        print(f"Inference time: {inference_time:.2f}s")
        print(f"Audio duration: {len(command_audio) / TARGET_SAMPLE_RATE:.2f}s")

        print("=" * 55)
        print("[SYSTEM] Hoàn thành một chu trình STT.")

    except KeyboardInterrupt:

        print("\n[SYSTEM] Đã dừng chương trình.")

    except Exception as error:

        print(f"\n[ERROR] {type(error).__name__}: {error}")


if __name__ == "__main__":
    main() 