"""EuropaLex Core Types — Pydantic models for type-safe data boundaries."""

from __future__ import annotations

import re
from enum import Enum
from pathlib import Path
from typing import ClassVar

import yaml
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


class ValidationError(RuntimeError):
    """Raised when raw LLM output fails structural validation.

    Mirrors the ai-pr-enricher-softmax pattern of a custom error type
    for AI output validation failures instead of generic exceptions.
    """

    def __init__(self, message: str, raw_output: str | None = None):
        super().__init__(message)
        self.raw_output = raw_output


class TextResult(BaseModel):
    """Structured output from a text-generation engine.

    The ``generated_texts`` field is always a non-empty list — never None.
    Use the classmethod ``validate_and_parse()`` to convert raw LLM output
    through the thinking-tag stripper and line-count gate before accessing
    this model directly.
    """

    generated_texts: list[str] = Field(
        default_factory=list,
        description="One sentence per requested batch size, in order",
    )

    @classmethod
    def validate_and_parse(
        cls,
        raw_text: str,
        expected_count: int | None = None,
    ) -> TextResult:
        """Validate and parse raw LLM output into a structured TextResult.

        Strips any ``<thinking>...</thinking>`` block, splits on newlines,
        and optionally enforces an exact sentence count. Mirrors the
        ai-pr-enricher-softmax pattern where a validation gate sits
        between the raw model response and downstream typed consumers.

        Args:
            raw_text: Raw string returned by the LLM (may contain thinking tags).
            expected_count: If set, raises ValidationError when line count
                does not match. Pass ``batch_size`` here for strict mode.

        Returns:
            TextResult with cleaned, validated lines.

        Raises:
            ValidationError: When ``expected_count`` is set and the line
                count doesn't match, or when no valid lines remain after
                stripping thinking tags.
        """
        # Strip <thinking>...</thinking> blocks (greedy across newlines)
        cleaned = re.sub(r"<thinking>.*?</thinking>", "", raw_text, flags=re.DOTALL).strip()
        lines = [line.strip() for line in cleaned.split("\n") if line.strip()]

        if not lines:
            raise ValidationError(
                "LLM output contained no valid sentences after stripping thinking tags.",
                raw_output=raw_text,
            )

        if expected_count is not None and len(lines) != expected_count:
            raise ValidationError(
                f"Expected {expected_count} sentences but got {len(lines)}. "
                f"Last output: {raw_text!r}",
                raw_output=raw_text,
            )

        return cls(generated_texts=lines)


class AudioResult(BaseModel):
    """Output from TTS generation.

    ``audio_paths`` is always a list (never None) — empty when no audio was
    generated. Mirrors the ai-pr-enricher-softmax convention of using
    ``default_factory=list`` so downstream code never sees None checks.
    """

    audio_paths: list[str | None] = Field(
        default_factory=list,
        description="Absolute paths to generated .wav files, one per input text (None if failed)",
    )


class ImageResult(BaseModel):
    """Output from image generation.

    ``image_paths`` is always a list (never None) — empty when no images were
    generated. Mirrors the ai-pr-enricher-softmax convention of using
    ``default_factory=list`` so downstream code never sees None checks.
    """

    image_paths: list[str | None] = Field(
        default_factory=list,
        description="Absolute paths to generated .png files, one per prompt (None if failed)",
    )


class EngineConfig(BaseModel):
    """Validated engine configuration loaded from settings.yaml."""

    models_dir: str = ".local/models"
    llm_model_path: str  # Path to TildeOpen GGUF file
    minicpm_model_path: str  # Path to MiniCPM5-1B Q8_0 GGUF file
    device: str = "cuda"  # "cuda", "mps", or "cpu"
    batch_size: int = 3

    # llama-cli generation parameters (Nemotron / TextEngine)
    n_ctx: int = 4096  # Context length in tokens
    n_threads: int = 5  # CPU thread pool size
    n_batch: int = 4096  # Evaluation batch size
    top_k: int = 40  # Top-K sampling
    repeat_penalty: float = 1.1  # Repeat penalty
    top_p: float = 0.9  # Top-P (nucleus) sampling
    min_p: float = 0.05  # Min-P sampling
    temperature: float = 0.7  # Generation temperature
    max_tokens: int = 512  # Maximum response length

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
        with open(path, "r") as f:
            raw = yaml.safe_load(f)

        models = raw.get("models", {})
        batch = raw.get("batch", {})

        try:
            import torch
            if torch.cuda.is_available():
                device = "cuda"
            elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                device = "mps"
            else:
                device = "cpu"
        except ImportError:
            pass  # torch not installed yet; default to cuda

        # Resolve LLM model path — supports both GGUF (llama-cli) and transformers runtimes
        llm_cfg = models.get("tiny_aya") # or models.get("tildeopen")
        llm_runtime = llm_cfg.get("runtime", "llama-cli") if llm_cfg else "llama-cli"
        llm_subdir = "tiny_aya" if llm_runtime in ("transformers", "llama-cpp-python") else ("tildeopen" if llm_cfg else "tildeopen")

        gen = raw.get("generation", {})

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
