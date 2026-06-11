# Europa Lex

AI-powered flashcard generator for European languages. Generates target-language translations, text-to-speech audio, and illustrative images — exports directly as Anki decks (`.apkg`) or CSV.

> **Note:** All commands and paths in this document are relative to the `EuropaLex/` project root. Assume you are already inside this directory.

## Hackathon Criteria

- **Off-Brand** — Custom CSS pushes past the default Gradio look; styled card widgets resembling physical flashcards
- **Llama Champion** — Model runs through llama.cpp runtime locally
- **Off the Grid** — No cloud APIs, all inference on local models or Modal-hosted endpoints
- **Sharing is Caring** — Cards exportable as `.apkg`/`.csv`; card datasets shareable via Hugging Face Hub

## Setup

### Local Development

Requires [uv](https://github.com/astral-sh/uv):

```bash
uv sync
# or install from requirements.txt:
pip install -r requirements.txt
```

Run the app:

```bash
uv run app.py
```

> **Dependencies:** This project requires PyTorch, diffusers, omnivoice, pydantic, and soundfile in addition to Gradio. These are installed automatically by `uv sync`.

### Running Smoke Tests

Before committing, verify all modules load correctly:

```bash
uv run python scripts/smoke_test.py
```

This checks imports for core types, engine classes, frontend UI, and the app module.

### Model Weights

All models are GGUF format, downloaded from Hugging Face Hub at runtime (no git submodules). Each model uses a different runtime:

```bash
# Download all models
uv run python -m models.download_models

# Or download specific models
uv run python -m models.download_models minicpm tiny_aya  # Text generation + translation (~3.2 GB)
uv run python -m models.download_models omnivoice           # TTS only (~945 MB)
uv run python -m models.download_models flux                # Image gen only (~2.6 GB)

# Custom output directory
uv run python -m models.download_models --output-dir ./my-models
```

| Model | HF Hub Repo | GGUF File | Runtime | Size | Role |
|---|---|---|---|---|---|
| MiniCPM5-1B Q8_0 | [Abiray/MiniCPM5-1B-GGUF](https://huggingface.co/Abiray/MiniCPM5-1B-GGUF) | `minicpm5-1b-Q8_0.gguf` | llama-cpp-python | ~1.1 GB | English text generation (Phase 1) |
| tiny-aya-water q4_k_m | [CohereLabs/tiny-aya-water-GGUF](https://huggingface.co/CohereLabs/tiny-aya-water-GGUF) | `tiny-aya-water-q4_k_m.gguf` | llama-cpp-python | ~2 GB | Translation (active) |
| TildeOpen-30b Q4_K_S ⚠️ | [bartowski/TildeAI_TildeOpen-30b-GGUF](https://huggingface.co/bartowski/TildeAI_TildeOpen-30b-GGUF) | `TildeAI_TildeOpen-30b-Q4_K_S.gguf` | llama-cli | 17.6 GB | Translation (available, not active) |
| OmniVoice Q8_0 (base + tokenizer) | [Serveurperso/OmniVoice-GGUF](https://huggingface.co/Serveurperso/OmniVoice-GGUF) | `omnivoice-base-Q8_0.gguf` + `omnivoice-tokenizer-Q8_0.gguf` | omnivoice.cpp | ~945 MB | Text-to-speech |
| FLUX.2-klein 4B Q4_K_M | [unsloth/FLUX.2-klein-4B-GGUF](https://huggingface.co/unsloth/FLUX.2-klein-4B-GGUF) | `flux-2-klein-4b-Q4_K_M.gguf` | ComfyUI-GGUF / diffusers | ~2.6 GB | Image generation |

> **Note:** Models use different runtimes:
> - **llama-cpp-python** for MiniCPM5-1B (English text generation) — lazy-load/unload via Python bindings (~1.1 GB RAM)
> - **llama-cpp-python** for tiny-aya-water (translation) — lazy-load/unload via Python bindings (~2 GB VRAM)
> - **omnivoice.cpp** for OmniVoice — text-to-speech (C++/GGML port)
> - **ComfyUI-GGUF / diffusers** for FLUX.2 — image generation (diffusion model)
>
> ⚠️ TildeOpen is still downloaded and available but not the active translation model. See `configs/settings.yaml` to switch back.

### Anki Integration

**Export path (everyone):** Download `.apkg` or `.csv` files from the Gradio UI.

**Tunnel sync (power users):** Run `npx @ankimcp/anki-mcp-server --tunnel` locally, then use the "Sync to Anki" button in the app.

## Workflow

EuropaLex generates flashcards in two phases: English text first (Phase 1), then translation + media (Phase 2).

### Phase 1 — Generate English Text

1. Enter a scenario or paste text in the input box
2. Select a CEFR level (`A0`–`C2`) from the dropdown
3. Set the batch size with the slider (number of cards to generate)
4. Click **Generate Text**
5. The app generates English sentences via MiniCPM5-1B (`MiniCPMTextEngine`, llama-cpp-python, lazy-load/unload)
6. Cards appear in the gallery with English text on the front and a placeholder on the back

> **Note:** Translation is deferred to Phase 2. Phase 1 produces English-only cards.

### Phase 2 — Generate Translation + Media (deferred)

1. After Phase 1 completes, the **Images** and **Audio** toggles become active
2. Toggle on whichever media types you want (images, audio, or both)
3. Click **Generate Cards**
4. The app translates via tiny-aya-water (`LlamaCppTextEngine`), then calls OmniVoice for TTS and FLUX.2 for images
5. Cards update: translation moves to the front, English stays on the back; image and audio controls appear on the front side

> **Note:** Phase 2 is currently deferred — the UI shows mock data until translation + media integration is complete.

### Export

1. Once cards are generated, click **Export to Anki** (`.apkg`) or **Export as CSV**
2. For power users: run `npx @ankimcp/anki-mcp-server --tunnel` locally and use the Sync to Anki button in the app

## Architecture

EuropaLex is organized into five main modules:

| Module | Purpose |
|---|---|
| `core/` | Data types (`types.py`), inference engine protocol + implementations (`engine.py`), batch pipeline orchestrator (`pipeline.py`) |
| `frontend/` | Gradio 6 UI: styled toggles (`widgets.py`), card rendering with two-phase layout (`cards.py`), custom CSS (`css/custom.css`) |
| `models/` | Hugging Face Hub model downloader — fetches models at runtime, no git submodules |
| `export/` | `.apkg` Anki package generator, CSV export, Anki tunnel sync via MCP server |
| `app.py` | Entry point — wires inputs to two-phase click handlers with progress tracking |

### Data Flow

```
User Input → [Gradio UI] → EnginePool (singleton) → MiniCPMTextEngine/TTS/ImageGen → Card Gallery → Export (.apkg / .csv)
```

- **Inference:** `core/engine.py` defines five engine classes:
  - `MiniCPMTextEngine` — llama-cpp-python wrapper for MiniCPM5-1B Q8_0 (lazy-load/unload, ~1.1 GB RAM, uses apply_chat_template). Validates output sentence count against `batch_size`; retries with stricter prompts on mismatch (max 3 attempts). Used in Phase 1 for English text generation only.
  - `LlamaCppTextEngine` — llama-cpp-python wrapper for tiny-aya-water translation (lazy-load/unload, ~2 GB VRAM). Used in Phase 2 for translation.
  - `TTSEngine` — OmniVoice Python package with lazy-load/unload cycle (GPU memory managed by EnginePool). Used in Phase 2 for TTS audio.
  - `ImageGenEngine` — diffusers Flux2KleinPipeline with lazy-load/unload cycle (GPU memory managed by EnginePool). Used in Phase 2 for images.
  - `EnginePool` — singleton orchestrator enforcing mutual exclusion between all GPU engines. Phase 1 uses only `MiniCPMTextEngine` (~1.1 GB RAM). Phase 2 loads GPU engines sequentially: translation → TTS/images.
- **Types:** `core/types.py` provides Pydantic models (`CardData`, `CEFRLevel`, `TextResult`, `AudioResult`, `ImageResult`, `EngineConfig`) for type-safe boundaries.
- **Pipeline:** `core/pipeline.py` orchestrates batch generation — text first, then audio and images in parallel based on toggle state.
- **Frontend:** `frontend/ui/cards.py` renders individual cards as HTML with conditional media elements; `generate_cards_html()` layouts them in a flex gallery with natural rotation offsets.
- **Export:** `export/apkg_generator.py` builds Anki packages; `export/csv_export.py` writes tabular data; `export/anki_tunnel.py` communicates with the Anki MCP tunnel server.

## Repository Structure

```
EuropaLex/
├── app.py                  # Entry point — Gradio UI wiring, two-phase generation handlers
├── pyproject.toml          # Project config (uv)
├── requirements.txt        # pip install dependencies
├── uv.lock                 # uv lock file
├── .gitignore
├── README.md               # This file
├── AGENTS.md               # AI agent conventions guide
├── core/                   # Shared business logic
│   ├── __init__.py
│   ├── types.py            # Pydantic models: CardData, CEFRLevel, TextResult, AudioResult, ImageResult, EngineConfig
│   ├── engine.py           # MiniCPMTextEngine (MiniCPM5-1B/llama-cpp-python), LlamaCppTextEngine (tiny-aya/llama-cpp-python), TTSEngine (OmniVoice), ImageGenEngine (diffusers), EnginePool singleton
│   └── pipeline.py         # Batch generator: text → audio → image orchestrator
├── frontend/               # Gradio 6 UI
│   ├── __init__.py
│   ├── ui/
│   │   ├── __init__.py
│   │   ├── widgets.py      # Styled toggle checkbox wrappers
│   │   └── cards.py        # Card rendering, gallery layout, progress bar
│   └── css/
│       └── custom.css      # Plain-white theme, card styling, disabled states
├── models/                 # Model management
│   ├── __init__.py
│   └── download_models.py  # HF Hub model downloader (runtime)
├── configs/                # Configuration
│   └── settings.yaml       # App settings, word lists
├── export/                 # Export formats
│   ├── __init__.py
│   ├── apkg_generator.py   # Anki .apkg package builder
│   ├── csv_export.py       # CSV export utility
│   └── anki_tunnel.py      # MCP tunnel sync for live Anki import
├── docs/                   # Design specs and implementation plans
│   └── superpowers/
│       ├── specs/          # Design specification documents
│       └── plans/          # Implementation plans
└── scripts/                # Utility scripts
    └── smoke_test.py       # Quick sanity check script
```

## CEFR Levels

`[A0, A1, A2, B1, B2, C1, C2]`

- **A0:** Uses curated common words list (no text generation model needed)
- **A1–C2:** MiniCPM5-1B generates English sentences at the selected level in Phase 1; tiny-aya-water translates them in Phase 2 (deferred)
