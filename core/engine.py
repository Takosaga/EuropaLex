"""EuropaLex Inference Engine — Local model backends via llama-cli, llama-cpp-python, and Python packages."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

import numpy as np
import torch

from core.types import CEFRLevel, EngineConfig, TextResult, ValidationError

logger = logging.getLogger(__name__)

# Global pre-loaded engines for zeroGPU module-level loading
_engines: dict[str, Any] = {}
_preload_success = False

class _LazyEngineWrapper:
    """Lazy-loading fallback wrapper for engines that failed to pre-load."""
    
    def __init__(self, name: str, factory_func):
        self.name = name
        self.factory = factory_func
        self._engine = None
    
    def _get_engine(self):
        if self._engine is None:
            try:
                engine = self.factory()
                # Load the model into CUDA (emulation mode -> real GPU at runtime)
                if hasattr(engine, '_load_model'):
                    engine._load_model()
                elif hasattr(engine, '_load_pipeline'):
                    engine._load_pipeline()
                self._engine = engine
                logger.info("Loaded fallback %s engine", self.name)
            except Exception as e:
                raise RuntimeError(f"Failed to load {self.name} engine: {e}")
        return self._engine
    
    def __getattr__(self, item):
        return getattr(self._get_engine(), item)

def _preload_all_models() -> None:
    """Pre-load all inference models at module level. Falls back to lazy-loading if any fail."""
    global _preload_success
    if _preload_success:
        return
    
    from core.types import EngineConfig
    try:
        config = EngineConfig.from_settings_yaml()
    except Exception as e:
        logger.error("Failed to load settings: %s", e)
        # Create fallback wrappers with minimal info
        _preload_success = False  # will retry on first use
        return
    
    engines_to_load = [
        ('english', lambda: MiniCPMTextEngine(config.minicpm_model_path, config.device)),
        ('translation', lambda: LlamaCppTextEngine(config.llm_model_path, config.device, config.target_language)),
        ('tts', lambda: TTSEngine(device=config.device)),
        ('image', lambda: ImageGenEngine(device=config.device)),
    ]
    
    for name, factory in engines_to_load:
        try:
            engine = factory()
            # Force load the model into CUDA
            if hasattr(engine, '_load_model'):
                engine._load_model()
            elif hasattr(engine, '_load_pipeline'):
                engine._load_pipeline()
            else:
                logger.warning("Engine %s has no load method", name)
            _engines[name] = engine
            logger.info("Pre-loaded %s engine", name)
        except Exception as e:
            logger.error("Failed to pre-load %s engine: %s", name, e)
            # Create lazy fallback wrapper for this engine
            _engines[name] = _LazyEngineWrapper(name, factory)
    
    # Trigger actual GPU allocation (forces emulation mode -> real GPU)
    import torch
    if torch.cuda.is_available():
        try:
            torch.tensor([0], device='cuda')
        except Exception as e:
            logger.error("Failed to trigger CUDA allocation: %s", e)
    
    _preload_success = True
    logger.info("Pre-load complete. Engines: %s", list(_engines.keys()))




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

            try:
                output = self._llm.create_chat_completion(
                    messages=messages,
                    max_tokens=128,
                    temperature=0.3,
                )
            except Exception as e:
                # CUDA decode failures (e.g. ggml-cuda launch_mul_mat_q on SWA models)
                # are often fixed by reloading the model — the fresh context gets
                # proper CUDA graph warmup.
                logger.warning(
                    "LlamaCppTextEngine: decode failed on attempt %d for '%s': %s — reloading model and retrying",
                    attempt, text[:30], e,
                )
                self.unload()  # free GPU memory from stale CUDA state
                self._load_model()  # fresh load gets clean warmup
                continue

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


# TTSEngine has been extracted to core.audio_gen
from core.audio_gen import TTSEngine  # noqa: F401


# ImageGenEngine has been extracted to core.image_gen
from core.image_gen import ImageGenEngine  # noqa: F401


class EnginePool:
    """Singleton providing access to pre-loaded inference engines.

    Maintains backward compatibility with the old singleton factory pattern.
    Engines are pre-loaded at module import time via _preload_all_models().
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            raise RuntimeError(
                "EnginePool must be accessed via EnginePool.get(config), not directly."
            )
        return cls._instance

    @classmethod
    def get(cls, config: EngineConfig) -> "EnginePool":
        """Get or create the singleton EnginePool instance.

        Args:
            config: EngineConfig (not used for instantiation but kept for compatibility).

        Returns:
            The singleton EnginePool instance.
        """
        if cls._instance is None:
            instance = super().__new__(cls)
            instance._config = config
            cls._instance = instance
        return cls._instance

    def get_english_engine(self) -> MiniCPMTextEngine:
        """Get the pre-loaded English text generation engine."""
        return _engines['english']

    def get_translation_engine(self) -> LlamaCppTextEngine:
        """Get the pre-loaded translation engine."""
        return _engines['translation']

    def get_tts_engine(self) -> TTSEngine:
        """Get the pre-loaded TTS engine."""
        return _engines['tts']

    def get_image_engine(self) -> ImageGenEngine:
        """Get the pre-loaded image generation engine."""
        return _engines['image']

# Pre-load all models at module import time
_preload_all_models()
