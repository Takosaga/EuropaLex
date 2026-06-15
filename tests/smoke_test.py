"""Pytest rewrite of EuropaLex smoke test.

Validates: all modules import, Pydantic model construction,
TextResult.validate_and_parse() gate behavior.
"""

import pytest


def test_all_modules_import():
    """All project modules can be imported without error."""
    import core.types       # noqa: F401
    import core.text_gen     # noqa: F401
    import core.engine       # noqa: F401
    import core.audio_gen    # noqa: F401
    import core.image_gen    # noqa: F401
    import frontend.ui.cards  # noqa: F401
    import frontend.ui.widgets  # noqa: F401


def test_carddata_construction():
    """CardData Pydantic model constructs with all fields."""
    from core.types import CardData

    card = CardData(text="Hello", translation="Sveiki")
    assert card.text == "Hello"
    assert card.translation == "Sveiki"
    assert card.audio_path is None
    assert card.image_path is None


def test_textresult_construction():
    """TextResult constructs with generated_texts list."""
    from core.types import TextResult

    result = TextResult(generated_texts=["A.", "B."])
    assert len(result.generated_texts) == 2


def test_audioreresult_construction():
    """AudioResult defaults to empty list."""
    from core.types import AudioResult

    result = AudioResult()
    assert result.audio_paths == []


def test_imageresult_construction():
    """ImageResult defaults to empty list."""
    from core.types import ImageResult

    result = ImageResult()
    assert result.image_paths == []


def test_engineconfig_from_settings():
    """EngineConfig loads from settings.yaml (uses default paths, no model check)."""
    from core.types import EngineConfig

    config = EngineConfig.from_settings_yaml()
    assert config.batch_size > 0
    assert config.device in ("cuda", "mps", "cpu")


def test_cefrlevel_enum():
    """CEFRLevel enum has all expected values and label/description methods."""
    from core.types import CEFRLevel

    levels = [CEFRLevel.A1, CEFRLevel.A2, CEFRLevel.B1, CEFRLevel.B2, CEFRLevel.C1, CEFRLevel.C2]
    for level in levels:
        assert isinstance(level.label(), str)
        assert len(level.label()) > 0
        assert isinstance(level.description(), str)
        assert len(level.description()) > 0


def test_validationerror_structure():
    """ValidationError carries raw_output attribute."""
    from core.types import ValidationError

    err = ValidationError("test message", raw_output="raw llm output")
    assert err.raw_output == "raw llm output"
    assert str(err) == "test message"


def test_textresult_validate_and_parse_strips_thinking_tags():
    """validate_and_parse strips <thinking> tags before splitting lines."""
    from core.types import TextResult

    raw = "<thinking>reasoning</thinking>\nHello.\nWorld."
    result = TextResult.validate_and_parse(raw, expected_count=2)
    assert result.generated_texts == ["Hello.", "World."]


def test_textresult_validate_and_parse_enforces_count():
    """validate_and_parse raises ValidationError when count mismatches."""
    from core.types import TextResult, ValidationError

    raw = "Line one.\nLine two."
    with pytest.raises(ValidationError) as exc_info:
        TextResult.validate_and_parse(raw, expected_count=5)
    assert "Expected 5 sentences but got 2" in str(exc_info.value)
    assert exc_info.value.raw_output == raw


def test_textresult_validate_and_parse_empty_raises():
    """validate_and_parse raises ValidationError on empty output after tag stripping."""
    from core.types import TextResult, ValidationError

    raw = "<thinking>only reasoning</thinking>"
    with pytest.raises(ValidationError):
        TextResult.validate_and_parse(raw, expected_count=1)


def test_textresult_validate_and_parse_no_expected_count():
    """validate_and_parse returns all lines when expected_count is None."""
    from core.types import TextResult

    raw = "A.\nB.\nC."
    result = TextResult.validate_and_parse(raw, expected_count=None)
    assert len(result.generated_texts) == 3
