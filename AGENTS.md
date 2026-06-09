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
