"""Tests for core.text_gen.extract_sentences — pure function, no LLM needed."""

import sys
from pathlib import Path

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_exact_count():
    """Extract exactly the expected number of sentences."""
    from core.text_gen import extract_sentences
    result = extract_sentences("1. Hello world.\n2. Goodbye world.", 2)
    assert len(result) == 2
    assert result[0] == "Hello world."
    assert result[1] == "Goodbye world."


def test_thinking_tag_stripping():
    """Strip <thinking> tags before parsing."""
    from core.text_gen import extract_sentences
    raw = "<thinking>some thoughts\nmore thoughts</thinking>\n1. Sentence one.\n2. Sentence two."
    result = extract_sentences(raw, 2)
    assert len(result) == 2
    assert result[0] == "Sentence one."
    assert result[1] == "Sentence two."


def test_questions_and_exclamations():
    """Handle sentences ending with ? and ! as valid."""
    from core.text_gen import extract_sentences
    raw = "1. Hello.\n2. How are you?\n3. What a day!"
    result = extract_sentences(raw, 3)
    assert len(result) == 3
    assert result[0] == "Hello."
    assert result[1] == "How are you?"
    assert result[2] == "What a day!"


def test_mixed_punctuation_with_thinking():
    """Strip tags and handle mixed . ? ! endings."""
    from core.text_gen import extract_sentences
    raw = "<thinking>reasoning here</thinking>\n1. The cat sits.\n2. Is it hungry?\n3. It wants food!"
    result = extract_sentences(raw, 3)
    assert len(result) == 3
    assert result[0] == "The cat sits."
    assert result[1] == "Is it hungry?"
    assert result[2] == "It wants food!"


def test_too_few_raises_validationerror():
    """Raise ValidationError if fewer than expected_count valid items."""
    from core.text_gen import extract_sentences, ValidationError
    try:
        extract_sentences("1. Only one.", 3)
        assert False, "Should raise ValidationError"
    except ValidationError:
        pass


def test_too_many_truncates():
    """Take first expected_count when more are provided."""
    from core.text_gen import extract_sentences
    result = extract_sentences("1. First.\n2. Second.\n3. Third.", 2)
    assert len(result) == 2
    assert result[0] == "First."
    assert result[1] == "Second."


def test_discards_lines_without_terminal_punctuation():
    """Discard lines that don't end with . ? or !."""
    from core.text_gen import extract_sentences, ValidationError
    # "incomplete line" has no terminal punctuation — should be discarded
    raw = "1. Valid sentence.\n2. Incomplete line\n3. Another valid."
    try:
        extract_sentences(raw, 3)
        assert False, "Should raise — only 2 valid items after discarding"
    except ValidationError:
        pass


def test_empty_after_tag_stripping_raises():
    """Raise if raw text contains only thinking tags."""
    from core.text_gen import extract_sentences, ValidationError
    try:
        extract_sentences("<thinking>only reasoning</thinking>", 1)
        assert False, "Should raise on empty output"
    except ValidationError:
        pass


def test_dot_numbering_format():
    """Handle numbered format with dot (1. 2. 3.)."""
    from core.text_gen import extract_sentences
    result = extract_sentences("1. First.\n2. Second.", 2)
    assert len(result) == 2
    assert result[0] == "First."


def test_dot_numbering_with_paren_format():
    """Handle numbered format with paren (1) 2) 3)."""
    from core.text_gen import extract_sentences
    result = extract_sentences("1) First.\n2) Second.", 2)
    assert len(result) == 2
    assert result[0] == "First."


def test_generate_sentences_success():
    """generate_sentences returns clean sentences on first try."""
    from unittest.mock import MagicMock
    from core.text_gen import generate_sentences
    from core.types import CEFRLevel

    mock_llm = MagicMock()
    mock_llm.create_chat_completion.return_value = {
        "choices": [{"message": {"content": "1. Hello world.\n2. Goodbye world."}}]
    }

    result = generate_sentences(
        scenario="greetings",
        cefr_level=CEFRLevel.A1,
        batch_size=2,
        llm=mock_llm,
    )
    assert len(result) == 2
    assert result[0] == "Hello world."
    assert result[1] == "Goodbye world."


def test_generate_sentences_retry_on_count_mismatch():
    """generate_sentences retries when LLM returns wrong count."""
    from unittest.mock import MagicMock, call
    from core.text_gen import generate_sentences, ValidationError
    from core.types import CEFRLevel

    mock_llm = MagicMock()
    # First call returns too few sentences (1 instead of 2)
    mock_llm.create_chat_completion.side_effect = [
        {"choices": [{"message": {"content": "1. Only one sentence."}}]},
        {"choices": [{"message": {"content": "1. Hello world.\n2. Goodbye world."}}]},
    ]

    result = generate_sentences(
        scenario="greetings",
        cefr_level=CEFRLevel.A1,
        batch_size=2,
        llm=mock_llm,
    )
    assert len(result) == 2
    # Verify retry was called (2 calls total)
    assert mock_llm.create_chat_completion.call_count == 2


def test_generate_sentences_fallback_after_exhausted_retries():
    """generate_sentences returns truncated fallback after 3 failed attempts."""
    from unittest.mock import MagicMock
    from core.text_gen import generate_sentences, ValidationError
    from core.types import CEFRLevel

    mock_llm = MagicMock()
    # Always return wrong count (always fewer than expected)
    mock_llm.create_chat_completion.side_effect = [
        {"choices": [{"message": {"content": "1. Only one."}}]},
        {"choices": [{"message": {"content": "2. Second attempt only."}}]},
        {"choices": [{"message": {"content": "3. Final attempt.\n4. Also this one.\n5. Too many but some will be discarded noise\n6. Another valid."}}]},
    ]

    result = generate_sentences(
        scenario="greetings",
        cefr_level=CEFRLevel.A1,
        batch_size=2,
        llm=mock_llm,
    )
    # Should return fallback (first 2 valid lines from last attempt, discarding line without terminal punctuation)
    assert len(result) == 2
    assert result[0] == "Final attempt."
    assert result[1] == "Also this one."


def test_generate_sentences_with_thinking_tags():
    """generate_sentences handles LLM output containing thinking tags."""
    from unittest.mock import MagicMock
    from core.text_gen import generate_sentences
    from core.types import CEFRLevel

    mock_llm = MagicMock()
    mock_llm.create_chat_completion.return_value = {
        "choices": [{
            "message": {
                "content": "<thinking>Let me think about this\nThe scenario is greetings</thinking>\n1. Hello there.\n2. How are you?"
            }
        }]
    }

    result = generate_sentences(
        scenario="greetings",
        cefr_level=CEFRLevel.A1,
        batch_size=2,
        llm=mock_llm,
    )
    assert len(result) == 2
    assert result[0] == "Hello there."
    assert result[1] == "How are you?"


def test_generate_sentences_with_questions():
    """generate_sentences handles question sentences."""
    from unittest.mock import MagicMock
    from core.text_gen import generate_sentences
    from core.types import CEFRLevel

    mock_llm = MagicMock()
    mock_llm.create_chat_completion.return_value = {
        "choices": [{"message": {"content": "1. What is your name?\n2. Where do you live?"}}]
    }

    result = generate_sentences(
        scenario="introductions",
        cefr_level=CEFRLevel.A1,
        batch_size=2,
        llm=mock_llm,
    )
    assert len(result) == 2
    assert result[0] == "What is your name?"
    assert result[1] == "Where do you live?"


if __name__ == "__main__":
    test_exact_count()
    print("test_exact_count: PASS")
    test_thinking_tag_stripping()
    print("test_thinking_tag_stripping: PASS")
    test_questions_and_exclamations()
    print("test_questions_and_exclamations: PASS")
    test_mixed_punctuation_with_thinking()
    print("test_mixed_punctuation_with_thinking: PASS")
    test_too_few_raises_validationerror()
    print("test_too_few_raises_validationerror: PASS")
    test_too_many_truncates()
    print("test_too_many_truncates: PASS")
    test_discards_lines_without_terminal_punctuation()
    print("test_discards_lines_without_terminal_punctuation: PASS")
    test_empty_after_tag_stripping_raises()
    print("test_empty_after_tag_stripping_raises: PASS")
    test_dot_numbering_format()
    print("test_dot_numbering_format: PASS")
    test_dot_numbering_with_paren_format()
    print("test_dot_numbering_with_paren_format: PASS")
    test_generate_sentences_success()
    print("test_generate_sentences_success: PASS")
    test_generate_sentences_retry_on_count_mismatch()
    print("test_generate_sentences_retry_on_count_mismatch: PASS")
    test_generate_sentences_fallback_after_exhausted_retries()
    print("test_generate_sentences_fallback_after_exhausted_retries: PASS")
    test_generate_sentences_with_thinking_tags()
    print("test_generate_sentences_with_thinking_tags: PASS")
    test_generate_sentences_with_questions()
    print("test_generate_sentences_with_questions: PASS")
    print("\nAll tests passed.")
