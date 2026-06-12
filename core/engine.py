"""EuropaLex Inference Engine — Local model backends via llama-cli, llama-cpp-python, and Python packages."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

import numpy as np
import soundfile as sf
import torch

from core.types import AudioResult, CEFRLevel, EngineConfig, ImageResult, TextResult, ValidationError

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
    Uses create_chat_completion to format prompts with MiniCPM's required message tokens.
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

    def generate(
        self,
        texts: list[str],
        scenario: str,
        cefr_level: CEFRLevel,
        batch_size: int | None = None,
        topic_description: str = "",
    ) -> TextResult:
        """Generate English sentences using the loaded GGUF model.

        Delegates to :func:`core.text_gen.generate_sentences` for LLM calling,
        retry loop, and extraction. Wraps result in ``TextResult``.

        Args:
            texts: Empty list (generation mode). Non-empty would be translation mode.
            scenario: Scenario/topic description for text generation.
            cefr_level: CEFR proficiency level (linguistic guidance only).
            batch_size: Number of sentences to generate.
            topic_description: Free-form description of topics/themes.

        Returns:
            TextResult with exactly one sentence per requested batch size.

        Raises:
            ValidationError: If generation fails after max attempts.
        """
        self._load_model()
        if batch_size is None:
            raise ValueError("batch_size is required for text generation")

        from core.text_gen import generate_sentences

        sentences = generate_sentences(scenario, cefr_level, batch_size, self._llm, topic_description)
        return TextResult(generated_texts=sentences)

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

    def __init__(
        self,
        model_path: str,
        device: str = "cuda",
        target_language: str = "Latvian",
    ):
        """Initialize the translation engine.

        Args:
            model_path: Absolute path to the GGUF model file.
            device: Device hint (informational; n_gpu_layers=99 used for CUDA).
            target_language: Target language for translations (e.g. "Latvian").
        """
        self.model_path = Path(model_path)
        if not self.model_path.exists():
            raise FileNotFoundError(f"Model not found: {self.model_path}")
        self.device = device
        self.target_language = target_language
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

    def _translate_single(
        self,
        text: str,
        cefr_level: CEFRLevel,
        topic_description: str = "",
        target_language: str | None = None,
    ) -> str:
        """Translate a single English sentence with retry loop.

        Uses ``create_chat_completion`` so the model's chat template (with
        special tokens like ``<|USER_TOKEN|>``) is applied correctly. Raw
        prompt strings bypass the chat template and produce poor output.

        Wraps the LLM call in a retry loop (max 3 attempts). Returns the
        translated string or falls back to the original English text on failure.

        Args:
            text: Single English sentence to translate.
            cefr_level: CEFR proficiency level (linguistic guidance only).
            topic_description: Free-form description of topics/themes (for context).
            target_language: Override target language for this call only.
                Defaults to ``self.target_language`` from config.

        Returns:
            Translated string, or the original English text as fallback.
        """
        self._load_model()
        effective_lang = target_language or self.target_language
        base_messages = [
            {
                "role": "system",
                "content": (
                    f"You are a professional translator. Translate English sentences into "
                    f"{effective_lang} at the specified CEFR level. Output ONLY the translation, "
                    f"one line. No explanations, no notes, no source text repetition."
                ),
            }
        ]
        last_messages: list = []

        for attempt in range(1, 4):
            messages = list(base_messages)
            if attempt > 1 and last_messages:
                # Append failed output + retry instruction in conversation context
                messages.extend(last_messages)

            messages.append({
                "role": "user",
                "content": self._build_single_translation_prompt(
                    text, cefr_level, topic_description, effective_lang,
                ),
            })

            output = self._llm.create_chat_completion(
                messages=messages,
                max_tokens=128,
                temperature=0.3,
            )

            raw_text = output.get("choices", [{}])[0].get("message", {}).get("content", "")
            last_messages = [
                {"role": "assistant", "content": raw_text},
            ]
            line = raw_text.strip()

            # Validate: must be a single non-empty line, not repetitive garbage
            if line and self._is_valid_translation(line):
                logger.info(
                    "LlamaCppTextEngine: translated '%s' on attempt %d -> '%s'",
                    text[:30], attempt, line[:40],
                )
                return line

            # Invalid output — retry with stricter prompt in context
            if attempt < 3:
                last_messages.append({
                    "role": "user",
                    "content": (
                        f"That output was invalid. Translate ONLY this sentence into {effective_lang}:\n"
                        f"{text}\n\n"
                        f"Output ONE line only — the translation. Nothing else."
                    ),
                })
                logger.warning(
                    "LlamaCppTextEngine attempt %d: invalid output for '%s' — retrying",
                    attempt, text[:30],
                )
            else:
                logger.warning(
                    "LlamaCppTextEngine: exhausted retries for '%s'. Falling back to English.",
                    text[:30],
                )

        # Exhausted retries — fall back to original English text
        logger.info("LlamaCppTextEngine: fallback to English for '%s'", text[:30])
        return text

    def _is_valid_translation(self, line: str) -> bool:
        """Check if a translation output is valid (single line, not repetitive garbage).

        Args:
            line: The raw model output to validate.

        Returns:
            True if the output looks like a reasonable translation.
        """
        if not line or len(line) < 2:
            return False

        # Reject if it contains multiple lines (model generated too much)
        if "\n" in line:
            return False

        # Reject if it's just the English text back (no translation happened)
        lower = line.lower()
        if any(word in lower for word in ["translate", "translation", "english"]):
            return False

        # Reject very short outputs that are likely noise
        words = line.split()
        if len(words) < 1:
            return False

        return True

    def generate(
        self,
        texts: list[str],
        scenario: str,
        cefr_level: CEFRLevel,
        batch_size: int | None = None,
        topic_description: str = "",
    ) -> TextResult:
        """Generate translations using the loaded GGUF model.

        Translates each sentence individually for better quality with small models.
        Falls back to English text on failure (after max retries).

        Args:
            texts: English sentences to translate.
            scenario: Scenario/topic description (contextual).
            cefr_level: CEFR proficiency level (linguistic guidance only).
            batch_size: Number of translations expected.
            topic_description: Free-form description of topics/themes (contextual).

        Returns:
            TextResult with one translation per input text.

        Raises:
            ValidationError: If generation fails after max attempts and no lines produced.
        """
        self._load_model()
        if batch_size is None:
            raise ValueError("batch_size is required for translation")

        translations = []
        for text in texts:
            translated = self._translate_single(text, cefr_level, topic_description)
            translations.append(translated)

        return TextResult(generated_texts=translations)

    def _build_single_translation_prompt(
            self,
            text: str,
            cefr_level: CEFRLevel,
            topic_description: str = "",
            target_language: str | None = None,
    ) -> str:
        """Build prompt for translating a single sentence.

        Optimized for small models (tiny-aya-water ~3.3B params). Produces
        natural, idiomatic output by emphasizing how native speakers actually
        phrase things — not literal word-for-word translation.

        Uses CEFR linguistic guidance only — no hardcoded topics.

        Args:
            text: English sentence to translate.
            cefr_level: CEFR proficiency level.
            topic_description: Free-form context for the translation.
            target_language: Language to translate into. Defaults to ``self.target_language``.
        """
        target_lang = target_language or self.target_language
        cefr_desc = cefr_level.description()
        topic_hint = f" Context: {topic_description}." if topic_description else ""
        return (
            f"Translate the following English sentence into {target_lang}.{topic_hint}\n"
            f"CEFR linguistic guidance: {cefr_desc}.\n\n"
            f"CRITICAL — NATURAL LANGUAGE RULES:\n"
            f"1. Produce how a native speaker at this CEFR level would naturally express this idea in {target_lang}.\n"
            f"2. Do NOT translate word-for-word. Capture the meaning and rephrase it naturally in {target_lang}.\n"
            f"3. Use common idiomatic expressions, colloquial phrasing, and everyday vocabulary appropriate for the level.\n"
            f"4. Follow the grammar patterns typical of {target_lang} — not English sentence structure.\n"
            f"5. If the English uses an awkward or literal construction, render it as a native speaker would say it.\n\n"
            f"Rules:\n"
            f"1. Output ONLY the translated sentence — one line, nothing else.\n"
            f"2. Do NOT include explanations, notes, labels, or quotation marks.\n"
            f"3. Do NOT repeat the English text in your output.\n"
            f"4. Match the CEFR linguistic complexity for the target level.\n\n"
            f"English: {text}\n"
            f"{target_lang}:"
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
        """Lazy-load the OmniVoice model from HF Hub (cached locally)."""
        if self._loaded:
            return

        try:
            from omnivoice import OmniVoice
        except ImportError:
            raise ImportError(
                "omnivoice package not installed. Run: pip install omnivoice"
            )

        logger.info("Loading OmniVoice from HF Hub (cached in ~/.cache/huggingface/)")
        self._model = OmniVoice.from_pretrained(
            "k2-fsa/OmniVoice",
            device_map=self.device,
            dtype=torch.float16 if self.device != "cpu" else torch.float32,
        )
        self._loaded = True
        logger.info("OmniVoice model loaded on %s", self.device)

    def synthesize(self, texts: list[str], output_dir: Path, language: str | None = None) -> AudioResult:
        """Generate audio for a batch of texts using voice design mode.

        Uses OmniVoice in voice design mode with a consistent female voice.
        Optionally accepts a target language for improved synthesis quality.

        Args:
            texts: List of text strings to convert to speech.
            output_dir: Directory to save .wav files.
            language: Target language name for TTS (e.g., "Latvian", "Spanish").
                Improves synthesis quality when known. Defaults to None (auto-detect).

        Returns:
            AudioResult with absolute paths to generated audio files.
        """
        self._load_model()
        output_dir.mkdir(parents=True, exist_ok=True)

        audio_paths = []
        for i, text in enumerate(texts):
            try:
                audio_data = self._model.generate(
                    text=text,
                    instruct="female",
                    language=language,
                )
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

        return AudioResult(audio_paths=list(audio_paths))

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
        """Lazy-load the Flux2Klein pipeline from HF Hub (cached locally)."""
        if self._loaded:
            return

        try:
            from diffusers import Flux2KleinPipeline
        except ImportError:
            raise ImportError(
                "diffusers package not installed. Run: pip install diffusers"
            )

        torch_dtype = torch.bfloat16 if self.device == "cuda" else torch.float32
        logger.info("Loading Flux2Klein from HF Hub (cached in ~/.cache/huggingface/)")
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

        return ImageResult(image_paths=list(image_paths))

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
                target_language=self._config.target_language,
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
