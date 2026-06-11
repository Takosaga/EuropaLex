"""Quick inline test for core.text_gen sentence extraction.

Tests extract_sentences and generate_sentences (via mock) with sample data.
No LLM call needed — tests pure parsing logic and retry orchestration.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_extract_sentences_basic():
    """Test basic numbered format extraction."""
    from core.text_gen import extract_sentences
    result = extract_sentences("1. Hello world.\n2. Goodbye world.")
    assert len(result) == 2
    assert result[0] == "Hello world."
    assert result[1] == "Goodbye world."
    print("test_extract_sentences_basic: PASS")


def test_extract_sentences_thinking_tags():
    """Test thinking tag stripping."""
    from core.text_gen import extract_sentences
    raw = "<thinking>some thoughts</thinking>\n1. Sentence one.\n2. Sentence two."
    result = extract_sentences(raw)
    assert len(result) == 2
    assert result[0] == "Sentence one."
    print("test_extract_sentences_thinking_tags: PASS")


def test_extract_sentences_questions_exclamations():
    """Test mixed punctuation handling."""
    from core.text_gen import extract_sentences
    raw = "1. Hello.\n2. How are you?\n3. What a day!"
    result = extract_sentences(raw)
    assert len(result) == 3
    assert result[1] == "How are you?"
    assert result[2] == "What a day!"
    print("test_extract_sentences_questions_exclamations: PASS")


def test_extract_sentences_zero_raises():
    """Test ValidationError when no numbered sentences found."""
    from core.text_gen import extract_sentences, ValidationError
    try:
        extract_sentences("No numbered lines here.")
        assert False, "Should raise"
    except ValidationError:
        pass
    print("test_extract_sentences_zero_raises: PASS")


def test_extract_sentences_all_returned():
    """Test that all numbered sentences are returned (no truncation)."""
    from core.text_gen import extract_sentences
    result = extract_sentences("1. A.\n2. B.\n3. C.")
    assert len(result) == 3
    assert result == ["A.", "B.", "C."]
    print("test_extract_sentences_all_returned: PASS")


def test_generate_sentences_mock():
    """Test generate_sentences with mocked LLM."""
    from unittest.mock import MagicMock
    from core.text_gen import generate_sentences
    from core.types import CEFRLevel

    mock_llm = MagicMock()
    mock_llm.create_chat_completion.return_value = {
        "choices": [{"message": {"content": "1. Hello.\n2. World."}}]
    }

    result = generate_sentences(
        scenario="test",
        cefr_level=CEFRLevel.A1,
        batch_size=2,
        llm=mock_llm,
    )
    assert len(result) == 2
    assert result[0] == "Hello."
    print("test_generate_sentences_mock: PASS")


if __name__ == "__main__":
    test_extract_sentences_basic()
    test_extract_sentences_thinking_tags()
    test_extract_sentences_questions_exclamations()
    test_extract_sentences_zero_raises()
    test_extract_sentences_all_returned()
    test_generate_sentences_mock()
    print("\nAll inline tests passed.")
