# HF Spaces Deployment Design

**Date:** 2026-07-04
**Status:** Approved
**Scope:** Setup code for deploying EuropaLex to Hugging Face Spaces with ZeroGPU. No Space is actually created in this cycle — just the deployment-ready code.

## Problem

EuropaLex currently targets local development via `uv sync`. It needs a deployment path that runs on Hugging Face Spaces using ZeroGPU, supporting all 4 models (MiniCPM5, tiny-aya, OmniVoice, FLUX).

## Approach: Conditional `@spaces.GPU` decorators in `app.py`

A conditional decorator pattern (`try/except ImportError`) makes `app.py` work unchanged locally and activate GPU management on ZeroGPU. Same file, two environments.

**Why not a separate `app_space.py`:** Two entry points to maintain creates drift risk. The conditional pattern adds ~20 lines and keeps one source of truth.

**Why not env-var toggle:** Adds config surface for what's really an environment detection question. Import-based detection is the established HF Spaces pattern (see spaces_testing reference).

## Changes (3 files)

### 1. `app.py` — Add ZeroGPU support (~20 lines)

**Top of file, after existing imports:**
```python
try:
    import spaces
    _HF_SPACES = True
    def gpu(fn): return spaces.GPU(duration=120)(fn)
except ImportError:
    _HF_SPACES = False
    def gpu(fn): return fn  # no-op locally
```

**Decorated functions:**
- `generate_text_async` — Phase 1 (MiniCPM5)
- Translation call inside `generate_media_async` — Phase 2 (tiny-aya)
- TTS call inside `generate_media_async` — Phase 2 (OmniVoice)
- Image gen call inside `generate_media_async` — Phase 2 (FLUX)

**Unchanged:** Gradio workarounds (BrotliMiddleware patch, FileResponse patch) stay — needed for HF's older Gradio version.

### 2. `requirements.txt` — Pre-compiled wheels for ZeroGPU

Replace the `uv export` generated file with hand-crafted entries using pre-compiled wheel indices:

```
--extra-index-url https://download.pytorch.org/whl/cu128
--extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cu124

spaces
torch==2.8.0
hf_transfer
llama-cpp-python==0.3.29
gradio>=6.0.0
pydantic>=2.0.0
genanki>=0.13.0
huggingface-hub>=1.18.0
pyyaml>=6.0
soundfile>=0.12.0
omnivoice>=0.1.0
diffusers>=0.28.0
```

- `torch==2.8.0` from PyTorch cu128 index — ships CUDA runtime libs ZeroGPU doesn't expose
- `llama-cpp-python==0.3.29` from cu124 prebuilt wheel index — avoids on-builder compilation
- `spaces` — ZeroGPU GPU context management
- `hf_transfer` — faster model downloads via parallel HTTP

### 3. `.gitignore` — No changes

Per user decision. Model weights are already handled by existing patterns.

## What stays the same

- `pyproject.toml` — unchanged, used for local `uv sync`
- All core logic (`core/`, `frontend/`, `export/`) — unchanged
- Test suite — unchanged
- `configs/settings.yaml` — unchanged

## How it works on ZeroGPU

Each `@spaces.GPU(duration=120)` wraps one engine call. The GPU attaches for ~120s per call, then detaches. Cold start on first message (model download + load), fast subsequent calls within the window. After idle, space sleeps and next message pays cold start again.

## How it works locally

The `try/except ImportError` pattern means `spaces` is only imported when running on HF. Locally, `gpu()` is a no-op decorator — everything runs as before with `uv run app.py`. No local behavior changes.
