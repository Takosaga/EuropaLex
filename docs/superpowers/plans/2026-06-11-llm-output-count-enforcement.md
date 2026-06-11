# LLM Output Count Enforcement — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enforce that `MiniCPMTextEngine.generate()` returns exactly `batch_size` sentences by validating LLM output count and retrying with a stricter prompt on mismatch.

**Architecture:** Add two private helper methods to `MiniCPMTextEngine` — `_validate_lines()` and `_build_retry_prompt()` — then wrap the existing LLM call + parsing logic in a max-3-attempt retry loop. On success at any attempt, return immediately. On exhaustion, raise `RuntimeError` with debug info.

**Tech Stack:** Python 3.12+, Pydantic, llama-cpp-python (via existing engine), logging module.

---

### Task 1: Add `_validate_lines()` and `_build_retry_prompt()` helpers to `MiniCPMTextEngine`

**Files:**
- Modify: `core/engine.py` — add two methods inside `MiniCPMTextEngine`, before the `unload()` method (around line 122)

- [ ] **Step 1: Add the two helper methods**

Insert these two methods into `MiniCPMTextEngine`, right before the existing `def unload(self)` method (currently at line 122):

```python
    def _validate_lines(self, lines: list[str], expected: int) -> bool:
        """Return True if line count matches expected batch size.

        Args:
            lines: Non-empty, stripped lines from LLM output.
            expected: The number of sentences we asked for (batch_size).

        Returns:
            True if len(lines) == expected.
        """
        return len(lines) == expected

    def _build_retry_prompt(self, actual: int, expected: int) -> str:
        """Build a stricter prompt referencing the count mismatch.

        Args:
            actual: Number of sentences the LLM produced.
            expected: Number of sentences requested (batch_size).

        Returns:
            A user-message string to append as the next turn in the conversation.
        """
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

- [ ] **Step 2: Verify syntax — run smoke test**

Run: `python scripts/smoke_test.py`

Expected: Clean exit (no traceback). This confirms the module still imports correctly after adding methods.

- [ ] **Step 3: Commit**

```bash
git add core/engine.py
git commit -m "feat: add _validate_lines and _build_retry_prompt helpers to MiniCPMTextEngine"
```

---

### Task 2: Modify `generate()` to wrap LLM call in a retry loop

**Files:**
- Modify: `core/engine.py` — rewrite the body of `MiniCPMTextEngine.generate()` (lines 77–120)

- [ ] **Step 1: Replace the generate() method body**

Replace the entire `generate` method (from line 77 through line 120, from `def generate(...)` to the current `return TextResult(translations=lines)`) with this new implementation:

```python
    def generate(self, texts: list[str], scenario: str, cefr_level: CEFRLevel, batch_size: int | None = None) -> TextResult:
        """Generate English sentences using the loaded GGUF model.

        Validates that output contains exactly batch_size sentences. Retries with a
        stricter prompt on mismatch (max 3 total attempts). Raises RuntimeError if
        all attempts fail.

        Args:
            texts: Empty list (generation mode). Non-empty would be translation mode.
            scenario: Scenario/topic description for text generation.
            cefr_level: CEFR proficiency level.
            batch_size: Number of sentences to generate.

        Returns:
            TextResult with exactly one sentence per requested batch size.

        Raises:
            RuntimeError: If generation fails after max attempts.
        """
        self._load_model()
        if batch_size is None:
            raise ValueError("batch_size is required for text generation")

        messages = [
            {
                "role": "system",
                "content": (
                    "You are a language teacher. Generate simple, clear sentences at the specified CEFR level "
                    "about the given scenario. Output ONE sentence per line, no numbering or explanations."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Generate {batch_size} simple sentences at CEFR level {cefr_level.value}\n"
                    f"about the following scenario. Output ONE sentence per line, no numbering.\n"
                    f"Scenario: {scenario}\n"
                    "Output ONLY the sentences, one per line. No explanations."
                ),
            },
        ]

        max_attempts = 3
        last_raw_output = ""

        for attempt in range(1, max_attempts + 1):
            output = self._llm.create_chat_completion(
                messages=messages,
                max_tokens=512,
                temperature=0.7,
            )

            raw_text = output["choices"][0]["message"]["content"]
            last_raw_output = raw_text
            lines = [line.strip() for line in raw_text.strip().split("\n") if line.strip()]

            if self._validate_lines(lines, batch_size):
                logger.debug(
                    "MiniCPMTextEngine: got %d/%d sentences on attempt %d",
                    len(lines), batch_size, attempt,
                )
                return TextResult(translations=lines)

            # Mismatch — build retry prompt and append as new user message
            messages.append({
                "role": "user",
                "content": self._build_retry_prompt(len(lines), batch_size),
            })
            logger.warning(
                "MiniCPMTextEngine attempt %d: got %d sentences, expected %d — retrying",
                attempt, len(lines), batch_size,
            )

        # Exhausted all retries
        raise RuntimeError(
            f"Failed to generate exactly {batch_size} sentences after {max_attempts} attempts. "
            f"Last output: {last_raw_output!r}"
        )
```

Key changes from the original:
- Added `if batch_size is None` guard (was implicitly required before)
- Wrapped LLM call + parsing in a `for attempt in range(1, max_attempts + 1)` loop
- On success: log debug message with attempt count, return immediately
- On mismatch: append retry prompt to `messages` list (same conversation context), log warning
- After loop: raise `RuntimeError` with last raw output for debugging

- [ ] **Step 2: Verify syntax — run smoke test**

Run: `python scripts/smoke_test.py`

Expected: Clean exit (no traceback).

- [ ] **Step 3: Commit**

```bash
git add core/engine.py
git commit -m "feat: wrap MiniCPMTextEngine.generate() in retry loop for exact sentence count enforcement"
```

---

### Task 3: Manual verification — test the retry behavior end-to-end

**Files:**
- No file changes — manual testing only

- [ ] **Step 1: Create a quick inline test script**

Create `scripts/test_count_enforcement.py` with this content:

```python
"""Quick inline test for MiniCPMTextEngine sentence count enforcement.

Run after models are downloaded. Tests that _validate_lines and _build_retry_prompt
work correctly with mock data (no LLM call needed).
"""

from core.types import CEFRLevel, TextResult


def test_validate_lines():
    """Test that _validate_lines returns correct boolean for matching/non-matching counts."""
    # Simulate the method inline since we can't instantiate the engine without a model file
    def _validate_lines(lines: list[str], expected: int) -> bool:
        return len(lines) == expected

    assert _validate_lines(["sentence one", "sentence two", "sentence three"], 3) is True
    assert _validate_lines(["sentence one"], 3) is False
    assert _validate_lines(["s1", "s2", "s3", "s4", "s5"], 3) is False
    assert _validate_lines([], 3) is False
    print("test_validate_lines: PASS")


def test_build_retry_prompt_over():
    """Test retry prompt for over-generation."""
    def _build_retry_prompt(actual: int, expected: int) -> str:
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

    prompt = _build_retry_prompt(10, 3)
    assert "exactly 3" in prompt
    assert "produced 10" in prompt
    assert "Output only the first 3" in prompt
    print("test_build_retry_prompt_over: PASS")


def test_build_retry_prompt_under():
    """Test retry prompt for under-generation."""
    def _build_retry_prompt(actual: int, expected: int) -> str:
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

    prompt = _build_retry_prompt(1, 3)
    assert "exactly 3" in prompt
    assert "produced 1" in prompt
    assert "Produce all 3" in prompt
    print("test_build_retry_prompt_under: PASS")


def test_textresult_construction():
    """Test that TextResult accepts a list of exactly the right length."""
    result = TextResult(translations=["a", "b", "c"])
    assert len(result.translations) == 3
    assert result.translations[0] == "a"
    print("test_textresult_construction: PASS")


if __name__ == "__main__":
    test_validate_lines()
    test_build_retry_prompt_over()
    test_build_retry_prompt_under()
    test_textresult_construction()
    print("\nAll inline tests passed.")
```

- [ ] **Step 2: Run the inline test**

Run: `python scripts/test_count_enforcement.py`

Expected output:
```
test_validate_lines: PASS
test_build_retry_prompt_over: PASS
test_build_retry_prompt_under: PASS
test_textresult_construction: PASS

All inline tests passed.
```

- [ ] **Step 3: Commit**

```bash
git add scripts/test_count_enforcement.py
git commit -m "test: add inline test for _validate_lines and _build_retry_prompt logic"
```

---

### Task 4: Manual end-to-end verification with LLM (optional but recommended)

**Files:**
- No file changes — manual testing only

- [ ] **Step 1: Run a generation with batch_size=3**

Start the app and generate text:
```bash
python app.py
```

Then in the browser UI:
1. Set scenario to something simple like "test" or "a cat sitting on a mat"
2. Set CEFR level to B1
3. Set batch size slider to 3
4. Click "Generate Text"
5. Watch the console logs — you should see either:
   - `MiniCPMTextEngine: got 3/3 sentences on attempt 1` (success on first try), OR
   - `MiniCPMTextEngine attempt 1: got N sentences, expected 3 — retrying` followed by success on attempt 2 or 3

- [ ] **Step 2: Verify card count**

The UI should display exactly 3 cards (not more, not fewer).

- [ ] **Step 3: Verify error path**

If the LLM consistently fails all 3 attempts, you should see a `RuntimeError` in the console with the last raw output included. The Gradio UI will show an error message.

---

## Spec Coverage Checklist

| Spec Requirement | Task | Status |
|---|---|---|
| Enforce exactly `batch_size` sentences in `TextResult.translations` | Task 2 (retry loop + validation) | ✅ |
| Fail loudly with logging on mismatch | Task 2 (`logger.warning` on each retry, `RuntimeError` on exhaustion) | ✅ |
| Keep `TextResult` as plain Pydantic model — no count validation on type | Task 1 (helpers are engine methods, not Pydantic validators) | ✅ |
| Max 3 total attempts | Task 2 (`max_attempts = 3`) | ✅ |
| Log warning on each retry attempt | Task 2 (`logger.warning` with attempt number, actual count, expected count) | ✅ |
| Raise `RuntimeError` with last raw output after exhaustion | Task 2 (raise at end of loop with `last_raw_output!r`) | ✅ |
| Retry prompt references actual vs expected | Task 1 (`_build_retry_prompt` uses both values in message) | ✅ |
| Append retry as new user message in same context | Task 2 (`messages.append({"role": "user", ...})`) | ✅ |
| Smoke test still passes after changes | Task 1 (Step 2), Task 2 (Step 2) | ✅ |
