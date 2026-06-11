# LLM Output Count Enforcement — Design Spec

**Date:** 2026-06-11
**Status:** Draft
**Module:** `core/engine.py` (`MiniCPMTextEngine`)

## Problem Statement

`MiniCPMTextEngine.generate()` sends a prompt asking for N sentences (where N = `batch_size`), but the LLM frequently returns many more — e.g., 10+ sentences when batch_size=3. The current band-aid in `app.py` silently slices `raw_cards[:batch_size]`, discarding extras without any validation at a type boundary. There is no contract enforcement: the engine splits output by newlines and returns everything it gets.

## Goals

- Enforce that `TextResult.translations` contains exactly `batch_size` sentences after generation.
- Fail loudly (with logging) when the LLM consistently misbehaves, rather than silently discarding output.
- Keep `TextResult` as a plain Pydantic model — no count validation on the type itself.

## Non-Goals

- Changing the prompt format for the initial request (the existing system + user prompts stay as-is).
- Adding retry logic to other engines (`LlamaCppTextEngine`, `TTSEngine`, `ImageGenEngine`).
- Modifying `app.py` slice logic beyond removing the now-redundant band-aid.

## Approach: Engine-Level Validation with Retry Loop

Validation lives inside `MiniCPMTextEngine.generate()`. The method performs a generate → validate → retry cycle before returning a `TextResult`.

### Flow

```
generate(texts, scenario, cefr_level, batch_size)
  │
  ├─ _load_model()
  │
  ├─ for attempt in range(1, max_attempts + 1):
  │   │
  │   ├─ call LLM with current prompt
  │   ├─ split output into non-empty lines
  │   │
  │   ├─ if len(lines) == batch_size:
  │   │   └─ return TextResult(translations=lines) ✓
  │   │
  │   └─ else:
  │       log.warning(f"Attempt {attempt}: got {len(lines)} sentences, expected {batch_size}")
  │       construct stricter prompt (see below)
  │
  └─ raise RuntimeError("Failed to generate exactly N sentences after X attempts")
```

### Retry Prompt Construction

When the count doesn't match, the retry prompt references the actual output:

**Over-generation** (`len(lines) > batch_size`):
> "You were asked for exactly {batch_size} sentences but produced {len(lines)}. Output only the first {batch_size} sentences now. ONE per line, no explanations."

**Under-generation** (`len(lines) < batch_size`):
> "You were asked for exactly {batch_size} sentences but produced {len(lines)}. Produce all {batch_size} sentences now. ONE per line, no explanations."

The retry prompt is appended as a new user message in the same conversation context (no system message reset), so the model sees its previous output and the correction.

### Parameters

| Parameter | Default | Description |
|---|---|---|
| `max_attempts` | 3 | Total attempts including the initial call. After 3 failures, raise `RuntimeError`. |
| `retry_temperature` | `None` (inherit) | If set, override temperature on retry calls to encourage different output. Currently not needed — stricter prompt alone is sufficient. |

### Error Handling

After exhausting all retries:
- Raise `RuntimeError` with a message containing the last raw LLM output for debugging.
- The error propagates through `pipeline.py` → `app.py` → Gradio UI as a visible error to the user.
- Model is unloaded after the method returns (success or failure), handled by `EnginePool`. The model stays loaded across retries within a single `generate()` call.

### Code Changes

**`core/engine.py` — `MiniCPMTextEngine`:**

Add two methods:

```python
def _validate_lines(self, lines: list[str], expected: int) -> bool:
    """Return True if line count matches expected."""
    return len(lines) == expected

def _build_retry_prompt(self, actual: int, expected: int) -> str:
    """Build a stricter prompt referencing the mismatch."""
    direction = "more" if actual < expected else "fewer"
    if actual > expected:
        return (
            f"You were asked for exactly {expected} sentences but produced {actual}. "
            f"Output only the first {expected} sentences now. ONE per line, no explanations."
        )
    else:
        return (
            f"You were asked for exactly {expected} sentences but produced {actual}. "
            f"Produce all {expected} sentences now. ONE per line, no explanations."
        )
```

Modify `generate()`:
- Wrap the LLM call + parsing in a retry loop (max 3 attempts).
- On mismatch, log warning and append retry prompt as new user message.
- On success at any attempt, return immediately.
- After exhausting retries, raise `RuntimeError` with last raw output.

**`core/pipeline.py`:**
- No changes required for this spec. Pipeline already calls `engine.generate()` and passes the result through. The `RuntimeError` will propagate naturally.

**`app.py`:**
- Keep `raw_cards[:batch_size]` slice as a secondary safety net until engine validation is confirmed working, then remove it in a follow-up commit.

## Data Flow

```
User sets batch_size=3 → app.py passes to MiniCPMTextEngine.generate()
  │
  ├─ Attempt 1: LLM returns 8 sentences → mismatch → retry prompt
  ├─ Attempt 2: LLM returns 3 sentences → match → return TextResult(translations=[...])
  └─ Pipeline receives exactly 3 translations → CardData created for each → UI renders 3 cards
```

## Testing Notes

- **Smoke test:** `scripts/smoke_test.py` should still pass (mock data path, no actual LLM calls).
- **Manual test:** Run a generation with batch_size=3 and verify the engine retries when over-generating, then returns exactly 3 sentences.
- **Edge case test:** Verify that after 3 failed attempts, `RuntimeError` is raised with debug info in the message.

## Open Questions

1. Should we log the full LLM output on retry, or just the line count? → Decision: log line count + direction (over/under) at WARNING level. Full output only on final failure.
2. Should retries share conversation context or start fresh? → Decision: append as new user message in same context so the model sees its own previous output and the correction.
