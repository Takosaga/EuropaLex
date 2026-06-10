"""EuropaLex Inference Engine — Local model backends via llama-cli, llama-cpp-python, and Python packages."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

import numpy as np
import soundfile as sf
import torch

from core.types import CEFRLevel, EngineConfig, TextResult

logger = logging.getLogger(__name__)


@dataclass
class _EngineState:
    """Tracks which GPU engine is currently loaded."""

    translation_engine: LlamaCppTextEngine | None = None
    tts_engine: TTSEngine | None = None
    image_engine: ImageGenEngine | None = None


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


class LlamaCppTextEngine:
    """Generates text using llama-cpp-python (GGUF models, lazy-load + unload).

    Uses the llama-cpp-python Python bindings instead of spawning subprocesses.
    Lazy-loads the model on first call, unloads after completion to free VRAM.
    Only one instance can be active at a time (enforced by EnginePool).

    Best for smaller GGUF models (e.g. tiny-aya-water Q4_K_M ~2 GB) where
    keeping the model in Python memory is efficient and avoids subprocess overhead.
    """

    def __init__(self, model_path: str, device: str = "cuda"):
        """Initialize the translation engine.

        Args:
            model_path: Absolute path to the GGUF model file.
            device: Device hint (informational; n_gpu_layers=99 used for CUDA).
        """
        self.model_path = Path(model_path)
        if not self.model_path.exists():
            raise FileNotFoundError(f"Model not found: {self.model_path}")
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
        logger.info("LlamaCppTextEngine loaded %s on %s", self.model_path.name, self.device)

    def generate(self, texts: list[str], scenario: str, cefr_level: CEFRLevel, batch_size: int | None = None) -> TextResult:
        """Generate translations using the loaded GGUF model.

        Args:
            texts: English sentences to translate.
            scenario: Scenario/topic description (not used with this model).
            cefr_level: CEFR proficiency level.
            batch_size: Not used.

        Returns:
            TextResult with one translation per input text.

        Raises:
            RuntimeError: If generation fails.
        """
        self._load_model()
        prompt = self._build_translation_prompt(texts, cefr_level)

        output = self._llm(
            prompt=prompt,
            max_tokens=512,
            temperature=0.7,
            echo=False,
        )

        text = output.get("choices", [{}])[0].get("text", "")
        lines = [line.strip() for line in text.strip().split("\n") if line.strip()]
        return TextResult(translations=lines)

    def _build_translation_prompt(self, texts: list[str], cefr_level: CEFRLevel) -> str:
        """Build prompt for translation."""
        text_lines = "\n".join(texts)
        target_lang = "Latvian"  # Default; can be parameterized later
        return (
            f"You are a translator. Translate the following {cefr_level.value} English text into {target_lang}.\n"
            f"Translate these sentences, one per line, in order:\n"
            f"{text_lines}\n"
            "Output ONLY the translations, one per line. No explanations."
        )

    def unload(self) -> None:
        """Unload the model and free GPU memory."""
        if self._llm is not None:
            del self._llm
            self._llm = None
            self._loaded = False
            try:
                torch.cuda.empty_cache()
            except Exception:
                pass
            logger.info("LlamaCppTextEngine unloaded")


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

    Ensures only one GPU model (LlamaCppTextEngine, TTSEngine, or ImageGenEngine)
    is loaded at a time. Text engines that use llama-cli subprocesses do not
    consume persistent VRAM.

    Usage:
        pool = EnginePool.get(config)
        text_result = pool.get_translation_engine().generate(texts, scenario, cefr_level)
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
            cls._instance._unload_translation()
            cls._instance._unload_tts()
            cls._instance._unload_image()
            cls._instance = None

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

    def get_translation_engine(self) -> LlamaCppTextEngine:
        """Get or create the translation engine (tiny-aya-water via llama-cpp-python).

        Unloads any active GPU engines before loading. The same instance is returned
        on subsequent calls until explicitly unloaded.
        """
        self._ensure_exclusive("translation")
        if self._state.translation_engine is None:
            self._state.translation_engine = LlamaCppTextEngine(
                model_path=self._config.llm_model_path,
                device=self._config.device,
            )
        return self._state.translation_engine

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
            self._unload_translation()
            self._unload_tts()
            self._unload_image()
            self._unload_english()
        elif target == "translation":
            self._unload_tts()
            self._unload_image()
        elif target == "tts":
            self._unload_translation()
            self._unload_image()
        elif target == "image":
            self._unload_translation()
            self._unload_tts()

    def _unload_translation(self) -> None:
        """Unload the translation engine if active."""
        if self._state.translation_engine is not None:
            self._state.translation_engine.unload()
            self._state.translation_engine = None

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

    def _unload_english(self) -> None:
        """Unload the English text engine if active."""
        # MiniCPMTextEngine instances are per-call (stateless), but we track
        # any loaded model state to ensure clean GPU memory.
        try:
            torch.cuda.empty_cache()
        except Exception:
            pass
