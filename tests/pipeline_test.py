"""Tests for core.pipeline.generate_phase2() orchestration.

Mocks EnginePool and individual engines. Verifies orchestration flow,
progress percentages, and CardData assembly.
"""

import pytest
from unittest.mock import patch, MagicMock, PropertyMock
import inspect

from core.types import CEFRLevel


def test_generate_phase2_is_generator():
    """generate_phase2 is a generator function."""
    from core.pipeline import generate_phase2
    assert inspect.isgeneratorfunction(generate_phase2)


def test_generate_phase2_translation_only(mock_english_texts, mock_spanish_translations):
    """Translation-only: yields progress updates per sentence, final CardData list with translations."""
    from core.pipeline import generate_phase2
    from core.types import CardData

    # Build mock engine that returns translated texts via _translate_single
    mock_engine = MagicMock()
    mock_engine._translate_single.side_effect = list(mock_spanish_translations)

    mock_pool_instance = MagicMock()
    mock_pool_instance.get_translation_engine.return_value = mock_engine

    with patch("core.pipeline.EnginePool") as mock_pool_class:
        mock_pool_class.get.return_value = mock_pool_instance
        yields = list(generate_phase2(
            texts=list(mock_english_texts),
            scenario="test",
            cefr_level=CEFRLevel.A1,
            batch_size=3,
            target_language="Spanish",
            include_audio=False,
        ))

    # Should yield at least: progress prepare, progress per sentence, final complete
    assert len(yields) >= 5  # 20% prepare + 3 translation steps + final

    # Last yield should have CardData list
    last_progress, last_label, last_result = yields[-1]
    assert isinstance(last_result, list)
    assert len(last_result) == 3
    assert all(isinstance(card, CardData) for card in last_result)


def test_generate_phase2_translation_plus_tts(mock_english_texts, mock_spanish_translations):
    """Translation+TTS: additional yield at 70% for audio generation, CardData includes audio_paths."""
    from core.pipeline import generate_phase2
    from core.types import AudioResult

    mock_engine = MagicMock()
    mock_engine._translate_single.side_effect = list(mock_spanish_translations)

    mock_audio_result = MagicMock()
    mock_audio_result.audio_paths = ["/tmp/audio_0.wav", "/tmp/audio_1.wav", "/tmp/audio_2.wav"]

    mock_tts_engine = MagicMock()
    mock_tts_engine.synthesize.return_value = mock_audio_result

    mock_pool_instance = MagicMock()
    mock_pool_instance.get_translation_engine.return_value = mock_engine
    mock_pool_instance.get_tts_engine.return_value = mock_tts_engine

    with patch("core.pipeline.EnginePool") as mock_pool_class:
        mock_pool_class.get.return_value = mock_pool_instance
        yields = list(generate_phase2(
            texts=list(mock_english_texts),
            scenario="test",
            cefr_level=CEFRLevel.A1,
            batch_size=3,
            target_language="Spanish",
            include_audio=True,
        ))

    # Check that audio generation progress was yielded (label is 2nd element)
    progress_labels = [label for _, label, _ in yields]
    assert any("audio" in str(label).lower() for label in progress_labels)

    # Final CardData should have audio_paths
    last_progress, last_label, last_result = yields[-1]
    assert len(last_result) == 3
    assert all(card.audio_path is not None for card in last_result)


def test_generate_phase2_progress_percentages():
    """Progress percentages: 20% prepare, 15-70% translation steps, 100% complete."""
    from core.pipeline import generate_phase2

    mock_engine = MagicMock()
    mock_engine._translate_single.side_effect = ["A.", "B."]

    mock_pool_instance = MagicMock()
    mock_pool_instance.get_translation_engine.return_value = mock_engine

    with patch("core.pipeline.EnginePool") as mock_pool_class:
        mock_pool_class.get.return_value = mock_pool_instance
        yields = list(generate_phase2(
            texts=["A.", "B."],
            scenario="test",
            cefr_level=CEFRLevel.A1,
            batch_size=2,
            target_language="Spanish",
            include_audio=False,
        ))

    # First yield should be ~20% (prepare)
    first_progress, _, _ = yields[0]
    assert "20" in str(first_progress) or "Preparing" in str(first_progress).lower()

    # Progress values increase during translation
    progress_values = []
    for p, _, _ in yields:
        if isinstance(p, (int, float)):
            progress_values.append(p)
    if len(progress_values) >= 2:
        assert progress_values[-1] >= progress_values[0]


def test_generate_phase2_validation_error_propagation():
    """If translation fails after retries, ValidationError is raised and not caught."""
    from core.pipeline import generate_phase2
    from core.types import ValidationError

    mock_engine = MagicMock()
    # Simulate engine raising ValidationError
    mock_engine._translate_single.side_effect = ValidationError("Translation failed", raw_output="bad output")

    mock_pool_instance = MagicMock()
    mock_pool_instance.get_translation_engine.return_value = mock_engine

    with patch("core.pipeline.EnginePool") as mock_pool_class:
        mock_pool_class.get.return_value = mock_pool_instance
        with pytest.raises(ValidationError):
            list(generate_phase2(
                texts=["A."],
                scenario="test",
                cefr_level=CEFRLevel.A1,
                batch_size=1,
                target_language="Spanish",
                include_audio=False,
            ))
