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
