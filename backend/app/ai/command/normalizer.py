import re
import unicodedata


def normalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFD", text).lower().replace("đ", "d")
    normalized = re.sub(r"\b(\w+)n't\b", r"\1 not", normalized)
    normalized = "".join(
        character
        for character in normalized
        if unicodedata.category(character) != "Mn"
    )
    normalized = re.sub(r"[^a-z0-9\s]", " ", normalized)
    return " ".join(normalized.split())
