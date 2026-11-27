from types import SimpleNamespace

from app.core.config import Settings
from app.ai.speech.speech_recognizer import SpeechRecognizer


def test_stt_defaults_to_english() -> None:
    assert Settings(_env_file=None).STT_LANGUAGE == "en"


def test_model_is_loaded_once_and_transcription_uses_english() -> None:
    created_models = []

    class FakeModel:
        def transcribe(self, audio, **options):
            assert options["language"] == "en"
            return iter(
                [
                    SimpleNamespace(text=" Turn on "),
                    SimpleNamespace(text="the living room light"),
                ]
            ), SimpleNamespace(
                language="en",
                language_probability=0.98,
                duration=1.2,
            )

    def create_model(*args, **kwargs):
        model = FakeModel()
        created_models.append(model)
        return model

    recognizer = SpeechRecognizer(model_factory=create_model)
    wav = b"RIFF\x00\x00\x00\x00WAVE"

    first = recognizer.transcribe(wav)
    second = recognizer.transcribe(wav)

    assert first["recognized_text"] == "Turn on the living room light"
    assert first["language"] == "en"
    assert first["language_probability"] == 0.98
    assert second["recognized_text"] == first["recognized_text"]
    assert len(created_models) == 1
