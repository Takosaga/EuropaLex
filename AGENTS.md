# Europa Lex — AI Agent Conventions

**Working directory:** All paths, commands, and file references below are relative to the `EuropaLex/` project root. Assume you are already inside this directory — do not `cd` into or out of it.

Guidelines for AI coding agents working on this codebase. Follow these conventions to produce changes that integrate cleanly.

## Project Overview

EuropaLex generates Anki-compatible flashcards for European languages using local AI models. It takes user input (text or scenario description), generates target-language translations at a selected CEFR level, and enriches cards with text-to-speech audio and illustrative images. Cards export as `.apkg` or `.csv`.

**Tech Stack:**
- Python 3.12+
- Gradio 6 (frontend UI)
- Pydantic >=2.0.0 (type-safe data models)
- llama-cpp-python (text generation: MiniCPM5-1B Q8_0, GGUF format)
- llama-cpp-python (translation: tiny-aya-water Q4_K_M, GGUF format)
- omnivoice (PyPI package, lazy-load/unload via EnginePool)
- diffusers >=0.28.0 (image gen: FLUX.2-klein 4B, lazy-load/unload via EnginePool)
- torch >=2.1.0 (PyTorch backend for TTS and image generation)
- soundfile >=0.12.0 (WAV audio I/O for TTS output)
- uv (dependency management), Hugging Face Hub (model weights)

**Models:**
| Model | Repo | Runtime | Role |
|---|---|---|---|
| MiniCPM5-1B Q8_0 | [Abiray/MiniCPM5-1B-GGUF](https://huggingface.co/Abiray/MiniCPM5-1B-GGUF) | llama-cpp-python | English text generation (Phase 1) |
| tiny-aya-water Q4_K_M | [CohereLabs/tiny-aya-water-GGUF](https://huggingface.co/CohereLabs/tiny-aya-water-GGUF) | llama-cpp-python | Translation (active) |
| TildeOpen-30b Q4_K_S ⚠️ | [bartowski/TildeAI_TildeOpen-30b-GGUF](https://huggingface.co/bartowski/TildeAI_TildeOpen-30b-GGUF) | llama-cli | Translation (available, not active) |
| OmniVoice Q8_0 | [Serveurperso/OmniVoice-GGUF](https://huggingface.co/Serveurperso/OmniVoice-GGUF) | omnivoice.cpp | Text-to-speech |
| FLUX.2-klein 4B Q4_K_M | [unsloth/FLUX.2-klein-4B-GGUF](https://huggingface.co/unsloth/FLUX.2-klein-4B-GGUF) | ComfyUI-GGUF / diffusers | Image generation |

> ⚠️ TildeOpen is still downloaded and available but not the active translation model. See `configs/settings.yaml` to switch back.

**Architecture at a glance:**
- `core/` — Pydantic types (`types.py`), inference engines + EnginePool singleton (`engine.py`), sentence extraction & generation helpers (`text_gen.py`), Phase 2 translation orchestration (`pipeline.py`)
- `frontend/` — Gradio UI: widgets, card rendering, custom CSS
- `models/` — HF Hub model downloader
- `export/` — .apkg generator, CSV export, Anki tunnel sync
- `app.py` — entry point, wires everything together (Phase 1 generates English text via MiniCPM; Phase 2 translates via tiny-aya)

## Code Structure

### Module Boundaries

| Module | Do | Don't |
|---|---|---|
| `core/` | Define types, implement inference protocols, Phase 2 translation orchestration (`pipeline.py`) | Import from `frontend/` or `export/` |
| `core/text_gen.py` | Sentence extraction (`extract_sentences`) and LLM generation with retry loop (`generate_sentences`) | Import from other modules for text generation logic |
| `frontend/` | Render UI, handle Gradio events, style cards | Implement inference logic or export formats |
| `models/` | Download and locate models | Run inference or generate content |
| `export/` | Generate .apkg, .csv, communicate with Anki tunnel | Import from `frontend/` |
| `app.py` | Wire modules together, define Gradio click handlers | Contain business logic (delegate to `core/`) |

### File Organization Rules

1. **One responsibility per file.** `cards.py` renders cards. `widgets.py` creates form controls. `pipeline.py` is the Phase 2 translation orchestration layer — extend it when adding new media types (TTS, images).
2. **`__init__.py` files are minimal.** Just package markers — no imports, no logic.
3. **UI components live in `frontend/ui/`.** Not in `app.py`. If a widget or renderer grows beyond ~100 lines, consider whether it needs its own file.
4. **CSS lives in `frontend/css/custom.css`.** Inline styles are acceptable in card HTML (for portability when rendered as strings), but theme-level rules go in the CSS file.
5. **Config lives in `configs/settings.yaml`.** Hard-coded values belong here, not scattered across modules.

### Import Conventions

- Use absolute imports from project root: `from core.types import CardData`
- Import Gradio as `import gradio as gr` (not `from gradio import ...`)
- Never import from `frontend/` in `core/`, `models/`, or `export/` — the frontend depends on everything, not vice versa

## Code Conventions

### Naming

- **Modules (lowercase, underscore):** `apkg_generator`, `anki_tunnel`, `download_models`
- **Classes (PascalCase):** `CardData`, `CEFRLevel`, `MiniCPMTextEngine`, `LlamaCppTextEngine`, `TTSEngine`, `ImageGenEngine`, `EnginePool`, `ValidationError`
- **Functions/variables (snake_case):** `render_card_html`, `generate_cards_html`, `batch_size`
- **Constants (UPPER_SNAKE_CASE):** None currently needed; keep config in YAML

### Style

- Type hints on all public functions. Private/helper functions may omit if trivially obvious.
- Docstrings: one-line summary + args/returns for multi-arg functions. See `frontend/ui/widgets.py:create_toggle()` as the template.
- No trailing whitespace. 4-space indentation (standard Python).
- Max line length: 100 characters. Break function calls and long strings.

### Data Flow Through the App

```
User input → app.py click handler → EnginePool.get(config) → MiniCPMTextEngine (Phase 1) → pipeline.generate_phase2() → LlamaCppTextEngine (translation, Phase 2) → TTSEngine (TTS audio, Phase 2) → frontend/ui/cards.py rendering → Gradio output
```

When adding a new feature, follow this chain. Phase 1 uses `MiniCPMTextEngine` directly; Phase 2 translation goes through `pipeline.generate_phase2()`.

**EnginePool singleton:** Manages mutual exclusion between all GPU engines: `MiniCPMTextEngine` (~1.1 GB RAM), `LlamaCppTextEngine` (translation, ~2 GB VRAM), `TTSEngine` (TTS), and `ImageGenEngine` (images). Only one can be loaded at a time.

## Frontend Patterns

### Gradio Widget Creation

Use the wrapper functions in `frontend/ui/widgets.py`. Example:

```python
from frontend.ui.widgets import create_toggle, create_voice_dropdown

images_toggle = create_toggle("🖼️ Images", value=True, elem_id="toggle-images")
audio_toggle = create_toggle("🔊 Audio", value=False, elem_id="toggle-audio")
voice_dropdown = create_voice_dropdown()  # hidden until audio toggle is ON
```

The `elem_id` follows the pattern: `toggle-<label-without-emoji>` for toggles; `voice-dropdown` for the voice selector. This is used for CSS targeting and two-phase disabled state management.

### Card Rendering

All card HTML goes through `frontend/ui/cards.py`:

- `render_card_html(card_data, include_image, include_audio, rotation, placeholder_back)` — single card
- `generate_cards_html(cards, include_image, include_audio, placeholder_back)` — full gallery

**Rules:**
- Never construct card HTML inline in `app.py`. Always call these functions.
- The `rotation` parameter creates the "spread on desk" visual effect. Use the rotation distribution logic from `generate_cards_html()` — don't hard-code angles.
- **Card layout:** Translation (target language) on front, English on back (after Phase 2). During Phase 1 (`placeholder_back=True`), English is on front with a dashed placeholder back.
- **Media placement:** Image 🖼️ and audio ▶ controls render as separate `.media-box` containers inside a `.media-boxes-row` flex column on the front side alongside the translation (not on the back).
- `placeholder_back=True` shows a dashed placeholder line instead of translation text (used during Phase 1 before translations are generated).

### Two-Phase Generation Workflow

The UI operates in two distinct phases:

**Phase 1 — Generate English Text:**
1. User clicks "Generate Text"
2. `app.py` calls the text generation handler → MiniCPM5-1B (`MiniCPMTextEngine`, llama-cpp-python, lazy-load/unload) generates English sentences from the scenario
3. Cards render with English on the front, placeholder back (dashed line)
4. After completion, `_enable_phase2()` removes disabled CSS and enables toggles + "Generate Cards" button

**Phase 2 — Generate Translation + Media:**
1. User selects a target language from the **Target Language** dropdown (defaults to Latvian)
2. After Phase 1 completes, the **Images** and **Audio** toggles become active (unchecked by default)
3. User toggles Images/Audio on/off; if Audio is ON, a hidden **Voice** dropdown becomes visible with 6 voice presets (gender × age)
4. User clicks "Generate Cards"
5. `app.py` calls the media generation handler → tiny-aya-water (`LlamaCppTextEngine`) translates, then OmniVoice (`TTSEngine`) generates TTS audio with the selected voice via voice design mode
6. Cards update: translation appears on the front, image and audio controls appear alongside it; English text moves to the back
6. Both buttons hide during generation, reappear when done

**Rules:**
- Never skip Phase 1. Even if media-only mode seems useful, text must be generated first.
- When user changes input parameters (scenario, CEFR level, batch size, target language), call `_reset_to_idle()` to restore disabled states and hidden buttons.
- The disabled state uses CSS class `europalex-btn-disabled` and inline styles with `#phase-css` ID. Don't remove these — they're tied to the two-phase state machine.

### Progress Tracking

Use `frontend/ui/cards.py:generate_progress_html(percent, phase_label)`. The function handles:
- Color transitions (brown → dark brown at 100%)
- Width animation via inline CSS
- Phase label text ("Generating text..." vs "Generating media...")

Return empty string (`""`) when `percent <= 0` — Gradio will hide the element.

## Core Module Rules

### types.py

The canonical data shapes — **all Pydantic models**, not dataclasses. If you add a new field to `CardData` or `CEFRLevel`, update it here first and propagate changes everywhere that consumes these types.

```python
# Template — match this structure (Pydantic BaseModel):
class CardData(BaseModel):
    text: str              # English source text
    translation: str       # Target-language translation (empty during Phase 1)
    audio_path: str | None = None   # Path to generated TTS audio (.wav)
    image_path: str | None = None   # Path to generated illustration (.png)
    cefr_level: CEFRLevel = CEFRLevel.B1  # Proficiency level
```

Other Pydantic models:
- `CEFRLevel(str, Enum)` — A0 through C2 proficiency levels
- `ValidationError(RuntimeError)` — `{raw_output: str | None}` structured error for LLM output validation failures (carries raw model output)
- `TextResult` — `{generated_texts: list[str] = Field(default_factory=list)}` from text generation; use classmethod `validate_and_parse(raw_text, expected_count=N)` to strip `<thinking>` tags and enforce count in one call
- `AudioResult` — `{audio_paths: list[str | None] = Field(default_factory=list)}` from TTS (individual failures tracked as `None`)
- `ImageResult` — `{image_paths: list[str | None] = Field(default_factory=list)}` from image generation (individual failures tracked as `None`)
- `EngineConfig(BaseModel)` — validated config from `configs/settings.yaml`

### engine.py

Five concrete engine classes replace the legacy `InferenceEngine` protocol:

| Class | Backend | Lifecycle |
|---|---|---|
| `MiniCPMTextEngine` | llama-cpp-python (GGUF) | Lazy-load on first `.generate()`, unload after completion (~1.1 GB RAM). Uses `apply_chat_template`. Validates output sentence count against `batch_size`; retries with stricter prompts on mismatch (max 3 attempts). Used in Phase 1 for English text generation. |
| `LlamaCppTextEngine` | llama-cpp-python (GGUF) | Lazy-load on first `.generate()`, unload after completion (~2 GB VRAM). Validates output line count against `batch_size`; retries with stricter prompts on mismatch (max 3 attempts). Used in Phase 2 for translation. |
| `TTSEngine` | omnivoice (PyTorch) | Lazy-load on first `.synthesize()`, unload after completion. Accepts `instruct` parameter for voice design mode (defaults to `"female, young adult"`). Used in Phase 2 for TTS audio. |
| `ImageGenEngine` | diffusers Flux2KleinPipeline (PyTorch) | Lazy-load on first `.generate()`, unload after completion. Image generation toggle is available but not yet wired into the pipeline. |
| `EnginePool` | Singleton factory | Manages mutual exclusion between all GPU engines. Phase 1 uses only `MiniCPMTextEngine` (~1.1 GB RAM). Phase 2 loads GPU engines sequentially: translation → TTS/images. |

**Rules:**
- All inference goes through `EnginePool.get(config)` — never instantiate engines directly in app code.
- All engines (MiniCPMTextEngine, LlamaCppTextEngine, TTSEngine, ImageGenEngine) are lazy-loaded and unloaded via `del` + `torch.cuda.empty_cache()`.
- Each engine class should be self-contained. Don't share state between implementations.

**MiniCPMTextEngine validation:** `generate()` wraps the LLM call in a retry loop (max 3 attempts). Each attempt uses `TextResult.validate_and_parse(raw_text, expected_count=batch_size)` as its validation gate — stripping `<thinking>` tags, splitting lines, and enforcing exact count in one call. On mismatch, `_build_retry_prompt()` constructs a stricter prompt referencing the actual vs expected count, appended as a new user message in the same conversation context. On exhaustion, raises `ValidationError` with `raw_output` attached for debugging. Do not bypass this loop — it is the contract enforcement layer between LLM output and `TextResult`.

**LlamaCppTextEngine validation:** `generate()` wraps the LLM call in a retry loop (max 3 attempts). If output line count does not match `batch_size`, `_build_retry_prompt()` constructs a stricter prompt referencing actual vs expected count. On exhaustion with zero lines, raises `ValidationError` with `raw_output`; on exhaustion with partial lines, returns whatever was produced. Do not bypass this loop.

### pipeline.py

Phase 2 translation orchestration layer. Provides `generate_phase2()` as a generator function that yields `(progress_percent, phase_label, cards)` tuples.

**Rules:**
- Extend this file when adding new media types (TTS, images). The pipeline is the single point of parallelism control.
- All Phase 2 translation logic flows through `generate_phase2()` — do not duplicate engine calls in `app.py`.
- Uses generator functions (`yield`) for streaming progress updates — Gradio consumes generators for real-time UI updates.

## Testing Expectations

### Smoke Tests

Run `tests/smoke_test.py` before committing. It performs a quick sanity check: imports all modules, validates dataclasses, and checks that the Gradio app can be constructed without errors.

```bash
python tests/smoke_test.py
```

Expected output: clean exit (no traceback). If it fails, something is broken at the module level.

### Mock Data

The frontend can render cards from mock data (no model inference needed). When testing UI changes:
- Use `frontend/ui/cards.py:render_card_html()` directly with a dict like `{"text": "Hello", "translation": "Sveiki"}`
- The card renderer handles missing fields gracefully — `translation` defaults to empty string, `audio_path`/`image_path` are ignored in HTML rendering.

### Inline Tests for Engine Retry Logic

For engine classes with retry loops, add inline tests that mock the LLM and verify count validation. See `tests/translation_retry_test.py` as an example — it tests `LlamaCppTextEngine.generate()` retry logic (exact count, short output, exhausted retries, empty output) without requiring a running model.

### Inline Tests

For new modules with non-trivial logic, add a test script in `tests/` guarded by `if __name__ == "__main__":`. See `tests/count_enforcement_test.py` as an example — it tests `TextResult.validate_and_parse()` (thinking-tag stripping, line-count enforcement) and retry-prompt logic without requiring model inference.

### No Unit Test Framework Required (Yet)

The project currently uses smoke tests and inline tests. If you add a new module with non-trivial logic (>30 lines of business logic), consider adding inline assertions or a simple test function at the bottom of the file guarded by `if __name__ == "__main__":`.

## Adding New Features

Use this checklist when extending EuropaLex:

1. **Identify the module** — Where does the feature belong? (See Code Structure table.)
2. **Define types first** — If the feature introduces new data, add it to `core/types.py`.
3. **Implement core logic** — In `core/` or the appropriate module. Follow the protocol pattern from `engine.py`.
4. **Wire up the UI** — Add widgets in `frontend/ui/widgets.py`, renderers in `frontend/ui/cards.py`. Update `app.py` click handlers last.
5. **Update CSS if needed** — New visual elements go in `frontend/css/custom.css`. Keep inline styles only for card-level dynamic properties (rotation, conditional display).
6. **Test with smoke test** — Run `python tests/smoke_test.py`.
7. **Commit** — One logical change per commit. Message format: `type: brief description` (e.g., `feat: add Japanese language support`, `fix: card rotation overflow`).

## Git Workflow

### Commit Conventions

Use [Conventional Commits](https://www.conventionalcommits.org/) prefix:
- `feat:` — new feature
- `fix:` — bug fix
- `docs:` — documentation only
- `style:` — formatting, no code change
- `refactor:` — code restructuring, no behavior change
- `test:` — test-related changes

### Branch Strategy

- Work on feature branches: `feat/<feature-name>` (e.g., `feat/gradio_frontend`, `feat/japanese-support`)
- Keep main clean — only merge when a feature is complete and tested.
- Commit frequently within branches (every 2-5 minutes of work).

### Before Merging

1. Run `python tests/smoke_test.py` — must pass
2. Verify the Gradio app starts: `python app.py` — must launch without errors on port 7860
3. Check that all new code follows the conventions in this document

## Known Pitfalls

### 1. Don't inline card HTML in app.py

Card rendering belongs in `frontend/ui/cards.py`. If you find yourself building `<div>` strings in `app.py`, move them to a function in `cards.py` or `widgets.py`.

### 2. Two-phase state machine is fragile

The disabled/enabled toggle states are managed via CSS injection (`#phase-css`) and Gradio element re-rendering. If you add new phase-dependent controls, remember to:
- Give them an `elem_id` for targeting
- Include them in `_reset_to_idle()` outputs (including `language_dropdown` which triggers reset on change)
- Include them in `_enable_phase2()` outputs

### 3. Gradio generator functions must yield tuples

When a click handler produces multiple outputs (e.g., progress bar + card gallery), it must be a generator that yields tuples matching the output order:

```python
def my_handler(...):
    # ... work ...
    yield progress_html, cards_html
```

If you forget `yield`, Gradio will not update the UI.

### 4. CSS specificity wars with Gradio

Gradio's default styles use `!important` heavily. Our `custom.css` also uses `!important` to override them. If a style isn't taking effect:
- Check if Gradio re-renders the element (re-rendered elements may get new inline styles)
- Increase specificity or add another `!important`
- Use `elem_id` targeting instead of class selectors when possible

### 5. Model paths are runtime-resolved

Models live in a configurable directory (default: `.local/models/`, see `configs/settings.yaml`). Never hard-code model file paths. Always resolve paths via the settings config or `models/download_models.py`. Each model has its own runtime engine — don't assume llama-cli can run all GGUF files.

### 6. Clear `_phase1_texts` between Phase 2 calls

`_phase1_texts` is a module-level global that persists across `generate_media_async()` calls. Without resetting it, Gradio's HTML output retains old cards (with stale audio paths) while new cards are appended, causing mixed-language output. Always save the texts first, then clear the global:

```python
_current_texts = list(_phase1_texts)
_phase1_texts = []
# ... use _current_texts for processing ...
```

### 7. Voice dropdown visibility is phase-dependent

The voice dropdown starts hidden (`visible = False`) and only becomes visible when the Audio toggle is ON (via `_enable_language_dropdown_on_audio`). It must be included in `_reset_to_idle()` outputs alongside toggles and buttons, and its `elem_id` must be targeted by disabled CSS. Do not assume it's always visible.

### 8. LLM output may not match expected count

Both `MiniCPMTextEngine.generate()` and `LlamaCppTextEngine.generate()` validate output count against `batch_size` and retry automatically (max 3 attempts). Do **not** slice output with `[:batch_size]` as a band-aid — the engines already handle this via retry loops. If you bypass an engine and call an LLM directly, you must implement the same validation logic.
