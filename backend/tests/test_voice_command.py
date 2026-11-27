from app.ai.command.normalizer import normalize_text
from app.ai.command.processor import CommandProcessor


def test_normalize_vietnamese_text() -> None:
    assert normalize_text("  BẬT đèn phòng khách!  ") == "bat den phong khach"


def test_recognizes_supported_command_with_accents() -> None:
    result = CommandProcessor().process("Bật đèn phòng khách")

    assert result["accepted"] is True
    assert result["intent"] == "LIGHT_ON"
    assert result["device_id"] == "light"


def test_negation_is_rejected_before_matching() -> None:
    result = CommandProcessor().process("Không bật đèn phòng khách")

    assert result["accepted"] is False
    assert result["reason"] == "NEGATION_DETECTED"
