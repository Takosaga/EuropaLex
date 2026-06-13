# Europa Lex

AI-powered flashcard generator for European languages. Generates target-language translations, text-to-speech audio, and illustrative images — exports as a zipped CSV folder (with media files) or an Anki-compatible `.apkg` package.

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

### Running Tests

All tests use pytest. Run the full suite:

```bash
# Run all tests
uv run pytest tests/ -v

# Run specific test file
uv run pytest tests/cards_test.py -v

# Run with coverage
uv run pytest tests/ -v --cov=core --cov=frontend --cov=app.py
```

The test suite mocks all GPU/model code — no model weights or GPU required to run tests.

### Quick Smoke Check

For a quick sanity check before committing:

```bash
uv run pytest tests/smoke_test.py -v
```

This checks imports for core types, engine classes, frontend UI, and the app module. The Gradio app must construct without errors — all widgets are created inside a `gr.Blocks()` context and the context variable is returned (not a fresh empty `Blocks` instance). Generator event handlers use `yield (val1, val2)` not `yield from` to match output component counts.

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

**CSV export:** Click **Download CSV + Media** after Phase 2 completes. The app creates a `.zip` archive containing:
- `cards.csv` — columns: scenario, cefr_level, target_language, english_text, translated_text, audio_filename, image_filename
- Media files in a flat folder alongside the CSV (no subfolders)
- Folder naming: `{scenario_slug}_{CEFR}_{LANG_ABBREV}` (e.g., `ordering_coffee_A2_LV`)
- Media file naming: `{scenario_slug}_{CEFR}_{LANG_ABBREV}_{card_index}.{ext}` (e.g., `ordering_coffee_A2_LV_0.wav`, `ordering_coffee_A2_LV_1.png`)

**APKG export:** Click **Export Anki Cards** after Phase 2 completes. The app creates a proper `.apkg` Anki package using genanki with:
- Four note fields: Translation, English, Audio, Image
- HTML escaping for special characters in text content
- Media injection via MD5 hashing with deduplication
- Manifest file updated within the archive
- Cards import directly into Anki with media embedded

> **Note:** The "Sync to Anki" button has been removed. Use CSV export for all imports into Anki (Anki supports CSV import natively).

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

### Phase 2 — Generate Translation + Media

1. Select a target language from the **Target Language** dropdown (Latvian, Spanish, French, German, Polish, Italian, Portuguese, Finnish)
2. After Phase 1 completes, the **Images** and **Audio** toggles become active (unchecked by default)
3. Toggle on whichever media types you want (images, audio, or both)
4. Click **Generate Cards**
5. The app translates via tiny-aya-water (`LlamaCppTextEngine`) with retry validation
6. If Audio is toggled ON, TTS audio is generated via OmniVoice (`TTSEngine`) with voice design mode
7. If Images is toggled ON, images are generated via `ImageGenEngine` (diffusers Flux2KleinPipeline)
8. Cards update: translation moves to the front, English stays on the back; image and audio controls appear alongside translations

> **Regenerating Cards:** After Phase 2 completes, changing any parameter (target language, audio/image toggles, or voice) automatically restores the **Generate Cards** button so you can regenerate with new settings without re-running Phase 1.

### Export

1. Once Phase 2 completes, click **Export CSV + Media** to download a `.zip` file containing the CSV and all media files
2. Click **Export Anki Cards** to download an `.apkg` Anki package (compatible with Anki 24+)
3. Import the CSV into Anki via Anki's native CSV import feature, or open the `.apkg` directly

## Architecture

EuropaLex is organized into five main modules:

| Module | Purpose |
|---|---|
| `core/` | Data types (`types.py`), text engines + EnginePool (`engine.py`), TTS (`audio_gen.py`), image gen (`image_gen.py`), sentence extraction & generation helpers (`text_gen.py`), Phase 2 translation orchestration (`pipeline.py`) |
| `frontend/` | Gradio 6 UI: styled toggles (`widgets.py`), card rendering with two-phase layout (`cards.py`), custom CSS (`css/custom.css`) |
| `models/` | Hugging Face Hub model downloader — fetches models at runtime, no git submodules |
| `export/` | `.apkg` Anki package generator (genanki-based), CSV zip export with media files, Anki tunnel sync (unused) |
| `app.py` | Entry point — wires inputs to two-phase click handlers with progress tracking |

### Data Flow

```
User Input → [Gradio UI] → EnginePool (singleton) → MiniCPMTextEngine (Phase 1) → pipeline.generate_phase2() → LlamaCppTextEngine (translation, Phase 2) → TTSEngine (`core/audio_gen.py`, TTS audio, Phase 2) → Card Gallery → Export (.apkg / .csv)
```

- **Inference:** `core/engine.py` defines five engine classes:
  - `MiniCPMTextEngine` — llama-cpp-python wrapper for MiniCPM5-1B Q8_0 (lazy-load/unload, ~1.1 GB RAM, uses apply_chat_template). Uses `TextResult.validate_and_parse()` to strip `<thinking>` tags and enforce exact sentence count; retries with stricter prompts on mismatch (max 3 attempts). Used in Phase 1 for English text generation only.
  - `LlamaCppTextEngine` — llama-cpp-python wrapper for tiny-aya-water translation (lazy-load/unload, ~2 GB VRAM). Validates output line count against `batch_size`; retries with stricter prompts on mismatch (max 3 attempts). Used in Phase 2 for translation.
  - `TTSEngine` (`core/audio_gen.py`) — OmniVoice Python package with lazy-load/unload cycle. Supports voice design mode via `instruct` parameter (e.g., "female, young adult"). Used in Phase 2 for TTS audio.
  - `ImageGenEngine` (`core/image_gen.py`) — diffusers Flux2KleinPipeline with lazy-load/unload cycle (GPU memory managed by EnginePool). Image generation toggle is available but not yet wired into the pipeline.
  - `EnginePool` — singleton orchestrator enforcing mutual exclusion between all GPU engines. Phase 1 uses only `MiniCPMTextEngine` (~1.1 GB RAM). Phase 2 loads GPU engines sequentially: translation → TTS/images.
- **Types:** `core/types.py` provides Pydantic models (`CardData`, `CEFRLevel`, `ValidationError`, `TextResult`, `AudioResult`, `ImageResult`, `EngineConfig`) for type-safe boundaries. `TextResult.generated_texts` replaces the legacy `.translations`; `AudioResult.audio_paths` and `ImageResult.image_paths` are `list[str | None]` (never None at top level).
- **Pipeline:** `core/pipeline.py` provides `generate_phase2()` — a generator function that yields `(progress_percent, phase_label, cards)` tuples for real-time UI updates. Extends this when adding new media types (TTS, images).
- **Frontend:** `frontend/ui/cards.py` renders individual cards as HTML with conditional media elements; `generate_cards_html()` layouts them in a flex gallery with natural rotation offsets.
- **Export:** `export/apkg_generator.py` builds Anki `.apkg` packages with genanki, media injection via MD5 hashing and deduplication; `export/csv_export.py` creates zipped folders containing CSV + media files; `export/anki_tunnel.py` is unused.

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
│   ├── engine.py           # MiniCPMTextEngine, LlamaCppTextEngine, EnginePool
│   ├── audio_gen.py        # TTSEngine (OmniVoice)
│   └── image_gen.py        # ImageGenEngine (diffusers Flux2KleinPipeline)
│   ├── text_gen.py         # Sentence extraction (extract_sentences) and generation with retry loop (generate_sentences)
│   └── pipeline.py         # Phase 2 translation orchestration — generate_phase2() generator with progress tracking
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
│   ├── apkg_generator.py   # Anki .apkg package builder (genanki-based, media injection with MD5 deduplication)
│   ├── csv_export.py       # CSV export utility
│   └── anki_tunnel.py      # MCP tunnel sync for live Anki import
├── docs/                   # Design specs and implementation plans
│   └── superpowers/
│       ├── specs/          # Design specification documents
│       └── plans/          # Implementation plans
├── tests/                  # Test suite (pytest-discoverable)
│   ├── smoke_test.py       # Integration test — module imports, app construction
│   ├── count_enforcement_test.py  # TextResult.validate_and_parse() testing
│   ├── extract_sentences_test.py  # core.text_gen.extract_sentences() testing
│   ├── progression_test.py      # _progress_pct() helper testing
│   └── translation_retry_test.py# LlamaCppTextEngine retry loop testing
```

## CEFR Levels

`[A0, A1, A2, B1, B2, C1, C2]`

- **A0:** Uses curated common words list (no text generation model needed)
- **A1–C2:** MiniCPM5-1B generates English sentences at the selected level in Phase 1; tiny-aya-water translates them in Phase 2
