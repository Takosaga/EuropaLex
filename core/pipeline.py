"""EuropaLex Pipeline — Phase 2 orchestration.

Receives English texts generated in Phase 1 and produces translated
CardData objects via tiny-aya-water translation engine.

Images and audio are not yet wired — those fields remain empty.
"""

from __future__ import annotations

import logging
from typing import Iterator

from core.engine import EnginePool
from core.types import CEFRLevel, CardData, EngineConfig, ValidationError

logger = logging.getLogger(__name__)


def generate_phase2(
    texts: list[str],
    scenario: str,
    cefr_level: CEFRLevel,
    batch_size: int,
) -> Iterator[tuple[int, str, list[CardData]]]:
    """Generate Latvian translations for Phase 1 English texts.

    Orchestrates the translation pipeline: gets the tiny-aya engine,
    calls generate with retry validation, and yields CardData objects.

    Yields (progress_percent, phase_label, cards) at each step.

    Args:
        texts: English sentences generated in Phase 1.
        scenario: Original scenario/topic description.
        cefr_level: CEFR proficiency level.
        batch_size: Number of translations expected.

    Yields:
        (20, "Preparing translation...", []) — before engine call
        (60, "Translating...", []) — during generation
        (100, "Translation complete!", cards) — with final CardData list

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

    cards = [
        CardData(
            text=text,
            translation=translation,
            audio_path=None,
            image_path=None,
            cefr_level=cefr_level,
        )
        for text, translation in zip(texts, translations)
    ]

    yield 100, "Translation complete!", cards
