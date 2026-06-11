"""Quick inline test for LlamaCppTextEngine retry loop.

Tests sentence-count validation and retry prompt building without
requiring a running model. Uses mock LLM output.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from unittest.mock import MagicMock, patch


def test_generate_exact_count():
    """Test that exact batch_size returns immediately."""
    from core.types import CEFRLevel
    from core.engine import LlamaCppTextEngine

    mock_llm = MagicMock()
    mock_llm.return_value = {
        "choices": [{"text": "Sveiki.\nKā tu esi?\nPaldies."}]
    }

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
    print("test_generate_exact_count: PASS")


def test_generate_retry_on_short_output():
    """Test retry when fewer lines than expected."""
    from core.types import CEFRLevel
    from core.engine import LlamaCppTextEngine

    mock_llm = MagicMock()
    # First call returns 1 line, second call returns 3 lines
    mock_llm.side_effect = [
        {"choices": [{"text": "Sveiki."}]},
        {"choices": [{"text": "Sveiki.\nKā tu esi?\nPaldies."}]},
    ]

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
    assert mock_llm.call_count == 2  # retried once
    print("test_generate_retry_on_short_output: PASS")


def test_generate_exhausted_retries_returns_partial():
    """Test that exhausted retries return whatever was produced."""
    from core.types import CEFRLevel
    from core.engine import LlamaCppTextEngine

    mock_llm = MagicMock()
    # Always returns wrong count
    mock_llm.return_value = {"choices": [{"text": "Sveiki."}]}

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

    assert len(result.generated_texts) == 1  # partial result returned
    assert mock_llm.call_count == 3  # all 3 attempts used
    print("test_generate_exhausted_retries_returns_partial: PASS")


def test_generate_empty_output_raises():
    """Test that zero lines after retries raises ValidationError."""
    from core.types import CEFRLevel, ValidationError
    from core.engine import LlamaCppTextEngine

    mock_llm = MagicMock()
    # Always returns empty string
    mock_llm.return_value = {"choices": [{"text": ""}]}

    with patch.object(LlamaCppTextEngine, "_load_model"):
        engine = LlamaCppTextEngine.__new__(LlamaCppTextEngine)
        engine._llm = mock_llm
        engine._loaded = True

        try:
            engine.generate(
                texts=["Hello.", "How are you?", "Thank you."],
                scenario="greetings",
                cefr_level=CEFRLevel.A1,
                batch_size=3,
            )
            assert False, "Should raise"
        except ValidationError as e:
            assert "Could not generate any translations" in str(e)

    print("test_generate_empty_output_raises: PASS")


def test_retry_prompt_contains_count_info():
    """Test that retry prompt references actual vs expected count."""
    from core.engine import LlamaCppTextEngine

    with patch.object(LlamaCppTextEngine, "_load_model"):
        engine = LlamaCppTextEngine.__new__(LlamaCppTextEngine)
        engine.model_path = Path("/dev/null")  # doesn't matter for this test

    retry_prompt = engine._build_retry_prompt("Sveiki.", 3)
    assert "1" in retry_prompt  # actual count
    assert "3" in retry_prompt  # expected count
    assert "regenerate ALL 3 translations" in retry_prompt
    print("test_retry_prompt_contains_count_info: PASS")


if __name__ == "__main__":
    test_generate_exact_count()
    test_generate_retry_on_short_output()
    test_generate_exhausted_retries_returns_partial()
    test_generate_empty_output_raises()
    test_retry_prompt_contains_count_info()
    print("\nAll inline tests passed.")
