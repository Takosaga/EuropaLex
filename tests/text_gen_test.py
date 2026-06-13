"""Tests for core.text_gen.extract_sentences and generate_sentences.

Merged from count_enforcement_test.py and extract_sentences_test.py.
All tests use mocking — no LLM inference needed.
"""

import pytest
from unittest.mock import MagicMock

from core.text_gen import extract_sentences, generate_sentences
from core.types import CEFRLevel, ValidationError


# ── extract_sentences ────────────────────────────────────────────

def test_extract_sentences_basic_numbered_format():
    """Basic numbered format: '1. Hello.\n2. World.' → ['Hello.', 'World.']"""
    result = extract_sentences("1. Hello world.\n2. Goodbye world.")
    assert len(result) == 2
    assert result[0] == "Hello world."
    assert result[1] == "Goodbye world."


def test_extract_sentences_thinking_tag_stripping():
    """Strips <thinking> tags before parsing."""
    raw = "<thinking>some thoughts\nmore thoughts</thinking>\n1. Sentence one.\n2. Sentence two."
    result = extract_sentences(raw)
    assert len(result) == 2
    assert result[0] == "Sentence one."
    assert result[1] == "Sentence two."


def test_extract_sentences_mixed_punctuation():
    """Sentences ending with ., ?, ! all recognized."""
    raw = "1. Hello.\n2. How are you?\n3. What a day!"
    result = extract_sentences(raw)
    assert len(result) == 3
    assert result[0] == "Hello."
    assert result[1] == "How are you?"
    assert result[2] == "What a day!"


def test_extract_sentences_zero_sentences_raises():
    """Zero numbered sentences raises ValidationError."""
    with pytest.raises(ValidationError):
        extract_sentences("No numbered lines here.\nJust plain text.")


def test_extract_sentences_uncapped_20_sentences():
    """20 numbered sentences all returned — no upper cap."""
    lines = "\n".join(f"{i}. Sentence {i}." for i in range(1, 21))
    result = extract_sentences(lines)
    assert len(result) == 20
    assert result[0] == "Sentence 1."
    assert result[19] == "Sentence 20."


def test_extract_sentences_ignores_non_numbered_lines():
    """Non-numbered lines silently ignored, not discarded."""
    raw = "Some intro text.\n1. Valid sentence.\nMore text.\n2. Another valid."
    result = extract_sentences(raw)
    assert len(result) == 2
    assert result[0] == "Valid sentence."
    assert result[1] == "Another valid."


def test_extract_sentences_dot_numbering_format():
    """Dot numbering (1., 2.) format recognized."""
    raw = "1. First.\n2. Second.\n3. Third."
    result = extract_sentences(raw)
    assert len(result) == 3
    assert result == ["First.", "Second.", "Third."]


def test_extract_sentences_paren_numbering_format():
    """Paren numbering (1), 2)) format recognized."""
    raw = "1) First.\n2) Second.\n3) Third."
    result = extract_sentences(raw)
    assert len(result) == 3
    assert result == ["First.", "Second.", "Third."]


def test_extract_sentences_empty_after_tag_stripping_raises():
    """Raw text contains only thinking tags → ValidationError."""
    with pytest.raises(ValidationError):
        extract_sentences("<thinking>only reasoning</thinking>")


# ── generate_sentences ───────────────────────────────────────────

def test_generate_sentences_success_first_try(mock_llm_response_factory):
    """Success on first try with exact batch_size."""
    mock_llm = MagicMock()
    mock_llm.create_chat_completion.return_value = mock_llm_response_factory(
        "1. Hello.\n2. World."
    )

    result = generate_sentences(
        scenario="test",
        cefr_level=CEFRLevel.A1,
        batch_size=2,
        llm=mock_llm,
    )
    assert len(result) == 2
    assert result[0] == "Hello."
    assert result[1] == "World."


def test_generate_sentences_uncapped_extraction():
    """More sentences than batch_size: returns all extracted (up to batch_size cap)."""
    mock_llm = MagicMock()
    mock_llm.create_chat_completion.return_value = {
        "choices": [{"message": {"content": "1. First.\n2. Second.\n3. Third.\n4. Fourth."}}]
    }

    result = generate_sentences(
        scenario="test",
        cefr_level=CEFRLevel.A1,
        batch_size=2,
        llm=mock_llm,
    )
    # batch_size is a cap: returns first 2
    assert len(result) == 2


def test_generate_sentences_retry_on_fewer_than_batch():
    """Retries when fewer than batch_size sentences on first call."""
    mock_llm = MagicMock()
    mock_llm.create_chat_completion.side_effect = [
        {"choices": [{"message": {"content": "1. Only one sentence."}}]},
        {"choices": [{"message": {"content": "2. Second.\n3. Third.\n4. Fourth."}}]},
    ]

    result = generate_sentences(
        scenario="greetings",
        cefr_level=CEFRLevel.A1,
        batch_size=3,
        llm=mock_llm,
    )
    assert len(result) == 3
    assert mock_llm.create_chat_completion.call_count == 2


def test_generate_sentences_fallback_after_exhausted_retries():
    """Returns whatever was produced after retries exhausted (3 LLM calls total)."""
    mock_llm = MagicMock()
    # 1st call: 1 sentence. 2nd call: 2 sentences (< batch_size=3, retries).
    # 3rd call: same output → returns 2 sentences after retry exhaustion.
    mock_llm.create_chat_completion.side_effect = [
        {"choices": [{"message": {"content": "1. Only one."}}]},
        {"choices": [{"message": {"content": "2. Second.\n3. Third."}}]},
        {"choices": [{"message": {"content": "2. Second.\n3. Third."}}]},  # attempt 3, returns result
    ]

    result = generate_sentences(
        scenario="greetings",
        cefr_level=CEFRLevel.A1,
        batch_size=3,
        llm=mock_llm,
    )
    assert len(result) == 2


def test_generate_sentences_thinking_tags_handled():
    """LLM output containing thinking tags handled correctly."""
    mock_llm = MagicMock()
    mock_llm.create_chat_completion.return_value = {
        "choices": [{"message": {"content": "<thinking>reasoning</thinking>\n1. Hello.\n2. World."}}]
    }

    result = generate_sentences(
        scenario="test",
        cefr_level=CEFRLevel.A1,
        batch_size=2,
        llm=mock_llm,
    )
    assert len(result) == 2
    assert result[0] == "Hello."


def test_generate_sentences_question_sentences_preserved():
    """Question sentences preserved in output."""
    mock_llm = MagicMock()
    mock_llm.create_chat_completion.return_value = {
        "choices": [{"message": {"content": "1. What is this?\n2. It is a cat."}}]
    }

    result = generate_sentences(
        scenario="test",
        cefr_level=CEFRLevel.A1,
        batch_size=2,
        llm=mock_llm,
    )
    assert len(result) == 2
    assert result[0] == "What is this?"
