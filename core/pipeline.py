"""EuropaLex Pipeline — Phase 2 orchestration.

Receives English texts generated in Phase 1 and produces translated
CardData objects via tiny-aya-water translation engine, with optional
TTS audio generation using OmniVoice voice design mode.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterator

from core.engine import EnginePool
from core.types import CEFRLevel, CardData, EngineConfig, ValidationError

logger = logging.getLogger(__name__)


def generate_phase2(
    texts: list[str],
    scenario: str,
    cefr_level: CEFRLevel,
    batch_size: int,
    target_language: str = "Latvian",
    include_audio: bool = False,
) -> Iterator[tuple[int, str, list[CardData]]]:
    """Generate translations and optional TTS audio for Phase 1 English texts.

    Orchestrates the translation pipeline: gets the tiny-aya engine,
    calls generate with retry validation, optionally generates TTS audio
    for all translations via OmniVoice (voice design mode), and yields CardData objects.

    Yields (progress_percent, phase_label, cards) at each step.

    Args:
        texts: English sentences generated in Phase 1.
        scenario: Original scenario/topic description.
        cefr_level: CEFR proficiency level.
        batch_size: Number of translations expected.
        target_language: Target language name for TTS (e.g., "Latvian"). Used to improve synthesis quality.
        include_audio: If True, generate TTS audio for all translations after translation completes.

    Yields:
        (20, "Preparing translation...", []) — before engine call
        (15-70, "Translating... (N/total)", []) — during per-sentence translation
        (70, "Generating audio...", []) — before TTS starts (if include_audio=True)
        (95, "Audio complete!", cards) — after TTS batch (if include_audio=True)
        (100, "Translation and audio complete!", cards) — with final CardData list

    Raises:
        ValidationError: If translation fails after max retries.
    """
    try:
        config = EngineConfig.from_settings_yaml()
        pool = EnginePool.get(config)
    except FileNotFoundError as e:
        logger.error("Phase 2 model not found: %s", e)
        raise

    yield 20, "Preparing translation...", []

    try:
        engine = pool.get_translation_engine()
        translations: list[str] = []
        total = len(texts)

        for i, text in enumerate(texts):
            translated = engine._translate_single(text, cefr_level)
            translations.append(translated)
            # Stream progress after each sentence (15% base + per-sentence increment up to 55%)
            progress = 15 + int((i + 1) / total * 55)
            yield progress, f"Translating... ({i + 1}/{total})", []

    except ValidationError:
        raise

    audio_paths: list[str | None] = [None] * len(translations)

    if include_audio:
        yield 70, "Generating audio...", []
        try:
            tts_engine = pool.get_tts_engine()
            output_dir = Path(config.models_dir) / "output" / "audio"
            audio_result = tts_engine.synthesize(translations, output_dir, language=target_language)
            audio_paths = audio_result.audio_paths
        except Exception as e:
            logger.error("TTS generation failed: %s", e, exc_info=True)
            # Continue with None audio paths — cards still render with translations

    cards = [
        CardData(
            text=text,
            translation=translation,
            audio_path=audio_paths[i] if include_audio else None,
            image_path=None,
            cefr_level=cefr_level,
        )
        for i, (text, translation) in enumerate(zip(texts, translations))
    ]

    if include_audio:
        yield 100, "Translation and audio complete!", cards
    else:
        yield 100, "Translation complete!", cards
