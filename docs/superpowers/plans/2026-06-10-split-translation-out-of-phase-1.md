# Split Translation Out of Phase 1 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire Nemotron TextEngine into Phase 1 of app.py so it generates English text via llama-cli subprocess, with no translation step. Phase 2 remains deferred (mock data).

**Architecture:** Phase 1 handler reads config from `configs/settings.yaml`, instantiates `TextEngine` via `EnginePool.get(config)`, calls `.generate()` with an empty texts list (triggers Nemotron generation mode), then converts the result to card dicts and renders with `placeholder_back=True`. Phase 2 stays unchanged (mock data).

**Tech Stack:** Python 3.12+, llama-cli subprocess, Pydantic, Gradio 6

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `app.py` | Modify | Replace mock Phase 1 with TextEngine call; keep Phase 2 as-is |
| `AGENTS.md` | Modify | Update two-phase workflow section to reflect Phase 1 = English only |

## What Does Not Change

- Card rendering (`frontend/ui/cards.py`) — already supports `placeholder_back=True`
- Progress tracking (`generate_progress_html`) — unchanged
- Toggles, disabled state management, CSS — unchanged
- EnginePool, engine classes — unchanged (already implemented)
- Phase 2 handler — deferred, stays with mock data

---

### Task 1: Write inline test for TextEngine generation mode

**Files:**
- Test: `core/test_text_engine.py` (new)

- [ ] **Step 1: Create the test file**

Create `core/test_text_engine.py`:

```python
"""Tests for TextEngine — English text generation via Nemotron."""

from core.engine import TextEngine
from core.types import CEFRLevel


def test_build_generation_prompt():
    """TextEngine builds correct prompt for Nemotron generation mode."""
    engine = TextEngine.__new__(TextEngine)  # skip __init__
    engine.model_path = "/dev/null"
    engine.device = "cuda"

    result = engine._build_generation_prompt(
        scenario="ordering coffee",
        cefr_level=CEFRLevel.B1,
        batch_size=3,
    )

    assert "ordering coffee" in result
    assert "B1" in result
    assert "3" in result
    assert "one sentence per line" in result.lower()
    assert "no numbering" in result.lower()
    assert "NO explanations" in result


def test_build_translation_prompt():
    """TextEngine builds correct prompt for translation mode."""
    engine = TextEngine.__new__(TextEngine)  # skip __init__
    engine.model_path = "/dev/null"
    engine.device = "cuda"

    result = engine._build_translation_prompt(
        texts=["Hello world", "Good morning"],
        scenario="",
        cefr_level=CEFRLevel.A2,
    )

    assert "Hello world" in result
    assert "Good morning" in result
    assert "A2" in result
    assert "Translate" in result
    assert "NO explanations" in result


def test_generate_calls_llama_cli_subprocess():
    """TextEngine.generate() calls llama-cli with correct arguments."""
    import subprocess
    from unittest.mock import patch, MagicMock

    engine = TextEngine.__new__(TextEngine)  # skip __init__
    engine.model_path = "/path/to/model.gguf"
    engine.device = "cuda"

    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "Sentence one.\nSentence two.\nSentence three."
    mock_result.stderr = ""

    with patch.object(subprocess, "run", return_value=mock_result) as mock_run:
        result = engine.generate(
            texts=[],  # empty = generation mode (Nemotron)
            scenario="family members",
            cefr_level=CEFRLevel.B1,
            batch_size=3,
        )

    assert len(result.translations) == 3
    assert result.translations[0] == "Sentence one."

    # Verify llama-cli was called with correct args
    call_args = mock_run.call_args
    assert call_args[0][0][0] == "llama-cli"
    assert "-m" in call_args[0][0]
    assert str(engine.model_path) in call_args[0][0]
    assert "-n" in call_args[0][0]
    assert "512" in call_args[0][0]


def test_generate_raises_on_subprocess_failure():
    """TextEngine.generate() raises RuntimeError on non-zero exit."""
    import subprocess
    from unittest.mock import patch, MagicMock

    engine = TextEngine.__new__(TextEngine)
    engine.model_path = "/path/to/model.gguf"
    engine.device = "cuda"

    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stdout = ""
    mock_result.stderr = "model not found"

    with patch.object(subprocess, "run", return_value=mock_result):
        try:
            engine.generate(
                texts=[],
                scenario="test",
                cefr_level=CEFRLevel.B1,
                batch_size=1,
            )
            assert False, "Should have raised RuntimeError"
        except RuntimeError as e:
            assert "llama-cli failed" in str(e)


if __name__ == "__main__":
    test_build_generation_prompt()
    print("PASS: build_generation_prompt")
    test_build_translation_prompt()
    print("PASS: build_translation_prompt")
    test_generate_calls_llama_cli_subprocess()
    print("PASS: generate calls subprocess")
    test_generate_raises_on_subprocess_failure()
    print("PASS: generate raises on failure")
    print("All tests passed.")
```

- [ ] **Step 2: Run the tests**

```bash
cd /home/takosaga/Projects/EuropaLex && python core/test_text_engine.py
```

Expected output: `All tests passed.`

- [ ] **Step 3: Commit**

```bash
git add core/test_text_engine.py
git commit -m "test: add inline tests for TextEngine generation and translation prompts"
```

---

### Task 2: Wire TextEngine into Phase 1 handler in app.py

**Files:**
- Modify: `app.py`

- [ ] **Step 1: Add imports at the top of app.py**

Replace the existing imports near the top of `app.py`:

```python
import gradio as gr
from core.engine import EnginePool, TextEngine
from core.types import EngineConfig, CEFRLevel
from frontend.ui.cards import render_card_html, generate_cards_html, generate_progress_html
from frontend.ui.widgets import create_toggle
```

- [ ] **Step 2: Replace the Phase 1 handler function**

Replace the entire `generate_text_async` function (lines ~73-95) with:

```python
def generate_text_async(
    scenario: str,
    cefr_level: str,
    batch_size: int,
):
    """Phase 1: Generate English text only using Nemotron (no translation).

    Yields (progress_html, card_output_html) tuples.
    Cards show English text with dashed placeholder back side.
    Phase 2 (translation + media) is deferred — stays as mock data.
    """
    # Load config and get engine
    try:
        config = EngineConfig.from_settings_yaml()
        pool = EnginePool.get(config)
        engine = pool.get_english_engine()

        cefr = CEFRLevel(cefr_level)
    except Exception as e:
        yield generate_progress_html(0, f"⚠️ Config error: {e}"), '<div style="color:#c44; padding:20px;">Engine config error. Check configs/settings.yaml.</div>'
        return

    # Generate English text via Nemotron
    try:
        yield generate_progress_html(20, "Loading Nemotron model..."), ""
        texts = engine.generate(
            texts=[],  # empty = generation mode (not translation)
            scenario=scenario,
            cefr_level=cefr,
            batch_size=batch_size,
        )
    except RuntimeError as e:
        yield generate_progress_html(0, f"⚠️ Generation failed: {e}"), '<div style="color:#c44; padding:20px;">Text generation failed. Check llama-cli is installed.</div>'
        return

    # Convert TextResult to card dicts for rendering
    cards = [{"text": t, "translation": "", "cefr_level": cefr} for t in texts.translations]

    yield generate_progress_html(60, "Generating text..."), ""
    yield generate_progress_html(100, "Text ready! Adjust media toggles and click Generate Cards."), generate_cards_html(cards, include_image=False, include_audio=False, placeholder_back=True)
```

- [ ] **Step 3: Verify Phase 2 handler is unchanged**

The `generate_media_async` function (starting at line ~98) should remain exactly as-is with mock data. Do NOT modify it.

- [ ] **Step 4: Run smoke test**

```bash
cd /home/takosaga/Projects/EuropaLex && python scripts/smoke_test.py
```

Expected: clean exit (no traceback).

- [ ] **Step 5: Commit**

```bash
git add app.py
git commit -m "feat: wire Nemotron TextEngine into Phase 1 — English text only, no translation"
```

---

### Task 3: Update AGENTS.md documentation

**Files:**
- Modify: `AGENTS.md`

- [ ] **Step 1: Update the Two-Phase Generation Workflow section**

Replace the existing "Two-Phase Generation Workflow" section (around line ~145) with:

```markdown
### Two-Phase Generation Workflow

The UI operates in two distinct phases:

**Phase 1 — Generate English Text:**
1. User clicks "Generate Text"
2. `app.py` calls the text generation handler → Nemotron (`TextEngine`, llama-cli subprocess) generates English sentences from the scenario
3. Cards render with English on the front, placeholder back (dashed line)
4. After completion, `_enable_phase2()` removes disabled CSS and enables toggles + "Generate Cards" button

**Phase 2 — Generate Translation + Media (deferred):**
1. User toggles Images/Audio on/off
2. User clicks "Generate Cards"
3. `app.py` calls the media generation handler → tiny-aya-water (`LlamaCppTextEngine`) translates, then OmniVoice (TTS) + FLUX.2 (images) fill in media
4. Cards update: translation appears on the front, image and audio controls appear with it; English text moves to the back
5. Both buttons hide during generation, reappear when done

**Rules:**
- Never skip Phase 1. Even if media-only mode seems useful, English text must be generated first.
- When user changes input parameters (scenario, CEFR level, batch size), call `_reset_to_idle()` to restore disabled states and hidden buttons.
- The disabled state uses CSS class `europalex-btn-disabled` and inline styles with `#phase-css` ID. Don't remove these — they're tied to the two-phase state machine.
```

- [ ] **Step 2: Update the data flow diagram**

Replace the existing data flow blockquote (around line ~105):

```markdown
```
User input → app.py click handler → EnginePool.get(config) → TextEngine (Nemotron, Phase 1) → LlamaCppTextEngine (translation, Phase 2) → TTSEngine/ImageGenEngine (media, Phase 2) → frontend/ui/cards.py rendering → Gradio output
```
```

- [ ] **Step 3: Update the EnginePool lifecycle notes**

In the "Core Module Rules" section under `engine.py`, update the EnginePool description to clarify that Phase 1 uses only `TextEngine` (subprocess, no VRAM), and Phase 2 loads GPU engines for translation + media.

- [ ] **Step 4: Run smoke test again**

```bash
cd /home/takosaga/Projects/EuropaLex && python scripts/smoke_test.py
```

Expected: clean exit.

- [ ] **Step 5: Commit**

```bash
git add AGENTS.md
git commit -m "docs: update AGENTS.md — Phase 1 = English only, Phase 2 deferred"
```

---

## Self-Review Checklist

1. **Spec coverage:** Design doc says "Phase 1 generates only English text via Nemotron." Task 2 wires TextEngine into Phase 1 with `texts=[]` (generation mode). ✓
2. **Placeholder scan:** No TBD, TODO, or vague placeholders. All code is concrete. ✓
3. **Type consistency:** Uses `CEFRLevel(cefr_level)` for string→enum conversion. `TextResult.translations` is `list[str]`. Card dicts match `generate_cards_html` expectations. ✓
4. **Scope check:** Only Phase 1 changes. Phase 2 untouched (mock data, deferred). AGENTS.md updated to reflect. ✓
5. **Testing:** Inline tests verify prompt building and subprocess invocation without needing a real model. Smoke test validates import chain. ✓
