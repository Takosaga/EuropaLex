"""EuropaLex Core Types — Pydantic models for type-safe data boundaries."""

from __future__ import annotations

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


class TextResult(BaseModel):
    """Output from a text generation engine."""

    translations: list[str]  # One per input text, in order


class AudioResult(BaseModel):
    """Output from TTS generation."""

    audio_paths: list[str] | None = None  # One per input text, absolute paths to .wav files


class ImageResult(BaseModel):
    """Output from image generation."""

    image_paths: list[str] | None = None  # One per prompt, absolute paths to .png files


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
