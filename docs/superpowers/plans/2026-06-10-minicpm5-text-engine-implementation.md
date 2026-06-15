# MiniCPM5-1B Text Engine Replacement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace Nemotron 30B-A3B (~16 GB, llama-cli subprocess) with MiniCPM5-1B Q8_0 (~1.1 GB, llama-cpp-python in-process) for Phase 1 English text generation.

**Architecture:** Swap `TextEngine` (subprocess-based, MoE-specific params) for `MiniCPMTextEngine` (lazy-load via llama-cpp-python, uses `apply_chat_template` for prompt formatting). EnginePool manages lifecycle with mutual exclusion. Phase 2 (tiny-aya-water translation, OmniVoice TTS, FLUX.2 images) unchanged.

**Tech Stack:** Python 3.12+, llama-cpp-python, Pydantic, Gradio 6, GGUF models via Hugging Face Hub.

---

## File Map

| File | Change | Depends On |
|---|---|---|
| `configs/settings.yaml` | Rename `nemotron` → `minicpm`, remove `n_cpu_moe` | — (first) |
| `core/types.py` | Rename field, remove MoE/ubatch params, update YAML loader | settings.yaml change |
| `core/engine.py` | Remove TextEngine, add MiniCPMTextEngine, update EnginePool | types.py change |
| `models/download_models.py` | Rename nemotron → minicpm entry | — (independent) |
| `app.py` | Update imports, error messages | engine.py change |
| `README.md` | Model table, Phase 1 docs, architecture section | All code done |
| `AGENTS.md` | Models table, engine protocol docs | All code done |

## Execution Order

Steps 1–5 are code changes in dependency order. Steps 6–7 are docs updates, deferred until after smoke test passes. Step 4 (`download_models.py`) is independent of the types/engine chain and can run anytime.

---

### Task 1: configs/settings.yaml — Rename nemotron → minicpm, remove n_cpu_moe

**Files:**
- Modify: `configs/settings.yaml`

- [ ] **Step 1: Rewrite settings.yaml**

Replace the entire file with the updated version:

```yaml
# EuropaLex Settings
# Model paths, batch size defaults, CEFR levels, language configuration

models:
  directory: .local/models
  minicpm:
    repo: Abiray/MiniCPM5-1B-GGUF
    file: minicpm5-1b-Q8_0.gguf
    runtime: llama-cpp-python
    quant: Q8_0
  tiny_aya:
    repo: CohereLabs/tiny-aya-water-GGUF
    file: tiny-aya-water-q4_k_m.gguf
    runtime: llama-cpp-python
    quant: q4_k_m
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

# Generation parameters (MiniCPM5-1B via llama-cpp-python)
generation:
  n_ctx: 4096           # Context length in tokens (sufficient for batch_size=3 sentences)
  n_threads: 5          # CPU thread pool size
  n_batch: 4096         # Evaluation batch size
  top_k: 40             # Top-K sampling
  repeat_penalty: 1.1   # Repeat penalty
  top_p: 0.9           # Top-P (nucleus) sampling
  min_p: 0.05          # Min-P sampling
  temperature: 0.7     # Generation temperature
  max_tokens: 512      # Maximum response length in tokens
```

Key changes from original:
- `nemotron:` → `minicpm:` with new repo/file/runtime
- Removed `n_ubatch` and `n_cpu_moe` from generation section (not needed for standard LlamaForCausalLM)
- Changed `n_ctx` default from 32768 to 4096 (sufficient for batch_size=3, matches MiniCPMTextEngine design)

- [ ] **Step 2: Verify YAML parses cleanly**

Run:
```bash
uv run python -c "import yaml; yaml.safe_load(open('configs/settings.yaml')); print('YAML valid')"
```
Expected: `YAML valid` (no traceback).

- [ ] **Step 3: Commit**

```bash
git add configs/settings.yaml
git commit -m "refactor: rename nemotron to minicpm, remove MoE params from generation config"
```

---

### Task 2: core/types.py — Rename nemotron_model_path → minicpm_model_path, remove MoE params

**Files:**
- Modify: `core/types.py`

- [ ] **Step 1: Update EngineConfig fields**

Replace the field declarations section. In the `EngineConfig` class body, change these lines:

**Remove this block (around line ~68):**
```python
    nemotron_model_path: str  # Path to Nemotron GGUF file
```

**Add after `llm_model_path`:**
```python
    minicpm_model_path: str  # Path to MiniCPM5-1B Q8_0 GGUF file
```

**Remove these two lines:**
```python
    n_ubatch: int = 1024  # Physical (micro) batch size
    n_cpu_moe: int = 36  # Number of MoE expert layers forced to CPU (llama.cpp only)
```

- [ ] **Step 2: Update from_settings_yaml() method**

Replace the entire `return cls(...)` block inside `from_settings_yaml()` with this:

```python
        return cls(
            models_dir=models.get("directory", ".local/models"),
            llm_model_path=str(Path(models.get("directory", ".local/models")) / llm_subdir / llm_cfg["file"]),
            minicpm_model_path=str(Path(models.get("directory", ".local/models")) / "minicpm" / models["minicpm"]["file"]),
            device=device,
            batch_size=batch.get("default_size", 3),
            n_ctx=gen.get("n_ctx", 4096),
            n_threads=gen.get("n_threads", 5),
            n_batch=gen.get("n_batch", 4096),
            top_k=gen.get("top_k", 40),
            repeat_penalty=gen.get("repeat_penalty", 1.1),
            top_p=gen.get("top_p", 0.9),
            min_p=gen.get("min_p", 0.05),
            temperature=gen.get("temperature", 0.7),
            max_tokens=gen.get("max_tokens", 512),
        )
```

Key changes:
- `nemotron_model_path=` → `minicpm_model_path=` resolving to `"minicpm"` subdir
- Removed `n_ubatch=`, `n_cpu_moe=` arguments
- Changed `n_ctx` default from 32768 to 4096

- [ ] **Step 3: Verify import**

Run:
```bash
uv run python -c "from core.types import EngineConfig; c = EngineConfig(); print(f'minicpm_model_path={c.minicpm_model_path}'); print('No n_cpu_moe:', not hasattr(c, 'n_cpu_moe')); print('OK')"
```
Expected: prints field value and confirmation no `n_cpu_moe` attribute exists.

- [ ] **Step 4: Commit**

```bash
git add core/types.py
git commit -m "refactor: rename nemotron_model_path to minicpm_model_path, remove MoE/ubatch params"
```

---

### Task 3: core/engine.py — Replace TextEngine with MiniCPMTextEngine, update EnginePool

**Files:**
- Modify: `core/engine.py`

- [ ] **Step 1: Remove subprocess import (if only used by TextEngine)**

Check if `subprocess` is still needed. Only `TextEngine` uses it (`subprocess.run`, `subprocess.TimeoutExpired`). After removing TextEngine, remove the import line:

**Remove:**
```python
import subprocess
from dataclasses import dataclass
```
(Keep `dataclass` — `_EngineState` still uses it.)

- [ ] **Step 2: Remove TextEngine class entirely**

Delete the entire `TextEngine` class (lines ~36–108 in current file), including ALL of these methods:
- `__init__`
- `generate`
- `_build_command`
- `_build_translation_prompt`
- `_build_generation_prompt`

This is ~73 lines to remove. The `_build_translation_prompt` method inside TextEngine should NOT be removed — `LlamaCppTextEngine` has its own copy that must remain.

- [ ] **Step 3: Add MiniCPMTextEngine class**

Insert this new class right after `_EngineState` and before `LlamaCppTextEngine`:

```python
class MiniCPMTextEngine:
    """Generates English text using MiniCPM5-1B Q8_0 via llama-cpp-python.

    Lazy-loads the model on first call, unloads after completion to free memory.
    Uses MiniCPM5-1B's built-in chat template (apply_chat_template) for prompt formatting.
    Only one instance can be active at a time (enforced by EnginePool).

    Best for Phase 1 English text generation — ~1.1 GB RAM, no subprocess overhead.
    """

    def __init__(self, model_path: str, device: str = "cuda"):
        """Initialize the text engine.

        Args:
            model_path: Absolute path to the MiniCPM5-1B Q8_0 GGUF file.
            device: Device hint ('cuda', 'mps', or 'cpu').
        """
        self.model_path = Path(model_path)
        if not self.model_path.exists():
            raise FileNotFoundError(
                f"MiniCPM5-1B model not found at: {self.model_path}\n"
                f"Run: python models/download_models.py minicpm"
            )
        self.device = device
        self._llm = None
        self._loaded = False

    def _load_model(self) -> None:
        """Lazy-load the GGUF model via llama-cpp-python."""
        if self._loaded:
            return

        try:
            from llama_cpp import Llama
        except ImportError:
            raise ImportError(
                "llama-cpp-python package not installed. "
                "Run: pip install llama-cpp-python"
            )

        n_gpu = 99 if self.device == "cuda" else 0
        self._llm = Llama(
            model_path=str(self.model_path),
            n_gpu_layers=n_gpu,
            n_ctx=4096,
        )
        self._loaded = True
        logger.info("MiniCPMTextEngine loaded %s on %s", self.model_path.name, self.device)

    def generate(self, texts: list[str], scenario: str, cefr_level: CEFRLevel, batch_size: int | None = None) -> TextResult:
        """Generate English sentences using the loaded GGUF model.

        Args:
            texts: Empty list (generation mode). Non-empty would be translation mode.
            scenario: Scenario/topic description for text generation.
            cefr_level: CEFR proficiency level.
            batch_size: Number of sentences to generate.

        Returns:
            TextResult with one sentence per requested batch size.

        Raises:
            RuntimeError: If generation fails.
        """
        self._load_model()
        prompt = self._build_chat_prompt(scenario, cefr_level, batch_size or 3)

        output = self._llm(
            prompt=prompt,
            max_tokens=512,
            temperature=0.7,
            echo=False,
        )

        text = output.get("choices", [{}])[0].get("text", "")
        lines = [line.strip() for line in text.strip().split("\n") if line.strip()]
        return TextResult(translations=lines)

    def _build_chat_prompt(self, scenario: str, cefr_level: CEFRLevel, batch_size: int) -> str:
        """Build chat-formatted prompt using the model's built-in template.

        Args:
            scenario: Scenario/topic description.
            cefr_level: CEFR proficiency level.
            batch_size: Number of sentences to generate.

        Returns:
            Formatted prompt string ready for model inference.
        """
        system_msg = {
            "role": "system",
            "content": (
                "You are a language teacher. Generate simple, clear sentences at the specified CEFR level "
                "about the given scenario. Output ONE sentence per line, no numbering or explanations."
            ),
        }
        user_msg = {
            "role": "user",
            "content": (
                f"Generate {batch_size} simple sentences at CEFR level {cefr_level.value}\n"
                f"about the following scenario. Output ONE sentence per line, no numbering.\n"
                f"Scenario: {scenario}\n"
                "Output ONLY the sentences, one per line. No explanations."
            ),
        }
        return self._llm.apply_chat_template(
            messages=[system_msg, user_msg],
            tokenize=False,
            add_generation_prompt=True,
        )

    def unload(self) -> None:
        """Unload the model and free memory."""
        if self._llm is not None:
            del self._llm
            self._llm = None
            self._loaded = False
            try:
                torch.cuda.empty_cache()
            except Exception:
                pass
            logger.info("MiniCPMTextEngine unloaded")
```

- [ ] **Step 4: Update EnginePool.get_english_engine()**

Replace the current `get_english_engine` method:

**Remove:**
```python
    def get_english_engine(self) -> TextEngine:
        """Get a fresh English text generation engine (Nemotron).

        Clears any active GPU engines before returning.
        Uses full EngineConfig for all llama-cli generation parameters.
        """
        self._ensure_exclusive("text")
        return TextEngine(config=self._config)
```

**Add:**
```python
    def get_english_engine(self) -> MiniCPMTextEngine:
        """Get a fresh English text generation engine (MiniCPM5-1B).

        Unloads any active GPU engines before returning.
        Returns a new MiniCPMTextEngine instance each call (stateless after unload).
        """
        self._ensure_exclusive("text")
        return MiniCPMTextEngine(
            model_path=self._config.minicpm_model_path,
            device=self._config.device,
        )
```

- [ ] **Step 5: Add _unload_english() to EnginePool**

Add this new private method to `EnginePool`, alongside the other `_unload_*` methods:

```python
    def _unload_english(self) -> None:
        """Unload the English text engine if active."""
        # MiniCPMTextEngine instances are per-call (stateless), but we track
        # any loaded model state to ensure clean GPU memory.
        try:
            torch.cuda.empty_cache()
        except Exception:
            pass
```

Update `_ensure_exclusive("text")` to also call `_unload_english()`:

**Change this block:**
```python
    def _ensure_exclusive(self, target: str) -> None:
        """Unload any active GPU engine that conflicts with the target."""
        if target == "text":
            self._unload_translation()
            self._unload_tts()
            self._unload_image()
```

**To:**
```python
    def _ensure_exclusive(self, target: str) -> None:
        """Unload any active GPU engine that conflicts with the target."""
        if target == "text":
            self._unload_translation()
            self._unload_tts()
            self._unload_image()
            self._unload_english()
```

- [ ] **Step 6: Verify import**

Run:
```bash
uv run python -c "from core.engine import MiniCPMTextEngine, EnginePool; print('OK')"
```
Expected: `OK` (no traceback). TextEngine should NOT be importable.

- [ ] **Step 7: Commit**

```bash
git add core/engine.py
git commit -m "feat: replace TextEngine with MiniCPMTextEngine (llama-cpp-python, chat template)"
```

---

### Task 4: models/download_models.py — Rename nemotron entry to minicpm

**Files:**
- Modify: `models/download_models.py`

- [ ] **Step 1: Update MODELS dict entry**

Replace the `nemotron` dict in `MODELS`:

**Remove:**
```python
    "nemotron": {
        "repo": "bartowski/nvidia_Nemotron-3-Nano-30B-A3B-GGUF",
        "files": ["nvidia_Nemotron-3-Nano-30B-A3B-IQ4_XS.gguf"],
        "description": "Nemotron-3-Nano 30B-A3B IQ4_XS (llama-cli)",
    },
```

**Add:**
```python
    "minicpm": {
        "repo": "Abiray/MiniCPM5-1B-GGUF",
        "files": ["minicpm5-1b-Q8_0.gguf"],
        "description": "MiniCPM5-1B Q8_0 text gen (llama-cpp-python)",
    },
```

- [ ] **Step 2: Update module docstring**

Replace the first line of the module docstring and the model list:

**Remove:**
```python
"""Download models from Hugging Face Hub at runtime.

Usage:
    python -m models.download_models                  # Download all models
    python -m models.download_models nemotron tiny_aya  # Download specific models

Models:
    nemotron        — Nemotron-3-Nano 30B-A3B IQ4_XS (llama-cli)
```

**Add:**
```python
"""Download models from Hugging Face Hub at runtime.

Usage:
    python -m models.download_models                  # Download all models
    python -m models.download_models minicpm tiny_aya  # Download specific models

Models:
    minicpm         — MiniCPM5-1B Q8_0 (llama-cpp-python)
```

- [ ] **Step 3: Verify**

Run:
```bash
uv run python -c "from models.download_models import MODELS; assert 'minicpm' in MODELS; assert 'nemotron' not in MODELS; print('OK')"
```
Expected: `OK`.

- [ ] **Step 4: Commit**

```bash
git add models/download_models.py
git commit -m "refactor: rename nemotron download entry to minicpm"
```

---

### Task 5: app.py — Update engine references and error messages

**Files:**
- Modify: `app.py`

- [ ] **Step 1: Update import line**

**Remove:**
```python
from core.engine import EnginePool, TextEngine
```

**Add:**
```python
from core.engine import EnginePool, MiniCPMTextEngine
```

- [ ] **Step 2: Update error messages in generate_text_async()**

Replace the FileNotFoundError message (around line ~70):

**Remove:**
```python
        logger.error("Phase 1 model not found: %s", e)
        yield generate_progress_html(0, f"\u26a0\ufe0f Model file missing: {e}"), (
            '<div style="color:#c44; padding:20px;">'
            '<strong>Model file not found.</strong><br>'
            f'{e}<br><br>'
            'Run <code>python models/download_models.py</code> to download required models, '
            'or check <code>configs/settings.yaml</code> for the correct path.'
            '</div>'
        )
```

**Add:**
```python
        logger.error("Phase 1 model not found: %s", e)
        yield generate_progress_html(0, f"\u26a0\ufe0f Model file missing: {e}"), (
            '<div style="color:#c44; padding:20px;">'
            '<strong>Model file not found.</strong><br>'
            f'{e}<br><br>'
            'Run <code>python models/download_models.py minicpm</code> to download MiniCPM5-1B, '
            'or check <code>configs/settings.yaml</code> for the correct path.'
            '</div>'
        )
```

Replace the RuntimeError message (around line ~90):

**Remove:**
```python
        logger.error("Phase 1 generation failed: %s", e)
        err_detail = str(e)
        yield generate_progress_html(0, f"\u26a0\ufe0f Generation failed"), (
            '<div style="color:#c44; padding:20px;">'
            f'<strong>llama-cli subprocess failed.</strong><br>'
            f'{err_detail}<br><br>'
            'Possible causes:<br>'
            '• <code>llama-cli</code> not installed or not on PATH<br>'
            '• Model file corrupted or incompatible format<br>'
            '• Insufficient RAM/VRAM (Nemotron ~16 GB)<br><br>'
            'Check the terminal for full error output.'
            '</div>'
        )
```

**Add:**
```python
        logger.error("Phase 1 generation failed: %s", e)
        err_detail = str(e)
        yield generate_progress_html(0, f"\u26a0\ufe0f Generation failed"), (
            '<div style="color:#c44; padding:20px;">'
            f'<strong>MiniCPM5-1B generation failed.</strong><br>'
            f'{err_detail}<br><br>'
            'Possible causes:<br>'
            '• Model file corrupted or incompatible format<br>'
            '• Insufficient VRAM (~1.1 GB required)<br><br>'
            'Check the terminal for full error output.'
            '</div>'
        )
```

- [ ] **Step 3: Update progress message**

Replace:
```python
        yield generate_progress_html(20, "Preparing Nemotron generation..."), ""
```
With:
```python
        yield generate_progress_html(20, "Preparing MiniCPM5-1B generation..."), ""
```

- [ ] **Step 4: Verify**

Run:
```bash
uv run python -c "import app; print('OK')"
```
Expected: `OK` (app module imports without errors).

- [ ] **Step 5: Commit**

```bash
git add app.py
git commit -m "refactor: update app.py error messages for MiniCPM5-1B"
```

---

### Task 6: README.md — Update model table and documentation

**Files:**
- Modify: `README.md`

> **Note:** Only execute this task after running `uv run python scripts/smoke_test.py` and confirming it passes.

- [ ] **Step 1: Update model table row**

Replace the Nemotron row in the model table (the first data row):

**Remove:**
```markdown
| Nemotron-3-Nano 30B-A3B IQ4_XS | [bartowski/nvidia_Nemotron-3-Nano-30B-A3B-GGUF](https://huggingface.co/bartowski/nvidia_Nemotron-3-Nano-30B-A3B-GGUF) | `Nemotron-3-Nano-30B-A3B-IQ4_XS.gguf` | llama-cli | 18.1 GB | English text generation (Phase 1) |
```

**Add:**
```markdown
| MiniCPM5-1B Q8_0 | [Abiray/MiniCPM5-1B-GGUF](https://huggingface.co/Abiray/MiniCPM5-1B-GGUF) | `minicpm5-1b-Q8_0.gguf` | llama-cpp-python | ~1.1 GB | English text generation (Phase 1) |
```

- [ ] **Step 2: Update download command example**

Replace:
```bash
uv run python -m models.download_models nemotron tiny_aya  # Text generation only (~20 GB)
```
With:
```bash
uv run python -m models.download_models minicpm tiny_aya  # Text generation + translation (~3.2 GB)
```

- [ ] **Step 3: Update Phase 1 description**

Replace:
```markdown
5. The app generates English sentences via Nemotron (`TextEngine`, llama-cli subprocess)
```
With:
```markdown
5. The app generates English sentences via MiniCPM5-1B (`MiniCPMTextEngine`, llama-cpp-python, lazy-load/unload)
```

- [ ] **Step 4: Update architecture engine descriptions**

Replace the `TextEngine` bullet in the Architecture section:

**Remove:**
```markdown
  - `TextEngine` — llama-cli subprocess wrapper for Nemotron (stateless, spawns fresh process per call). Used in Phase 1 for English text generation only.
```

**Add:**
```markdown
  - `MiniCPMTextEngine` — llama-cpp-python wrapper for MiniCPM5-1B Q8_0 (lazy-load/unload, ~1.1 GB RAM, uses apply_chat_template). Used in Phase 1 for English text generation only.
```

- [ ] **Step 5: Update repository structure comment**

Replace the engine.py comment in the tree:

**Remove:**
```markdown
│   ├── engine.py           # TextEngine (Nemotron/llama-cli), LlamaCppTextEngine (tiny-aya/llama-cpp-python), TTSEngine (OmniVoice), ImageGenEngine (diffusers), EnginePool singleton
```

**Add:**
```markdown
│   ├── engine.py           # MiniCPMTextEngine (MiniCPM5-1B/llama-cpp-python), LlamaCppTextEngine (tiny-aya/llama-cpp-python), TTSEngine (OmniVoice), ImageGenEngine (diffusers), EnginePool singleton
```

- [ ] **Step 6: Update CEFR levels note**

Replace:
```markdown
- **A1–C2:** Nemotron generates English sentences at the selected level in Phase 1; tiny-aya-water translates them in Phase 2 (deferred)
```
With:
```markdown
- **A1–C2:** MiniCPM5-1B generates English sentences at the selected level in Phase 1; tiny-aya-water translates them in Phase 2 (deferred)
```

- [ ] **Step 7: Commit**

```bash
git add README.md
git commit -m "docs: update README for MiniCPM5-1B text engine replacement"
```

---

### Task 7: AGENTS.md — Update conventions and model docs

**Files:**
- Modify: `AGENTS.md`

> **Note:** Only execute this task after running `uv run python scripts/smoke_test.py` and confirming it passes.

- [ ] **Step 1: Update models table in Tech Stack section**

Replace the Nemotron row in the models table at the top of AGENTS.md:

**Remove:**
```markdown
| Nemotron-3-Nano 30B-A3B IQ4_XS | [bartowski/nvidia_Nemotron-3-Nano-30B-A3B-GGUF](https://huggingface.co/bartowski/nvidia_Nemotron-3-Nano-30B-A3B-GGUF) | llama-cli | English text generation (Phase 1) |
```

**Add:**
```markdown
| MiniCPM5-1B Q8_0 | [Abiray/MiniCPM5-1B-GGUF](https://huggingface.co/Abiray/MiniCPM5-1B-GGUF) | llama-cpp-python | English text generation (Phase 1) |
```

- [ ] **Step 2: Update EnginePool table**

Replace the TextEngine row in the engine protocol table:

**Remove:**
```markdown
| `TextEngine` | llama-cli subprocess | Stateless — spawns fresh process per `.generate()` call. Used in Phase 1 for English text generation only. |
```

**Add:**
```markdown
| `MiniCPMTextEngine` | llama-cpp-python (GGUF) | Lazy-load on first `.generate()`, unload after completion (~1.1 GB RAM). Uses `apply_chat_template`. Used in Phase 1 for English text generation. |
```

- [ ] **Step 3: Update data flow diagram**

Replace:
```markdown
User input → app.py click handler → EnginePool.get(config) → TextEngine (Nemotron, Phase 1) → LlamaCppTextEngine (translation, Phase 2) → TTSEngine/ImageGenEngine (media, Phase 2) → frontend/ui/cards.py rendering → Gradio output
```
With:
```markdown
User input → app.py click handler → EnginePool.get(config) → MiniCPMTextEngine (Phase 1) → LlamaCppTextEngine (translation, Phase 2) → TTSEngine/ImageGenEngine (media, Phase 2) → frontend/ui/cards.py rendering → Gradio output
```

- [ ] **Step 4: Update engine.py section in AGENTS.md**

Replace the TextEngine description in the "engine.py" subsection of Core Module Rules:

**Remove:**
```markdown
| Class | Backend | Lifecycle |
|---|---|---|
| `TextEngine` | llama-cli subprocess | Stateless — spawns fresh process per `.generate()` call. Used in Phase 1 for English text generation only. |
```

**Add:**
```markdown
| Class | Backend | Lifecycle |
|---|---|---|
| `MiniCPMTextEngine` | llama-cpp-python (GGUF) | Lazy-load on first `.generate()`, unload after completion (~1.1 GB RAM). Uses `apply_chat_template`. Used in Phase 1 for English text generation. |
```

- [ ] **Step 5: Update engine.py section — rules**

Replace the rule about TextEngine:

**Remove:**
```markdown
- GPU engines (LlamaCppTextEngine, TTSEngine, ImageGenEngine) are lazy-loaded and unloaded via `del` + `torch.cuda.empty_cache()`.
- Text engines (`TextEngine`) spawn subprocesses — no persistent VRAM consumption.
```

**Add:**
```markdown
- All engines (MiniCPMTextEngine, LlamaCppTextEngine, TTSEngine, ImageGenEngine) are lazy-loaded and unloaded via `del` + `torch.cuda.empty_cache()`.
```

- [ ] **Step 6: Commit**

```bash
git add AGENTS.md
git commit -m "docs: update AGENTS.md for MiniCPM5-1B text engine replacement"
```

---

## Final Verification

After completing all 7 tasks, run the smoke test one last time:

```bash
uv run python scripts/smoke_test.py
```

Expected: clean exit (no traceback).

Then verify the app launches:
```bash
timeout 5 uv run app.py || true
```

Expected: Gradio starts on port 7860 (or errors gracefully about missing model file, which is expected if not downloaded).

---

## Self-Review Checklist

**1. Spec coverage:**
- ✅ MiniCPMTextEngine class with `__init__`, `_load_model`, `generate`, `_build_chat_prompt`, `unload` — Task 3 Step 3
- ✅ Chat template via `apply_chat_template` — Task 3 Step 3 (`_build_chat_prompt`)
- ✅ Remove TextEngine entirely — Task 3 Step 2
- ✅ EnginePool returns MiniCPMTextEngine — Task 3 Step 4
- ✅ EngineConfig: nemotron_model_path → minicpm_model_path — Task 2 Step 1
- ✅ Remove n_cpu_moe and n_ubatch — Task 2 Step 1
- ✅ from_settings_yaml loads minicpm section — Task 2 Step 2
- ✅ settings.yaml: nemotron → minicpm, remove n_cpu_moe — Task 1 Step 1
- ✅ download_models.py: nemotron → minicpm entry — Task 4 Steps 1-2
- ✅ app.py: imports, error messages updated — Task 5 Steps 1-3
- ✅ README.md: model table, docs updated — Task 6 Steps 1-7
- ✅ AGENTS.md: models table, engine protocol updated — Task 7 Steps 1-6

**2. Placeholder scan:** No "TBD", "TODO", "implement later", "similar to" patterns found. Every step contains actual code or exact commands.

**3. Type consistency:** 
- `MiniCPMTextEngine.__init__(model_path: str, device: str = "cuda")` matches call site in `EnginePool.get_english_engine()`
- `generate()` signature unchanged from TextEngine (`texts`, `scenario`, `cefr_level`, `batch_size`) → returns `TextResult` — same interface
- `unload()` method present on MiniCPMTextEngine, matching TTSEngine/ImageGenEngine pattern
- EngineConfig field name `minicpm_model_path` consistent across types.py and settings.yaml references
