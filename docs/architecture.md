# Kiến trúc dự kiến

Microphone/client gửi dữ liệu tới backend. Backend điều phối pipeline:

1. Speech-to-text (STT).
2. Natural language understanding (NLU).
3. Context và service điều khiển thiết bị.
4. Text-to-speech (TTS) hoặc phản hồi API.

