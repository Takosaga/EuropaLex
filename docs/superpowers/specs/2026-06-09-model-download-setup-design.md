# Model Download & Configuration Setup

**Date:** 2026-06-09
**Status:** Approved

## Overview

Set up downloading four AI models from Hugging Face and configuring them for EuropaLex's use with `llama-cli` (text generation), `omnivoice.cpp` (TTS), and `ComfyUI-GGUF`/`diffusers` (image generation). All models are in GGUF format but require different runtimes.

## Models

| Model | Repo | File(s) | Runtime | Size |
|-------|------|---------|---------|------|
| Nemotron-3-Nano-30B-A3B | `bartowski/nvidia_Nemotron-3-Nano-30B-A3B-GGUF` | `Nemotron-3-Nano-30B-A3B-IQ4_XS.gguf` | llama-cli | 18.1 GB |
| TildeOpen-30b | `bartowski/TildeAI_TildeOpen-30b-GGUF` | `TildeAI_TildeOpen-30b-Q4_K_S.gguf` | llama-cli | 17.6 GB |
| OmniVoice (TTS) | `Serveurperso/OmniVoice-GGUF` | `omnivoice-base-Q8_0.gguf`, `omnivoice-tokenizer-Q8_0.gguf` | omnivoice.cpp | ~945 MB total |
| FLUX.2-klein-4B (images) | `unsloth/FLUX.2-klein-4B-GGUF` | `flux-2-klein-4b-Q4_K_M.gguf` | ComfyUI-GGUF / diffusers | ~2.6 GB |

## Changes

### 1. Update `models/download_models.py`

Replace the current stub definitions with four real model entries:

```python
MODELS = {
    "nemotron": {
        "repo": "bartowski/nvidia_Nemotron-3-Nano-30B-A3B-GGUF",
        "files": ["Nemotron-3-Nano-30B-A3B-IQ4_XS.gguf"],
        "description": "Nemotron-3-Nano 30B-A3B IQ4_XS text generation",
    },
    "tildeopen": {
        "repo": "bartowski/TildeAI_TildeOpen-30b-GGUF",
        "files": ["TildeAI_TildeOpen-30b-Q4_K_S.gguf"],
        "description": "TildeOpen-30b Q4_K_S translation model",
    },
    "omnivoice": {
        "repo": "Serveurperso/OmniVoice-GGUF",
        "files": ["omnivoice-base-Q8_0.gguf", "omnivoice-tokenizer-Q8_0.gguf"],
        "description": "OmniVoice Q8_0 TTS (base + tokenizer)",
    },
    "flux": {
        "repo": "unsloth/FLUX.2-klein-4B-GGUF",
        "files": ["flux-2-klein-4b-Q4_K_M.gguf"],
        "description": "FLUX.2-klein 4B Q4_K_M image generation",
    },
}
```

Each entry includes repo ID, exact files to download, description, and runtime notes. Download uses `huggingface-hub snapshot_download` (or `huggingface-cli` fallback).

### 2. Populate `configs/settings.yaml`

Add model configuration section:

```yaml
models:
  directory: .local/models
  nemotron:
    repo: bartowski/nvidia_Nemotron-3-Nano-30B-A3B-GGUF
    file: Nemotron-3-Nano-30B-A3B-IQ4_XS.gguf
    runtime: llama-cli
    quant: IQ4_XS
  tildeopen:
    repo: bartowski/TildeAI_TildeOpen-30b-GGUF
    file: TildeAI_TildeOpen-30b-Q4_K_S.gguf
    runtime: llama-cli
    quant: Q4_K_S
  omnivoice:
    repo: Serveurperso/OmniVoice-GGUF
    files:
      - omnivoice-base-Q8_0.gguf
      - omnivoice-tokenizer-Q8_0.gguf
    runtime: omnivoice.cpp
    quant: Q8_0
  flux:
    repo: unsloth/FLUX.2-klein-4B-GGUF
    file: flux-2-klein-4b-Q4_K_M.gguf
    runtime: ComfyUI-GGUF
    quant: Q4_K_M
```

### 3. Runtime Engine Registry (future-proofing)

Add a small helper that maps engine names to their CLI commands and expected model paths — this will make wiring `core/engine.py` later straightforward.

## In Scope

- Update download script with correct repos/files
- Populate settings.yaml with model configuration
- No inference code changes

## Out of Scope

- Implementing `core/engine.py`
- Implementing `core/pipeline.py`
- Updating app.py handlers
