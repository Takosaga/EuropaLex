"""Tests for core.audio_gen.TTSEngine."""

from pathlib import Path
from unittest.mock import patch, MagicMock, call
import pytest

from core.audio_gen import TTSEngine
from core.types import AudioResult


def test_tts_engine_synthesize_success(mock_audio_paths, temp_output_dir):
    """Success path: mock model returns audio data → .wav file written, path in result."""
    engine = TTSEngine(device="cpu")

    mock_model = MagicMock()
    # Simulate model returning numpy-like audio data (48000 samples at 24kHz = 2 seconds)
    import numpy as np
    mock_model.generate.return_value = [np.zeros(48000, dtype=np.float32)]

    with patch.object(engine, "_load_model"):
        engine._model = mock_model
        engine._loaded = True

        result = engine.synthesize(
            texts=["Hello.", "World."],
            output_dir=temp_output_dir,
            language="English",
            instruct="female, young adult",
        )

    assert isinstance(result, AudioResult)
    assert len(result.audio_paths) == 2
    assert result.audio_paths[0] is not None
    assert result.audio_paths[1] is not None
    assert Path(result.audio_paths[0]).exists()
    assert Path(result.audio_paths[1]).exists()
    assert mock_model.generate.call_count == 2


def test_tts_engine_synthesize_failure_path(temp_output_dir):
    """Failure path: mock model raises exception → None in result list."""
    engine = TTSEngine(device="cpu")

    mock_model = MagicMock()
    mock_model.generate.side_effect = RuntimeError("GPU OOM")

    with patch.object(engine, "_load_model"):
        engine._model = mock_model
        engine._loaded = True

        result = engine.synthesize(
            texts=["Hello.", "World."],
            output_dir=temp_output_dir,
        )

    assert len(result.audio_paths) == 2
    assert result.audio_paths[0] is None
    assert result.audio_paths[1] is None


def test_tts_engine_synthesize_empty_input(temp_output_dir):
    """Empty input list: returns empty AudioResult."""
    engine = TTSEngine(device="cpu")

    with patch.object(engine, "_load_model"):
        result = engine.synthesize(
            texts=[],
            output_dir=temp_output_dir,
        )

    assert isinstance(result, AudioResult)
    assert result.audio_paths == []


def test_tts_engine_synthesize_language_and_instruct_passed(temp_output_dir):
    """Language and instruct parameters passed to model.generate()."""
    engine = TTSEngine(device="cpu")

    mock_model = MagicMock()
    mock_model.generate.return_value = [MagicMock()]

    with patch.object(engine, "_load_model"):
        engine._model = mock_model
        engine._loaded = True

        engine.synthesize(
            texts=["Test"],
            output_dir=temp_output_dir,
            language="Latvian",
            instruct="male, middle-aged",
        )

    mock_model.generate.assert_called_once()
    call_kwargs = mock_model.generate.call_args[1]
    assert call_kwargs["language"] == "Latvian"
    assert call_kwargs["instruct"] == "male, middle-aged"


def test_tts_engine_synthesize_default_instruct(temp_output_dir):
    """Default instruct is 'female, young adult' when omitted."""
    engine = TTSEngine(device="cpu")

    mock_model = MagicMock()
    mock_model.generate.return_value = [MagicMock()]

    with patch.object(engine, "_load_model"):
        engine._model = mock_model
        engine._loaded = True

        engine.synthesize(
            texts=["Test"],
            output_dir=temp_output_dir,
            language="English",
        )

    call_kwargs = mock_model.generate.call_args[1]
    assert call_kwargs["instruct"] == "female, young adult"


def test_tts_engine_unload():
    """Model deleted, _loaded reset to False, torch.cuda.empty_cache() called."""
    engine = TTSEngine(device="cuda")

    mock_model = MagicMock()
    engine._model = mock_model
    engine._loaded = True

    with patch("torch.cuda.empty_cache") as mock_empty:
        engine.unload()

    assert engine._model is None
    assert engine._loaded is False
    mock_empty.assert_called_once()


def test_tts_engine_unload_already_unloaded():
    """Calling unload when already unloaded does not error."""
    engine = TTSEngine(device="cuda")
    engine._model = None
    engine._loaded = False

    # Should not raise
    engine.unload()
    assert engine._loaded is False


def test_tts_engine_synthesize_empty_audio_data(temp_output_dir):
    """Model returns empty audio data → None path."""
    engine = TTSEngine(device="cpu")

    mock_model = MagicMock()
    mock_model.generate.return_value = []  # Empty output

    with patch.object(engine, "_load_model"):
        engine._model = mock_model
        engine._loaded = True

        result = engine.synthesize(
            texts=["Test"],
            output_dir=temp_output_dir,
        )

    assert len(result.audio_paths) == 1
    assert result.audio_paths[0] is None
