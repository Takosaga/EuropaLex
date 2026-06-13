"""Shared pytest fixtures for EuropaLex test suite."""

from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def mock_english_texts():
    """Phase 1 English sentences."""
    return [
        "I love eating fresh fruits.",
        "She enjoys cooking pasta.",
        "The chef prepared a delicious meal.",
    ]


@pytest.fixture
def mock_spanish_translations():
    """Phase 2 Spanish translations."""
    return [
        "Me encanta comer frutas frescas.",
        "Le encanta cocinar pasta.",
        "El chef preparó una comida deliciosa.",
    ]


@pytest.fixture
def mock_audio_paths():
    """Real .wav paths from tests/test_outputs/audio/ for file-existence tests."""
    audio_dir = PROJECT_ROOT / "tests" / "test_outputs" / "audio"
    return [str(audio_dir / f"audio_{i}.wav") for i in range(3)]


@pytest.fixture
def mock_image_paths():
    """Real .png paths from tests/test_outputs/images/ for file-existence tests."""
    image_dir = PROJECT_ROOT / "tests" / "test_outputs" / "images"
    return [str(image_dir / f"image_{i}.png") for i in range(3)]


@pytest.fixture
def temp_output_dir(tmp_path):
    """Temporary directory for TTS/image generation tests, auto-cleaned."""
    output = tmp_path / "output"
    output.mkdir(parents=True)
    return output


@pytest.fixture
def mock_llm_response_factory():
    """Factory to build LLM response dicts: {"choices": [{"message": {"content": "..."}}]}."""

    def _factory(content: str):
        return {"choices": [{"message": {"content": content}}]}

    return _factory
