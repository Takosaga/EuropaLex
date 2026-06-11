# Replace Nemotron with MiniCPM5-1B — Design Spec

## Overview

Replace the Phase 1 English text generation pipeline: swap `TextEngine` (which spawns `llama-cli` subprocesses with Nemotron 30B-A3B, ~16 GB) for a new `MiniCPMTextEngine` that loads MiniCPM5-1B Q8_0 via llama-cpp-python (~1.1 GB). Phase 2 translation via tiny-aya-water remains unchanged.

## Why This Change

| Aspect | Nemotron (current) | MiniCPM5-1B (new) |
|---|---|---|
| Model size | ~16 GB (IQ4_XS) | ~1.1 GB (Q8_0) |
| Runtime | llama-cli subprocess | llama-cpp-python in-process |
| Architecture | MoE (needs `--n-cpu-moe`) | Standard LlamaForCausalLM |
| VRAM / RAM usage | High (~16 GB) | Low (~1.1 GB) |
| Subprocess overhead | Yes (spawn + wait per call) | No (lazy-load once, unload after) |
| Context window | 32k | 131k |

## Architecture

```
User input → app.py click handler → EnginePool.get(config) → MiniCPMTextEngine (Phase 1) → cards rendered with English on front
```

### Component Changes

**New:** `MiniCPMTextEngine` in `core/engine.py`
- Uses llama-cpp-python directly (same runtime as existing `LlamaCppTextEngine`)
- Lazy-loads the Q8_0 model (~1.1 GB) on first `.generate()` call
- Unloads after completion to free memory (via EnginePool mutual exclusion)
- Uses MiniCPM5-1B's built-in chat template (`apply_chat_template`) — no manual prompt formatting

**Removed:** `TextEngine` in `core/engine.py`
- Deletes the entire class and all llama-cli subprocess logic
- Removes `_build_command`, `_build_generation_prompt`, `_build_translation_prompt`, `_build_translation_prompt` methods that were only used by TextEngine
- Keeps translation-specific prompts inside `LlamaCppTextEngine` (those are still needed)

**Updated:** `EnginePool.get_english_engine()` returns `MiniCPMTextEngine` instead of `TextEngine`

**Updated:** `EngineConfig.from_settings_yaml()` loads `minicpm_model_path` and simplified generation params (no MoE, no n_ubatch)

**Unchanged:** Phase 2 pipeline — `LlamaCppTextEngine`, `TTSEngine`, `ImageGenEngine`, `EnginePool._ensure_exclusive("translation")`, all media engines

## Component Details

### MiniCPMTextEngine

```python
class MiniCPMTextEngine:
    def __init__(self, model_path: str, device: str = "cuda"): ...
    def _load_model(self) -> None: ...        # Lazy-load via llama_cpp.Llama
    def generate(self, texts: list[str], scenario: str, cefr_level: CEFRLevel, batch_size: int | None = None) -> TextResult: ...
    def unload(self) -> None: ...              # del model + torch.cuda.empty_cache()
```

**Prompt format:** Chat template via `apply_chat_template(messages=[{"role": "system", "content": "..."}, {"role": "user", "content": "..."}])`

System prompt instructs the model to act as a language teacher generating simple sentences at the specified CEFR level about the given scenario. User message is identical to the current Nemotron prompt (batch size, CEFR level, scenario).

**Generation parameters:**
- `max_tokens`: 512
- `temperature`: 0.7
- `echo`: False
- `n_ctx`: 4096 (sufficient for batch_size=3 sentences)

### EngineConfig Changes

| Removed | Added |
|---|---|
| `nemotron_model_path: str` | `minicpm_model_path: str` |
| `n_cpu_moe: int = 36` | *(not needed — standard Llama arch)* |
| `n_ubatch: int = 1024` | *(llama-cpp-python handles this internally)* |

All other fields (`n_ctx`, `n_threads`, `n_batch`, `top_k`, `repeat_penalty`, `top_p`, `min_p`, `temperature`, `max_tokens`) are retained.

### settings.yaml Changes

- Rename `nemotron` section to `minicpm` with repo `Abiray/MiniCPM5-1B-GGUF`, file `minicpm5-1b-Q8_0.gguf`, runtime `llama-cpp-python`
- Remove `n_cpu_moe` from `generation` section

### download_models.py Changes

- Rename `nemotron` entry to `minicpm` with repo `Abiray/MiniCPM5-1B-GGUF`, file `minicpm5-1b-Q8_0.gguf`
- Update description text

## Data Flow

```
Phase 1:
User enters scenario + CEFR level → app.py clicks "Generate Text"
  → generate_text_async() calls EnginePool.get(config).get_english_engine()
  → returns MiniCPMTextEngine (lazy-load on first call)
  → .generate(texts=[], scenario, cefr_level, batch_size)
  → MiniCPM builds chat prompt, generates sentences
  → TextResult.translations → list of English sentences
  → Cards rendered with placeholder_back=True

Phase 2 (unchanged):
User clicks "Generate Cards" → EnginePool.get_translation_engine()
  → LlamaCppTextEngine (tiny-aya-water) translates sentences
```

## Error Handling

- Model file missing: `FileNotFoundError` raised in `__init__`, caught by `generate_text_async()` with same user-facing message pattern as current Nemotron error handling
- llama-cpp-python not installed: `ImportError` — but package is already installed via `LlamaCppTextEngine`, so this path is unlikely
- Generation failure: RuntimeError with stderr capture, shown to user in styled error box (same as current)

## Testing

- `scripts/smoke_test.py`: Must pass (imports all modules, constructs Gradio app)
- Manual test: Generate text for a scenario → verify MiniCPM produces readable English sentences at appropriate CEFR level
- Phase 2 still works unchanged: generate media after text generation

## Files Modified

| File | Action |
|---|---|
| `core/engine.py` | Remove `TextEngine`, add `MiniCPMTextEngine` |
| `core/types.py` | Rename `nemotron_model_path` → `minicpm_model_path`, remove MoE/ubatch params |
| `configs/settings.yaml` | Rename nemotron → minicpm, remove n_cpu_moe |
| `models/download_models.py` | Rename nemotron entry to minicpm |
| `docs/superpowers/specs/2026-06-10-minicpm5-text-engine-design.md` | This spec (new) |
