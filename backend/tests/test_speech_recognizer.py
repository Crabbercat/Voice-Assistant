from types import SimpleNamespace

from app.ai.speech.speech_recognizer import SpeechRecognizer


def test_model_is_loaded_once_and_transcription_is_vietnamese() -> None:
    created_models = []

    class FakeModel:
        def transcribe(self, audio, **options):
            assert options["language"] == "vi"
            return iter(
                [
                    SimpleNamespace(text=" Bật đèn "),
                    SimpleNamespace(text="phòng khách"),
                ]
            ), SimpleNamespace(
                language="vi",
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

    assert first["recognized_text"] == "Bật đèn phòng khách"
    assert first["language"] == "vi"
    assert first["language_probability"] == 0.98
    assert second["recognized_text"] == first["recognized_text"]
    assert len(created_models) == 1
