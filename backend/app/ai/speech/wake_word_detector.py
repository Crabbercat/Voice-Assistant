from collections.abc import Iterable

from app.ai.command.normalizer import normalize_text


class WakeWordDetector:
    def __init__(self, wake_words: Iterable[str]) -> None:
        normalized_words = {
            normalize_text(wake_word)
            for wake_word in wake_words
            if normalize_text(wake_word)
        }
        if not normalized_words:
            raise ValueError("At least one valid wake word is required.")
        self.wake_words = tuple(sorted(normalized_words))

    def detect(self, text: str) -> bool:
        normalized = normalize_text(text)
        return any(
            f" {wake_word} " in f" {normalized} "
            for wake_word in self.wake_words
        )
