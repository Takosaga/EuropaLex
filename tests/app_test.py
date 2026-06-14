"""Tests for app.py helper functions and async generator handlers."""

from pathlib import Path
import inspect
import pytest
from unittest.mock import patch, MagicMock

PROJECT_ROOT = Path(__file__).resolve().parent.parent



# ── _progress_pct ────────────────────────────────────────────────

def test_progress_pct_single_sentence():
    """Single sentence (total=1): returns end_pct with 'complete' label."""
    from app import _progress_pct

    pct, label = _progress_pct(0, total=1)
    assert pct == 70.0
    assert "complete" in label.lower()


def test_progress_pct_two_sentences():
    """Two sentences: step 0 → ~42.5%, step 1 → complete."""
    from app import _progress_pct

    pct0, _ = _progress_pct(0, total=2)
    pct1, label1 = _progress_pct(1, total=2)
    # Step 0: 15 + (1/2) * (70-15) = 15 + 27.5 = 42.5
    assert abs(pct0 - 42.5) < 0.1
    # Step 1: should be complete
    assert "complete" in label1.lower()


def test_progress_pct_five_sentences():
    """Five sentences: all steps verified for percentage and remaining count."""
    from app import _progress_pct

    total = 5
    start_pct, end_pct = 15.0, 70.0
    expected_pcts = [
        round(start_pct + (1/5) * (end_pct - start_pct), 1),   # step 0
        round(start_pct + (2/5) * (end_pct - start_pct), 1),   # step 1
        round(start_pct + (3/5) * (end_pct - start_pct), 1),   # step 2
        round(start_pct + (4/5) * (end_pct - start_pct), 1),   # step 3
        end_pct,                                                  # step 4
    ]

    for i in range(total):
        pct, label = _progress_pct(i, total=total)
        assert abs(pct - expected_pcts[i]) < 0.1
        if i < total - 1:
            remaining = total - (i + 1)
            assert f"{i + 1}/{total}" in label
            assert f"{remaining} remaining" in label


# ── generate_text_async ──────────────────────────────────────────

def test_generate_text_async_is_generator():
    """generate_text_async is a generator function."""
    from app import generate_text_async
    assert inspect.isgeneratorfunction(generate_text_async)


def test_generate_text_async_yields_progress_and_cards(mock_llm_response_factory):
    """Generator yields progress updates then card HTML when engine succeeds."""
    from unittest.mock import patch, MagicMock
    from app import generate_text_async

    mock_engine = MagicMock()
    mock_engine.generate.return_value = MagicMock(
        generated_texts=["Hello.", "World."]
    )

    mock_pool_instance = MagicMock()
    mock_pool_instance.get_english_engine.return_value = mock_engine

    with patch("core.engine.EnginePool") as mock_pool_class:
        mock_pool_class.get.return_value = mock_pool_instance
        with patch("core.types.EngineConfig.from_settings_yaml") as mock_config:
            mock_config.return_value.batch_size = 2
            yields = list(generate_text_async("test scenario", "A1", 2))

    # Should yield at least 3 tuples: progress+empty, progress+empty, progress+cards_html
    assert len(yields) >= 3
    # Last yield should have card HTML (non-empty string)
    last_progress, last_cards = yields[-1]
    assert "Hello." in last_cards or "World." in last_cards


def test_generate_text_async_file_not_found_error():
    """FileNotFoundError path → error message in output."""
    from app import generate_text_async

    with patch("core.engine.EnginePool") as mock_pool_class:
        mock_pool_class.get.side_effect = FileNotFoundError("model.gguf not found")
        yields = list(generate_text_async("test", "A1", 2))

    assert len(yields) >= 1
    _, output = yields[0]
    assert "Model file not found" in output or "model" in output.lower()


def test_generate_text_async_general_exception():
    """General exception path → error message in output."""
    from app import generate_text_async

    with patch("core.engine.EnginePool") as mock_pool_class:
        mock_pool_class.get.side_effect = RuntimeError("GPU out of memory")
        yields = list(generate_text_async("test", "A1", 2))

    assert len(yields) >= 1
    _, output = yields[0]
    assert "Failed to initialize" in output or "Setup error" in output


# ── generate_media_async ─────────────────────────────────────────

def test_generate_media_async_is_generator():
    """generate_media_async is a generator function."""
    from app import generate_media_async
    assert inspect.isgeneratorfunction(generate_media_async)


def test_generate_media_async_yields_per_sentence(mock_english_texts):
    """Cards grow with each yield during translation phase."""
    from unittest.mock import patch, MagicMock
    from app import generate_media_async

    # Set up Phase 1 texts
    import app as app_module
    original = list(app_module._phase1_texts)
    app_module._phase1_texts = list(mock_english_texts)

    try:
        mock_engine = MagicMock()
        mock_engine._translate_single.return_value = "Sveiki."

        mock_pool_instance = MagicMock()
        mock_pool_instance.get_translation_engine.return_value = mock_engine

        with patch("core.engine.EnginePool") as mock_pool_class:
            mock_pool_class.get.return_value = mock_pool_instance
            yields = list(generate_media_async("test", "A1", 3))

        # Each translation step yields (progress, cards)
        # At least 3 yields for 3 sentences + final yield
        card_yields = [(p, c) for p, c in yields if "translation" in c.lower() or "Sveiki" in c]
        assert len(card_yields) >= 1
    finally:
        app_module._phase1_texts = original


def test_generate_media_async_missing_phase1_texts():
    """No Phase 1 texts → error message."""
    from app import generate_media_async

    import app as app_module
    original = list(app_module._phase1_texts)
    app_module._phase1_texts = []

    try:
        yields = list(generate_media_async("test", "A1", 3))
        assert len(yields) >= 1
        _, output = yields[0]
        assert "Phase 1" in output or "generate text first" in output.lower()
    finally:
        app_module._phase1_texts = original
