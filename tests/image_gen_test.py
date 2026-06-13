"""Tests for core.image_gen.ImageGenEngine."""

from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

from core.image_gen import ImageGenEngine
from core.types import ImageResult


def test_imagegen_engine_generate_success(mock_image_paths, temp_output_dir):
    """Success path: mock pipeline returns images → .png file written, path in result."""
    engine = ImageGenEngine(device="cpu")

    mock_pipeline = MagicMock()
    # Simulate pipeline returning a list with one PIL-like image object
    mock_image = MagicMock()
    mock_image.size = (512, 512)

    def save_side_effect(path):
        # Create the actual file so Path.exists() assertions pass
        Path(path).touch()

    mock_image.save = MagicMock(side_effect=save_side_effect)

    mock_result = MagicMock()
    mock_result.images = [mock_image]
    mock_pipeline.return_value = mock_result

    with patch.object(engine, "_load_pipeline"):
        engine._pipeline = mock_pipeline
        engine._loaded = True

        result = engine.generate(
            prompts=["A cat.", "A dog."],
            output_dir=temp_output_dir,
        )

    assert isinstance(result, ImageResult)
    assert len(result.image_paths) == 2
    assert result.image_paths[0] is not None
    assert result.image_paths[1] is not None
    assert Path(result.image_paths[0]).exists()
    assert Path(result.image_paths[1]).exists()


def test_imagegen_engine_generate_failure_path(temp_output_dir):
    """Failure path: mock pipeline raises exception → None in result list."""
    engine = ImageGenEngine(device="cpu")

    mock_pipeline = MagicMock()
    mock_pipeline.side_effect = RuntimeError("OOM")

    with patch.object(engine, "_load_pipeline"):
        engine._pipeline = mock_pipeline
        engine._loaded = True

        result = engine.generate(
            prompts=["A cat.", "A dog."],
            output_dir=temp_output_dir,
        )

    assert len(result.image_paths) == 2
    assert result.image_paths[0] is None
    assert result.image_paths[1] is None


def test_imagegen_engine_generate_empty_input(temp_output_dir):
    """Empty input list: returns empty ImageResult."""
    engine = ImageGenEngine(device="cpu")

    with patch.object(engine, "_load_pipeline"):
        result = engine.generate(
            prompts=[],
            output_dir=temp_output_dir,
        )

    assert isinstance(result, ImageResult)
    assert result.image_paths == []


def test_imagegen_engine_generate_empty_output_warning(temp_output_dir):
    """Pipeline returns empty list → None path logged."""
    engine = ImageGenEngine(device="cpu")

    mock_pipeline = MagicMock()
    mock_result = MagicMock()
    mock_result.images = []  # Empty output
    mock_pipeline.return_value = mock_result

    with patch.object(engine, "_load_pipeline"):
        engine._pipeline = mock_pipeline
        engine._loaded = True

        result = engine.generate(
            prompts=["A cat."],
            output_dir=temp_output_dir,
        )

    assert len(result.image_paths) == 1
    assert result.image_paths[0] is None


def test_imagegen_engine_unload():
    """Pipeline deleted, _loaded reset to False, torch.cuda.empty_cache() called."""
    engine = ImageGenEngine(device="cuda")

    mock_pipeline = MagicMock()
    engine._pipeline = mock_pipeline
    engine._loaded = True

    with patch("torch.cuda.empty_cache") as mock_empty:
        engine.unload()

    assert engine._pipeline is None
    assert engine._loaded is False
    mock_empty.assert_called_once()


def test_imagegen_engine_unload_already_unloaded():
    """Calling unload when already unloaded does not error."""
    engine = ImageGenEngine(device="cuda")
    engine._pipeline = None
    engine._loaded = False

    engine.unload()
    assert engine._loaded is False
