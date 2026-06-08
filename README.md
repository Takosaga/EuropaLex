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
# or install from requirements.txt:
pip install -r requirements.txt
```

Run the app:

```bash
python app.py
```

### Model Weights

Models are downloaded from Hugging Face Hub at runtime (no git submodules):

```bash
# Download all models
python -m models.download_models

# Or download specific models
python -m models.download_models tilde-open omnivoice

# Custom output directory
python -m models.download_models --output-dir ./my-models
```

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
```

## CEFR Levels

`[A0, A1, A2, B1, B2, C1, C2]`

- **A0:** Uses curated common words list (no text generation model needed)
- **A1–C2:** TildeOpen generates target-language text at the selected level
