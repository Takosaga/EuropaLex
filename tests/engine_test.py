"""Tests for core.engine engines: MiniCPMTextEngine, LlamaCppTextEngine, EnginePool.

Merged from translation_retry_test.py. All tests mock the LLM — no model inference.
"""

import pytest
from unittest.mock import patch, MagicMock

from core.types import CEFRLevel, TextResult, ValidationError
from core.engine import MiniCPMTextEngine, LlamaCppTextEngine, EnginePool


# ── MiniCPMTextEngine ────────────────────────────────────────────

def test_minicpm_generate_calls_llm(mock_llm_response_factory):
    """generate() calls llm.create_chat_completion and wraps in TextResult."""
    mock_llm = MagicMock()
    mock_llm.create_chat_completion.return_value = mock_llm_response_factory(
        "1. Hello.\n2. World."
    )

    with patch.object(MiniCPMTextEngine, "_load_model"):
        engine = MiniCPMTextEngine.__new__(MiniCPMTextEngine)
        engine._llm = mock_llm
        engine._loaded = True

        result = engine.generate(
            texts=[],  # empty = generation mode (not translation)
            scenario="test",
            cefr_level=CEFRLevel.A1,
            batch_size=2,
        )

    assert isinstance(result, TextResult)
    assert len(result.generated_texts) == 2
    assert result.generated_texts[0] == "Hello."
    mock_llm.create_chat_completion.assert_called_once()


def test_minicpm_generate_propagates_validation_error():
    """ValidationError from text_gen propagate through generate()."""
    from core.text_gen import ValidationError as TextGenValidationError

    mock_llm = MagicMock()
    # LLM returns content that yields 0 sentences after parsing
    mock_llm.create_chat_completion.return_value = {"choices": [{"message": {"content": "no numbers here"}}]}

    with patch.object(MiniCPMTextEngine, "_load_model"):
        engine = MiniCPMTextEngine.__new__(MiniCPMTextEngine)
        engine._llm = mock_llm
        engine._loaded = True

        # Should raise ValidationError after retries exhausted
        with pytest.raises((ValidationError, TextGenValidationError)):
            engine.generate(
                texts=[],
                scenario="test",
                cefr_level=CEFRLevel.A1,
                batch_size=2,
            )


# ── LlamaCppTextEngine._is_valid_translation ─────────────────────

def test_is_valid_translation_valid():
    """Valid: non-empty single line, no English words."""
    with patch.object(LlamaCppTextEngine, "_load_model"):
        engine = LlamaCppTextEngine.__new__(LlamaCppTextEngine)
        engine._loaded = True

    assert engine._is_valid_translation("Sveiki.") is True
    assert engine._is_valid_translation("Labrīt!") is True
    assert engine._is_valid_translation("Paldies, ka jautāji.") is True


def test_is_valid_translation_invalid_empty():
    """Invalid: empty string or whitespace-only."""
    with patch.object(LlamaCppTextEngine, "_load_model"):
        engine = LlamaCppTextEngine.__new__(LlamaCppTextEngine)
        engine._loaded = True

    assert engine._is_valid_translation("") is False
    assert engine._is_valid_translation("   ") is False


def test_is_valid_translation_invalid_english_words():
    """Invalid: contains English words (model echoed back)."""
    with patch.object(LlamaCppTextEngine, "_load_model"):
        engine = LlamaCppTextEngine.__new__(LlamaCppTextEngine)
        engine._loaded = True

    assert engine._is_valid_translation("This is the translation") is False
    assert engine._is_valid_translation("Translate this sentence") is False


def test_is_valid_translation_invalid_multiline():
    """Invalid: multiline output."""
    with patch.object(LlamaCppTextEngine, "_load_model"):
        engine = LlamaCppTextEngine.__new__(LlamaCppTextEngine)
        engine._loaded = True

    assert engine._is_valid_translation("Line1\nLine2") is False


# ── LlamaCppTextEngine._translate_single ─────────────────────────

def test_translate_single_success():
    """Valid translation returned on first attempt."""
    mock_llm = MagicMock()
    mock_llm.create_chat_completion.return_value = {"choices": [{"message": {"content": "Sveiki."}}]}

    with patch.object(LlamaCppTextEngine, "_load_model"):
        engine = LlamaCppTextEngine.__new__(LlamaCppTextEngine)
        engine._llm = mock_llm
        engine._loaded = True
        engine.target_language = "Latvian"

        result = engine._translate_single("Hello.", CEFRLevel.A1)

    assert result == "Sveiki."
    assert mock_llm.create_chat_completion.call_count == 1


def test_translate_single_retry_on_invalid():
    """Retry when first output invalid (contains English word), second succeeds."""
    mock_llm = MagicMock()
    mock_llm.create_chat_completion.side_effect = [
        {"choices": [{"message": {"content": "This is the English text"}}]},
        {"choices": [{"message": {"content": "Paldies."}}]},
    ]

    with patch.object(LlamaCppTextEngine, "_load_model"):
        engine = LlamaCppTextEngine.__new__(LlamaCppTextEngine)
        engine._llm = mock_llm
        engine._loaded = True
        engine.target_language = "Latvian"

        result = engine._translate_single("Thank you.", CEFRLevel.A1)

    assert result == "Paldies."
    assert mock_llm.create_chat_completion.call_count == 2


def test_translate_single_exhausted_retries_fallback():
    """Exhausted retries → fallback to original English text."""
    mock_llm = MagicMock()
    # All 3 attempts return invalid output (empty string)
    mock_llm.create_chat_completion.return_value = {"choices": [{"message": {"content": ""}}]}

    with patch.object(LlamaCppTextEngine, "_load_model"):
        engine = LlamaCppTextEngine.__new__(LlamaCppTextEngine)
        engine._llm = mock_llm
        engine._loaded = True
        engine.target_language = "Latvian"

        result = engine._translate_single("Hello.", CEFRLevel.A1)

    assert result == "Hello."  # fallback to original English
    assert mock_llm.create_chat_completion.call_count == 3


def test_translate_single_multiline_rejected():
    """Multiline output rejected, triggers retry."""
    mock_llm = MagicMock()
    mock_llm.create_chat_completion.side_effect = [
        {"choices": [{"message": {"content": "Line1\nLine2"}}]},  # invalid: multiline
        {"choices": [{"message": {"content": "Paldies."}}]},  # valid (no English words)
    ]

    with patch.object(LlamaCppTextEngine, "_load_model"):
        engine = LlamaCppTextEngine.__new__(LlamaCppTextEngine)
        engine._llm = mock_llm
        engine._loaded = True
        engine.target_language = "Latvian"

        result = engine._translate_single("Hello.", CEFRLevel.A1)

    assert result == "Paldies."
    assert mock_llm.create_chat_completion.call_count == 2


# ── LlamaCppTextEngine.generate ──────────────────────────────────

def test_generate_calls_per_sentence():
    """generate() calls _translate_single for each input text."""
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
        engine.target_language = "Latvian"

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


# ── EnginePool ───────────────────────────────────────────────────

def test_engine_pool_get_creates_singleton():
    """First get() creates a new EnginePool instance."""
    from core.types import EngineConfig

    config = MagicMock(spec=EngineConfig)
    config.batch_size = 3
    config.target_language = "Latvian"
    config.device = "cpu"
    pool = EnginePool.get(config)
    assert isinstance(pool, EnginePool)
    EnginePool.reset()


def test_engine_pool_get_returns_same_instance():
    """Second get() returns the same instance."""
    from core.types import EngineConfig

    config = MagicMock(spec=EngineConfig)
    config.batch_size = 3
    config.target_language = "Latvian"
    config.device = "cpu"
    pool1 = EnginePool.get(config)
    pool2 = EnginePool.get(config)
    assert pool1 is pool2
    EnginePool.reset()


def test_engine_pool_reset_clears_singleton():
    """reset() clears singleton and unloads engines."""
    from core.types import EngineConfig

    config = MagicMock(spec=EngineConfig)
    config.batch_size = 3
    config.target_language = "Latvian"
    config.device = "cpu"
    pool1 = EnginePool.get(config)

    # Create a second reference
    pool2 = EnginePool.get(config)
    assert pool1 is pool2

    EnginePool.reset()

    # After reset, new get() should return a different instance
    pool3 = EnginePool.get(config)
    assert pool3 is not pool1
