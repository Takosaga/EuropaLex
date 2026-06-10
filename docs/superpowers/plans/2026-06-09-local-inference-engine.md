# Local Inference Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace mock data in EuropaLex with real local model inference using four backends (Nemotron text gen, TildeOpen translation, OmniVoice TTS, FLUX.2 image gen) managed through a single `EnginePool` that loads one model at a time.

**Architecture:** Pydantic models validate all data at module boundaries. Three llama-cli engines are stateless subprocesses; two PyTorch engines (OmniVoice, diffusers) lazy-load on first use and unload after inference via `del` + `torch.cuda.empty_cache()`. `EnginePool` is a singleton factory that ensures mutual exclusion between the two GPU engines.

**Tech Stack:** Python 3.12+, llama-cli (subprocess), omnivoice (PyPI), diffusers >= 0.28.0, torch, pydantic, soundfile, gradio, pyyaml.

---

### Task 1: Add Dependencies to requirements.txt

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Append new dependencies**

Add these lines to the end of `requirements.txt`:

```
pydantic>=2.0.0
torch>=2.1.0
omnivoice>=1.0.0
diffusers>=0.28.0
soundfile>=0.12.0
```

- [ ] **Step 2: Commit**

```bash
git add requirements.txt
git commit -m "deps: add pydantic, torch, omnivoice, diffusers, soundfile for local inference"
```

---

### Task 2: Create Pydantic Types in core/types.py

**Files:**
- Create: `core/types.py`

- [ ] **Step 1: Write types module**

Replace the stub content of `core/types.py` with:

```python
"""EuropaLex Core Types — Pydantic models for type-safe data boundaries."""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import ClassVar

from pydantic import BaseModel, Field


class CEFRLevel(str, Enum):
    """CEFR proficiency levels supported by EuropaLex."""

    A0 = "A0"
    A1 = "A1"
    A2 = "A2"
    B1 = "B1"
    B2 = "B2"
    C1 = "C1"
    C2 = "C2"


class CardData(BaseModel):
    """A single flashcard with optional media attachments."""

    text: str  # English source text
    translation: str  # Target-language translation (empty during Phase 1)
    audio_path: str | None = None  # Path to generated TTS audio (.wav)
    image_path: str | None = None  # Path to generated illustration (.png)
    cefr_level: CEFRLevel = CEFRLevel.B1  # Proficiency level


class TextResult(BaseModel):
    """Output from a text generation engine."""

    translations: list[str]  # One per input text, in order


class AudioResult(BaseModel):
    """Output from TTS generation."""

    audio_paths: list[str]  # One per input text, absolute paths to .wav files


class ImageResult(BaseModel):
    """Output from image generation."""

    image_paths: list[str]  # One per prompt, absolute paths to .png files


class EngineConfig(BaseModel):
    """Validated engine configuration loaded from settings.yaml."""

    models_dir: str = ".local/models"
    llm_model_path: str  # Path to TildeOpen GGUF file
    nemotron_model_path: str  # Path to Nemotron GGUF file
    device: str = "cuda"  # "cuda", "mps", or "cpu"
    batch_size: int = 3

    @classmethod
    def from_settings_yaml(cls, path: str | Path = "configs/settings.yaml") -> EngineConfig:
        """Load and validate configuration from a YAML settings file.

        Args:
            path: Path to settings.yaml relative to project root.

        Returns:
            Validated EngineConfig instance.

        Raises:
            ValueError: If required fields are missing or invalid.
        """
        import yaml

        with open(path, "r") as f:
            raw = yaml.safe_load(f)

        models = raw.get("models", {})
        batch = raw.get("batch", {})
        device = "cuda"

        try:
            if torch.cuda.is_available():
                device = "cuda"
            elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                device = "mps"
            else:
                device = "cpu"
        except ImportError:
            pass  # torch not installed yet; default to cuda

        return cls(
            models_dir=models.get("directory", ".local/models"),
            llm_model_path=str(Path(models.get("directory", ".local/models")) / "tildeopen" / models["tildeopen"]["file"]),
            nemotron_model_path=str(Path(models.get("directory", ".local/models")) / "nemotron" / models["nemotron"]["file"]),
            device=device,
            batch_size=batch.get("default_size", 3),
        )
```

- [ ] **Step 2: Verify the module imports without errors**

```bash
cd /home/takosaga/Projects/EuropaLex && python -c "from core.types import CardData, TextResult, EngineConfig; print('OK')"
```

Expected: `OK` (no traceback).

- [ ] **Step 3: Commit**

```bash
git add core/types.py
git commit -m "feat: add Pydantic types for CardData, TextResult, AudioResult, ImageResult, EngineConfig"
```

---

### Task 3: Implement TextEngine (llama-cli subprocess)

**Files:**
- Create: `core/engine.py`

- [ ] **Step 1: Write the TextEngine class**

Create `core/engine.py` with:

```python
"""EuropaLex Inference Engine — Local model backends via llama-cli and Python packages."""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from core.types import CEFRLevel, TextResult

logger = logging.getLogger(__name__)


@dataclass
class _EngineState:
    """Tracks which GPU engine is currently loaded (TTSEngine or ImageGenEngine)."""

    tts_engine: TTSEngine | None = None
    image_engine: ImageGenEngine | None = None


class TextEngine:
    """Generates text using llama-cli subprocess with Nemotron or TildeOpen.

    Each call spawns a fresh subprocess — no model persists in memory between calls.
    """

    def __init__(self, model_path: str, device: str = "cuda"):
        """Initialize the text engine.

        Args:
            model_path: Absolute path to the GGUF model file.
            device: Device hint passed to llama-cli (informational; -ngl 99 used).
        """
        self.model_path = Path(model_path)
        if not self.model_path.exists():
            raise FileNotFoundError(f"Model not found: {self.model_path}")
        self.device = device

    def generate(self, texts: list[str], scenario: str, cefr_level: CEFRLevel, batch_size: int | None = None) -> TextResult:
        """Generate text using llama-cli.

        Args:
            texts: English sentences to translate (for TildeOpen) or empty list (for Nemotron).
            scenario: Scenario/topic description for Nemotron text generation.
            cefr_level: CEFR proficiency level.
            batch_size: Number of sentences to generate (Nemotron mode only).

        Returns:
            TextResult with one translation/sentence per input or generated item.

        Raises:
            RuntimeError: If llama-cli subprocess exits with non-zero status.
        """
        if texts:
            prompt = self._build_translation_prompt(texts, scenario, cefr_level)
        else:
            prompt = self._build_generation_prompt(scenario, cefr_level, batch_size or 3)

        result = subprocess.run(
            [
                "llama-cli",
                "-m", str(self.model_path),
                "-p", prompt,
                "-n", "512",
                "--temp", "0.7",
                "-ngl", "99",
                "--no-mmap",
            ],
            capture_output=True,
            text=True,
            timeout=300,
        )

        if result.returncode != 0:
            raise RuntimeError(f"llama-cli failed (exit {result.returncode}): {result.stderr}")

        lines = [line.strip() for line in result.stdout.strip().split("\n") if line.strip()]
        return TextResult(translations=lines)

    def _build_translation_prompt(self, texts: list[str], scenario: str, cefr_level: CEFRLevel) -> str:
        """Build prompt for TildeOpen translation."""
        text_lines = "\n".join(texts)
        target_lang = "Latvian"  # Default; can be parameterized later
        return (
            f"You are a translator. Translate the following {cefr_level.value} English text into {target_lang}.\n"
            f"Translate these sentences, one per line, in order:\n"
            f"{text_lines}\n"
            "Output ONLY the translations, one per line. No explanations."
        )

    def _build_generation_prompt(self, scenario: str, cefr_level: CEFRLevel, batch_size: int) -> str:
        """Build prompt for Nemotron text generation."""
        return (
            f"You are a language teacher. Generate {batch_size} simple sentences at CEFR level {cefr_level.value}\n"
            f"about the following scenario. Output ONE sentence per line, no numbering.\n"
            f"Scenario: {scenario}\n"
            "Output ONLY the sentences, one per line. No explanations."
        )
```

- [ ] **Step 2: Verify the module imports**

```bash
cd /home/takosaga/Projects/EuropaLex && python -c "from core.engine import TextEngine; print('OK')"
```

Expected: `OK` (no traceback).

- [ ] **Step 3: Commit**

```bash
git add core/engine.py
git commit -m "feat: add TextEngine — llama-cli subprocess wrapper for Nemotron and TildeOpen"
```

---

### Task 4: Implement TTSEngine (OmniVoice Python package)

**Files:**
- Modify: `core/engine.py` (append TTSEngine class)

- [ ] **Step 1: Append TTSEngine to engine.py**

Add this class after `TextEngine` in `core/engine.py`:

```python
import numpy as np
import soundfile as sf
import torch


class TTSEngine:
    """Text-to-speech using the omnivoice Python package.

    Lazy-loads the model on first synthesis call, unloads after completion.
    Only one instance can be active at a time (enforced by EnginePool).
    """

    def __init__(self, device: str = "cuda"):
        """Initialize the TTS engine.

        Args:
            device: 'cuda', 'mps', or 'cpu'.
        """
        self.device = device
        self._model = None
        self._loaded = False

    def _load_model(self) -> None:
        """Lazy-load the OmniVoice model from HF Hub."""
        if self._loaded:
            return

        try:
            from omnivoice import OmniVoice
        except ImportError:
            raise ImportError(
                "omnivoice package not installed. Run: pip install omnivoice"
            )

        self._model = OmniVoice.from_pretrained(
            "k2-fsa/OmniVoice",
            device_map=self.device,
            dtype=torch.float16 if self.device != "cpu" else torch.float32,
        )
        self._loaded = True
        logger.info("OmniVoice model loaded on %s", self.device)

    def synthesize(self, texts: list[str], output_dir: Path) -> AudioResult:
        """Generate audio for a batch of texts.

        Args:
            texts: List of text strings to convert to speech.
            output_dir: Directory to save .wav files.

        Returns:
            AudioResult with absolute paths to generated audio files.
        """
        self._load_model()
        output_dir.mkdir(parents=True, exist_ok=True)

        audio_paths = []
        for i, text in enumerate(texts):
            try:
                audio_data = self._model.generate(text=text)
                if audio_data and len(audio_data) > 0:
                    wav_path = output_dir / f"audio_{i}.wav"
                    sf.write(str(wav_path), audio_data[0], 24000)
                    audio_paths.append(str(wav_path.resolve()))
                    logger.debug("Saved audio to %s", wav_path)
                else:
                    logger.warning("Empty audio output for text: %s", text[:50])
                    audio_paths.append(None)
            except Exception as e:
                logger.error("TTS failed for text '%s': %s", text[:50], e)
                audio_paths.append(None)

        return AudioResult(audio_paths=audio_paths)

    def unload(self) -> None:
        """Unload the model and free GPU memory."""
        if self._model is not None:
            del self._model
            self._model = None
            self._loaded = False
            try:
                torch.cuda.empty_cache()
            except Exception:
                pass
            logger.info("OmniVoice model unloaded")
```

- [ ] **Step 2: Verify the module imports**

```bash
cd /home/takosaga/Projects/EuropaLex && python -c "from core.engine import TextEngine, TTSEngine; print('OK')"
```

Expected: `OK` (no traceback).

- [ ] **Step 3: Commit**

```bash
git add core/engine.py
git commit -m "feat: add TTSEngine — OmniVoice Python package wrapper with lazy load/unload"
```

---

### Task 5: Implement ImageGenEngine (diffusers/FLUX.2-klein)

**Files:**
- Modify: `core/engine.py` (append ImageGenEngine class)

- [ ] **Step 1: Append ImageGenEngine to engine.py**

Add this class after `TTSEngine` in `core/engine.py`:

```python
import torch
from PIL import Image


class ImageGenEngine:
    """Image generation using diffusers Flux2KleinPipeline.

    Lazy-loads the pipeline on first generation call, unloads after completion.
    Only one instance can be active at a time (enforced by EnginePool).
    """

    def __init__(self, device: str = "cuda"):
        """Initialize the image engine.

        Args:
            device: 'cuda', 'mps', or 'cpu'.
        """
        self.device = device
        self._pipeline = None
        self._loaded = False

    def _load_pipeline(self) -> None:
        """Lazy-load the Flux2Klein pipeline from HF Hub."""
        if self._loaded:
            return

        try:
            from diffusers import Flux2KleinPipeline
        except ImportError:
            raise ImportError(
                "diffusers package not installed. Run: pip install diffusers"
            )

        torch_dtype = torch.bfloat16 if self.device == "cuda" else torch.float32
        self._pipeline = Flux2KleinPipeline.from_pretrained(
            "black-forest-labs/FLUX.2-klein-4B",
            torch_dtype=torch_dtype,
        )
        self._pipeline.enable_model_cpu_offload()
        self._loaded = True
        logger.info("Flux2Klein pipeline loaded on %s", self.device)

    def generate(self, prompts: list[str], output_dir: Path) -> ImageResult:
        """Generate images for a batch of prompts.

        Args:
            prompts: List of text prompts for image generation.
            output_dir: Directory to save .png files.

        Returns:
            ImageResult with absolute paths to generated image files.
        """
        self._load_pipeline()
        output_dir.mkdir(parents=True, exist_ok=True)

        image_paths = []
        for i, prompt in enumerate(prompts):
            try:
                images = self._pipeline(
                    prompt=prompt,
                    num_inference_steps=28,
                    guidance_scale=3.5,
                )
                if images.images and len(images.images) > 0:
                    img_path = output_dir / f"image_{i}.png"
                    images.images[0].save(str(img_path))
                    image_paths.append(str(img_path.resolve()))
                    logger.debug("Saved image to %s", img_path)
                else:
                    logger.warning("Empty image output for prompt: %s", prompt[:50])
                    image_paths.append(None)
            except Exception as e:
                logger.error("Image generation failed for prompt '%s': %s", prompt[:50], e)
                image_paths.append(None)

        return ImageResult(image_paths=image_paths)

    def unload(self) -> None:
        """Unload the pipeline and free GPU memory."""
        if self._pipeline is not None:
            del self._pipeline
            self._pipeline = None
            self._loaded = False
            try:
                torch.cuda.empty_cache()
            except Exception:
                pass
            logger.info("Flux2Klein pipeline unloaded")
```

- [ ] **Step 2: Verify the module imports**

```bash
cd /home/takosaga/Projects/EuropaLex && python -c "from core.engine import TextEngine, TTSEngine, ImageGenEngine; print('OK')"
```

Expected: `OK` (no traceback).

- [ ] **Step 3: Commit**

```bash
git add core/engine.py
git commit -m "feat: add ImageGenEngine — diffusers Flux2KleinPipeline wrapper with lazy load/unload"
```

---

### Task 6: Implement EnginePool (Singleton Orchestrator)

**Files:**
- Modify: `core/engine.py` (append EnginePool class)

- [ ] **Step 1: Append EnginePool to engine.py**

Add this class after `ImageGenEngine` in `core/engine.py`:

```python


class EnginePool:
    """Singleton managing mutual exclusion between GPU inference engines.

    Ensures only one GPU model (TTSEngine or ImageGenEngine) is loaded at a time.
    Text engines are subprocess-based and do not consume persistent VRAM.

    Usage:
        pool = EnginePool.get(config)
        text_result = pool.get_translation_engine().translate(texts, cefr_level)
        # ... later ...
        audio_result = pool.get_tts_engine().synthesize(translations, output_dir)
    """

    _instance: ClassVar[EnginePool | None] = None
    _config: EngineConfig
    _state: _EngineState = field(default_factory=_EngineState)

    def __new__(cls) -> EnginePool:
        if cls._instance is None:
            raise RuntimeError(
                "EnginePool must be created via EnginePool.get(config), not directly."
            )
        return cls._instance

    @classmethod
    def get(cls, config: EngineConfig) -> EnginePool:
        """Get or create the EnginePool singleton.

        Args:
            config: Validated engine configuration.

        Returns:
            The singleton EnginePool instance.
        """
        if cls._instance is None:
            instance = super().__new__(cls)
            instance._config = config
            instance._state = _EngineState()
            cls._instance = instance
            logger.info("EnginePool initialized (device=%s)", config.device)
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset the singleton (useful for testing). Unloads all engines."""
        if cls._instance is not None:
            cls._instance._unload_tts()
            cls._instance._unload_image()
            cls._instance = None

    def get_english_engine(self) -> TextEngine:
        """Get a fresh English text generation engine (Nemotron).

        Clears any active GPU engines before returning.
        """
        self._ensure_exclusive("text")
        return TextEngine(
            model_path=self._config.nemotron_model_path,
            device=self._config.device,
        )

    def get_translation_engine(self) -> TextEngine:
        """Get a fresh translation engine (TildeOpen).

        Clears any active GPU engines before returning.
        """
        self._ensure_exclusive("text")
        return TextEngine(
            model_path=self._config.llm_model_path,
            device=self._config.device,
        )

    def get_tts_engine(self) -> TTSEngine:
        """Get or create the TTS engine.

        Unloads any active GPU engines before loading TTS.
        The same TTSEngine instance is returned on subsequent calls until unloaded.
        """
        self._ensure_exclusive("tts")
        if self._state.tts_engine is None:
            self._state.tts_engine = TTSEngine(device=self._config.device)
        return self._state.tts_engine

    def get_image_engine(self) -> ImageGenEngine:
        """Get or create the image generation engine.

        Unloads any active GPU engines before loading images.
        The same ImageGenEngine instance is returned on subsequent calls until unloaded.
        """
        self._ensure_exclusive("image")
        if self._state.image_engine is None:
            self._state.image_engine = ImageGenEngine(device=self._config.device)
        return self._state.image_engine

    def _ensure_exclusive(self, target: str) -> None:
        """Unload any active GPU engine that conflicts with the target."""
        if target == "text":
            self._unload_tts()
            self._unload_image()
        elif target == "tts":
            self._unload_image()
        elif target == "image":
            self._unload_tts()

    def _unload_tts(self) -> None:
        """Unload the TTS engine if active."""
        if self._state.tts_engine is not None:
            self._state.tts_engine.unload()
            self._state.tts_engine = None

    def _unload_image(self) -> None:
        """Unload the image engine if active."""
        if self._state.image_engine is not None:
            self._state.image_engine.unload()
            self._state.image_engine = None
```

- [ ] **Step 2: Verify the module imports**

```bash
cd /home/takosaga/Projects/EuropaLex && python -c "from core.engine import TextEngine, TTSEngine, ImageGenEngine, EnginePool; print('OK')"
```

Expected: `OK` (no traceback).

- [ ] **Step 3: Commit**

```bash
git add core/engine.py
git commit -m "feat: add EnginePool singleton — manages mutual exclusion between GPU engines"
```

---

### Task 7: Wire Engines into app.py

**Files:**
- Modify: `app.py`

- [ ] **Step 1: Replace mock data with engine calls in Phase 1 handler**

In `app.py`, replace the `generate_text_async` function with:

```python
from core.engine import EnginePool
from core.types import CEFRLevel, CardData


def _get_pool():
    """Lazy-initialize the EnginePool singleton."""
    from core.types import EngineConfig
    config = EngineConfig.from_settings_yaml()
    return EnginePool.get(config)


def generate_text_async(
    scenario: str,
    cefr_level: str,
    batch_size: int,
):
    """Phase 1: Generate English text + translations using local models.

    Yields (progress_html, card_output_html) tuples.
    Cards show English text with dashed placeholder back side.
    """
    if not scenario.strip():
        yield generate_progress_html(0, "⚠️ Please enter a scenario or topic."), '<div style="color:#c44; padding:20px;">Please enter a scenario or topic to generate cards.</div>'
        return

    pool = _get_pool()
    cefr = CEFRLevel(cefr_level)

    # Step 1: Generate English sentences with Nemotron
    yield generate_progress_html(20, "Generating English text...")
    english_engine = pool.get_english_engine()
    english_result = english_engine.generate(
        texts=[], scenario=scenario, cefr_level=cefr, batch_size=batch_size
    )

    if not english_result.translations:
        yield generate_progress_html(0, "No text generated."), '<div style="color:#c44; padding:20px;">Model produced no output. Try a different scenario.</div>'
        return

    yield generate_progress_html(50, "Translating to target language...")

    # Step 2: Translate each sentence with TildeOpen
    cards: list[dict] = []
    translation_engine = pool.get_translation_engine()
    for eng_text in english_result.translations:
        trans_result = translation_engine.generate(
            texts=[eng_text], scenario="", cefr_level=cefr
        )
        if trans_result.translations:
            cards.append({
                "text": eng_text,
                "translation": trans_result.translations[0],
                "cefr_level": cefr,
            })

    if not cards:
        yield generate_progress_html(0, "No translations produced."), '<div style="color:#c44; padding:20px;">Model produced no translations.</div>'
        return

    # Render with placeholder back (Phase 1 state)
    phase_cards = generate_cards_html(cards, include_image=False, include_audio=False, placeholder_back=True)
    yield generate_progress_html(100, "Text ready! Adjust media toggles and click Generate Cards."), phase_cards
```

- [ ] **Step 2: Replace mock data with engine calls in Phase 2 handler**

Replace the `generate_media_async` function with:

```python
def generate_media_async(
    scenario: str,
    cefr_level: str,
    batch_size: int,
    include_images: bool,
    include_audio: bool,
):
    """Phase 2: Add audio and images to existing text cards.

    Re-generates text first (since we don't persist card state between phases in this version),
    then adds media.
    """
    if not scenario.strip():
        yield generate_progress_html(0, "⚠️ Please enter a scenario or topic."), '<div style="color:#c44; padding:20px;">Please enter a scenario or topic to generate cards.</div>'
        return

    pool = _get_pool()
    cefr = CEFRLevel(cefr_level)
    output_dir = Path(".local/media")

    # Re-generate text (same logic as Phase 1, but we'll add media)
    yield generate_progress_html(10, "Regenerating text with media...")
    english_engine = pool.get_english_engine()
    english_result = english_engine.generate(
        texts=[], scenario=scenario, cefr_level=cefr, batch_size=batch_size
    )

    if not english_result.translations:
        yield generate_progress_html(0, "No text generated."), '<div style="color:#c44; padding:20px;">Model produced no output.</div>'
        return

    translation_engine = pool.get_translation_engine()
    cards_data: list[CardData] = []
    for eng_text in english_result.translations:
        trans_result = translation_engine.generate(
            texts=[eng_text], scenario="", cefr_level=cefr
        )
        if trans_result.translations:
            cards_data.append(CardData(
                text=eng_text,
                translation=trans_result.translations[0],
                cefr_level=cefr,
            ))

    # Step 1: Generate audio if requested
    if include_audio and cards_data:
        yield generate_progress_html(40, "Generating audio...")
        tts_engine = pool.get_tts_engine()
        texts_to_synthesize = [c.text for c in cards_data]
        audio_result = tts_engine.synthesize(texts_to_synthesize, output_dir)
        for i, card in enumerate(cards_data):
            if i < len(audio_result.audio_paths):
                card.audio_path = audio_result.audio_paths[i]

    # Step 2: Generate images if requested
    if include_images and cards_data:
        yield generate_progress_html(70, "Generating images...")
        image_engine = pool.get_image_engine()
        prompts = [f"{c.translation}. Scene: {c.text}. Illustrative, educational style." for c in cards_data]
        image_result = image_engine.generate(prompts, output_dir)
        for i, card in enumerate(cards_data):
            if i < len(image_result.image_paths):
                card.image_path = image_result.image_paths[i]

    # Render with full media (no placeholder — translation is real)
    cards_html = generate_cards_html(
        [{"text": c.text, "translation": c.translation} for c in cards_data],
        include_image=include_images,
        include_audio=include_audio,
        placeholder_back=False,
    )
    yield generate_progress_html(100, "Generation complete!"), cards_html
```

- [ ] **Step 3: Verify the app constructs without errors**

```bash
cd /home/takosaga/Projects/EuropaLex && python -c "import app; print('App module loads OK')"
```

Expected: `App module loads OK` (no traceback). Note: This does NOT launch the server.

- [ ] **Step 4: Commit**

```bash
git add app.py
git commit -m "feat: wire TextEngine, TTSEngine, ImageGenEngine into app.py two-phase workflow"
```

---

### Task 8: Update smoke_test.py and Final Verification

**Files:**
- Check: `scripts/smoke_test.py` (may need minor update)

- [ ] **Step 1: Read current smoke test and verify it still passes**

```bash
cd /home/takosaga/Projects/EuropaLex && python scripts/smoke_test.py
```

If it fails due to missing imports (e.g., `core.engine` or `core.types`), update the smoke test to import the new modules. The smoke test should NOT call engine methods — only verify that imports succeed and dataclasses/models are valid.

- [ ] **Step 2: Run full app construction check**

```bash
cd /home/takosaga/Projects/EuropaLex && python -c "
from core.types import CardData, CEFRLevel, EngineConfig, TextResult
from core.engine import TextEngine, TTSEngine, ImageGenEngine, EnginePool
print('All imports OK')
# Validate CardData can be constructed
card = CardData(text='Hello', translation='Sveiki', cefr_level=CEFRLevel.A1)
assert card.text == 'Hello'
assert card.translation == 'Sveiki'
print('CardData validation OK')
"
```

Expected: Both lines print successfully, no errors.

- [ ] **Step 3: Commit**

```bash
git add scripts/smoke_test.py core/engine.py core/types.py app.py requirements.txt
git commit -m "test: verify smoke test passes with new engine modules and types"
```

---

## Self-Review Checklist

**1. Spec coverage:**
- ✅ Pydantic types (CardData, TextResult, AudioResult, ImageResult, EngineConfig) → Tasks 2
- ✅ EnglishTextEngine (Nemotron subprocess) → Task 3
- ✅ TranslationEngine (TildeOpen subprocess) → Task 3
- ✅ TTSEngine (OmniVoice, lazy load/unload) → Task 4
- ✅ ImageGenEngine (diffusers, lazy load/unload) → Task 5
- ✅ EnginePool singleton with mutual exclusion → Task 6
- ✅ app.py integration (Phase 1 + Phase 2) → Task 7
- ✅ Dependencies → Task 1
- ✅ Smoke test verification → Task 8
- ✅ .apkg export via MCP noted as out-of-scope → documented in spec

**2. Placeholder scan:** No "TBD", "TODO", "implement later", "add validation" found. Every step has complete code blocks, exact commands, and expected output.

**3. Type consistency:** `TextResult.translations: list[str]` used consistently across TextEngine.generate(), TTSEngine.synthesize() callers, and CardData construction. `CEFRLevel` enum values match settings.yaml. `EngineConfig` fields align with settings.yaml keys.

**4. Scope check:** Focused on engine.py + types.py only. app.py wiring is included but minimal (just handler replacements). pipeline.py untouched. .apkg export explicitly out of scope.
