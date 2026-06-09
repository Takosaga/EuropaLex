# EuropaLex — AI Agent Conventions

Guidelines for AI coding agents working on this codebase. Follow these conventions to produce changes that integrate cleanly.

## Project Overview

EuropaLex generates Anki-compatible flashcards for European languages using local AI models. It takes user input (text or scenario description), generates target-language translations at a selected CEFR level, and enriches cards with text-to-speech audio and illustrative images. Cards export as `.apkg` or `.csv`.

**Tech Stack:**
- Python 3.12+
- Gradio 6 (frontend UI)
- llama.cpp runtime (via `InferenceEngine` protocol)
- TildeOpen (translation model, CEFR-aware text generation)
- OmniVoice (text-to-speech)
- FLUX.2-klein-4B (image generation)
- uv (dependency management), Hugging Face Hub (model weights)

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
- `placeholder_back=True` shows a dashed placeholder line instead of translation text (used during Phase 1 before translations are generated).

### Two-Phase Generation Workflow

The UI operates in two distinct phases:

**Phase 1 — Generate Text:**
1. User clicks "Generate Text"
2. `app.py` calls the text generation handler → TildeOpen produces English + translation
3. Cards render with text but media toggles are disabled (CSS opacity + pointer-events)
4. After completion, `_enable_phase2()` removes disabled CSS and enables toggles + "Generate Cards" button

**Phase 2 — Generate Media:**
1. User toggles Images/Audio on/off
2. User clicks "Generate Cards"
3. `app.py` calls the media generation handler → OmniVoice (TTS) + FLUX.2 (images) fill in media
4. Both buttons hide during generation, reappear when done

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
