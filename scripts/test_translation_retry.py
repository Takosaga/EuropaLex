"""Quick inline test for LlamaCppTextEngine retry loop.

Tests per-sentence translation with chat completion, retry on invalid
output, and fallback — without requiring a running model. Uses mock LLM.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from unittest.mock import MagicMock, patch


def test_translate_single_success():
    """Test that a valid translation is returned on first attempt."""
    from core.types import CEFRLevel
    from core.engine import LlamaCppTextEngine

    mock_llm = MagicMock()
    mock_llm.create_chat_completion.return_value = {
        "choices": [{"message": {"content": "Sveiki."}}]
    }

    with patch.object(LlamaCppTextEngine, "_load_model"):
        engine = LlamaCppTextEngine.__new__(LlamaCppTextEngine)
        engine._llm = mock_llm
        engine._loaded = True

        result = engine._translate_single("Hello.", CEFRLevel.A1)

    assert result == "Sveiki."
    assert mock_llm.create_chat_completion.call_count == 1
    print("test_translate_single_success: PASS")


def test_translate_single_retry_on_invalid():
    """Test retry when first output is invalid (contains English word)."""
    from core.types import CEFRLevel
    from core.engine import LlamaCppTextEngine

    mock_llm = MagicMock()
    # First call returns invalid (contains "English" — rejected by _is_valid_translation)
    # Second call returns valid translation
    mock_llm.create_chat_completion.side_effect = [
        {"choices": [{"message": {"content": "This is the English text"}}]},
        {"choices": [{"message": {"content": "Paldies."}}]},
    ]

    with patch.object(LlamaCppTextEngine, "_load_model"):
        engine = LlamaCppTextEngine.__new__(LlamaCppTextEngine)
        engine._llm = mock_llm
        engine._loaded = True

        result = engine._translate_single("Thank you.", CEFRLevel.A1)

    assert result == "Paldies."
    assert mock_llm.create_chat_completion.call_count == 2
    print("test_translate_single_retry_on_invalid: PASS")


def test_translate_single_exhausted_retries_fallback():
    """Test that exhausted retries fall back to original English text."""
    from core.types import CEFRLevel
    from core.engine import LlamaCppTextEngine

    mock_llm = MagicMock()
    # All 3 attempts return empty strings (invalid)
    mock_llm.create_chat_completion.return_value = {
        "choices": [{"message": {"content": ""}}]
    }

    with patch.object(LlamaCppTextEngine, "_load_model"):
        engine = LlamaCppTextEngine.__new__(LlamaCppTextEngine)
        engine._llm = mock_llm
        engine._loaded = True

        result = engine._translate_single("Hello.", CEFRLevel.A1)

    assert result == "Hello."  # fallback to original English
    assert mock_llm.create_chat_completion.call_count == 3
    print("test_translate_single_exhausted_retries_fallback: PASS")


def test_translate_single_multiline_rejected():
    """Test that multiline output is rejected (model generated too much)."""
    from core.types import CEFRLevel
    from core.engine import LlamaCppTextEngine

    mock_llm = MagicMock()
    # First call returns multiline — rejected
    # Second call returns single valid line
    mock_llm.create_chat_completion.side_effect = [
        {"choices": [{"message": {"content": "Sveiki.\nKā tu esi?"}}]},
        {"choices": [{"message": {"content": "Sveiki."}}]},
    ]

    with patch.object(LlamaCppTextEngine, "_load_model"):
        engine = LlamaCppTextEngine.__new__(LlamaCppTextEngine)
        engine._llm = mock_llm
        engine._loaded = True

        result = engine._translate_single("Hello.", CEFRLevel.A1)

    assert result == "Sveiki."
    assert mock_llm.create_chat_completion.call_count == 2
    print("test_translate_single_multiline_rejected: PASS")


def test_is_valid_translation():
    """Test the _is_valid_translation helper for various inputs."""
    from core.engine import LlamaCppTextEngine

    with patch.object(LlamaCppTextEngine, "_load_model"):
        engine = LlamaCppTextEngine.__new__(LlamaCppTextEngine)
        engine._loaded = True

    # Valid translations
    assert engine._is_valid_translation("Sveiki.") is True
    assert engine._is_valid_translation("Labrīt!") is True
    assert engine._is_valid_translation("Paldies, ka jautāji.") is True

    # Invalid: empty
    assert engine._is_valid_translation("") is False
    assert engine._is_valid_translation("   ") is False

    # Invalid: contains English words (model echoed back)
    assert engine._is_valid_translation("This is the translation") is False
    assert engine._is_valid_translation("Translate this sentence") is False

    # Invalid: multiline
    assert engine._is_valid_translation("Line1\nLine2") is False

    print("test_is_valid_translation: PASS")


def test_generate_calls_per_sentence():
    """Test that generate() calls _translate_single for each input text."""
    from core.types import CEFRLevel
    from core.engine import LlamaCppTextEngine

    mock_llm = MagicMock()
    responses = [
        {"choices": [{"message": {"content": "Sveiki."}}]},
        {"choices": [{"message": {"content": "Kā tu esi?"}}]},
        {"choices": [{"message": {"content": "Paldies."}}]},
    ]
    mock_llm.create_chat_completion.side_effect = responses

    with patch.object(LlamaCppTextEngine, "_load_model"):
        engine = LlamaCppTextEngine.__new__(LlamaCppTextEngine)
        engine._llm = mock_llm
        engine._loaded = True

        result = engine.generate(
            texts=["Hello.", "How are you?", "Thank you."],
            scenario="greetings",
            cefr_level=CEFRLevel.A1,
            batch_size=3,
        )

    assert len(result.generated_texts) == 3
    assert result.generated_texts[0] == "Sveiki."
    assert result.generated_texts[1] == "Kā tu esi?"
    assert result.generated_texts[2] == "Paldies."
    assert mock_llm.create_chat_completion.call_count == 3
    print("test_generate_calls_per_sentence: PASS")


if __name__ == "__main__":
    test_translate_single_success()
    test_translate_single_retry_on_invalid()
    test_translate_single_exhausted_retries_fallback()
    test_translate_single_multiline_rejected()
    test_is_valid_translation()
    test_generate_calls_per_sentence()
    print("\nAll inline tests passed.")
