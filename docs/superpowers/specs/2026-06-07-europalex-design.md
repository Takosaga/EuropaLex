# EuropaLex — Design Document

**Date:** 2026-06-07
**Project:** Hugging Face Build Small Hackathon Entry
**Goal:** Generate Anki flashcards for European languages (starting with Latvian) using local AI models, with a custom-styled Gradio frontend.

---

## 1. Overview

EuropaLex generates language-learning flashcards at the push of a button. A user enters a scenario or topic (e.g., "ordering coffee"), selects a CEFR level and batch size, and receives cards containing:

- **Front:** target-language text
- **Back:** source-language translation
- **Media:** audio pronunciation + relevant image

Cards are exported as `.apkg` Anki packages or synced directly to local Anki via the anki-mcp-server tunnel.

### Hackathon Criteria Alignment

| Criterion | How EuropaLex Delivers |
|---|---|
| **Off-Brand** | Custom CSS overrides push past default Gradio look; styled card widgets that resemble physical flashcards |
| **Llama Champion** | Model runs through llama.cpp runtime locally |
| **Off the Grid** | No cloud APIs — all inference runs on local models or Modal-hosted endpoints |
| **Sharing is Caring** | Cards exportable as `.apkg`/`.csv`; card datasets shareable via Hugging Face Hub |

---

## 2. Architecture

Monorepo with one `pyproject.toml` at root, using `uv` as the dependency manager. Four layers communicate through well-defined interfaces:

### Layer 1 — Core (`core/`)
Shared library defining the data contract and inference abstraction. Contains type definitions, engine protocol, and pipeline orchestrator.

### Layer 2 — Model Submodules (`models/`)
Three git submodules, each wrapping one model with a consistent interface.

### Layer 3 — Frontend (`frontend/`)
Gradio app with custom CSS for an "off-brand" look. Thin `app.py` delegates to the core pipeline.

### Layer 4 — Export (`export/`)
Handles two paths: file export (`.apkg`/`.csv`) and tunnel sync to local Anki via anki-mcp-server.

**Deployment:** HF Spaces hosts the Gradio frontend → calls Modal HTTP endpoints for inference → cards exported locally or synced via tunnel.

---

## 3. Components & Data Flow

### Frontend (`frontend/`)

- **`app.py`** — Thin entry point. Creates `gr.Blocks()` with custom CSS. Three UI sections:
  1. Input panel (scenario/topic text + CEFR level dropdown + batch size slider)
  2. Progress display (pipeline status per card)
  3. Card gallery (styled card widgets showing front/back text, play audio button, image display)

- **`ui/widgets.py`** — Custom Gradio component wrappers. Card widget renders front text on top half, back text below with audio/image media embedded. Styled via CSS overrides to look like physical flashcards.

- **`css/custom.css`** — Overrides Gradio's default theme: card-like containers with shadows/borders, custom typography for language text, styled audio player, image frame styling.

### Core (`core/`)

- **`types.py`** — Dataclasses:
  ```python
  @dataclass
  class Card:
      front_text: str          # Target-language text
      back_text: str           # Source-language translation
      cefr_level: CEFRLevel    # A0, A1, A2, B1, B2, C1, C2
      audio_path: str | None   # Path to generated audio file
      image_path: str | None   # Path to generated image file

  @dataclass
  class CardBatch:
      cards: list[Card]
  ```

- **`engine.py`** — `InferenceEngine` protocol with methods:
  - `generate_text(prompt: str, cefr_level: str) -> str`
  - `synthesize_speech(text: str) -> bytes`
  - `generate_image(prompt: str) -> bytes`

  Two implementations:
  - **`LocalInference`** — Uses `llama-cpp-python` directly (local dev).
  - **`ModalInference`** — HTTP POST to Modal endpoints (HF Spaces production).

- **`pipeline.py`** — Orchestrator. Takes topic + CEFR level + batch size:
  1. Stage 1 (Text): Calls text generation for all cards in parallel
  2. Stage 2 (Audio): Passes texts to TTS in parallel
  3. Stage 3 (Image): Passes prompts to image gen in parallel
  4. Returns `CardBatch`

### Model Submodules (`models/`)

Each submodule follows the same pattern:
- One Python file with a single public function
- Loads its model from `.local/models/` on first call
- Returns raw output wrapped into `core/types.py` dataclasses

| Submodule | Model | Purpose |
|---|---|---|
| `models/tilde-open/` | TildeOpen-30b | Generate target-language text at specified CEFR level |
| `models/omnivoice/` | OmniVoice | Synthesize speech audio from text |
| `models/flux/` | FLUX.2-klein-4B | Generate illustrative images for cards |

### Export (`export/`)

- **`apkg_generator.py`** — Creates `.apkg` (Anki package) files. Each card becomes a note with front/back fields + media attachments.
- **`csv_export.py`** — Simple CSV fallback: `front_text,back_text,audio_path,image_path`.
- **`anki_tunnel.py`** — Connects via anki-mcp-server tunnel protocol. Pushes cards directly into local Anki when `ankimcp --tunnel` is running. Falls back to file export if tunnel unavailable.

### Data Flow (one generation)

```
User input: "ordering coffee" + B1 + 3 cards
       │
       ▼
frontend/app.py ──calls──► core/pipeline.py
       │                          │
       │                  [Stage 1: Text] models/tilde-open/ → 3 card texts
       │                  [Stage 2: Audio] models/omnivoice/ → 3 audio files
       │                  [Stage 3: Image] models/flux/ → 3 images
       │                          │
       │                  returns CardBatch[3]
       │                          │
frontend/app.py ◄──displays── Card widgets (front/back/audio/image)
       │
       ▼
User clicks "Export" ──► export/apkg_generator.py → .apkg download
User clicks "Sync to Anki" ──► export/anki_tunnel.py → tunnel sync
```

---

## 4. A0 Special Path (Common Words)

A0 is a distinct learning path that does **not** call TildeOpen at all:

1. `core/pipeline.py` checks the CEFR level first. If A0, it loads a curated JSON file (`configs/common_words/{language}.json`) containing the top 100 most common words in the target language (e.g., Latvian).
2. Each card uses one word from this list, with a simple example sentence template filled in around it.
3. TTS and image gen proceed normally on those words/sentences.

This means A0 skips Stage 1 (text generation) entirely — faster generation, no model needed for text.

---

## 5. Error Handling & Resilience

### Pipeline resilience
- **Per-card retry:** If one card fails in any stage, it's retried once with a fallback response. Other cards continue processing independently.
- **Stage-level error isolation:** Text generation failure doesn't block TTS on texts that succeeded. Image gen failures show a placeholder rather than breaking the card.
- **Graceful degradation:** Tunnel unavailable → export still offers `.apkg`/`.csv`. Modal endpoints down → clear error message to retry later.

### Model submodule errors
Each model catches its own runtime errors (loading failures, inference timeouts) and raises a consistent `ModelError`. The core engine surfaces these through the pipeline's progress display — no silent failures.

### Configuration validation
- CEFR level must be one of `[A0, A1, A2, B1, B2, C1, C2]`.
- Batch size defaults to 3, clamped between 1–10.
- Invalid values show inline Gradio errors before the pipeline starts — no wasted inference time.

### Local vs. Remote mode detection
- `ENV=production` (set in HF Spaces) → `ModalInference`.
- Otherwise → `LocalInference` (llama.cpp runtime).
- Missing model files in `.local/models/` show a clear README-linked setup message.

---

## 6. Testing

### Core library tests (`core/`)
- **`types.py`:** Dataclass field validation — `CEFRLevel` accepts only valid values, `Card` requires at least front/back text.
- **`engine.py`:** Mock-based tests for both `LocalInference` and `ModalInference`. Verify protocol contract satisfaction. Test mode auto-detection logic.
- **`pipeline.py`:** Integration test with mocked model submodules. Given 3 card texts, verify TTS and image gen are called in the right order with correct inputs. Verify A0 path skips text generation and reads from `configs/common_words/`.

### Model submodule tests (`models/`)
Each submodule gets a minimal test: does its public function return output that can be wrapped into a `core/types.py` dataclass? No actual model inference — just verify the interface contract.

### Frontend tests (`frontend/`)
- **`app.py`:** Verify Gradio blocks are constructed correctly (components exist, CSS is loaded).
- **`ui/widgets.py`:** Test that card widgets render front/back text and media references correctly.

### Export tests (`export/`)
- **`apkg_generator.py`:** Generate a test `.apkg`, unzip it, verify the note structure matches Anki's expected format (front/back fields, media in `media/` folder).
- **`csv_export.py`:** Verify CSV output is valid and parseable with correct headers.
- **`anki_tunnel.py`:** Mock the tunnel connection — test that cards are pushed correctly when connected, and fallback to export path when disconnected.

### Integration smoke test
A single end-to-end script (`scripts/smoke_test.py`) that runs the full pipeline with mock models (no actual inference) and verifies: input → pipeline → CardBatch → export file. Fast, deterministic, no GPU needed.

---

## 7. Dependency Management

- **Single source of truth:** `pyproject.toml` at root.
- **Dependency manager:** `uv` for local development (fast installs, reproducible).
- **HF Spaces:** Reads from `pyproject.toml` directly (Spaces supports `uv` natively).

---

## 8. Model List (referenced in README.md)

The following models will be used but are not downloaded as part of the repo setup:

| Model | HF Hub | Purpose |
|---|---|---|
| **Nemotron-3-Nano-30B-A3B-GGUF** | [unsloth/Nemotron-3-Nano-30B-A3B-GGUF](https://huggingface.co/unsloth/Nemotron-3-Nano-30B-A3B-GGUF) | General inference via llama.cpp runtime |
| **TildeOpen-30b** | [TildeAI/TildeOpen-30b](https://huggingface.co/TildeAI/TildeOpen-30b) | Generate target-language text at CEFR levels for Anki cards |
| **OmniVoice** | [k2-fsa/OmniVoice](https://huggingface.co/k2-fsa/OmniVoice) | Text-to-speech for card audio |
| **FLUX.2-klein-4B** | [black-forest-labs/FLUX.2-klein-4B](https://huggingface.co/black-forest-labs/FLUX.2-klein-4B) | Generate illustrative images for Anki cards |

---

## 9. Repository Structure

```
EuropaLex/
├── pyproject.toml          # Optional - uv export here
│   # Or export with: uv export > requirements.txt
├── requirements.txt        # ← REQUIRED for pip install
├── app.py                  # ← REQUIRED entry point (or main.py)
├── core/                   # Your shared modules
│   ├── __init__.py         # Python package marker
│   ├── engine.py           # InferenceEngine protocol + implementations
│   ├── pipeline.py         # Batch generator: text → audio → image
│   └── types.py            # Card, CardData, CEFRLevel dataclasses
├── frontend/               # Gradio UI code inside app.py
│   ├── __init__.py
│   ├── css/custom.css      # Custom card styling
│   └── ui/                 # Widget and card components
├── models/                 # ← Use HF Hub URLs instead of submodules!
│   ├── __init__.py
│   └── download_models.py  # Script to fetch from HF Hub at runtime
├── configs/                # Settings, word lists
│   └── settings.yaml
├── export/                 # .apkg generator
│   ├── __init__.py
│   ├── apkg_generator.py
│   ├── csv_export.py
│   └── anki_tunnel.py
└── README.md               # Documentation
`
```

---

## 10. Key Design Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Frontend approach | Styled Gradio with custom CSS | Hackathon-feasible while achieving "Off-Brand" goal |
| Submodule boundary | Each model as a submodule | Clean per-model boundaries, easy to swap models later |
| Communication between submodules | Shared dataclasses via core lib | Type-safe interfaces without service overhead |
| Repo layout | Monorepo with submodules | Clean boundaries without excessive repo management |
| Dependency management | pyproject.toml (uv-native) | Single source of truth, HF Spaces uses requirements.txt |
| A0 path | Curated common words list | Skips text generation model entirely, faster for beginners |
| Anki integration | Hybrid: export + tunnel | Works for everyone (export) AND power users (tunnel sync) |
| Local vs. remote | Auto-detect via ENV var | Same codebase works locally (llama.cpp) and on Spaces (Modal) |
| CEFR levels | User-selectable, one per generation | Simple UX, focused learning output per request |
| Batch size | Default 3 cards, adjustable | Manageable for hackathon demo, easy to scale later |

---
