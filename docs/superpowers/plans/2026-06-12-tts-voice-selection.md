# TTS Voice Selection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a 6-option voice selection dropdown that appears when the Audio toggle is ON, passing the selected voice through to OmniVoice's `instruct` parameter.

**Architecture:** Three files changed — add a widget factory in `widgets.py`, accept an optional `instruct` parameter in `TTSEngine.synthesize()`, and wire the dropdown into `app.py`'s Phase 2 controls with visibility tied to the Audio toggle. No new files needed.

**Tech Stack:** Python 3.12+, Gradio 6, Pydantic, omnivoice

---

### Task 1: Add `create_voice_dropdown()` widget factory

**Files:**
- Modify: `frontend/ui/widgets.py`

- [ ] **Step 1: Add the widget factory function**

Append to `frontend/ui/widgets.py`:

```python
def create_voice_dropdown(default_voice: str = "female, young adult") -> "gr.Dropdown":
    """Create a voice selection dropdown for TTS audio generation.

    Six presets mapped to OmniVoice instruct strings (gender × age).
    Ordered by gender first, then age from oldest to youngest.

    Args:
        default_voice: Default OmniVoice instruct string.

    Returns:
        Configured gr.Dropdown with 6 voice presets.
    """
    import gradio as gr

    choices = [
        "Female — Middle-Aged",
        "Female — Young Adult",
        "Female — Teenager",
        "Male — Middle-Aged",
        "Male — Young Adult",
        "Male — Teenager",
    ]

    return gr.Dropdown(
        label="Voice",
        choices=choices,
        value=default_voice,
        elem_id="voice-dropdown",
    )
```

- [ ] **Step 2: Run smoke test to verify no import errors**

Run: `python scripts/smoke_test.py`
Expected: clean exit (no traceback)

- [ ] **Step 3: Commit**

```bash
git add frontend/ui/widgets.py
git commit -m "feat: add create_voice_dropdown() widget factory"
```

---

### Task 2: Accept `instruct` parameter in `TTSEngine.synthesize()`

**Files:**
- Modify: `core/engine.py` (~lines 305-340)

- [ ] **Step 1: Update method signature**

Find the `synthesize` method in `TTSEngine` (around line 305). Change the signature from:

```python
def synthesize(self, texts: list[str], output_dir: Path, language: str | None = None) -> AudioResult:
```

To:

```python
def synthesize(
    self,
    texts: list[str],
    output_dir: Path,
    language: str | None = None,
    instruct: str | None = None,
) -> AudioResult:
```

- [ ] **Step 2: Update the docstring**

Add `instruct` to the Args section of the docstring:

```python
        instruct: OmniVoice voice design string (e.g., "female, young adult").
            Defaults to "female, young adult" when omitted.
```

- [ ] **Step 3: Replace hardcoded `"female"` in model.generate() call**

Find this block inside `synthesize()` (around line 320):

```python
                audio_data = self._model.generate(
                    text=text,
                    instruct="female",
                    language=language,
                )
```

Replace with:

```python
                audio_data = self._model.generate(
                    text=text,
                    instruct=instruct or "female, young adult",
                    language=language,
                )
```

- [ ] **Step 4: Run smoke test**

Run: `python scripts/smoke_test.py`
Expected: clean exit (no traceback)

- [ ] **Step 5: Commit**

```bash
git add core/engine.py
git commit -m "feat: accept instruct parameter in TTSEngine.synthesize()"
```

---

### Task 3: Wire voice dropdown into `app.py`

**Files:**
- Modify: `app.py`

- [ ] **Step 1: Import the new widget factory**

Add to the imports section (near line 16, after `create_toggle`):

```python
from frontend.ui.widgets import create_toggle, create_voice_dropdown
```

- [ ] **Step 2: Add voice dropdown widget in Phase 2 controls area**

After the existing toggles row (line ~364-367), add a new block for the voice dropdown. The current code is:

```python
            with gr.Row():
                audio_toggle = create_toggle("🔊 Audio", value=False, elem_id="toggle-audio")
                images_toggle = create_toggle("🖼️ Images", value=False, elem_id="toggle-images")

            generate_cards_btn = gr.Button("Generate Cards", elem_id="generate-cards-btn", variant="secondary")
```

Insert the voice dropdown **between** the toggles row and the Generate Cards button:

```python
            with gr.Row():
                audio_toggle = create_toggle("🔊 Audio", value=False, elem_id="toggle-audio")
                images_toggle = create_toggle("🖼️ Images", value=False, elem_id="toggle-images")

            voice_dropdown = create_voice_dropdown()
            voice_dropdown.visible = False  # hidden until Audio is ON

            generate_cards_btn = gr.Button("Generate Cards", elem_id="generate-cards-btn", variant="secondary")
```

- [ ] **Step 3: Update `_enable_phase2()` to show the voice dropdown**

Find `_enable_phase2()` (around line 410). Current return:

```python
    def _enable_phase2():
        """After text generation, enable toggles and Generate Cards button by removing disabled CSS."""
        return gr.Checkbox(interactive=True), gr.Checkbox(interactive=True), gr.Button(interactive=True), ""
```

Change to return 5 values (add voice dropdown visible):

```python
    def _enable_phase2():
        """After text generation, enable toggles and Generate Cards button by removing disabled CSS."""
        return (
            gr.Checkbox(interactive=True),
            gr.Checkbox(interactive=True),
            gr.Button(interactive=True),
            "",
            gr.Dropdown(visible=True),
        )
```

- [ ] **Step 4: Update `_reset_to_idle()` to hide the voice dropdown**

Find `_reset_to_idle()` (around line 416). Current return has 5 values. Change to 6:

```python
    def _reset_to_idle():
        """Reset UI to idle state when user changes parameters."""
        return (
            gr.Button(visible=True, interactive=True),
            gr.Checkbox(interactive=False),
            gr.Checkbox(interactive=False),
            gr.Button(visible=True, interactive=False, variant="secondary"),
            """<style id="phase-css">#toggle-images, #toggle-audio { opacity: 0.45; pointer-events: none; cursor: not-allowed; } #generate-cards-btn { opacity: 0.45; pointer-events: none; cursor: not-allowed; }</style>""",
            gr.Dropdown(visible=False),
        )
```

- [ ] **Step 5: Update the `.then()` output list for `_enable_phase2`**

Find the click handler chain (around line 430). The current outputs list is:

```python
    ).then(
        fn=_enable_phase2,
        inputs=[],
        outputs=[images_toggle, audio_toggle, generate_cards_btn, phase_css],
    )
```

Add `voice_dropdown` to the outputs list:

```python
    ).then(
        fn=_enable_phase2,
        inputs=[],
        outputs=[images_toggle, audio_toggle, generate_cards_btn, phase_css, voice_dropdown],
    )
```

- [ ] **Step 6: Update `_reset_to_idle` output list**

Find all four `.change()` calls (lines ~440-445). Each currently references `[generate_text_btn, images_toggle, audio_toggle, generate_cards_btn, phase_css]`. Add `voice_dropdown` to each:

```python
    scenario_input.change(_reset_to_idle, inputs=[], outputs=[generate_text_btn, images_toggle, audio_toggle, generate_cards_btn, phase_css, voice_dropdown])
    cefr_dropdown.change(_reset_to_idle, inputs=[], outputs=[generate_text_btn, images_toggle, audio_toggle, generate_cards_btn, phase_css, voice_dropdown])
    batch_slider.change(_reset_to_idle, inputs=[], outputs=[generate_text_btn, images_toggle, audio_toggle, generate_cards_btn, phase_css, voice_dropdown])
    language_dropdown.change(_reset_to_idle, inputs=[], outputs=[generate_text_btn, images_toggle, audio_toggle, generate_cards_btn, phase_css, voice_dropdown])
```

- [ ] **Step 7: Update `_handle_media_generation` wrapper to accept voice**

Find the wrapper function (around line 395). Change signature from:

```python
    def _handle_media_generation(scenario, cefr_level, batch_size, target_language, include_audio):
```

To:

```python
    def _handle_media_generation(scenario, cefr_level, batch_size, target_language, include_audio, voice):
```

And pass `voice` to the pipeline call inside:

```python
        for result in generate_media_async(scenario, cefr_level, batch_size, target_language, include_audio, voice):
```

- [ ] **Step 8: Update `generate_media_async()` signature and pipeline call**

Find the function definition (around line 145). Change signature from:

```python
def generate_media_async(
    scenario: str,
    cefr_level: str,
    batch_size: int,
    target_language: str = "Latvian",
    include_audio: bool = False,
):
```

To:

```python
def generate_media_async(
    scenario: str,
    cefr_level: str,
    batch_size: int,
    target_language: str = "Latvian",
    include_audio: bool = False,
    voice: str = "female, young adult",
):
```

Find the `tts_engine.synthesize()` call (around line 210) and add `instruct=voice`:

```python
            audio_result = tts_engine.synthesize(
                translations_list, output_dir, language=target_language, instruct=voice,
            )
```

- [ ] **Step 9: Wire voice_dropdown input to the media generation handler**

Find the `generate_cards_btn.click()` call. Current inputs:

```python
    generate_cards_btn.click(
        fn=_handle_media_generation,
        inputs=[scenario_input, cefr_dropdown, batch_slider, language_dropdown, audio_toggle],
        outputs=[progress_html, card_output],
    )
```

Add `voice_dropdown` to inputs:

```python
    generate_cards_btn.click(
        fn=_handle_media_generation,
        inputs=[scenario_input, cefr_dropdown, batch_slider, language_dropdown, audio_toggle, voice_dropdown],
        outputs=[progress_html, card_output],
    )
```

- [ ] **Step 10: Run smoke test**

Run: `python scripts/smoke_test.py`
Expected: clean exit (no traceback)

- [ ] **Step 11: Commit**

```bash
git add app.py
git commit -m "feat: wire voice dropdown into TTS audio generation"
```

---

### Task 4: Final verification

**Files:**
- None (verification only)

- [ ] **Step 1: Run smoke test one final time**

Run: `python scripts/smoke_test.py`
Expected: clean exit (no traceback)

- [ ] **Step 2: Manual UI verification**

Start the app: `python app.py`

Verify:
1. App launches on port 7860 without errors
2. Phase 1: Enter scenario → Generate Text → cards appear with placeholder back
3. Phase 2 controls: Audio toggle and Images toggle appear side-by-side (Audio left, Images right)
4. Voice dropdown is hidden initially
5. Toggle Audio ON → voice dropdown appears with 6 options
6. Select different voices → click Generate Cards → audio generated with selected voice
7. Change any input parameter (scenario/CEFR/batch/language) → audio toggle resets to OFF and voice dropdown hides

- [ ] **Step 3: Commit**

```bash
git add .
git commit -m "test: final smoke test verification"
```

---

## Self-Review Checklist

**1. Spec coverage:**
- ✅ Voice presets (6 options, correct order) — Task 1
- ✅ Dropdown placement under Audio toggle — Task 3 Step 2
- ✅ Visibility tied to Audio toggle ON/OFF — Task 3 Steps 3-4
- ✅ `instruct` param in TTSEngine.synthesize() — Task 2
- ✅ Voice passed through pipeline — Task 3 Steps 7-9
- ✅ State machine integration (reset/enable) — Task 3 Steps 3-6

**2. Placeholder scan:** No TBD, TODO, or "similar to" references found.

**3. Type consistency:** `voice: str` used consistently across `_handle_media_generation`, `generate_media_async`, and the Gradio input wiring. Default value `"female, young adult"` matches everywhere.

---

Plan complete and saved to `docs/superpowers/plans/2026-06-12-tts-voice-selection.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
