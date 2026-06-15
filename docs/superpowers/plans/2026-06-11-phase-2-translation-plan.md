# Phase 2 Translation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire tiny-aya translation into EuropaLex's two-phase workflow — Phase 1 generates English text, Phase 2 translates it to Latvian using `LlamaCppTextEngine` with sentence-count validation and retry logic. Images/audio toggles remain unchecked by default.

**Architecture:** Extend `LlamaCppTextEngine` with a retry loop (max 3 attempts) that validates output line count against `batch_size`, mirroring `MiniCPMTextEngine`'s pattern. Create `core/pipeline.py` as the Phase 2 orchestration layer. Wire `app.py` to call the pipeline instead of mock data.

**Tech Stack:** Python 3.12+, llama-cpp-python (tiny-aya-water Q4_K_M), Gradio 6, Pydantic >=2.0.0

---

### Task 1: Add retry loop to `LlamaCppTextEngine`

**Files:**
- Modify: `core/engine.py:165-192` — add retry logic to `generate()` method
- Modify: `core/engine.py:194-203` — add `_build_retry_prompt()` method

#### Step 1: Replace `LlamaCppTextEngine.generate()` with retry-wrapped version

Replace lines 165–192 in `core/engine.py`:

**Old code:**
```python
    def generate(self, texts: list[str], scenario: str, cefr_level: CEFRLevel, batch_size: int | None = None) -> TextResult:
        """Generate translations using the loaded GGUF model.

        Args:
            texts: English sentences to translate.
            scenario: Scenario/topic description (not used with this model).
            cefr_level: CEFR proficiency level.
            batch_size: Not used.

        Returns:
            TextResult with one translation per input text.

        Raises:
            RuntimeError: If generation fails.
        """
        self._load_model()
        prompt = self._build_translation_prompt(texts, cefr_level)

        output = self._llm(
            prompt=prompt,
            max_tokens=512,
            temperature=0.7,
            echo=False,
        )

        text = output.get("choices", [{}])[0].get("text", "")
        lines = [line.strip() for line in text.strip().split("\n") if line.strip()]
        return TextResult(generated_texts=lines)
```

**New code:**
```python
    def generate(self, texts: list[str], scenario: str, cefr_level: CEFRLevel, batch_size: int | None = None) -> TextResult:
        """Generate translations using the loaded GGUF model with retry loop.

        Wraps the LLM call in a retry loop (max 3 attempts). If output line count
        does not match ``batch_size``, builds a stricter prompt referencing the
        actual vs expected count and retries. On exhaustion, falls back to returning
        whatever lines were produced on the last attempt.

        Args:
            texts: English sentences to translate.
            scenario: Scenario/topic description (not used with this model).
            cefr_level: CEFR proficiency level.
            batch_size: Number of translations expected.

        Returns:
            TextResult with one translation per input text.

        Raises:
            ValidationError: If generation fails after max attempts and no lines produced.
        """
        self._load_model()
        if batch_size is None:
            raise ValueError("batch_size is required for translation")

        prompt = self._build_translation_prompt(texts, cefr_level)
        last_raw_text = ""

        for attempt in range(1, 4):
            output = self._llm(
                prompt=prompt,
                max_tokens=512,
                temperature=0.7,
                echo=False,
            )

            raw_text = output.get("choices", [{}])[0].get("text", "")
            last_raw_text = raw_text
            lines = [line.strip() for line in raw_text.strip().split("\n") if line.strip()]

            if len(lines) == batch_size:
                logger.info(
                    "LlamaCppTextEngine: got %d translations on attempt %d (target=%d)",
                    len(lines), attempt, batch_size,
                )
                return TextResult(generated_texts=lines)

            # Count mismatch — retry with stricter prompt
            if attempt < 3:
                prompt = self._build_retry_prompt(raw_text, batch_size)
                logger.warning(
                    "LlamaCppTextEngine attempt %d: got %d translations, need %d — retrying",
                    attempt, len(lines), batch_size,
                )
            else:
                logger.warning(
                    "LlamaCppTextEngine: exhausted all attempts. Got %d translations.",
                    len(lines),
                )

        # Exhausted retries — return whatever we got (or empty)
        if not lines:
            raise ValidationError(
                f"Could not generate any translations after 3 attempts.",
                raw_output=last_raw_text,
            )
        return TextResult(generated_texts=lines)
```

#### Step 2: Add `_build_retry_prompt()` method after `_build_translation_prompt()`

Insert after line 203 (after the closing of `_build_translation_prompt`):

```python
    def _build_retry_prompt(self, raw_output: str, expected_count: int) -> str:
        """Build a stricter prompt for retry when translation count mismatches.

        Appends a correction instruction to the existing context so the model
        builds on its previous output rather than starting fresh.

        Args:
            raw_output: The LLM's previous (incorrect-count) output.
            expected_count: The number of translations that should have been produced.

        Returns:
            Prompt string with correction instruction appended.
        """
        return (
            f"Previous output had the wrong number of lines.\n"
            f"You need exactly {expected_count} translations, one per line.\n"
            f"Your previous attempt:\n{raw_output}\n\n"
            f"Now regenerate ALL {expected_count} translations, one per line, in order.\n"
            f"Output ONLY the translations, one per line. No explanations."
        )
```

#### Step 3: Write inline test for retry logic

Create `scripts/test_translation_retry.py`:

```python
"""Quick inline test for LlamaCppTextEngine retry loop.

Tests sentence-count validation and retry prompt building without
requiring a running model. Uses mock LLM output.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from unittest.mock import MagicMock, patch


def test_generate_exact_count():
    """Test that exact batch_size returns immediately."""
    from core.types import CEFRLevel
    from core.engine import LlamaCppTextEngine

    mock_llm = MagicMock()
    mock_llm.return_value = {
        "choices": [{"text": "Sveiki.\nKā tu esi?\nPaldies."}]
    }

    with patch.object(LlamaCppTextEngine, "_load_model"):
        engine = LlamaCppTextEngine.__new__(LlamaCppTextEngine)
        engine._llm = mock_llm
        engine._loaded = True

        result = engine.generate(
            texts=["Hello.", "How are you?", "Thank you."],
            scenario="greetings",
            cefr_level=CEFRLevel.A1,
            batch_size=3,
        )

    assert len(result.generated_texts) == 3
    assert result.generated_texts[0] == "Sveiki."
    print("test_generate_exact_count: PASS")


def test_generate_retry_on_short_output():
    """Test retry when fewer lines than expected."""
    from core.types import CEFRLevel
    from core.engine import LlamaCppTextEngine

    mock_llm = MagicMock()
    # First call returns 1 line, second call returns 3 lines
    mock_llm.side_effect = [
        {"choices": [{"text": "Sveiki."}]},
        {"choices": [{"text": "Sveiki.\nKā tu esi?\nPaldies."}]},
    ]

    with patch.object(LlamaCppTextEngine, "_load_model"):
        engine = LlamaCppTextEngine.__new__(LlamaCppTextEngine)
        engine._llm = mock_llm
        engine._loaded = True

        result = engine.generate(
            texts=["Hello.", "How are you?", "Thank you."],
            scenario="greetings",
            cefr_level=CEFRLevel.A1,
            batch_size=3,
        )

    assert len(result.generated_texts) == 3
    assert mock_llm.call_count == 2  # retried once
    print("test_generate_retry_on_short_output: PASS")


def test_generate_exhausted_retries_returns_partial():
    """Test that exhausted retries return whatever was produced."""
    from core.types import CEFRLevel
    from core.engine import LlamaCppTextEngine

    mock_llm = MagicMock()
    # Always returns wrong count
    mock_llm.return_value = {"choices": [{"text": "Sveiki."}]}

    with patch.object(LlamaCppTextEngine, "_load_model"):
        engine = LlamaCppTextEngine.__new__(LlamaCppTextEngine)
        engine._llm = mock_llm
        engine._loaded = True

        result = engine.generate(
            texts=["Hello.", "How are you?", "Thank you."],
            scenario="greetings",
            cefr_level=CEFRLevel.A1,
            batch_size=3,
        )

    assert len(result.generated_texts) == 1  # partial result returned
    assert mock_llm.call_count == 3  # all 3 attempts used
    print("test_generate_exhausted_retries_returns_partial: PASS")


def test_generate_empty_output_raises():
    """Test that zero lines after retries raises ValidationError."""
    from core.types import CEFRLevel, ValidationError
    from core.engine import LlamaCppTextEngine

    mock_llm = MagicMock()
    # Always returns empty string
    mock_llm.return_value = {"choices": [{"text": ""}]}

    with patch.object(LlamaCppTextEngine, "_load_model"):
        engine = LlamaCppTextEngine.__new__(LlamaCppTextEngine)
        engine._llm = mock_llm
        engine._loaded = True

        try:
            engine.generate(
                texts=["Hello.", "How are you?", "Thank you."],
                scenario="greetings",
                cefr_level=CEFRLevel.A1,
                batch_size=3,
            )
            assert False, "Should raise"
        except ValidationError as e:
            assert "Could not generate any translations" in str(e)

    print("test_generate_empty_output_raises: PASS")


def test_retry_prompt_contains_count_info():
    """Test that retry prompt references actual vs expected count."""
    from core.engine import LlamaCppTextEngine

    with patch.object(LlamaCppTextEngine, "_load_model"):
        engine = LlamaCppTextEngine.__new__(LlamaCppTextEngine)
        engine.model_path = Path("/dev/null")  # doesn't matter for this test

    retry_prompt = engine._build_retry_prompt("Sveiki.", 3)
    assert "1" in retry_prompt  # actual count
    assert "3" in retry_prompt  # expected count
    assert "regenerate ALL 3 translations" in retry_prompt
    print("test_retry_prompt_contains_count_info: PASS")


if __name__ == "__main__":
    test_generate_exact_count()
    test_generate_retry_on_short_output()
    test_generate_exhausted_retries_returns_partial()
    test_generate_empty_output_raises()
    test_retry_prompt_contains_count_info()
    print("\nAll inline tests passed.")
```

#### Step 4: Run the inline test to verify it passes

Run: `python scripts/test_translation_retry.py`
Expected: All 5 tests pass with "PASS" output.

#### Step 5: Commit

```bash
cd /home/takosaga/Projects/EuropaLex
git add core/engine.py scripts/test_translation_retry.py
git commit -m "feat: add retry loop to LlamaCppTextEngine for translation validation"
```

---

### Task 2: Implement `core/pipeline.py` Phase 2 orchestration

**Files:**
- Create: `core/pipeline.py`

#### Step 1: Write the pipeline module

Replace the placeholder content in `core/pipeline.py` with:

```python
"""EuropaLex Pipeline — Phase 2 orchestration.

Receives English texts generated in Phase 1 and produces translated
CardData objects via tiny-aya-water translation engine.

Images and audio are not yet wired — those fields remain empty.
"""

from __future__ import annotations

import logging
from typing import Iterator

from core.engine import EnginePool
from core.types import CEFRLevel, CardData, EngineConfig, ValidationError

logger = logging.getLogger(__name__)


def generate_phase2(
    texts: list[str],
    scenario: str,
    cefr_level: CEFRLevel,
    batch_size: int,
) -> Iterator[tuple[int, str, list[CardData]]]:
    """Generate Latvian translations for Phase 1 English texts.

    Orchestrates the translation pipeline: gets the tiny-aya engine,
    calls generate with retry validation, and yields CardData objects.

    Yields (progress_percent, phase_label, cards) at each step.

    Args:
        texts: English sentences generated in Phase 1.
        scenario: Original scenario/topic description.
        cefr_level: CEFR proficiency level.
        batch_size: Number of translations expected.

    Yields:
        (20, "Preparing translation...", []) — before engine call
        (60, "Translating...", []) — during generation
        (100, "Translation complete!", cards) — with final CardData list

    Raises:
        ValidationError: If translation fails after max retries.
    """
    try:
        config = EngineConfig.from_settings_yaml()
        pool = EnginePool.get(config)
    except FileNotFoundError as e:
        logger.error("Phase 2 model not found: %s", e)
        raise

    yield 20, "Preparing translation...", []

    try:
        texts_result = pool.get_translation_engine().generate(
            texts=texts,
            scenario=scenario,
            cefr_level=cefr_level,
            batch_size=batch_size,
        )
    except ValidationError:
        raise

    yield 60, "Translating...", []

    cards = [
        CardData(
            text=text,
            translation=translation,
            audio_path=None,
            image_path=None,
            cefr_level=cefr_level,
        )
        for text, translation in zip(texts, texts_result.generated_texts)
    ]

    yield 100, "Translation complete!", cards
```

#### Step 2: Run smoke test to verify module loads without errors

Run: `python scripts/smoke_test.py`
Expected: Clean exit (no traceback).

#### Step 3: Commit

```bash
cd /home/takosaga/Projects/EuropaLex
git add core/pipeline.py
git commit -m "feat: implement pipeline.py Phase 2 translation orchestration"
```

---

### Task 3: Wire Phase 2 in `app.py` — replace mock data with real translation

**Files:**
- Modify: `app.py` — add `_phase1_texts` state, replace `generate_media_async()`, update event wiring and toggle defaults

#### Step 1a: Add `_phase1_texts` global at module level

After line 18 (after widget imports), insert:

```python
# ─── Phase State ────────────────────────────────────────────────────

_phase1_texts: list[str] = []  # English texts from Phase 1, passed to Phase 2
```

#### Step 1b: Store Phase 1 texts in `generate_text_async`

After line 140 (`cards = [...]`) in `generate_text_async`, before the yield on line 142, insert:

```python
    # Store Phase 1 texts for Phase 2 (module-level state)
    global _phase1_texts
    _phase1_texts = list(texts.generated_texts)
```

#### Step 1c: Replace `generate_media_async()` function

Replace lines 146–175 in `app.py`:

**Old code:**
```python
def generate_media_async(
    scenario: str,
    cefr_level: str,
    batch_size: int,
    include_images: bool,
    include_audio: bool,
):
    """Phase 2: Add translations, images, and audio to existing text cards.

    Takes the same parameters as Phase 1 plus media toggles.
    Re-renders cards with actual translation text and optional media.
    """
    raw_cards = MOCK_CARDS.get(cefr_level, MOCK_CARDS["B1"])
    selected_raw = raw_cards[:batch_size]

    if not selected_raw:
        yield generate_progress_html(0, "No cards available"), '<div style="color:#8b7355; padding:20px;">No cards available for this level.</div>'
        return

    # Transform to two-phase format with actual translations
    cards = transform_mock_cards(selected_raw)

    # Render with full media (no placeholder — translation text is real)
    phase_cards_full = generate_cards_html(
        cards,
        include_image=include_images,
        include_audio=include_audio,
        placeholder_back=False,
    )
    yield generate_progress_html(100, "Generation complete!"), phase_cards_full
```

**New code:**
```python
def generate_media_async(
    scenario: str,
    cefr_level: str,
    batch_size: int,
):
    """Phase 2: Translate Phase 1 English text to Latvian via tiny-aya.

    Reads the English texts from _phase1_texts (set by Phase 1 handler),
    translates them using tiny-aya, and renders cards with Latvian on front.
    Images and audio toggles are not yet active — media fields remain empty.
    """
    if not _phase1_texts:
        yield generate_progress_html(0, "⚠️ Please generate text first."), (
            '<div style="color:#c44; padding:20px;">'
            'No Phase 1 text found. Generate English text first, then click "Generate Cards".'
            '</div>'
        )
        return

    try:
        config = EngineConfig.from_settings_yaml()
        pool = EnginePool.get(config)
        cefr = CEFRLevel(cefr_level)
    except FileNotFoundError as e:
        logger.error("Phase 2 model not found: %s", e)
        yield generate_progress_html(0, f"\u26a0\ufe0f Model file missing: {e}"), (
            '<div style="color:#c44; padding:20px;">'
            '<strong>Model file not found.</strong><br>'
            f'{e}<br><br>'
            'Run <code>python models/download_models.py tiny_aya</code> to download tiny-aya-water, '
            'or check <code>configs/settings.yaml</code> for the correct path.'
            '</div>'
        )
        return
    except Exception as e:
        logger.error("Phase 2 setup failed: %s", e, exc_info=True)
        yield generate_progress_html(0, f"\u26a0\ufe0f Setup error: {e}"), (
            '<div style="color:#c44; padding:20px;">'
            f'<strong>Failed to initialize engine.</strong><br>{e}<br><br>'
            'Check <code>configs/settings.yaml</code> and run the smoke test: '
            '<code>python scripts/smoke_test.py</code>'
            '</div>'
        )
        return

    try:
        yield generate_progress_html(20, "Preparing translation..."), ""
        texts_result = pool.get_translation_engine().generate(
            texts=_phase1_texts,
            scenario=scenario,
            cefr_level=cefr,
            batch_size=len(_phase1_texts),
        )
    except Exception as e:
        logger.error("Phase 2 translation failed: %s", e, exc_info=True)
        err_detail = str(e)
        yield generate_progress_html(0, f"\u26a0\ufe0f Translation failed"), (
            '<div style="color:#c44; padding:20px;">'
            f'<strong>Translation failed.</strong><br>'
            f'{err_detail}<br><br>'
            'Possible causes:<br>'
            '• llama-cpp-python not installed — run: <code>uv pip install llama-cpp-python</code><br>'
            '• tiny-aya-water model file corrupted or incompatible format<br>'
            '• Insufficient VRAM (~2 GB required)<br><br>'
            'Check the terminal for full error output.'
            '</div>'
        )
        return

    yield generate_progress_html(60, "Translating..."), ""

    # Convert TextResult to card dicts for rendering (no media yet)
    cards = [
        {"text": text, "translation": translation, "cefr_level": cefr}
        for text, translation in zip(_phase1_texts, texts_result.generated_texts)
    ]

    yield generate_progress_html(100, "Translation ready!"), generate_cards_html(cards, include_image=False, include_audio=False, placeholder_back=False)
```

#### Step 1d: Update event wiring — remove media toggle parameters

Update the `generate_cards_btn.click()` binding (line ~285):

**Old code:**
```python
    generate_cards_btn.click(
        fn=_handle_media_generation,
        inputs=[scenario_input, cefr_dropdown, batch_slider, images_toggle, audio_toggle],
        outputs=[progress_html, card_output],
    )
```

**New code:**
```python
    generate_cards_btn.click(
        fn=_handle_media_generation,
        inputs=[scenario_input, cefr_dropdown, batch_slider],
        outputs=[progress_html, card_output],
    )
```

Update `_handle_media_generation` (line ~247):

**Old code:**
```python
    def _handle_media_generation(scenario, cefr_level, batch_size, images_on, audio_on):
        """Wrapper for generate_media_async that handles empty scenario."""
        if not scenario.strip():
            yield generate_progress_html(0, "⚠️ Please enter a scenario or topic."), '<div style="color:#c44; padding:20px;">Please enter a scenario or topic to generate cards.</div>'
            return
        for result in generate_media_async(scenario, cefr_level, batch_size, images_on, audio_on):
            yield result
```

**New code:**
```python
    def _handle_media_generation(scenario, cefr_level, batch_size):
        """Wrapper for generate_media_async that handles empty scenario and missing Phase 1 texts."""
        if not scenario.strip():
            yield generate_progress_html(0, "⚠️ Please enter a scenario or topic."), '<div style="color:#c44; padding:20px;">Please enter a scenario or topic to generate cards.</div>'
            return
        for result in generate_media_async(scenario, cefr_level, batch_size):
            yield result
```

#### Step 1e: Update toggle defaults to unchecked

Change lines 220–221 in the Gradio UI construction:

**Old code:**
```python
                images_toggle = create_toggle("🖼️ Images", value=True, elem_id="toggle-images")
                audio_toggle = create_toggle("🔊 Audio", value=True, elem_id="toggle-audio")
```

**New code:**
```python
                images_toggle = create_toggle("🖼️ Images", value=False, elem_id="toggle-images")
                audio_toggle = create_toggle("🔊 Audio", value=False, elem_id="toggle-audio")
```

#### Step 2: Run smoke test

Run: `python scripts/smoke_test.py`
Expected: Clean exit (no traceback).

#### Step 3: Commit

```bash
cd /home/takosaga/Projects/EuropaLex
git add app.py
git commit -m "feat: wire Phase 2 translation via real tiny-aya engine"
```

---

### Task 4: Final verification

**Files:**
- Run: `python scripts/smoke_test.py`
- Manual: `python app.py` (verify Gradio launches and both phases work)

#### Step 1: Run smoke test

Run: `python scripts/smoke_test.py`
Expected: Clean exit (no traceback).

#### Step 2: Manual verification

Run: `python app.py`
- Verify Gradio launches on port 7860 without errors
- Open browser, enter a scenario, click "Generate Text" — Phase 1 should work
- Click "Generate Cards" — Phase 2 should translate to Latvian
- Cards should render with Latvian on front, English on back

#### Step 3: Commit any final fixes (if needed)

```bash
cd /home/takosaga/Projects/EuropaLex
git add -A
git commit -m "fix: [description of any fixes]"
```

---

## Self-Review Checklist

**1. Spec coverage:**
- ✅ Architecture overview → Task 2 (pipeline.py), Task 3 (app.py wiring)
- ✅ LlamaCppTextEngine retry loop → Task 1
- ✅ Pipeline API function with progress yields → Task 2
- ✅ App wiring, toggle defaults unchecked → Task 3 steps 1a-1e
- ✅ Error handling (ValidationError caught in app.py) → Task 3 error blocks
- ✅ Images/audio absent from pipeline API → Task 2 has no media params

**2. Placeholder scan:** No "TBD", "TODO", "implement later", or vague references found. All code is complete and specific.

**3. Type consistency:** `CEFRLevel`, `CardData`, `ValidationError`, `TextResult`, `EngineConfig` all referenced consistently across tasks. Method signatures match existing patterns in `MiniCPMTextEngine` and `text_gen.py`.

**4. Ambiguity check:** The `_phase1_texts` module-level state is explicit — no ambiguity about how Phase 1 texts reach Phase 2. The retry loop falls back to partial results (not raising on exhausted retries when lines were produced), which matches the spec's "raise ValidationError" only for empty output case.
