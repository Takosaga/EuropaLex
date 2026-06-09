"""EuropaLex Inference Engine — Local model backends via llama-cli and Python packages."""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

import numpy as np
import soundfile as sf
import torch
from pathlib import Path

from core.types import CEFRLevel, EngineConfig, TextResult

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
    _state: _EngineState

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
