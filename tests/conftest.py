"""Shared pytest fixtures for EuropaLex test suite."""

from pathlib import Path

# ─── Patch Starlette FileResponse to skip Content-Length ─────────────
# Prevents h11 "Too little data for declared Content-Length" errors during tests.
# Mirrors the patch in app.py that applies at server startup.
try:
    from starlette.responses import FileResponse as _FileResponseBase
    import starlette.responses as _sr_mod

    class _NoContentLengthFileResponse(_FileResponseBase):
        """FileResponse that never sets Content-Length to avoid h11 bugs."""

        def set_stat_headers(self, stat_result):
            """Override to skip setting Content-Length (keeps last-modified and etag)."""
            last_modified = _sr_mod.formatdate(stat_result.st_mtime, usegmt=True)
            etag_base = str(stat_result.st_mtime) + "-" + str(stat_result.st_size)
            import hashlib
            etag = '"' + hashlib.md5(etag_base.encode(), usedforsecurity=False).hexdigest() + '"'
            self.headers.setdefault("last-modified", last_modified)
            self.headers.setdefault("etag", etag)

    _sr_mod.FileResponse = _NoContentLengthFileResponse  # type: ignore[assignment]
except Exception:
    pass  # Non-critical for tests

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
