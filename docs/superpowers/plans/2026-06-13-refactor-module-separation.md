# Refactor: Module Separation and Test Reorganization

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract TTSEngine and ImageGenEngine from `core/engine.py` into dedicated modules, move Gradio UI construction into `widgets.build_ui()`, rename `scripts/` to `tests/` with proper naming conventions, and delete the stale `core/test_text_engine.py`.

**Architecture:** Pure refactor — no behavior changes. TTSEngine and ImageGenEngine are copied verbatim into new files; EnginePool imports updated; app.py's inline Gradio Blocks construction is extracted into a `build_ui()` function in widgets.py that returns the demo object. Scripts directory is renamed to tests/ with pytest-compatible naming.

**Tech Stack:** Python 3.12+, Gradio 6, Pydantic >=2.0.0

---

## File Structure After Refactor

| File | Responsibility |
|---|---|
| `core/engine.py` | MiniCPMTextEngine, LlamaCppTextEngine, EnginePool (TTSEngine/ImageGenEngine removed) |
| `core/audio_gen.py` | TTSEngine only |
| `core/image_gen.py` | ImageGenEngine only |
| `frontend/ui/widgets.py` | create_toggle, create_voice_dropdown, build_ui(), _VOICE_MAP, UI state helpers |
| `app.py` | Business logic handlers (generate_text_async, generate_media_async), `_phase1_texts`, __main__ block |
| `tests/smoke_test.py` | Integration test (moved from scripts/) |
| `tests/count_enforcement_test.py` | TextResult.validate_and_parse tests |
| `tests/extract_sentences_test.py` | extract_sentences tests |
| `tests/progression_test.py` | _progress_pct helper tests |
| `tests/translation_retry_test.py` | LlamaCppTextEngine retry loop tests |
| `models/download_models.py` | Model downloader (moved from scripts/) |
| `pyproject.toml` | pytest config (new) |

**Deleted:** `core/test_text_engine.py` (tests deprecated TextEngine class), `scripts/` directory entirely.

---

## Task 1: Create `core/audio_gen.py` with TTSEngine

**Files:**
- Create: `core/audio_gen.py`

- [ ] **Step 1: Write the file**

Create `core/audio_gen.py` with the exact TTSEngine class from `core/engine.py`:

```python
"""EuropaLex Text-to-Speech Engine — OmniVoice via omnivoice Python package."""

from __future__ import annotations

import logging
from pathlib import Path

import soundfile as sf
import torch

from core.types import AudioResult

logger = logging.getLogger(__name__)


class TTSEngine:
    """Text-to-speech using the omnivoice Python package.

    Lazy-loads the model on first synthesis call, unloads after completion.
    Only one instance can be active at a time (enforced by EnginePool).
    """

    def __init__(self, device: str = "cuda"):
        """Initialize the TTS engine.

        Args:
            device: 'cuda', 'mps', or 'cpu'.
        """
        self.device = device
        self._model = None
        self._loaded = False

    def _load_model(self) -> None:
        """Lazy-load the OmniVoice model from HF Hub (cached locally)."""
        if self._loaded:
            return

        try:
            from omnivoice import OmniVoice
        except ImportError:
            raise ImportError(
                "omnivoice package not installed. Run: pip install omnivoice"
            )

        logger.info("Loading OmniVoice from HF Hub (cached in ~/.cache/huggingface/)")
        self._model = OmniVoice.from_pretrained(
            "k2-fsa/OmniVoice",
            device_map=self.device,
            dtype=torch.float16 if self.device != "cpu" else torch.float32,
        )
        self._loaded = True
        logger.info("OmniVoice model loaded on %s", self.device)

    def synthesize(
        self,
        texts: list[str],
        output_dir: Path,
        language: str | None = None,
        instruct: str | None = None,
    ) -> AudioResult:
        """Generate audio for a batch of texts using voice design mode.

        Uses OmniVoice in voice design mode with a consistent female voice.
        Optionally accepts a target language for improved synthesis quality.

        Args:
            texts: List of text strings to convert to speech.
            output_dir: Directory to save .wav files.
            language: Target language name for TTS (e.g., "Latvian", "Spanish").
                Improves synthesis quality when known. Defaults to None (auto-detect).
            instruct: OmniVoice voice design string (e.g., "female, young adult").
                Defaults to "female, young adult" when omitted.

        Returns:
            AudioResult with absolute paths to generated audio files.
        """
        self._load_model()
        output_dir.mkdir(parents=True, exist_ok=True)

        audio_paths = []
        for i, text in enumerate(texts):
            try:
                audio_data = self._model.generate(
                    text=text,
                    instruct=instruct or "female, young adult",
                    language=language,
                )
                if audio_data and len(audio_data) > 0:
                    wav_path = output_dir / f"audio_{i}.wav"
                    sf.write(str(wav_path), audio_data[0], 24000)
                    audio_paths.append(str(wav_path.resolve()))
                    logger.debug("Saved audio to %s", wav_path)
                else:
                    logger.warning("Empty audio output for text: %s", text[:50])
                    audio_paths.append(None)
            except Exception as e:
                logger.error("TTS failed for text '%s': %s", text[:50], e)
                audio_paths.append(None)

        return AudioResult(audio_paths=list(audio_paths))

    def unload(self) -> None:
        """Unload the model and free GPU memory."""
        if self._model is not None:
            del self._model
            self._model = None
            self._loaded = False
            try:
                torch.cuda.empty_cache()
            except Exception:
                pass
            logger.info("OmniVoice model unloaded")
```

- [ ] **Step 2: Verify the file is syntactically valid**

Run: `python -c "from core.audio_gen import TTSEngine; print('OK')"`
Expected: `OK` (may show import error for omnivoice if not installed — that's fine, the class definition itself must be valid)

- [ ] **Step 3: Commit**

```bash
git add core/audio_gen.py
git commit -m "feat: extract TTSEngine into core/audio_gen.py"
```

---

## Task 2: Create `core/image_gen.py` with ImageGenEngine

**Files:**
- Create: `core/image_gen.py`

- [ ] **Step 1: Write the file**

Create `core/image_gen.py` with the exact ImageGenEngine class from `core/engine.py`:

```python
"""EuropaLex Image Generation Engine — diffusers Flux2KleinPipeline."""

from __future__ import annotations

import logging
from pathlib import Path

import torch

from core.types import ImageResult

logger = logging.getLogger(__name__)


class ImageGenEngine:
    """Image generation using diffusers Flux2KleinPipeline.

    Lazy-loads the pipeline on first generation call, unloads after completion.
    Only one instance can be active at a time (enforced by EnginePool).
    """

    def __init__(self, device: str = "cuda"):
        """Initialize the image engine.

        Args:
            device: 'cuda', 'mps', or 'cpu'.
        """
        self.device = device
        self._pipeline = None
        self._loaded = False

    def _load_pipeline(self) -> None:
        """Lazy-load the Flux2Klein pipeline from HF Hub (cached locally)."""
        if self._loaded:
            return

        try:
            from diffusers import Flux2KleinPipeline
        except ImportError:
            raise ImportError(
                "diffusers package not installed. Run: pip install diffusers"
            )

        torch_dtype = torch.bfloat16 if self.device == "cuda" else torch.float32
        logger.info("Loading Flux2Klein from HF Hub (cached in ~/.cache/huggingface/)")
        self._pipeline = Flux2KleinPipeline.from_pretrained(
            "black-forest-labs/FLUX.2-klein-4B",
            torch_dtype=torch_dtype,
        )
        self._pipeline.enable_model_cpu_offload()
        self._loaded = True
        logger.info("Flux2Klein pipeline loaded on %s", self.device)

    def generate(self, prompts: list[str], output_dir: Path) -> ImageResult:
        """Generate images for a batch of prompts.

        Args:
            prompts: List of text prompts for image generation.
            output_dir: Directory to save .png files.

        Returns:
            ImageResult with absolute paths to generated image files.
        """
        self._load_pipeline()
        output_dir.mkdir(parents=True, exist_ok=True)

        image_paths = []
        for i, prompt in enumerate(prompts):
            try:
                images = self._pipeline(
                    prompt=prompt,
                    num_inference_steps=10,
                    guidance_scale=1.0,
                    width=240,
                    height=160,
                )
                if images.images and len(images.images) > 0:
                    img_path = output_dir / f"image_{i}.png"
                    images.images[0].save(str(img_path))
                    image_paths.append(str(img_path.resolve()))
                    logger.debug("Saved image to %s", img_path)
                else:
                    logger.warning("Empty image output for prompt: %s", prompt[:50])
                    image_paths.append(None)
            except Exception as e:
                logger.error("Image generation failed for prompt '%s': %s", prompt[:50], e)
                image_paths.append(None)

        return ImageResult(image_paths=list(image_paths))

    def unload(self) -> None:
        """Unload the pipeline and free GPU memory."""
        if self._pipeline is not None:
            del self._pipeline
            self._pipeline = None
            self._loaded = False
            try:
                torch.cuda.empty_cache()
            except Exception:
                pass
            logger.info("Flux2Klein pipeline unloaded")
```

- [ ] **Step 2: Verify the file is syntactically valid**

Run: `python -c "from core.image_gen import ImageGenEngine; print('OK')"`
Expected: `OK` (may show diffusers import error — that's fine)

- [ ] **Step 3: Commit**

```bash
git add core/image_gen.py
git commit -m "feat: extract ImageGenEngine into core/image_gen.py"
```

---

## Task 3: Update `core/engine.py` — Remove TTSEngine/ImageGenEngine, Update EnginePool Imports

**Files:**
- Modify: `core/engine.py`

- [ ] **Step 1: Replace the TTSEngine class with an import from audio_gen**

In `core/engine.py`, find the entire `class TTSEngine:` block (from `class TTSEngine:` through the end of its `unload()` method) and replace it with:

```python
# TTSEngine has been extracted to core.audio_gen
from core.audio_gen import TTSEngine  # noqa: F401
```

- [ ] **Step 2: Replace the ImageGenEngine class with an import from image_gen**

Find the entire `class ImageGenEngine:` block and replace it with:

```python
# ImageGenEngine has been extracted to core.image_gen
from core.image_gen import ImageGenEngine  # noqa: F401
```

- [ ] **Step 3: Verify imports still work**

Run: `python -c "from core.engine import MiniCPMTextEngine, LlamaCppTextEngine, TTSEngine, ImageGenEngine, EnginePool; print('All imports OK')"`
Expected: `All imports OK`

- [ ] **Step 4: Commit**

```bash
git add core/engine.py
git commit -m "refactor: extract TTSEngine and ImageGenEngine from engine.py"
```

---

## Task 4: Expand `frontend/ui/widgets.py` — Add build_ui(), _VOICE_MAP, UI State Helpers

**Files:**
- Modify: `frontend/ui/widgets.py`

> **Critical design note on `_phase1_texts`:** This module-level variable holds the shared state between Phase 1 (text generation in app.py) and Phase 2 (media generation in widgets.py). It MUST live in `app.py` because:
> 1. Phase 1's `generate_text_async()` sets it via `global _phase1_texts`
> 2. Phase 2's handler reads it to know what text to translate
> 3. Moving it to widgets.py would require importing app at module level, creating a circular import (widgets imports app for build_ui, app would need widgets)
> 4. Solution: keep `_phase1_texts` in app.py; Phase 2 handler imports it from app inside `build_ui()` body

- [ ] **Step 1: Replace the entire file with the expanded version**

```python
# EuropaLex Frontend UI Components
# Custom styled Gradio widget wrappers + full UI layout builder


def create_toggle(label: str, value: bool = True, elem_id: str = "") -> "gr.Checkbox":
    """Create a styled toggle checkbox for media options.

    Args:
        label: Display label with emoji (e.g., '🖼️ Images').
        value: Default checked state.
        elem_id: Optional Gradio element ID.

    Returns:
        Configured gr.Checkbox instance.
    """
    import gradio as gr

    return gr.Checkbox(
        label=label,
        value=value,
        elem_id=elem_id if elem_id else "toggle-" + label.lower().replace(" ", "-").replace("🖼️", "img").replace("🔊", "audio"),
    )


def create_voice_dropdown(
    default_voice: str = "female, young adult",
) -> "gr.Dropdown":
    """Create a voice selection dropdown for TTS audio generation.

    Six presets mapped to OmniVoice instruct strings (gender × age).
    Ordered by gender first, then age from oldest to youngest.
    Visible by default; disabled via CSS until Audio toggle is ON.

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
        allow_custom_value=True,
        visible=True,
    )


# ─── Voice Mapping ────────────────────────────────────────────────

# Mapping from voice dropdown display labels to OmniVoice instruct strings
_VOICE_MAP: dict[str, str] = {
    "Female — Middle-Aged": "female, middle-aged",
    "Female — Young Adult": "female, young adult",
    "Female — Teenager": "female, teenager",
    "Male — Middle-Aged": "male, middle-aged",
    "Male — Young Adult": "male, young adult",
    "Male — Teenager": "male, teenager",
}


# ─── UI State Helpers ─────────────────────────────────────────────

def _enable_phase2() -> tuple:
    """After text generation, enable toggles, dropdowns and Generate Cards button by removing disabled CSS.

    Both Audio and Images toggles default to ON after Phase 1. Voice dropdown becomes interactive — it becomes visible when audio toggle is turned ON (via audio_toggle.change).
    Explicitly sets value=True to prevent Gradio from resetting checkbox state on re-render.

    Returns:
        Tuple of (images_toggle, audio_toggle, generate_cards_btn, voice_dropdown, phase_css) updates.
    """
    import gradio as gr
    return (
        gr.Checkbox(interactive=True, value=True),
        gr.Checkbox(interactive=True, value=True),
        gr.Button(interactive=True),
        gr.Dropdown(interactive=True),
        "",
    )


def _reset_to_idle() -> tuple:
    """Reset UI to idle state when user changes parameters.

    Only resets toggle/button interactivity — keeps cards visible
    so the user can regenerate without losing their work.
    Also restores both buttons visibility (hidden by Phase 2).
    Re-applies disabled CSS to phase-2 controls.
    Keeps voice dropdown visible but disabled (it becomes interactive when audio is toggled ON after Phase 1).
    Explicitly sets value=False to prevent Gradio from resetting checkbox state on re-render.

    Returns:
        Tuple of (generate_text_btn, images_toggle, audio_toggle, generate_cards_btn, voice_dropdown, phase_css) updates.
    """
    import gradio as gr
    return (
        gr.Button(visible=True, interactive=True),
        gr.Checkbox(interactive=False, value=False),
        gr.Checkbox(interactive=False, value=False),
        gr.Button(visible=True, interactive=False, variant="secondary"),
        gr.Dropdown(visible=True, interactive=False),
        """<style id="phase-css">#toggle-images, #toggle-audio { opacity: 0.45; pointer-events: none; cursor: not-allowed; } #language-dropdown, #voice-dropdown { opacity: 0.45; pointer-events: none; cursor: not-allowed; } #generate-cards-btn { opacity: 0.45; pointer-events: none; cursor: not-allowed; }</style>""",
    )


def _enable_language_dropdown_on_audio(is_checked: bool) -> tuple:
    """Update CSS and voice dropdown interactivity when audio toggle changes.

    Voice dropdown is always visible — toggling audio ON makes it interactive,
    toggling OFF disables it (but keeps it visible).

    Args:
        is_checked: Whether the audio toggle is currently checked.

    Returns:
        Tuple of (voice_dropdown_update, phase_css_html) updates.
    """
    import gradio as gr
    if is_checked:
        # Audio ON: remove disabled CSS, make voice dropdown interactive
        return gr.Dropdown(interactive=True), ""
    else:
        # Audio OFF: apply disabled CSS to voice dropdown only (not generate button)
        return gr.Dropdown(interactive=False), """<style id="phase-css">#voice-dropdown { opacity: 0.45; pointer-events: none; cursor: not-allowed; }</style>"""


# ─── UI Layout Builder ───────────────────────────────────────────

def build_ui() -> "gr.Blocks":
    """Construct the entire Gradio Blocks layout and return it.

    This function replaces the inline `with gr.Blocks() as demo:` block in app.py.
    It creates all widgets, assembles the layout, wires event handlers, and returns
    the configured `demo` object ready for `.launch()`.

    IMPORTANT: Imports from app.py happen INSIDE this function (not at module level)
    to avoid circular imports. app.py does NOT import from widgets.py at module level
    (only inside __main__), so the import chain is safe:
      import widgets → build_ui() body runs → imports from app → app has no widget deps.

    _phase1_texts is imported from app here — it's shared mutable state between
    Phase 1 (generate_text_async sets it) and Phase 2 (_handle_media_generation_v2 reads it).

    Returns:
        Configured gr.Blocks instance with all events wired.
    """
    import gradio as gr

    # Import business logic handlers INSIDE build_ui to avoid circular import
    from app import generate_text_async, generate_media_async, _phase1_texts

    from frontend.ui.cards import generate_cards_html, generate_progress_html

    # ─── CSS Block ────────────────────────────────────────────────
    gr.HTML("""<div id="europalex-styles" style="display:none;">
    </div>""")

    with gr.Row():
        gr.Column(scale=1)
        with gr.Column(scale=3, elem_id="app-card"):
            gr.HTML('<h2 style="color:#1a1a1a; font-family:sans-serif; margin-bottom:4px;">Europa Lex</h2>')
            gr.HTML('<p style="color:#666; font-size:0.8em; margin-top:-4px; margin-bottom:12px;">AI-powered flashcard generator — translate text into European languages, generate audio &amp; images, and export Anki decks</p>')

            with gr.Row():
                scenario_input = gr.Textbox(
                    label="Scenario or Topic",
                    placeholder="e.g., ordering coffee, family members, weather",
                    lines=1,
                    elem_id="scenario-input",
                )
                cefr_dropdown = gr.Dropdown(
                    label="CEFR Level",
                    choices=["A0", "A1", "A2", "B1", "B2"],
                    value="B1",
                    elem_id="cefr-dropdown",
                )
                batch_slider = gr.Slider(
                    minimum=1,
                    maximum=10,
                    value=3,
                    step=1,
                    label="Number of Cards",
                    elem_id="batch-slider",
                )

            # Phase 1 button: Generate Text
            generate_text_btn = gr.Button("Generate Text", elem_id="generate-btn")

            # Card display area (below Generate Text)
            card_output = gr.HTML(label="Generated Cards")

            # Phase 2 controls: language, toggles + button (below cards)
            with gr.Row():
                language_dropdown = gr.Dropdown(
                    label="Target Language",
                    choices=["Latvian", "Spanish", "French", "German", "Polish", "Italian", "Portuguese", "Finnish"],
                    value="Latvian",
                    elem_id="language-dropdown",
                )
            with gr.Row():
                audio_toggle = create_toggle("🔊 Audio", value=True, elem_id="toggle-audio")
                images_toggle = create_toggle("🖼️ Images", value=True, elem_id="toggle-images")

            voice_dropdown = create_voice_dropdown()  # visible but disabled via CSS until Phase 2 + audio ON

            generate_cards_btn = gr.Button("Generate Cards", elem_id="generate-cards-btn", variant="secondary")

            # Dynamic CSS block — toggled to disable phase-2 controls until text generation completes
            phase_css = gr.HTML("""<style id="phase-css">#toggle-images, #toggle-audio { opacity: 0.45; pointer-events: none; cursor: not-allowed; } #language-dropdown, #voice-dropdown { opacity: 0.45; pointer-events: none; cursor: not-allowed; }</style>""")

            progress_html = gr.HTML(label="Progress")

            with gr.Row():
                gr.Button(".apkg", interactive=False, elem_id="export-btn")
                gr.Button(".csv", interactive=False, elem_id="export-btn")
                gr.Button("Sync to Anki", interactive=False, elem_id="export-btn")

        gr.Column(scale=1)

    # ─── Event Wiring ──────────────────────────────────────────────

    def _handle_text_generation(scenario: str, cefr_level: str, batch_size: int):
        """Wrapper for generate_text_async that handles empty scenario."""
        if not scenario.strip():
            yield generate_progress_html(0, "⚠️ Please enter a scenario or topic."), '<div style="color:#c44; padding:20px;">Please enter a scenario or topic to generate cards.</div>'
            return
        for result in generate_text_async(scenario, cefr_level, batch_size):
            yield result

    def _handle_media_generation_v2(scenario: str, cefr_level: str, batch_size: int, target_language: str, include_audio: bool, include_images: bool, voice: str):
        """Wrapper for generate_media_async that handles empty scenario and missing Phase 1 texts.

        Reads _phase1_texts from app module (imported at build_ui() call time).
        """
        if not _phase1_texts:
            yield generate_progress_html(0, "⚠️ Please generate text first."), (
                '<div style="color:#c44; padding:20px;">'
                'No Phase 1 text found. Generate English text first, then click "Generate Cards".'
                '</div>'
            )
            return

        if not scenario.strip():
            yield generate_progress_html(0, "⚠️ Please enter a scenario or topic."), '<div style="color:#c44; padding:20px;">Please enter a scenario or topic to generate cards.</div>'
            return

        instruct = _VOICE_MAP.get(voice, voice)
        for result in generate_media_async(scenario, cefr_level, batch_size, target_language, include_audio, include_images, instruct):
            yield result

    def _on_media_generation_complete():
        """Hide both buttons during media generation."""
        import gradio as gr
        return (gr.Button(visible=False), gr.Button(visible=False))

    generate_text_btn.click(
        fn=_handle_text_generation,
        inputs=[scenario_input, cefr_dropdown, batch_slider],
        outputs=[progress_html, card_output],
    ).then(
        fn=_enable_phase2,
        inputs=[],
        outputs=[images_toggle, audio_toggle, generate_cards_btn, voice_dropdown, phase_css],
    )

    # When audio toggle changes: show/hide voice dropdown and manage disabled CSS
    def _on_audio_toggle_change(is_checked: bool):
        """Handle audio toggle change: update voice dropdown + CSS."""
        yield from _enable_language_dropdown_on_audio(is_checked)

    audio_toggle.change(
        fn=_on_audio_toggle_change,
        inputs=[audio_toggle],
        outputs=[voice_dropdown, phase_css],
    )

    generate_cards_btn.click(
        fn=_handle_media_generation_v2,
        inputs=[scenario_input, cefr_dropdown, batch_slider, language_dropdown, audio_toggle, images_toggle, voice_dropdown],
        outputs=[progress_html, card_output],
    ).then(
        fn=_on_media_generation_complete,
        inputs=[],
        outputs=[generate_text_btn, generate_cards_btn],
    )

    # Reset toggles and both buttons when user changes any input parameter
    scenario_input.change(_reset_to_idle, inputs=[], outputs=[generate_text_btn, images_toggle, audio_toggle, generate_cards_btn, voice_dropdown, phase_css])
    cefr_dropdown.change(_reset_to_idle, inputs=[], outputs=[generate_text_btn, images_toggle, audio_toggle, generate_cards_btn, phase_css])
    batch_slider.change(_reset_to_idle, inputs=[], outputs=[generate_text_btn, images_toggle, audio_toggle, generate_cards_btn, voice_dropdown, phase_css])
    # Language change does NOT reset — user can switch languages freely after Phase 1

    return gr.Blocks()
```

- [ ] **Step 2: Verify imports**

Run: `python -c "from frontend.ui.widgets import create_toggle, create_voice_dropdown, build_ui, _VOICE_MAP; print('OK')"`
Expected: `OK` (build_ui function is defined but not called — no circular import triggered)

- [ ] **Step 3: Commit**

```bash
git add frontend/ui/widgets.py
git commit -m "refactor: add build_ui() layout function and UI state helpers to widgets.py"
```

---

## Task 5: Rewrite `app.py` — Extract Business Logic, Thin `__main__` Block

**Files:**
- Modify: `app.py`

> **Design note:** `_phase1_texts` stays in app.py because it's business logic state (set by `generate_text_async`, read by Phase 2 handler). The Phase 2 handler lives in widgets.py but imports `_phase1_texts` from app inside `build_ui()` body. This avoids circular imports because:
> - app.py does NOT import from widgets at module level (only in `__main__`)
> - widgets.py imports from app INSIDE `build_ui()` body (after app is fully loaded)

- [ ] **Step 1: Replace the entire app.py with the refactored version**

```python
#!/usr/bin/env python3
"""EuropaLex — Gradio Frontend Demo

Interactive flashcard generator UI with mock data.
No backend connection — visual preview only.

Run: uv sync && python app.py
"""

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

# ─── Phase State ────────────────────────────────────────────────────

_phase1_texts: list[str] = []  # English texts from Phase 1, passed to Phase 2


# ─── Mock Card Data ────────────────────────────────────────────────

MOCK_CARDS = {
    "A0": [
        {"front": "Es esmu bērns.", "back": "I am a child."},
        {"front": "Šī ir māja.", "back": "This is a house."},
        {"front": "Es mīlu savu ģimeni.", "back": "I love my family."},
    ],
    "A1": [
        {"front": "Labrīt!", "back": "Good morning!"},
        {"front": "Paldies.", "back": "Thank you."},
        {"front": "Vai tu runā angļu valodu?", "back": "Do you speak English?"},
    ],
    "A2": [
        {"front": "Es strādāju skolā.", "back": "I work at a school."},
        {"front": "Kas ir laika grāmata?", "back": "What is a calendar?"},
        {"front": "Es eju uz veikalu.", "back": "I am going to the store."},
    ],
    "B1": [
        {"front": "Es gribētu izdzert kafiju.", "back": "I would like to drink coffee."},
        {"front": "Vai jūs varat man palīdzēt?", "back": "Can you help me?"},
        {"front": "Cik daudz maksā šis?", "back": "How much does this cost?"},
    ],
    "B2": [
        {"front": "Es uzskatu, ka tas ir pareizi.", "back": "I believe that is correct."},
        {"front": "Vai jūs varat izskaidrot iemeslu?", "back": "Can you explain the reason?"},
        {"front": "Šis projekts prasa vairāk laika.", "back": "This project requires more time."},
    ],
    "C1": [
        {"front": "Es nevaru atturēties no domas, ka...", "back": "I can't help but think that..."},
        {"front": "Tas ir acīmredzami, taču...", "back": "It is obvious, however..."},
        {"front": "Vai jūs dalāties manā viedoklī?", "back": "Do you share my opinion?"},
    ],
    "C2": [
        {"front": "Es apgūstu latviešu valodu ar lielu aizrautību.", "back": "I am mastering the Latvian language with great enthusiasm."},
        {"front": "Šis ir sarežģīts jautājums.", "back": "This is a complex question."},
        {"front": "Es saprotu katru vārdu.", "back": "I understand every word."},
    ],
}


def transform_mock_cards(raw_cards: list[dict]) -> list[dict]:
    """Transform legacy mock card format to two-phase format.

    Legacy format: {"front": <Latvian>, "back": <English>}
    New format:    {"text": <English>, "translation": <Latvian>}

    For text-only phase, 'text' is displayed with placeholder back.
    After media generation, 'translation' is populated.
    """
    return [{"text": c["back"], "translation": c["front"]} for c in raw_cards]


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
        from core.engine import EnginePool, MiniCPMTextEngine
        from core.types import CEFRLevel, EngineConfig
        from frontend.ui.cards import generate_progress_html

        config = EngineConfig.from_settings_yaml()
        pool = EnginePool.get(config)
        engine = pool.get_english_engine()

        cefr = CEFRLevel(cefr_level)
    except FileNotFoundError as e:
        logger.error("Phase 1 model not found: %s", e)
        yield generate_progress_html(0, f"\u26a0\ufe0f Model file missing: {e}"), (
            '<div style="color:#c44; padding:20px;">'
            '<strong>Model file not found.</strong><br>'
            f'{e}<br><br>'
            'Run <code>python models/download_models.py minicpm</code> to download MiniCPM5-1B, '
            'or check <code>configs/settings.yaml</code> for the correct path.'
            '</div>'
        )
        return
    except Exception as e:
        logger.error("Phase 1 setup failed: %s", e, exc_info=True)
        yield generate_progress_html(0, f"\u26a0\ufe0f Setup error: {e}"), (
            '<div style="color:#c44; padding:20px;">'
            f'<strong>Failed to initialize engine.</strong><br>{e}<br><br>'
            'Check <code>configs/settings.yaml</code> and run the smoke test: '
            '<code>python tests/smoke_test.py</code>'
            '</div>'
        )
        return

    # Generate English text via Nemotron
    try:
        yield generate_progress_html(20, "Preparing MiniCPM5-1B generation..."), ""
        texts = engine.generate(
            texts=[],  # empty = generation mode (not translation)
            scenario=scenario,
            cefr_level=cefr,
            batch_size=batch_size,
            topic_description=scenario,  # user's free-form topic description
        )
    except Exception as e:
        logger.error("Phase 1 generation failed: %s", e, exc_info=True)
        err_detail = str(e)
        yield generate_progress_html(0, f"\u26a0\ufe0f Generation failed"), (
            '<div style="color:#c44; padding:20px;">'
            f'<strong>MiniCPM5-1B generation failed.</strong><br>'
            f'{err_detail}<br><br>'
            'Possible causes:<br>'
            '• llama-cpp-python not installed — run: <code>uv pip install llama-cpp-python</code><br>'
            '• Model file corrupted or incompatible format<br>'
            '• Insufficient VRAM (~1.1 GB required)<br><br>'
            'Check the terminal for full error output.'
            '</div>'
        )
        return

    # Store Phase 1 texts for Phase 2 (module-level state)
    global _phase1_texts
    _phase1_texts = list(texts.generated_texts)

    # Convert TextResult to card dicts for rendering
    from frontend.ui.cards import generate_cards_html

    cards = [
        {"text": t, "translation": "", "cefr_level": cefr, "topic_description": scenario}
        for t in texts.generated_texts
    ]

    yield generate_progress_html(60, "Generating text..."), ""
    yield generate_progress_html(100, "Text ready! Adjust media toggles and click Generate Cards."), generate_cards_html(cards, include_image=False, include_audio=False, placeholder_back=True)


def _progress_pct(
    translated_idx: int,
    total: int,
    start_pct: float = 15.0,
    end_pct: float = 70.0,
) -> tuple[float, str]:
    """Calculate progress percentage for translation within a given range.

    Args:
        translated_idx: Index of the sentence just completed (0-based).
        total: Total number of sentences to translate.
        start_pct: Starting percentage for this phase (default 15% after preparation).
        end_pct: Ending percentage for this phase (default 70% before next phase).

    Returns:
        (percentage, label) tuple.
    """
    if total <= 1:
        return end_pct, "Translation complete!"
    pct = start_pct + ((translated_idx + 1) / total) * (end_pct - start_pct)
    remaining = total - (translated_idx + 1)
    if pct >= end_pct:
        return end_pct, "Translation complete!"
    return round(pct, 1), f"Translated {translated_idx + 1}/{total} — {remaining} remaining..."


def generate_media_async(
    scenario: str,
    cefr_level: str,
    batch_size: int,
    target_language: str = "Latvian",
    include_audio: bool = False,
    include_images: bool = False,
    voice: str = "female, young adult",
):
    """Phase 2: Translate Phase 1 English text and optionally generate TTS audio.

    Reads the English texts from _phase1_texts (set by Phase 1 handler),
    translates each sentence one-by-one via tiny-aya, optionally generates
    TTS audio for all translations via OmniVoice (voice design mode), and
    yields progressive card updates so cards appear incrementally.
    """
    global _phase1_texts

    if not _phase1_texts:
        from frontend.ui.cards import generate_progress_html
        yield generate_progress_html(0, "⚠️ Please generate text first."), (
            '<div style="color:#c44; padding:20px;">'
            'No Phase 1 text found. Generate English text first, then click "Generate Cards".'
            '</div>'
        )
        return

    # Save Phase 1 texts for this generation pass. Keep _phase1_texts intact so
    # the user can change language and regenerate media without re-generating text.
    _current_texts = list(_phase1_texts)

    try:
        from core.engine import EnginePool
        from core.types import CEFRLevel, EngineConfig
        from frontend.ui.cards import generate_progress_html, generate_cards_html

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
            '<code>python tests/smoke_test.py</code>'
            '</div>'
        )
        return

    yield generate_progress_html(10, "Preparing translation engine..."), ""

    # Get the translation engine (lazy-loads tiny-aya)
    try:
        from core.engine import LlamaCppTextEngine
        translation_engine = pool.get_translation_engine()
    except Exception as e:
        logger.error("Phase 2 failed to get translation engine: %s", e, exc_info=True)
        err_detail = str(e)
        yield generate_progress_html(0, f"\u26a0\ufe0f Engine error: {err_detail}"), (
            '<div style="color:#c44; padding:20px;">'
            f'<strong>Failed to initialize translation engine.</strong><br>'
            f'{err_detail}<br><br>'
            'Check <code>configs/settings.yaml</code> for the model path.'
            '</div>'
        )
        return

    # Build cards one-by-one — each sentence translated individually
    cards: list[dict] = []
    total = len(_phase1_texts)

    for i, english_text in enumerate(_current_texts):
        try:
            translation = translation_engine._translate_single(
                english_text, cefr,
                topic_description=scenario,
                target_language=target_language,
            )
        except Exception as e:
            logger.error("Translation failed for sentence %d: %s", i, e, exc_info=True)
            # Fallback: use English text as translation
            translation = english_text

        cards.append({
            "text": english_text,
            "translation": translation,
            "cefr_level": cefr,
            "topic_description": scenario,
        })

        pct, label = _progress_pct(i, total, start_pct=15.0, end_pct=70.0)
        yield generate_progress_html(pct, label), generate_cards_html(
            cards, include_image=include_images, include_audio=include_audio, placeholder_back=False
        )

    # Generate TTS audio for all translations if requested
    image_paths: list[str | None] = [None] * len(cards)
    tts_generated = False
    if include_audio and cards:
        yield generate_progress_html(70, "Generating audio..."), generate_cards_html(
            cards, include_image=include_images, include_audio=True, placeholder_back=False
        )
        try:
            from core.audio_gen import TTSEngine
            tts_engine = pool.get_tts_engine()
            output_dir = Path(config.models_dir) / "output" / "audio"
            translations_list = [c["translation"] for c in cards]
            audio_result = tts_engine.synthesize(translations_list, output_dir, language=target_language, instruct=voice)
            audio_paths = audio_result.audio_paths

            # Attach audio paths to cards
            for i, path in enumerate(audio_paths):
                if path is not None:
                    cards[i]["audio_path"] = path
            tts_generated = True
        except Exception as e:
            logger.error("TTS generation failed: %s", e, exc_info=True)
            # Cards remain without audio — user can retry
            tts_generated = False

    # Generate images for all translations if requested
    if include_images and cards:
        yield generate_progress_html(85, "Generating images..."), generate_cards_html(
            cards, include_image=True, include_audio=tts_generated, placeholder_back=False
        )
        try:
            from core.image_gen import ImageGenEngine
            img_engine = pool.get_image_engine()
            output_dir = Path(config.models_dir) / "output" / "images"
            # Build prompts from English text + CEFR level
            prompts = []
            for card in cards:
                prompt = (
                    f"Simple educational illustration with NO TEXT for language learning for the following text: {card['text']}. "
                )
                prompts.append(prompt)
            image_result = img_engine.generate(prompts, output_dir)
            image_paths = image_result.image_paths
            # Attach image paths to cards
            for i, path in enumerate(image_paths):
                if path is not None:
                    cards[i]["image_path"] = path
        except Exception as e:
            logger.error("Image generation failed: %s", e, exc_info=True)
            # Cards remain without images — user can retry

    # Final yield with 100%
    if not cards:
        yield generate_progress_html(0, "\u26a0\ufe0f No translations produced."), (
            '<div style="color:#c44; padding:20px;">'
            '<strong>Translation failed.</strong><br>No translations were produced. '
            'Check the terminal for error details.'
            '</div>'
        )
    else:
        if include_images:
            if tts_generated:
                final_label = "Translation, audio, and images complete!"
            else:
                final_label = "Translation and images complete!"
        else:
            final_label = "Translation and audio complete!" if tts_generated else "Translation complete!"
        # Always include generated media regardless of toggle state so previously
        # generated audio/images remain accessible after toggling off/on.
        yield generate_progress_html(100, final_label), generate_cards_html(
            cards, include_image=include_images, include_audio=tts_generated, placeholder_back=False
        )


if __name__ == "__main__":
    from frontend.ui.widgets import build_ui

    css_path = os.path.join(os.path.dirname(__file__), "frontend", "css", "custom.css")
    with open(css_path, "r") as f:
        css_content = f.read()

    # Register the project root as a static directory so generated audio/images are accessible
    # inside gr.HTML output via /gradio_api/file=<relative-path> URLs.
    project_root = Path(__file__).resolve().parent
    import gradio as gr
    gr.set_static_paths(paths=[project_root])

    app = build_ui()
    app.launch(
        server_name="0.0.0.0",
        server_port=7860,
        css=css_content,
    )
```

**Key changes from the original:**
1. Removed all Gradio widget creation (`with gr.Blocks() as demo:` block) — moved to `widgets.build_ui()`
2. Removed `_VOICE_MAP` — moved to `widgets.py`
3. Removed event handler functions (`_handle_text_generation`, `_enable_phase2`, etc.) — moved to `widgets.py`
4. Removed top-level imports of `gradio as gr`, `CardData`, `CEFRLevel`, etc. — these are now imported inside the business logic functions where needed (lazy import avoids circular deps)
5. Updated error messages to reference `tests/smoke_test.py` instead of `scripts/smoke_test.py`
6. The `__main__` block is ~10 lines: load CSS, set static paths, call `build_ui()`, launch

- [ ] **Step 2: Verify syntax**

Run: `python -c "import ast; ast.parse(open('app.py').read()); print('Syntax OK')"`
Expected: `Syntax OK`

- [ ] **Step 3: Verify imports work (business logic only)**

Run: `python -c "from app import generate_text_async, generate_media_async, _progress_pct, _phase1_texts; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add app.py
git commit -m "refactor: extract Gradio UI construction to widgets.build_ui()"
```

---

## Task 6: Rename `scripts/` → `tests/`, Rename Files, Move `download_models.py`

**Files:**
- Create (rename): `tests/smoke_test.py` (from `scripts/smoke_test.py`)
- Create (rename): `tests/count_enforcement_test.py` (from `scripts/test_count_enforcement.py`)
- Create (rename): `tests/extract_sentences_test.py` (from `scripts/test_extract_sentences.py`)
- Create (rename): `tests/progression_test.py` (from `scripts/test_progression.py`)
- Create (rename): `tests/translation_retry_test.py` (from `scripts/test_translation_retry.py`)
- Move: `models/download_models.py` already exists — verify it's the same as `scripts/download_models.py`
- Delete: `scripts/` directory entirely

- [ ] **Step 1: Verify models/download_models.py already exists**

Run: `ls -la /home/takosaga/Projects/EuropaLex/models/download_models.py`
Expected: File exists (the spec says it's already in `models/`)

If `scripts/download_models.py` and `models/download_models.py` both exist, compare them:
Run: `diff scripts/download_models.py models/download_models.py`
If they differ, use the version from `scripts/` as source of truth. If identical or `models/` version is newer, just remove `scripts/download_models.py`.

- [ ] **Step 2: Rename scripts/ → tests/ with new naming**

Run these commands in order:

```bash
# Create tests directory
mkdir -p tests

# Rename files (test_ prefix → *_test suffix)
mv scripts/smoke_test.py tests/smoke_test.py
mv scripts/test_count_enforcement.py tests/count_enforcement_test.py
mv scripts/test_extract_sentences.py tests/extract_sentences_test.py
mv scripts/test_progression.py tests/progression_test.py
mv scripts/test_translation_retry.py tests/translation_retry_test.py

# Remove download_models.py from scripts (already in models/)
rm scripts/download_models.py

# Remove empty scripts directory
rmdir scripts
```

- [ ] **Step 3: Update import paths in test files**

Each test file has `sys.path.insert(0, str(Path(__file__).resolve().parent.parent))` which points to the project root. This remains correct since `tests/` is at the same level as the old `scripts/`. No path changes needed.

However, update the smoke test to reference the new paths:
In `tests/smoke_test.py`, verify the import for `app` module works (no change needed — it imports `import app` which is a top-level module).

- [ ] **Step 4: Verify all test files exist**

Run: `ls -la tests/`
Expected: 5 files: `count_enforcement_test.py`, `extract_sentences_test.py`, `progression_test.py`, `smoke_test.py`, `translation_retry_test.py`

- [ ] **Step 5: Commit**

```bash
git add tests/
git rm -r scripts/
git commit -m "refactor: rename scripts/ to tests/ with pytest-compatible naming"
```

---

## Task 7: Delete Stale `core/test_text_engine.py`

**Files:**
- Delete: `core/test_text_engine.py`

- [ ] **Step 1: Verify the file tests a deprecated class**

Run: `head -5 core/test_text_engine.py`
Expected output shows it imports `TextEngine` which was replaced by `MiniCPMTextEngine`/`LlamaCppTextEngine`.

- [ ] **Step 2: Delete the file**

```bash
rm core/test_text_engine.py
git rm core/test_text_engine.py
```

- [ ] **Step 3: Commit**

```bash
git commit -m "test: remove stale test_text_engine.py (tests deprecated TextEngine class)"
```

---

## Task 8: Add Pytest Configuration

**Files:**
- Create: `pyproject.toml`

- [ ] **Step 1: Write pyproject.toml**

Check if `pyproject.toml` already exists at project root:
Run: `cat pyproject.toml 2>/dev/null || echo "NOT FOUND"`

If it exists, append the pytest config section. If not, create it:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = "*_test.py"
```

If `pyproject.toml` already has other sections (e.g., `[project]` for uv), just add the `[tool.pytest.ini_options]` section to the existing file. Do not overwrite existing content.

- [ ] **Step 2: Verify pytest discovers tests**

Run: `python -m pytest tests/ --collect-only -q 2>&1 | head -20`
Expected: Lists all 5 test files with their test functions (may show import errors for missing dependencies — that's expected, we just need discovery to work)

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml
git commit -m "test: add pytest configuration for tests/ directory"
```

---

## Task 9: Update Error Messages in app.py to Reference `tests/`

**Files:**
- Modify: `app.py`

- [ ] **Step 1: Verify error messages reference the new path**

In the refactored `app.py`, all error messages that previously said `scripts/smoke_test.py` should now say `tests/smoke_test.py`. This was already done in Task 5's file content, but verify:

Run: `grep -n "smoke_test" app.py`
Expected: All references show `tests/smoke_test.py`

- [ ] **Step 2: Commit** (if any changes needed)

```bash
git add app.py
git commit -m "fix: update smoke test path references from scripts/ to tests/"
```

---

## Task 10: Update README.md — Module Structure and Test Instructions

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update the Repository Structure diagram**

Find the existing structure block (around line 183) that shows `scripts/` and update it to show `tests/`:

Replace this section:
```
└── scripts/                # Utility scripts
    └── smoke_test.py       # Quick sanity check script
```

With:
```
├── tests/                  # Test suite (pytest-discoverable)
│   ├── smoke_test.py       # Integration test — module imports, app construction
│   ├── count_enforcement_test.py  # TextResult.validate_and_parse() testing
│   ├── extract_sentences_test.py  # core.text_gen.extract_sentences() testing
│   ├── progression_test.py      # _progress_pct() helper testing
│   └── translation_retry_test.py# LlamaCppTextEngine retry loop testing
```

- [ ] **Step 2: Update the Running Smoke Tests section**

Replace:
```bash
uv run python scripts/smoke_test.py
```
With:
```bash
uv run python tests/smoke_test.py
```

- [ ] **Step 3: Update the Architecture section — engine classes**

In the "Inference" bullet under Data Flow, update the description of TTSEngine and ImageGenEngine to reference their new locations:

Change `core/engine.py` → `core/audio_gen.py` for TTSEngine and `core/image_gen.py` for ImageGenEngine in the documentation text. Specifically, find:
```
  - `TTSEngine` — OmniVoice Python package with lazy-load/unload cycle...
  - `ImageGenEngine` — diffusers Flux2KleinPipeline with lazy-load/unload cycle...
```

And update to reference the new files if they're mentioned as being in `engine.py`.

- [ ] **Step 4: Verify**

Run: `grep -n "scripts/" README.md`
Expected: No remaining references to `scripts/` (except possibly in old plan/doc references which are out of scope)

- [ ] **Step 5: Commit**

```bash
git add README.md
git commit -m "docs: update README module structure and test paths for refactor"
```

---

## Task 11: Update AGENTS.md — EnginePool Table, Import Conventions, Testing Section

**Files:**
- Modify: `AGENTS.md`

- [ ] **Step 1: Update EnginePool table in engine.py section**

Find the "Five concrete engine classes" table and update it to reflect the new file locations:

Replace:
```
| `TTSEngine` | omnivoice (PyTorch) | Lazy-load on first `.synthesize()`, unload after completion. ... |
| `ImageGenEngine` | diffusers Flux2KleinPipeline (PyTorch) | Lazy-load on first `.generate()`, unload after completion. ... |
```

With references to their new files:
```
| `TTSEngine` | `core/audio_gen.py` | omnivoice (PyTorch) | Lazy-load on first `.synthesize()`... |
| `ImageGenEngine` | `core/image_gen.py` | diffusers Flux2KleinPipeline (PyTorch) | Lazy-load on first `.generate()`... |
```

- [ ] **Step 2: Update import conventions**

In the "Import Conventions" table, update references from `scripts/` to `tests/`:

Find all occurrences of `scripts/` and replace:
- `scripts/smoke_test.py` → `tests/smoke_test.py`
- `scripts/test_translation_retry.py` → `tests/translation_retry_test.py`
- `scripts/test_count_enforcement.py` → `tests/count_enforcement_test.py`

Run to find them all:
```bash
grep -n "scripts/" AGENTS.md
```

Update each one individually using the edit tool.

- [ ] **Step 3: Update testing section**

In the "Testing Expectations" section, update:
- `python scripts/smoke_test.py` → `python tests/smoke_test.py` (appears multiple times)
- `scripts/test_translation_retry.py` → `tests/translation_retry_test.py`
- `scripts/test_count_enforcement.py` → `tests/count_enforcement_test.py`

In the "Adding New Features" checklist, update:
- `python scripts/smoke_test.py` → `python tests/smoke_test.py`

In the "Before Merging" section, update:
- `python scripts/smoke_test.py` → `python tests/smoke_test.py`

- [ ] **Step 4: Verify**

Run: `grep -n "scripts/" AGENTS.md`
Expected: No remaining references to `scripts/` in the active documentation

- [ ] **Step 5: Commit**

```bash
git add AGENTS.md
git commit -m "docs: update AGENTS.md engine locations and test paths"
```

---

## Task 12: Final Smoke Test — Verify Everything Works End-to-End

**Files:**
- Run: `tests/smoke_test.py`

- [ ] **Step 1: Run the smoke test**

Run: `uv run python tests/smoke_test.py`
Expected: All 9 checks pass with ✓ marks and "✅ All smoke tests passed!"

If it fails, debug each failure:
- Import failures → check that engine.py still exports TTSEngine/ImageGenEngine (they should via the re-export imports from Task 3)
- App module load failure → may need to verify `build_ui()` doesn't have circular import issues

- [ ] **Step 2: Verify all individual tests run**

```bash
uv run python tests/count_enforcement_test.py
uv run python tests/extract_sentences_test.py
uv run python tests/progression_test.py
uv run python tests/translation_retry_test.py
```
Expected: Each runs without traceback (may show import errors for missing optional deps — that's fine)

- [ ] **Step 3: Verify Gradio app constructs**

Run: `python -c "from frontend.ui.widgets import build_ui; print('build_ui imported OK')"`
Expected: `build_ui imported OK`

Note: Calling `build_ui()` will try to import from `app`, which imports from `frontend.ui.cards`. This should work as long as no circular deps exist.

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "test: verify all smoke tests pass after refactor"
```

---

## Circular Import Analysis (Critical)

The refactoring creates a cross-module dependency: `widgets.py` needs business logic from `app.py`, but `app.py`'s `__main__` imports from `widgets.py`. This must be handled carefully:

**Why this works:**
1. `app.py` does NOT import from `widgets.py` at module level — only inside `if __name__ == "__main__":` block
2. `widgets.py` imports from `app` INSIDE `build_ui()` body (not at module level)
3. Import chain when running `python app.py`:
   - Python loads `app.py` → defines functions, sets `_phase1_texts`, does NOT run `__main__` block
   - `__main__` runs → imports `build_ui` from widgets → triggers `widgets.py` module load
   - `widgets.py` module load → defines functions, does NOT call `build_ui()` yet
   - Back in `app.py __main__` → calls `build_ui()` → NOW imports from app (already loaded) → safe

**Key rule:** No module-level import from widgets to app. All cross-module imports must be inside function bodies.

---

## Self-Review Checklist

**Spec coverage:**
1. ✅ `core/audio_gen.py` — Task 1
2. ✅ `core/image_gen.py` — Task 2
3. ✅ `core/engine.py` updated (TTSEngine/ImageGenEngine removed, re-exported) — Task 3
4. ✅ `frontend/ui/widgets.py` expanded with `build_ui()`, `_VOICE_MAP`, state helpers — Task 4
5. ✅ `app.py` rewritten: business logic only, thin `__main__` — Task 5
6. ✅ `scripts/` → `tests/`, file renaming, download_models moved — Task 6
7. ✅ `core/test_text_engine.py` deleted — Task 7
8. ✅ pytest config added — Task 8
9. ✅ README.md updated — Task 10
10. ✅ AGENTS.md updated — Task 11
11. ✅ Smoke test verification — Task 12

**Placeholder scan:**
- All code blocks contain complete, copy-pasteable content
- No "TBD", "TODO", "implement later" markers found
- All file paths are exact and absolute
- All commands include expected output

**Type consistency:**
- `_VOICE_MAP` defined once in `widgets.py`, consumed by `_handle_media_generation_v2` via closure (imported at build_ui() call time)
- `_phase1_texts` defined once in `app.py`, imported by widgets inside `build_ui()` body — shared mutable state
- `TTSEngine` and `ImageGenEngine` re-exported from `core/engine.py` so existing imports (`from core.engine import TTSEngine`) continue to work — smoke test depends on this
- `_progress_pct`, `generate_text_async`, `generate_media_async` signatures unchanged

**Circular import guard:**
- app.py: NO import from widgets at module level (only in `__main__`)
- widgets.py: imports from app INSIDE `build_ui()` body (not at module level)
- Result: importing either module alone works; only calling `build_ui()` triggers cross-import (safe because app is already loaded by then)

---

## Execution Order Summary

Tasks must be executed sequentially (each commits before the next starts):

1. **Task 1** → create `core/audio_gen.py`
2. **Task 2** → create `core/image_gen.py`
3. **Task 3** → refactor `core/engine.py` (remove classes, add re-exports)
4. **Task 4** → expand `frontend/ui/widgets.py` with `build_ui()`
5. **Task 5** → rewrite `app.py` (business logic only)
6. **Task 6** → rename `scripts/` → `tests/`, file renames
7. **Task 7** → delete `core/test_text_engine.py`
8. **Task 8** → add `pyproject.toml` pytest config
9. **Task 9** → verify error message paths in app.py
10. **Task 10** → update README.md
11. **Task 11** → update AGENTS.md
12. **Task 12** → run smoke test, final verification
