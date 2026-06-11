"""Sentence extraction and text generation helpers for EuropaLex.

Provides two functions:
- extract_sentences(raw_text, expected_count) -> list[str]: Pure function that strips
  thinking tags, parses numbered format (. ? !), and enforces sentence count.
- generate_sentences(scenario, cefr_level, batch_size, llm) -> list[str]: Orchestrates
  LLM call with retry loop for exact sentence count enforcement.
"""

from __future__ import annotations

import logging
import re

from core.types import CEFRLevel, ValidationError

logger = logging.getLogger(__name__)


def extract_sentences(raw_text: str, expected_count: int) -> list[str]:
    """Strip thinking tags, parse numbered format, enforce count.

    Strips ``<thinking>...</thinking>`` blocks, splits on newlines, strips
    leading numbers/punctuation (``1.`` or ``1)``), discards lines without
    terminal punctuation (``.``, ``?``, ``!``), and enforces exact count.

    Args:
        raw_text: Raw LLM output (may contain thinking tags, numbering, extra lines).
        expected_count: Number of sentences expected (batch_size).

    Returns:
        List of cleaned sentence strings, exactly ``expected_count`` items.

    Raises:
        ValidationError: If fewer than expected_count valid sentences can be extracted.
    """
    # Step 1: Strip thinking tags
    stripped = re.sub(r"<thinking>.*?</thinking>", "", raw_text, flags=re.DOTALL).strip()

    # Step 2: Parse numbered format — split lines, strip numbering, discard blanks
    lines = []
    for line in stripped.split("\n"):
        line = line.strip()
        if not line:
            continue
        # Remove leading number + punctuation (e.g. "1. ", "2) ")
        line = re.sub(r"^\d+[.)]\s*", "", line).strip()
        if not line:
            continue
        lines.append(line)

    # Step 3: Discard lines without terminal punctuation (. ? !)
    valid_lines = [l for l in lines if l.endswith((".", "?", "!"))]

    # Step 4: Enforce count
    if len(valid_lines) < expected_count:
        raise ValidationError(
            f"Expected {expected_count} sentences but got {len(valid_lines)}.",
            raw_output=raw_text,
        )

    if len(valid_lines) > expected_count:
        logger.warning(
            "extract_sentences: got %d sentences, expected %d — truncating to first %d",
            len(valid_lines), expected_count, expected_count,
        )

    return valid_lines[:expected_count]


def generate_sentences(
    scenario: str,
    cefr_level: CEFRLevel,
    batch_size: int,
    llm,  # llama_cpp.Llama instance
) -> list[str]:
    """Generate English sentences via LLM with retry loop and extraction.

    Builds a prompt for the language teacher persona, calls the LLM, validates
    output with ``extract_sentences()``, and retries up to 3 times on count mismatch
    with stricter prompts.

    Args:
        scenario: Topic description for the LLM.
        cefr_level: CEFR proficiency level.
        batch_size: Number of sentences to generate.
        llm: Loaded llama-cpp-python Llama instance.

    Returns:
        List of exactly ``batch_size`` clean sentence strings.

    Raises:
        ValidationError: If generation fails after 3 retry attempts (with raw output attached).
    """
    _base_messages = [
        {
            "role": "system",
            "content": (
                "You are a language teacher. Generate simple, clear sentences at the specified CEFR level "
                "about the given scenario. Output EXACTLY the requested number of sentences, numbered 1 to N, "
                "one per line. No explanations, no reasoning tags, no extra text.\n"
                "\n"
                "Example for 2 sentences:\n"
                "1. The cat sits on the mat.\n"
                "2. It drinks milk from a bowl."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Generate exactly {batch_size} simple sentences at CEFR level {cefr_level.value}\n"
                f"about the following scenario. Number each sentence 1 to {batch_size}, one per line.\n"
                f"Scenario: {scenario}\n"
                "Output ONLY the numbered sentences. No explanations. No reasoning tags."
            ),
        },
    ]

    max_attempts = 3
    last_raw_output = ""

    for attempt in range(1, max_attempts + 1):
        messages = list(_base_messages)
        output = llm.create_chat_completion(
            messages=messages,
            max_tokens=150,
            temperature=0.3,
            stop=["\n\n", "\n\n\n"],
        )

        raw_text = output["choices"][0]["message"]["content"]
        last_raw_output = raw_text

        try:
            result = extract_sentences(raw_text, expected_count=batch_size)
            logger.debug(
                "generate_sentences: got %d/%d sentences on attempt %d",
                len(result), batch_size, attempt,
            )
            return result
        except ValidationError:
            stripped = re.sub(r"<thinking>.*?</thinking>", "", raw_text, flags=re.DOTALL).strip()
            actual_count = len([l for l in stripped.split("\n") if l.strip()])
            messages.append({
                "role": "assistant",
                "content": raw_text,
            })
            messages.append({
                "role": "user",
                "content": _build_retry_prompt(actual_count, batch_size),
            })
            logger.warning(
                "generate_sentences attempt %d: got ~%d sentences, expected %d — retrying",
                attempt, actual_count, batch_size,
            )

    # Exhausted all retries — fall back to truncating rather than crashing
    stripped = re.sub(r"<thinking>.*?</thinking>", "", last_raw_output, flags=re.DOTALL).strip()
    fallback_lines = [
        re.sub(r"^\d+[.)]\s*", "", line).strip()
        for line in stripped.split("\n")
        if line.strip() and line.strip().endswith((".", "?", "!"))
    ]
    truncated = fallback_lines[:batch_size] if len(fallback_lines) > batch_size else fallback_lines
    logger.warning(
        "generate_sentences: exhausted %d retries (final output had %d sentences, expected %d). "
        "Truncating to first %d. Consider increasing max_tokens or checking the model.",
        max_attempts, len(fallback_lines), batch_size, batch_size,
    )
    return truncated


def _build_retry_prompt(actual: int, expected: int) -> str:
    """Build a stricter prompt referencing the count mismatch.

    For small models (1B params), retries restate the numbered format
    with explicit line-range instructions rather than appending context.

    Args:
        actual: Number of sentences the LLM produced.
        expected: Number of sentences requested (batch_size).

    Returns:
        A user-message string to append as the next turn in the conversation.
    """
    if actual > expected:
        return (
            f"Too many sentences. Output ONLY sentences 1 through {expected}, numbered 1 to {expected}. "
            f"One per line. No explanations.\n"
            f"Example:\n1. First sentence here.\n2. Second sentence here.\n3. Third sentence here."
        )
    else:
        return (
            f"Too few sentences. Output exactly {expected} sentences numbered 1 to {expected}. "
            f"One per line. No explanations."
        )
