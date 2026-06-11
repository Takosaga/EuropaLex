"""Sentence extraction and text generation helpers for EuropaLex.

Provides two functions:
- extract_sentences(raw_text) -> list[str]: Pure function that strips thinking tags,
  parses numbered format (1., 2), etc.), and returns ALL extracted sentences — no cap.
- generate_sentences(scenario, cefr_level, batch_size, llm, topic_description) -> list[str]:
  Orchestrates LLM call with uncapped token limit, extracts numbered sentences and enforces
  a minimum count. batch_size is the floor; if more are produced, only the first ``batch_size``
  are returned. Retries up to 2 times if fewer than ``batch_size`` are produced.
  CEFR level provides linguistic guidance only — topics come from topic_description.
"""

from __future__ import annotations

import logging
import re

from core.types import CEFRLevel, ValidationError

logger = logging.getLogger(__name__)


def extract_sentences(raw_text: str) -> list[str]:
    """Strip thinking tags, parse numbered format, return all extracted sentences.

    Strips ``<thinking>...</thinking>`` blocks, extracts lines that start with
    a number + punctuation (``1.``, ``2)``, etc.), strips the numbering,
    and returns all valid non-empty lines — no upper cap.

    Args:
        raw_text: Raw LLM output (may contain thinking tags, numbering, extra lines).

    Returns:
        List of cleaned sentence strings from all numbered lines found.

    Raises:
        ValidationError: If zero numbered sentences can be extracted.
    """
    # Step 1: Strip thinking tags
    stripped = re.sub(r"<thinking>.*?</thinking>", "", raw_text, flags=re.DOTALL).strip()

    # Step 2: Extract ONLY numbered lines — split, check for leading number+punct
    sentences = []
    for line in stripped.split("\n"):
        line = line.strip()
        if not line:
            continue
        match = re.match(r"^(\d+[.)]\s*)(.*)", line)
        if match:
            content = match.group(2).strip()
            if content:
                sentences.append(content)

    # Step 3: Enforce at least one sentence
    if not sentences:
        raise ValidationError(
            "Expected at least 1 numbered sentence but got none.",
            raw_output=raw_text,
        )

    logger.info("extract_sentences: extracted %d numbered sentences", len(sentences))
    return sentences


def generate_sentences(
    scenario: str,
    cefr_level: CEFRLevel,
    batch_size: int,
    llm,  # llama_cpp.Llama instance
    topic_description: str = "",
) -> list[str]:
    """Generate English sentences via LLM and extract all numbered output.

    Builds a prompt for the language teacher persona, calls the LLM with an
    uncapped token limit, then extracts all numbered sentences (1., 2., 3., …)
    from the output. The ``batch_size`` parameter is used as a minimum floor
    — if fewer sentences are produced than requested, retries once.

    Args:
        scenario: Topic description for the LLM.
        cefr_level: CEFR proficiency level (linguistic guidance only).
        batch_size: Minimum number of sentences to return.
        llm: Loaded llama-cpp-python Llama instance.
        topic_description: Free-form description of topics/themes. Overrides any
            topic hints from the CEFR level.

    Returns:
        List of clean sentence strings (up to ``batch_size``) from numbered lines in the output.

    Raises:
        ValidationError: If extraction fails on both attempts (with raw output attached).
    """
    # Build topic guidance — use free-form description if provided, otherwise fall back to scenario
    if topic_description:
        topic_guidance = (
            f"Focus on these topics/themes: {topic_description}. "
            "Each sentence should explore a different aspect of these topics."
        )
    else:
        topic_guidance = (
            f"Focus on the scenario described below. "
            "Each sentence should explore a different aspect of it."
        )

    _base_messages = [
        {
            "role": "system",
            "content": (
                "You are a language teacher. Generate clear sentences appropriate for the specified CEFR level "
                "about the given topics/scenario. Number each sentence 1 to N, one per line. "
                f"Generate AT LEAST {batch_size} numbered sentences — more is acceptable.\n"
                "\n"
                "CEFR LINGUISTIC GUIDANCE:\n"
                f"{cefr_level.description()}\n"
                "\n"
                f"{topic_guidance}\n"
                "\n"
                "VARIETY REQUIREMENT: Each sentence must cover a different aspect or sub-topic. "
                "Do NOT repeat similar ideas. Mix sentence types (statements, questions, exclamations). "
                "Use diverse vocabulary and sentence structures — avoid starting multiple sentences the same way.\n"
                "\n"
                "OUTPUT FORMAT: ONLY output numbered lines (1., 2., 3.) — one sentence per line. No explanations, no extra text.\n"
                "\n"
                "Example:\n"
                "1. The cat sits on the mat.\n"
                "2. It drinks milk from a bowl."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Generate sentences appropriate for CEFR level {cefr_level.value}\n"
                f"about the following topics/scenario. Number each sentence 1 to N, one per line.\n"
                f"Generate AT LEAST {batch_size} sentences — more is acceptable.\n"
                "\n"
                f"Topics/themes: {topic_description if topic_description else scenario}\n"
                f"Scenario details: {scenario}\n"
                "\n"
                "IMPORTANT: Make each sentence about a DIFFERENT aspect of the topics/scenario. "
                "Use varied vocabulary and structures — no repetitive patterns.\n"
                "\n"
                "Output ONLY the numbered sentences, one per line. No other text."
            ),
        },
    ]

    max_tokens = 2048
    last_raw_output = ""

    for attempt in range(1, 4):
        messages = list(_base_messages)
        output = llm.create_chat_completion(
            messages=messages,
            max_tokens=max_tokens,
            temperature=0.7,
        )

        raw_text = output["choices"][0]["message"]["content"]
        last_raw_output = raw_text

        try:
            result = extract_sentences(raw_text)
            # More than enough — take the first batch_size
            if len(result) >= batch_size:
                trimmed = result[:batch_size]
                if len(result) > batch_size:
                    logger.info(
                        "generate_sentences: got %d sentences on attempt %d (target=%d, trimming)",
                        len(result), attempt, batch_size,
                    )
                else:
                    logger.info(
                        "generate_sentences: got %d sentences on attempt %d (target=%d)",
                        len(result), attempt, batch_size,
                    )
                return trimmed
            # Fewer than batch_size — retry with a hint
            if attempt < 3:
                messages.append({
                    "role": "assistant",
                    "content": raw_text,
                })
                messages.append({
                    "role": "user",
                    "content": (
                        f"You generated {len(result)} but need at least {batch_size}. "
                        f"Regenerate all {batch_size} numbered sentences, one per line.\n"
                        f"Output ONLY numbered lines like:\n1. Sentence here.\n2. Another sentence."
                    ),
                })
                logger.warning(
                    "generate_sentences attempt %d: got %d sentences, need at least %d — retrying",
                    attempt, len(result), batch_size,
                )
            else:
                return result
        except ValidationError:
            if attempt < 2:
                messages.append({
                    "role": "assistant",
                    "content": raw_text,
                })
                messages.append({
                    "role": "user",
                    "content": (
                        f"No numbered sentences found. Please output your sentences as:\n"
                        f"1. First sentence here.\n2. Second sentence here.\n3. Third sentence here."
                    ),
                })
                logger.warning(
                    "generate_sentences attempt %d: no numbered sentences — retrying",
                    attempt,
                )
            else:
                raise

    # Exhausted retries — return whatever we got (or empty)
    logger.warning(
        "generate_sentences: exhausted all attempts. Got %d numbered sentences.",
        len(extract_sentences(last_raw_output)) if last_raw_output else 0,
    )
    try:
        return extract_sentences(last_raw_output)
    except ValidationError:
        raise ValidationError(
            f"Could not extract any numbered sentences after multiple attempts.",
            raw_output=last_raw_output,
        )
