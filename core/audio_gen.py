"""EuropaLex Text-to-Speech Engine — OmniVoice via omnivoice Python package."""

from __future__ import annotations

import logging
from pathlib import Path

import soundfile as sf
import torch

from core.types import AudioResult

logger = logging.getLogger(__name__)


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

    def synthesize(
        self,
        texts: list[str],
        output_dir: Path,
        language: str | None = None,
        instruct: str | None = None,
    ) -> AudioResult:
        """Generate audio for a batch of texts using voice design mode.

        Uses OmniVoice in voice design mode with a consistent female voice.
        Optionally accepts a target language for improved synthesis quality.

        Args:
            texts: List of text strings to convert to speech.
            output_dir: Directory to save .wav files.
            language: Target language name for TTS (e.g., "Latvian", "Spanish").
                Improves synthesis quality when known. Defaults to None (auto-detect).
            instruct: OmniVoice voice design string (e.g., "female, young adult").
                Defaults to "female, young adult" when omitted.

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
                    instruct=instruct or "female, young adult",
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
