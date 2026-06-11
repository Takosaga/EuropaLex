# Text Generation & Sentence Extraction Module

**Date:** 2026-06-11
**Status:** Approved
**Related:** `MiniCPMTextEngine` in `core/engine.py`, `scripts/test_count_enforcement.py`

## Overview

Extract the LLM text generation and sentence parsing logic from `MiniCPMTextEngine` into a standalone module (`core/text_gen.py`). This makes the extraction logic independently testable and reusable across engines.

## Architecture

```
core/text_gen.py          ← new file
├── extract_sentences(raw_text: str, expected_count: int) -> list[str]
│   └── Pure function. Strips <thinking> tags, parses numbered format (. ? !), enforces count.
│       Raises ValidationError on mismatch.
│
└── generate_sentences(scenario: str, cefr_level: CEFRLevel, batch_size: int, llm: Llama) -> list[str]
    └── Orchestrates LLM call + retry loop. Builds prompt, calls LLM, validates with extract_sentences(), retries up to 3x.
```

## Functions

### `extract_sentences(raw_text, expected_count) -> list[str]`

Pure function — no side effects. Three steps:

1. **Strip thinking tags:** Remove `<thinking>...</thinking>` blocks from raw text.
2. **Parse numbered format:** Split on newlines, strip leading numbers/punctuation (`^\d+[.)]\s*`), trim whitespace, discard blank lines and lines without terminal punctuation (`.`, `?`, `!`).
3. **Enforce count:** If fewer than `expected_count` valid items remain, raise `ValidationError`. If more, take the first `expected_count` (with a warning logged).

### `generate_sentences(scenario, cefr_level, batch_size, llm) -> list[str]`

Orchestrates generation with retry logic:

1. **Build prompt:** System message (language teacher persona, numbered format example) + user message (scenario, CEFR level, count).
2. **Call LLM:** `llm.create_chat_completion()` with temperature 0.3, max_tokens 150, stop on blank lines.
3. **Validate:** Pass raw output to `extract_sentences()`.
4. **Retry on mismatch:** On `ValidationError`, append the model's failed assistant turn + a stricter retry prompt (referencing actual vs expected count). Max 3 total attempts.
5. **Fallback:** After exhaustion, truncate the first N lines rather than crashing.

## MiniCPMTextEngine Refactoring

The engine's `generate()` method shrinks from ~80 lines to ~15:

```python
def generate(self, texts: list[str], scenario: str, cefr_level: CEFRLevel, batch_size: int | None = None) -> TextResult:
    self._load_model()
    if batch_size is None:
        raise ValueError("batch_size is required")
    
    sentences = generate_sentences(scenario, cefr_level, batch_size, self._llm)
    return TextResult(generated_texts=sentences)
```

The system prompt, retry logic, and parsing all move into `text_gen.py`. The engine becomes a thin adapter: load model → delegate → wrap in `TextResult`.

## File Changes

| File | Change |
|---|---|
| `core/text_gen.py` | **New** — contains `extract_sentences()` and `generate_sentences()` |
| `core/engine.py` | Removed inline prompt/retry/parsing from `MiniCPMTextEngine.generate()` (~65 lines removed, ~10 added) |
| `scripts/test_count_enforcement.py` | Updated to import from `core.text_gen` instead of `MiniCPMTextEngine._validate_lines` |
| `README.md` | Added `text_gen.py` to Architecture table and Repository Structure tree |
| `AGENTS.md` | Added module boundary row for `text_gen.py`, documented functions |

## Backward Compatibility

- `TextResult.validate_and_parse()` in `core/types.py` remains unchanged — it is still used by the translation engine (`LlamaCppTextEngine`). This new module does not replace it.
- No public API changes to `MiniCPMTextEngine.generate()` signature or return type.

## Testing

- `extract_sentences()` is a pure function — testable with unit tests (existing `scripts/test_count_enforcement.py` can be refactored to import from the new module).
- `generate_sentences()` requires a loaded Llama instance — tested via smoke tests and inline assertions in its own module.
