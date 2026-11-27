from app.ai.command.normalizer import normalize_text
from app.ai.command.processor import CommandProcessor


def test_normalize_vietnamese_text() -> None:
    assert normalize_text("  BẬT đèn phòng khách!  ") == "bat den phong khach"


def test_normalize_english_contractions_for_negation() -> None:
    assert normalize_text("Don't turn on the light!") == "do not turn on the light"


def test_recognizes_supported_command_with_accents() -> None:
    result = CommandProcessor().process("Bật đèn phòng khách")

    assert result["accepted"] is True
    assert result["intent"] == "LIGHT_ON"
    assert result["device_id"] == "light"


def test_recognizes_english_command_and_room() -> None:
    result = CommandProcessor().process("Turn on the living room light")

    assert result["accepted"] is True
    assert result["intent"] == "LIGHT_ON"
    assert result["device_id"] == "light"
    assert result["target"] == "living_room"


def test_negation_is_rejected_before_matching() -> None:
    result = CommandProcessor().process("Không bật đèn phòng khách")

    assert result["accepted"] is False
    assert result["reason"] == "NEGATION_DETECTED"


def test_english_negation_is_rejected_before_matching() -> None:
    result = CommandProcessor().process("Don't turn on the living room light")

    assert result["accepted"] is False
    assert result["reason"] == "NEGATION_DETECTED"
