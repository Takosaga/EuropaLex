# Europa Lex — AI Agent Conventions

**Working directory:** All paths, commands, and file references below are relative to the `EuropaLex/` project root. Assume you are already inside this directory — do not `cd` into or out of it.

Guidelines for AI coding agents working on this codebase. Follow these conventions to produce changes that integrate cleanly.

## Project Overview

EuropaLex generates Anki-compatible flashcards for European languages using local AI models. It takes user input (text or scenario description), generates target-language translations at a selected CEFR level, and enriches cards with text-to-speech audio and illustrative images. Cards export as `.apkg` or `.csv`.

**Tech Stack:**
- Python 3.12+
- Gradio 6 (frontend UI)
- llama-cli (text generation: Nemotron-3-Nano + TildeOpen, GGUF format)
- omnivoice.cpp (TTS: OmniVoice Q8_0, GGUF format)
- ComfyUI-GGUF / diffusers (image gen: FLUX.2-klein 4B, GGUF format)
- uv (dependency management), Hugging Face Hub (model weights)

**Models:**
| Model | Repo | Runtime |
|---|---|---|
| Nemotron-3-Nano 30B-A3B IQ4_XS | [bartowski/nvidia_Nemotron-3-Nano-30B-A3B-GGUF](https://huggingface.co/bartowski/nvidia_Nemotron-3-Nano-30B-A3B-GGUF) | llama-cli |
| TildeOpen-30b Q4_K_S | [bartowski/TildeAI_TildeOpen-30b-GGUF](https://huggingface.co/bartowski/TildeAI_TildeOpen-30b-GGUF) | llama-cli |
| OmniVoice Q8_0 | [Serveurperso/OmniVoice-GGUF](https://huggingface.co/Serveurperso/OmniVoice-GGUF) | omnivoice.cpp |
| FLUX.2-klein 4B Q4_K_M | [unsloth/FLUX.2-klein-4B-GGUF](https://huggingface.co/unsloth/FLUX.2-klein-4B-GGUF) | ComfyUI-GGUF / diffusers |

**Architecture at a glance:**
- `core/` — types, inference engine, batch pipeline
- `frontend/` — Gradio UI: widgets, card rendering, custom CSS
- `models/` — HF Hub model downloader
- `export/` — .apkg generator, CSV export, Anki tunnel sync
- `app.py` — entry point, wires everything together

## Code Structure

### Module Boundaries

| Module | Do | Don't |
|---|---|---|
| `core/` | Define types, implement inference protocols, orchestrate batch pipelines | Import from `frontend/` or `export/` |
| `frontend/` | Render UI, handle Gradio events, style cards | Implement inference logic or export formats |
| `models/` | Download and locate models | Run inference or generate content |
| `export/` | Generate .apkg, .csv, communicate with Anki tunnel | Import from `frontend/` |
| `app.py` | Wire modules together, define Gradio click handlers | Contain business logic (delegate to `core/`) |

### File Organization Rules

1. **One responsibility per file.** `cards.py` renders cards. `widgets.py` creates form controls. `pipeline.py` orchestrates batching. Don't mix responsibilities.
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
- **Classes (PascalCase):** `InferenceEngine`, `CardData`, `CEFRLevel`, `LocalInference`
- **Functions/variables (snake_case):** `render_card_html`, `generate_cards_html`, `batch_size`
- **Constants (UPPER_SNAKE_CASE):** None currently needed; keep config in YAML

### Style

- Type hints on all public functions. Private/helper functions may omit if trivially obvious.
- Docstrings: one-line summary + args/returns for multi-arg functions. See `frontend/ui/widgets.py:create_toggle()` as the template.
- No trailing whitespace. 4-space indentation (standard Python).
- Max line length: 100 characters. Break function calls and long strings.

### Data Flow Through the App

```
User input → app.py click handler → core/engine.py inference → core/pipeline.py batching → frontend/ui/cards.py rendering → Gradio output
```

When adding a new feature, follow this chain. Don't bypass `pipeline.py` — even single-card generation should go through it for consistency.

## Frontend Patterns

### Gradio Widget Creation

Use the wrapper functions in `frontend/ui/widgets.py`. Example:

```python
from frontend.ui.widgets import create_toggle

images_toggle = create_toggle("🖼️ Images", value=True, elem_id="toggle-images")
audio_toggle = create_toggle("🔊 Audio", value=False, elem_id="toggle-audio")
```

The `elem_id` follows the pattern: `toggle-<label-without-emoji>`. This is used for CSS targeting and two-phase disabled state management.

### Card Rendering

All card HTML goes through `frontend/ui/cards.py`:

- `render_card_html(card_data, include_image, include_audio, rotation, placeholder_back)` — single card
- `generate_cards_html(cards, include_image, include_audio, placeholder_back)` — full gallery

**Rules:**
- Never construct card HTML inline in `app.py`. Always call these functions.
- The `rotation` parameter creates the "spread on desk" visual effect. Use the rotation distribution logic from `generate_cards_html()` — don't hard-code angles.
- **Card layout:** Translation (target language) on front, English on back (after Phase 2). During Phase 1 (`placeholder_back=True`), English is on front with a dashed placeholder back.
- **Media placement:** Image 🖼️ and audio ▶ controls render on the front side alongside the translation (not on the back).
- `placeholder_back=True` shows a dashed placeholder line instead of translation text (used during Phase 1 before translations are generated).

### Two-Phase Generation Workflow

The UI operates in two distinct phases:

**Phase 1 — Generate Text:**
1. User clicks "Generate Text"
2. `app.py` calls the text generation handler → TildeOpen produces English + translation
3. Cards render with English on the front, placeholder back (dashed line)
4. After completion, `_enable_phase2()` removes disabled CSS and enables toggles + "Generate Cards" button

**Phase 2 — Generate Media:**
1. User toggles Images/Audio on/off
2. User clicks "Generate Cards"
3. `app.py` calls the media generation handler → OmniVoice (TTS) + FLUX.2 (images) fill in media
4. Cards update: translation appears on the front, image and audio controls appear with it; English text moves to the back
5. Both buttons hide during generation, reappear when done

**Rules:**
- Never skip Phase 1. Even if media-only mode seems useful, text must be generated first.
- When user changes input parameters (scenario, CEFR level, batch size), call `_reset_to_idle()` to restore disabled states and hidden buttons.
- The disabled state uses CSS class `europalex-btn-disabled` and inline styles with `#phase-css` ID. Don't remove these — they're tied to the two-phase state machine.

### Progress Tracking

Use `frontend/ui/cards.py:generate_progress_html(percent, phase_label)`. The function handles:
- Color transitions (brown → dark brown at 100%)
- Width animation via inline CSS
- Phase label text ("Generating text..." vs "Generating media...")

Return empty string (`""`) when `percent <= 0` — Gradio will hide the element.

## Core Module Rules

### types.py

The canonical data shapes. If you add a new field to `CardData` or `CEFRLevel`, update it here first and propagate changes everywhere that consumes these types.

```python
# Template — match this structure:
@dataclass
class CardData:
    text: str              # English source text
    translation: str       # Target-language translation (empty during Phase 1)
    audio_path: str | None = None   # Path to generated TTS audio
    image_path: str | None = None   # Path to generated illustration
```

### engine.py

The `InferenceEngine` protocol defines the interface. Implementations wrap different backends (local llama.cpp vs Modal-hosted). **Rules:**
- Never bypass the protocol — all inference goes through `InferenceEngine.generate()` or equivalent.
- Each implementation should be self-contained. Don't share state between `LocalInference` and `ModalInference`.

### pipeline.py

The batch orchestrator. It receives a list of texts and produces batches of (text, audio, image) outputs based on toggle state. **Rules:**
- Pipeline is the single point of parallelism control. If adding new media types, add them here first.
- Use generator functions (`yield`) for streaming progress updates — Gradio consumes generators for real-time UI updates.

## Testing Expectations

### Smoke Tests

Run `scripts/smoke_test.py` before committing. It performs a quick sanity check: imports all modules, validates dataclasses, and checks that the Gradio app can be constructed without errors.

```bash
python scripts/smoke_test.py
```

Expected output: clean exit (no traceback). If it fails, something is broken at the module level.

### Mock Data

The frontend can render cards from mock data (no model inference needed). When testing UI changes:
- Use `frontend/ui/cards.py:render_card_html()` directly with a dict like `{"text": "Hello", "translation": "Sveiki"}`
- The card renderer handles missing fields gracefully — `translation` defaults to empty string, `audio_path`/`image_path` are ignored in HTML rendering.

### No Unit Test Framework Required (Yet)

The project currently uses smoke tests only. If you add a new module with non-trivial logic (>30 lines of business logic), consider adding inline assertions or a simple test function at the bottom of the file guarded by `if __name__ == "__main__":`.

## Adding New Features

Use this checklist when extending EuropaLex:

1. **Identify the module** — Where does the feature belong? (See Code Structure table.)
2. **Define types first** — If the feature introduces new data, add it to `core/types.py`.
3. **Implement core logic** — In `core/` or the appropriate module. Follow the protocol pattern from `engine.py`.
4. **Wire up the UI** — Add widgets in `frontend/ui/widgets.py`, renderers in `frontend/ui/cards.py`. Update `app.py` click handlers last.
5. **Update CSS if needed** — New visual elements go in `frontend/css/custom.css`. Keep inline styles only for card-level dynamic properties (rotation, conditional display).
6. **Test with smoke test** — Run `python scripts/smoke_test.py`.
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

1. Run `python scripts/smoke_test.py` — must pass
2. Verify the Gradio app starts: `python app.py` — must launch without errors on port 7860
3. Check that all new code follows the conventions in this document

## Known Pitfalls

### 1. Don't inline card HTML in app.py

Card rendering belongs in `frontend/ui/cards.py`. If you find yourself building `<div>` strings in `app.py`, move them to a function in `cards.py` or `widgets.py`.

### 2. Two-phase state machine is fragile

The disabled/enabled toggle states are managed via CSS injection (`#phase-css`) and Gradio element re-rendering. If you add new phase-dependent controls, remember to:
- Give them an `elem_id` for targeting
- Include them in `_reset_to_idle()` outputs
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
