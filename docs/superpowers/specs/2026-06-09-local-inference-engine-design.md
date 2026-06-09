# Local Inference Engine Design

**Date:** 2026-06-09  
**Status:** Approved  
**Scope:** `core/types.py` (Pydantic models) + `core/engine.py` (three inference backends + orchestrator)

---

## Purpose

Replace mock data in EuropaLex with real local model inference. Three backends — text generation (llama-cli), text-to-speech (OmniVoice Python package), and image generation (diffusers/FLUX.2-klein) — each loading one model at a time to manage GPU VRAM.

## Constraints

- **One model in memory at a time.** After each inference phase, the model is unloaded (`del` + `torch.cuda.empty_cache()`) before the next engine loads.
- **GPU first, CPU fallback.** All engines target CUDA/MPS. If unavailable, fall back to CPU with a warning.
- **Pydantic for all data shapes.** No raw dicts or dataclasses — every field validated at boundaries.
- **llama-cli is subprocess-only.** No Python binding exists; it spawns `llama-cli` as a child process.
- **OmniVoice and diffusers load from HF Hub at runtime.** The GGUF files in `.local/models/` are for the C++ runtimes (omnivoice.cpp, ComfyUI). The Python packages download their own model weights on first use.

---

## Architecture Overview

```
app.py
  │
  ├─ EnginePool.get_text_engine() → TextEngine.generate(texts) ─┐
  │                                                               │
  ├─ EnginePool.get_tts_engine()  → TTSEngine.synthesize(texts)  ├─→ CardData (audio_path)
  │                                                               │
  └─ EnginePool.get_image_engine()→ ImageGenEngine.generate(prompts)┘
```

`EnginePool` is a singleton that ensures mutual exclusion: requesting an engine unloads any currently loaded model before loading the new one.

---

## Component Design

### 1. `core/types.py` — Pydantic Models

All models in `pydantic.BaseModel`. No dataclasses.

```python
from pydantic import BaseModel, Field
from enum import Enum

class CEFRLevel(str, Enum):
    A0 = "A0"
    A1 = "A1"
    A2 = "A2"
    B1 = "B1"
    B2 = "B2"
    C1 = "C1"
    C2 = "C2"

class CardData(BaseModel):
    """A single flashcard with optional media."""
    text: str                              # English source text
    translation: str                       # Target-language translation (empty during Phase 1)
    audio_path: str | None = None          # Path to generated TTS audio (.wav)
    image_path: str | None = None          # Path to generated illustration
    cefr_level: CEFRLevel = CEFRLevel.B1   # Proficiency level

class TextResult(BaseModel):
    """Output from text generation."""
    translations: list[str]                # One per input text

class AudioResult(BaseModel):
    """Output from TTS generation."""
    audio_paths: list[str]                 # One per input text

class ImageResult(BaseModel):
    """Output from image generation."""
    image_paths: list[str]                 # One per input text

class EngineConfig(BaseModel):
    """Validated engine configuration from settings.yaml."""
    models_dir: str = ".local/models"
    llm_model_path: str                    # Path to TildeOpen GGUF
    device: str = "cuda"                   # "cuda", "mps", or "cpu"
    batch_size: int = 3
```

**Rationale:** Pydantic models validate at boundaries (app.py ↔ engine.py). `CEFRLevel` as an enum prevents invalid levels. `EngineConfig` replaces scattered config reads — one validated object passed to engines.

### 2. `core/engine.py` — Inference Engines

#### `TextEngine`

Spawns `llama-cli` as a subprocess. Reads output from stdout, parses JSON or text response.

```python
class TextEngine:
    def __init__(self, model_path: str, device: str = "cuda"): ...
    def generate(self, texts: list[str], scenario: str, cefr_level: CEFRLevel) -> TextResult: ...
```

**Invocation:** `llama-cli -m <tildeopen_gguf> -p <prompt> -n 512 --temp 0.7 -ngl 99`
The prompt is a structured template:

```
You are a translator. Translate the following {cefr_level} text into the target language.
Scenario: {scenario}
Translate these sentences, one per line, in order:
{text_lines}
Output ONLY the translations, one per line. No explanations.
```

llama-cli outputs plain text (one translation per line). Output is split by newlines and wrapped in `TextResult`.

**Note:** `-ngl 99` offloads all layers to GPU. TildeOpen GGUF path comes from settings.yaml (`models.tildeopen.file`).

**No load/unload needed.** llama-cli is a stateless subprocess — it exits after generating output. No VRAM persists between calls.

#### `TTSEngine`

Uses the `omnivoice` Python package. Loads model on first access, unloads after synthesis.

```python
class TTSEngine:
    def __init__(self, device: str = "cuda"): ...
    def _load_model(self) -> None: ...   # Lazy load on first use
    def synthesize(self, texts: list[str], output_dir: Path) -> AudioResult: ...
    def unload(self) -> None: ...         # del model + torch.cuda.empty_cache()
```

**Invocation:** `model.generate(text=...)` → returns `list[np.ndarray]` at 24 kHz. Each array is saved to a `.wav` file via `soundfile`.

**Lifecycle:** Model loads once per `synthesize()` call, runs inference, saves files, then unloads. The `_loaded` flag prevents repeated loading within the same session if multiple texts are batched.

#### `ImageGenEngine`

Uses `diffusers.Flux2KleinPipeline.from_pretrained()` loading the base model repo (`black-forest-labs/FLUX.2-klein-4B`) from HF Hub on first access. Unloads after generation.

```python
class ImageGenEngine:
    def __init__(self, device: str = "cuda"): ...
    def _load_pipeline(self) -> None: ...  # Lazy load on first use
    def generate(self, prompts: list[str], output_dir: Path) -> ImageResult: ...
    def unload(self) -> None: ...           # del pipeline + torch.cuda.empty_cache()
```

**Invocation:** `pipe(prompt=prompt, num_inference_steps=28, guidance_scale=3.5)` → returns list of PIL images. Each saved as `.png`.

**Prompt generation:** Each card's prompt is constructed from its English text + translation: `{translation}. Scene: {text}. Illustrative, educational style.`

**Lifecycle:** Same pattern as TTSEngine — lazy load, batch inference, unload.

#### `EnginePool` (Singleton)

Manages mutual exclusion between engines.

```python
class EnginePool:
    """Singleton managing mutual exclusion between inference engines.

    Factory pattern via classmethod — callers use EnginePool.get(config) to
    obtain (or create) the singleton instance.
    """
    _instance: ClassVar[EnginePool | None] = None

    @classmethod
    def get(cls, config: EngineConfig) -> "EnginePool": ...

    def get_text_engine(self) -> TextEngine: ...
    def get_tts_engine(self) -> TTSEngine: ...
    def get_image_engine(self) -> ImageGenEngine: ...

    def _ensure_exclusive(self, target: str) -> None:
        """Unload any loaded engine except the target. Called before each get_*()."""
        if target == "text":
            self._unload_tts()
            self._unload_image()
        elif target == "tts":
            self._unload_image()
        elif target == "image":
            self._unload_tts()
```

**Behavior:**
- `get_text_engine()` — returns a new TextEngine each time (no VRAM to free). Clears TTS and image engines.
- `get_tts_engine()` — unloads ImageGenEngine if active, then lazy-loads TTSEngine.
- `get_image_engine()` — unloads TTSEngine if active, then lazy-loads ImageGenEngine.

**Thread safety:** Not required. Gradio handlers run sequentially in a single thread.

### 3. Integration with Existing Code

**`app.py` changes:**
- Replace `MOCK_CARDS` with calls to `EnglishTextEngine.generate()` (Phase 1 step 1) and `TranslationEngine.translate()` (Phase 1 step 2).
- Replace mock media rendering with calls to `TTSEngine.synthesize()` and `ImageGenEngine.generate()`.
- Create `EnginePool(config)` at startup.

**`pipeline.py` remains unchanged for now.** It orchestrates the batch flow; it will consume the engine results but doesn't need to know about loading/unloading — that's EnginePool's responsibility.

**`.apkg` export:** Handled externally via an MCP server, not within engine.py scope.

### 4. Error Handling

| Failure mode | Handling |
|---|---|
| Model download fails (OmniVoice/diffusers) | Raise `RuntimeError` with HF Hub error details |
| llama-cli subprocess fails | Parse stderr, raise `RuntimeError` with diagnostic |
| GPU unavailable | Fall back to CPU with warning log; continue |
| TTS generates empty audio | Skip card, log warning, continue batch |
| Image generation fails (safety filter, OOM) | Log error, set `image_path = None`, continue batch |

### 5. Dependencies

New dependencies added to `requirements.txt`:

```
torch>=2.1.0           # For OmniVoice and diffusers
omnivoice>=1.0.0       # TTS Python package
diffusers>=0.28.0      # Image generation pipeline
soundfile>=0.12.0      # Save TTS audio to WAV
```

`gradio` and `pyyaml` already present. `pydantic` is the new core dependency for type safety.

---

## Data Flow (End-to-End)

```
Phase 1 — Generate Text:
  User clicks "Generate Text"
    → app.py calls EnginePool.get_text_engine().generate(texts, scenario, cefr_level)
    → TextEngine spawns llama-cli subprocess
    → llama-cli returns translations
    → TextResult → list[CardData] with text + translation, placeholder_back=True
    → Cards render in Gradio

Phase 2 — Generate Media:
  User toggles Images/Audio, clicks "Generate Cards"
    → app.py calls EnginePool.get_tts_engine().synthesize(translations)
    → TTSEngine loads OmniVoice model (GPU), generates audio for each text
    → AudioResult → list[paths] → CardData.audio_path populated
    → EnginePool unloads TTS model
    → If images requested: EnginePool.get_image_engine().generate(prompts)
    → ImageGenEngine loads FLUX pipeline (GPU), generates images
    → ImageResult → list[paths] → CardData.image_path populated
    → EnginePool unloads image engine
    → Cards re-render with media
```

## Testing Strategy

- **Smoke test:** `python scripts/smoke_test.py` validates imports and that the app constructs without errors. The smoke test should pass with mock data (engines not called).
- **Integration test (future):** A separate script that runs a single text generation call end-to-end, verifying output format. Not in scope for this design — deferred until implementation.

## Open Questions

None. All constraints and choices documented above.
