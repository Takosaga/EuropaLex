# EuropaLex

Generate Anki flashcards for European languages using local AI models. Starting with Latvian, designed to support any language available through TildeOpen.

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
```

### Model Weights

Models are not included in this repo. Download them manually to `.local/models/`:

| Model | HF Hub | Purpose |
|---|---|---|
| Nemotron-3-Nano-30B-A3B-GGUF | [unsloth/Nemotron-3-Nano-30B-A3B-GGUF](https://huggingface.co/unsloth/Nemotron-3-Nano-30B-A3B-GGUF) | General inference via llama.cpp runtime |
| TildeOpen-30b | [TildeAI/TildeOpen-30b](https://huggingface.co/TildeAI/TildeOpen-30b) | Generate target-language text at CEFR levels |
| OmniVoice | [k2-fsa/OmniVoice](https://huggingface.co/k2-fsa/OmniVoice) | Text-to-speech for card audio |
| FLUX.2-klein-4B | [black-forest-labs/FLUX.2-klein-4B](https://huggingface.co/black-forest-labs/FLUX.2-klein-4B) | Generate illustrative images for cards |

### Anki Integration

**Export path (everyone):** Download `.apkg` or `.csv` files from the Gradio UI.

**Tunnel sync (power users):** Run `npx @ankimcp/anki-mcp-server --tunnel` locally, then use the "Sync to Anki" button in the app.

## Repository Structure

```
EuropaLex/
├── pyproject.toml          # uv dependency management
├── core/                   # Shared types, engine protocol, pipeline
├── models/                 # Git submodules (one per model)
│   ├── tilde-open/         # TildeOpen-30b text generation
│   ├── omnivoice/          # OmniVoice TTS
│   └── flux/               # FLUX.2-klein image generation
├── frontend/               # Gradio app with custom CSS
├── export/                 # .apkg generator, CSV export, tunnel sync
├── configs/                # Settings and common words lists (A0)
├── scripts/                # Utility scripts (smoke test)
└── .modal/                 # Modal deployment config
```

## CEFR Levels

`[A0, A1, A2, B1, B2, C1, C2]`

- **A0:** Uses curated common words list (no text generation model needed)
- **A1–C2:** TildeOpen generates target-language text at the selected level
