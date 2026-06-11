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
    print("\nAll extract_sentences tests passed.")
