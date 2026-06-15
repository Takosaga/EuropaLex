# Model Download Setup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Configure EuropaLex to download four AI models (Nemotron, TildeOpen, OmniVoice, FLUX.2) from Hugging Face and store their configuration in settings.yaml.

**Architecture:** Two files change: `models/download_models.py` gets updated MODELS dict with correct HF repos and exact GGUF filenames; `configs/settings.yaml` gets populated with model paths, quant types, and runtime engine mappings. No new files created. No inference code changes.

**Tech Stack:** Python 3.12+, huggingface-hub (already a dependency per existing download script), PyYAML for settings.yaml parsing.

---

### Task 1: Populate `configs/settings.yaml` with model configuration

**Files:**
- Create: `configs/settings.yaml` (overwrite stub)
- Test: Run `python -c "import yaml; data = yaml.safe_load(open('configs/settings.yaml')); assert 'models' in data"`

- [ ] **Step 1: Write settings.yaml**

Replace the stub file with full model configuration:

```yaml
# EuropaLex Settings
# Model paths, batch size defaults, CEFR levels, language configuration

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

# Batch defaults
batch:
  default_size: 3
  max_size: 10

# CEFR levels supported
cefr_levels:
  - A0
  - A1
  - A2
  - B1
  - B2
  - C1
  - C2
```

- [ ] **Step 2: Verify YAML parses correctly**

Run: `python -c "import yaml; data = yaml.safe_load(open('configs/settings.yaml')); print(f'Models: {list(data[\"models\"].keys())}'); assert len(data['models']) == 4"`
Expected: `Models: ['nemotron', 'tildeopen', 'omnivoice', 'flux']`

- [ ] **Step 3: Commit**

```bash
git add configs/settings.yaml
git commit -m "config: populate settings.yaml with model configuration"
```

---

### Task 2: Update `models/download_models.py` with correct model definitions

**Files:**
- Modify: `models/download_models.py` — replace MODELS dict, update docstring and help text
- Test: Run `python -m models.download_models --help` to verify choices

- [ ] **Step 1: Replace MODELS dict**

Replace the entire MODELS dictionary (lines 10-24) with:

```python
# Model definitions — HF Hub repos with exact GGUF filenames
MODELS = {
    "nemotron": {
        "repo": "bartowski/nvidia_Nemotron-3-Nano-30B-A3B-GGUF",
        "files": ["Nemotron-3-Nano-30B-A3B-IQ4_XS.gguf"],
        "description": "Nemotron-3-Nano 30B-A3B IQ4_XS (llama-cli)",
    },
    "tildeopen": {
        "repo": "bartowski/TildeAI_TildeOpen-30b-GGUF",
        "files": ["TildeAI_TildeOpen-30b-Q4_K_S.gguf"],
        "description": "TildeOpen-30b Q4_K_S translation (llama-cli)",
    },
    "omnivoice": {
        "repo": "Serveurperso/OmniVoice-GGUF",
        "files": ["omnivoice-base-Q8_0.gguf", "omnivoice-tokenizer-Q8_0.gguf"],
        "description": "OmniVoice Q8_0 TTS (base + tokenizer, omnivoice.cpp)",
    },
    "flux": {
        "repo": "unsloth/FLUX.2-klein-4B-GGUF",
        "files": ["flux-2-klein-4b-Q4_K_M.gguf"],
        "description": "FLUX.2-klein 4B Q4_K_M image gen (ComfyUI-GGUF)",
    },
}
```

- [ ] **Step 2: Update docstring**

Replace the module docstring (lines 1-5) with:

```python
"""Download models from Hugging Face Hub at runtime.

Usage:
    python -m models.download_models                  # Download all models
    python -m models.download_models nemotron tildeopen  # Download specific models

Models:
    nemotron        — Nemotron-3-Nano 30B-A3B IQ4_XS (llama-cli)
    tildeopen       — TildeOpen-30b Q4_K_S (llama-cli)
    omnivoice       — OmniVoice Q8_0 TTS (omnivoice.cpp, requires base + tokenizer)
    flux            — FLUX.2-klein 4B Q4_K_M image gen (ComfyUI-GGUF)
"""
```

- [ ] **Step 3: Update help text**

Replace the choices line in `main()` (line 56) — the `choices=list(MODELS.keys())` already dynamically reads from MODELS, so no change needed there. Just verify by running the help command.

- [ ] **Step 4: Verify download script parses correctly**

Run: `python -m models.download_models --help`
Expected output includes choices: `nemotron`, `tildeopen`, `omnivoice`, `flux`

- [ ] **Step 5: Run smoke test**

Run: `python scripts/smoke_test.py`
Expected: clean exit (no traceback)

- [ ] **Step 6: Commit**

```bash
git add models/download_models.py
git commit -m "feat: update model download script with correct GGUF repos"
```

---

### Task 3: Add `.local/models/` to `.gitignore`

**Files:**
- Modify: `.gitignore` (create if not exists)
- Test: Verify `git status` does not show model files

- [ ] **Step 1: Create or update .gitignore**

Create `.gitignore` with:

```gitignore
# Model weights — large binary downloads, not tracked in git
.local/models/
models/

# Virtual environment
.venv/
venv/

# Python cache
__pycache__/
*.pyc
*.pyo

# Gradio cache
.gradio/

# OS files
.DS_Store
Thumbs.db
```

- [ ] **Step 2: Verify git status is clean**

Run: `git status --short | grep -E '\.local|models/'`
Expected: no output (model directories excluded)

- [ ] **Step 3: Commit**

```bash
git add .gitignore
git commit -m "config: add .gitignore for model weights and build artifacts"
```

---

## Self-Review Checklist

1. **Spec coverage:** All four models from the spec are in both settings.yaml and download_models.py. ✓
2. **Placeholder scan:** No TBD, TODO, or vague references. Every file path and filename is concrete. ✓
3. **Type consistency:** Model keys (`nemotron`, `tildeopen`, `omnivoice`, `flux`) match between both files. ✓
4. **Scope check:** Only download script + config changes. No engine/pipeline/app.py modifications. ✓
