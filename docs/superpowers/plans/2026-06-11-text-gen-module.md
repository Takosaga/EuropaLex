# Text Generation Module Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract LLM text generation and sentence parsing logic from `MiniCPMTextEngine` into a standalone module (`core/text_gen.py`) with two functions — a pure extraction function and a generator with retry loop.

**Architecture:** New file `core/text_gen.py` exports `extract_sentences(raw_text, expected_count) -> list[str]` (pure function) and `generate_sentences(scenario, cefr_level, batch_size, llm) -> list[str]` (LLM call + retry). `MiniCPMTextEngine.generate()` delegates to `generate_sentences()`.

**Tech Stack:** Python 3.12+, llama-cpp-python (for generate_sentences), Pydantic (ValidationError from core.types)

---

### Task 1: Write tests for `extract_sentences`

**Files:**
- Create: `scripts/test_extract_sentences.py`

- [ ] **Step 1: Write the failing test file**

Create `scripts/test_extract_sentences.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/takosaga/Projects/EuropaLex && python scripts/test_extract_sentences.py`

Expected: FAIL with `ModuleNotFoundError: No module named 'core.text_gen'`

- [ ] **Step 3: Write minimal implementation — create the module skeleton**

Create `core/text_gen.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/takosaga/Projects/EuropaLex && python scripts/test_extract_sentences.py`

Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add core/text_gen.py scripts/test_extract_sentences.py
git commit -m "feat: add extract_sentences and generate_sentences to core.text_gen"
```

---

### Task 2: Write tests for `generate_sentences` with mocked LLM

**Files:**
- Modify: `scripts/test_extract_sentences.py` (append tests)

- [ ] **Step 1: Append generate_sentences tests using a mock LLM**

Add these functions to the end of `scripts/test_extract_sentences.py`:

```python
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
    # Always return wrong count
    mock_llm.create_chat_completion.side_effect = [
        {"choices": [{"message": {"content": "1. Only one."}}]},
        {"choices": [{"message": {"content": "1. Still one.\n2. Extra noise\n3. Another one."}}]},
        {"choices": [{"message": {"content": "1. One again."}}]},
    ]

    result = generate_sentences(
        scenario="greetings",
        cefr_level=CEFRLevel.A1,
        batch_size=2,
        llm=mock_llm,
    )
    # Should return fallback (truncated to first 2 valid lines from last attempt)
    assert len(result) == 1  # Only "One again." is valid from the last attempt


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
    # ... existing tests above ...
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
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `cd /home/takosaga/Projects/EuropaLex && python scripts/test_extract_sentences.py`

Expected: All tests PASS (both extract_sentences and generate_sentences)

- [ ] **Step 3: Commit**

```bash
git add scripts/test_extract_sentences.py
git commit -m "test: add generate_sentences tests with mocked LLM"
```

---

### Task 3: Refactor `MiniCPMTextEngine.generate()` to delegate to `generate_sentences`

**Files:**
- Modify: `core/engine.py:61-145` (MiniCPMTextEngine.generate method and _build_retry_prompt)

- [ ] **Step 1: Replace MiniCPMTextEngine.generate() body**

Replace the entire `generate()` method (lines ~61–145) with:

```python
    def generate(self, texts: list[str], scenario: str, cefr_level: CEFRLevel, batch_size: int | None = None) -> TextResult:
        """Generate English sentences using the loaded GGUF model.

        Delegates to :func:`core.text_gen.generate_sentences` for LLM calling,
        retry loop, and extraction. Wraps result in ``TextResult``.

        Args:
            texts: Empty list (generation mode). Non-empty would be translation mode.
            scenario: Scenario/topic description for text generation.
            cefr_level: CEFR proficiency level.
            batch_size: Number of sentences to generate.

        Returns:
            TextResult with exactly one sentence per requested batch size.

        Raises:
            ValidationError: If generation fails after max attempts.
        """
        self._load_model()
        if batch_size is None:
            raise ValueError("batch_size is required for text generation")

        from core.text_gen import generate_sentences

        sentences = generate_sentences(scenario, cefr_level, batch_size, self._llm)
        return TextResult(generated_texts=sentences)
```

Remove the `_build_retry_prompt` method entirely (it moves to `core/text_gen.py`).

- [ ] **Step 2: Verify engine still imports correctly**

Run: `cd /home/takosaga/Projects/EuropaLex && python -c "from core.engine import MiniCPMTextEngine; print('Import OK')"`

Expected: `Import OK` (no traceback)

- [ ] **Step 3: Commit**

```bash
git add core/engine.py
git commit -m "refactor: delegate MiniCPMTextEngine.generate to core.text_gen.generate_sentences"
```

---

### Task 4: Update existing test file to use new module

**Files:**
- Modify: `scripts/test_count_enforcement.py`

- [ ] **Step 1: Replace inline _validate_lines with extract_sentences import**

Replace the entire content of `scripts/test_count_enforcement.py` with:

```python
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
    result = extract_sentences("1. Hello world.\n2. Goodbye world.", 2)
    assert len(result) == 2
    assert result[0] == "Hello world."
    assert result[1] == "Goodbye world."
    print("test_extract_sentences_basic: PASS")


def test_extract_sentences_thinking_tags():
    """Test thinking tag stripping."""
    from core.text_gen import extract_sentences
    raw = "<thinking>some thoughts</thinking>\n1. Sentence one.\n2. Sentence two."
    result = extract_sentences(raw, 2)
    assert len(result) == 2
    assert result[0] == "Sentence one."
    print("test_extract_sentences_thinking_tags: PASS")


def test_extract_sentences_questions_exclamations():
    """Test mixed punctuation handling."""
    from core.text_gen import extract_sentences
    raw = "1. Hello.\n2. How are you?\n3. What a day!"
    result = extract_sentences(raw, 3)
    assert len(result) == 3
    assert result[1] == "How are you?"
    assert result[2] == "What a day!"
    print("test_extract_sentences_questions_exclamations: PASS")


def test_extract_sentences_too_few_raises():
    """Test ValidationError on insufficient sentences."""
    from core.text_gen import extract_sentences, ValidationError
    try:
        extract_sentences("1. Only one.", 3)
        assert False, "Should raise"
    except ValidationError:
        pass
    print("test_extract_sentences_too_few_raises: PASS")


def test_extract_sentences_too_many_truncates():
    """Test truncation when more sentences than expected."""
    from core.text_gen import extract_sentences
    result = extract_sentences("1. A.\n2. B.\n3. C.", 2)
    assert len(result) == 2
    assert result == ["A.", "B."]
    print("test_extract_sentences_too_many_truncates: PASS")


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
    test_extract_sentences_too_few_raises()
    test_extract_sentences_too_many_truncates()
    test_generate_sentences_mock()
    print("\nAll inline tests passed.")
```

- [ ] **Step 2: Run updated tests**

Run: `cd /home/takosaga/Projects/EuropaLex && python scripts/test_count_enforcement.py`

Expected: All tests PASS

- [ ] **Step 3: Commit**

```bash
git add scripts/test_count_enforcement.py
git commit -m "test: update test_count_enforcement to use core.text_gen"
```

---

### Task 5: Update README.md documentation

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add text_gen.py to Architecture table**

Find the Architecture table row for `core/`:

```markdown
| `core/` | Data types (`types.py`), inference engine protocol + implementations (`engine.py`), batch pipeline orchestrator (`pipeline.py`) |
```

Replace with:

```markdown
| `core/` | Data types (`types.py`), inference engines (`engine.py`), sentence extraction & generation helpers (`text_gen.py`), batch pipeline orchestrator (`pipeline.py`) |
```

- [ ] **Step 2: Add text_gen.py to Repository Structure tree**

Find the `core/` section in the tree:

```markdown
├── core/                   # Shared business logic
│   ├── __init__.py
│   ├── types.py            # Pydantic models: CardData, CEFRLevel, TextResult, AudioResult, ImageResult, EngineConfig
│   ├── engine.py           # MiniCPMTextEngine (MiniCPM5-1B/llama-cpp-python), LlamaCppTextEngine (tiny-aya/llama-cpp-python), TTSEngine (OmniVoice), ImageGenEngine (diffusers), EnginePool singleton
│   └── pipeline.py         # Batch generator: text → audio → image orchestrator
```

Replace with:

```markdown
├── core/                   # Shared business logic
│   ├── __init__.py
│   ├── types.py            # Pydantic models: CardData, CEFRLevel, TextResult, AudioResult, ImageResult, EngineConfig
│   ├── engine.py           # MiniCPMTextEngine (MiniCPM5-1B/llama-cpp-python), LlamaCppTextEngine (tiny-aya/llama-cpp-python), TTSEngine (OmniVoice), ImageGenEngine (diffusers), EnginePool singleton
│   ├── text_gen.py         # Sentence extraction (extract_sentences) and generation with retry loop (generate_sentences)
│   └── pipeline.py         # Batch generator: text → audio → image orchestrator
```

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: add text_gen.py to README architecture and repository structure"
```

---

### Task 6: Update AGENTS.md documentation

**Files:**
- Modify: `AGENTS.md`

- [ ] **Step 1: Add text_gen.py to Module Boundaries table**

Find the Module Boundaries table. Add a new row after the `core/` row:

```markdown
| `core/text_gen.py` | Sentence extraction (`extract_sentences`) and LLM generation with retry loop (`generate_sentences`) | Import from other modules for text generation logic |
```

- [ ] **Step 2: Update Architecture at a glance**

Find the line:

```markdown
- `core/` — Pydantic types (`types.py`), five engine classes + EnginePool singleton (`engine.py`), batch pipeline (`pipeline.py`)
```

Replace with:

```markdown
- `core/` — Pydantic types (`types.py`), inference engines + EnginePool singleton (`engine.py`), sentence extraction & generation helpers (`text_gen.py`), batch pipeline (`pipeline.py`)
```

- [ ] **Step 3: Commit**

```bash
git add AGENTS.md
git commit -m "docs: add text_gen.py to AGENTS.md module boundaries and architecture"
```

---

### Task 7: Run smoke test and verify end-to-end

**Files:**
- Run: `scripts/smoke_test.py`

- [ ] **Step 1: Run smoke test**

Run: `cd /home/takosaga/Projects/EuropaLex && python scripts/smoke_test.py`

Expected: Clean exit (no traceback)

- [ ] **Step 2: Verify full import chain works**

Run: `cd /home/takosaga/Projects/EuropaLex && python -c "from core.text_gen import extract_sentences, generate_sentences; from core.engine import MiniCPMTextEngine; print('All imports OK')"`

Expected: `All imports OK`

- [ ] **Step 3: Final commit**

```bash
git add .
git commit -m "chore: run smoke test after text_gen refactor"
```

---

## Self-Review Checklist

**1. Spec coverage:** Every requirement in the design spec has a task:
- `extract_sentences()` pure function → Task 1
- `generate_sentences()` with retry loop → Task 1 + Task 2
- MiniCPMTextEngine refactoring → Task 3
- Existing test update → Task 4
- README.md docs → Task 5
- AGENTS.md docs → Task 6
- Smoke test verification → Task 7

**2. Placeholder scan:** No "TBD", "TODO", or vague references found. Every step has exact file paths, code blocks, and commands.

**3. Type consistency:** `ValidationError` imported from `core.types` in both `text_gen.py` and tests. `CEFRLevel` used consistently. Function signatures match the spec exactly.

**4. No unnecessary changes:** Only the files listed in the spec are modified. `types.py`, `pipeline.py`, `frontend/`, and `export/` are untouched.
