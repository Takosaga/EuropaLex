# Pytest Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate all EuropaLex tests from `if __name__ == "__main__":` + `print()` inline style to proper pytest test files with fixtures, mocking, and assertions.

**Architecture:** Flat test structure in `tests/`, one file per source module. All GPU/model code mocked via `unittest.mock`. Real `.wav` and `.png` files from `tests/test_outputs/` serve as file-existence fixtures.

**Tech Stack:** pytest 9+, unittest.mock, Pydantic, Gradio (mocked)

---

## File Structure

```
tests/
├── conftest.py                        # Shared fixtures (NEW)
├── smoke_test.py                      # Pytest rewrite: imports + types validation
├── cards_test.py                      # Card HTML rendering (NEW)
├── widgets_test.py                    # Widget creation + UI state helpers (NEW)
├── app_test.py                        # App helpers + async generators (NEW)
├── audio_gen_test.py                  # TTSEngine (NEW)
├── image_gen_test.py                  # ImageGenEngine (NEW)
├── engine_test.py                     # MiniCPMTextEngine, LlamaCppTextEngine, EnginePool
├── pipeline_test.py                   # Phase 2 orchestration (NEW)
└── text_gen_test.py                   # Merged: extract_sentences + generate_sentences
```

**Old files to remove after migration:** `count_enforcement_test.py`, `extract_sentences_test.py`, `translation_retry_test.py`, `progression_test.py`

## Source Module Reference

| File | Functions/Classes Tested |
|---|---|
| `core/types.py` | CEFRLevel, CardData, TextResult, AudioResult, ImageResult, EngineConfig, ValidationError |
| `core/text_gen.py` | extract_sentences(), generate_sentences() |
| `core/engine.py` | MiniCPMTextEngine.generate(), LlamaCppTextEngine._translate_single(), _is_valid_translation(), generate(), EnginePool.get()/reset() |
| `core/audio_gen.py` | TTSEngine.synthesize(), unload() |
| `core/image_gen.py` | ImageGenEngine.generate(), unload() |
| `core/pipeline.py` | generate_phase2() generator |
| `frontend/ui/cards.py` | render_card_html(), generate_cards_html(), generate_progress_html() |
| `frontend/ui/widgets.py` | create_toggle(), create_voice_dropdown(), _VOICE_MAP, _enable_phase2(), _reset_to_idle(), _enable_language_dropdown_on_audio() |
| `app.py` | transform_mock_cards(), _progress_pct(), generate_text_async(), generate_media_async() |

---

### Task 1: conftest.py — Shared Fixtures

**Files:**
- Create: `tests/conftest.py`

```python
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
```

---

### Task 2: smoke_test.py — Pytest Rewrite (Imports + Types)

**Files:**
- Create: `tests/smoke_test.py`

```python
"""Pytest rewrite of EuropaLex smoke test.

Validates: all modules import, Pydantic model construction,
TextResult.validate_and_parse() gate behavior.
"""

import pytest


def test_all_modules_import():
    """All project modules can be imported without error."""
    import core.types       # noqa: F401
    import core.text_gen     # noqa: F401
    import core.engine       # noqa: F401
    import core.audio_gen    # noqa: F401
    import core.image_gen    # noqa: F401
    import frontend.ui.cards  # noqa: F401
    import frontend.ui.widgets  # noqa: F401


def test_carddata_construction():
    """CardData Pydantic model constructs with all fields."""
    from core.types import CardData

    card = CardData(text="Hello", translation="Sveiki")
    assert card.text == "Hello"
    assert card.translation == "Sveiki"
    assert card.audio_path is None
    assert card.image_path is None


def test_textresult_construction():
    """TextResult constructs with generated_texts list."""
    from core.types import TextResult

    result = TextResult(generated_texts=["A.", "B."])
    assert len(result.generated_texts) == 2


def test_audioreresult_construction():
    """AudioResult defaults to empty list."""
    from core.types import AudioResult

    result = AudioResult()
    assert result.audio_paths == []


def test_imageresult_construction():
    """ImageResult defaults to empty list."""
    from core.types import ImageResult

    result = ImageResult()
    assert result.image_paths == []


def test_engineconfig_from_settings():
    """EngineConfig loads from settings.yaml (uses default paths, no model check)."""
    from core.types import EngineConfig

    config = EngineConfig.from_settings_yaml()
    assert config.batch_size > 0
    assert config.device in ("cuda", "mps", "cpu")


def test_cefrlevel_enum():
    """CEFRLevel enum has all expected values and label/description methods."""
    from core.types import CEFRLevel

    levels = [CEFRLevel.A1, CEFRLevel.A2, CEFRLevel.B1, CEFRLevel.B2, CEFRLevel.C1, CEFRLevel.C2]
    for level in levels:
        assert isinstance(level.label(), str)
        assert len(level.label()) > 0
        assert isinstance(level.description(), str)
        assert len(level.description()) > 0


def test_validationerror_structure():
    """ValidationError carries raw_output attribute."""
    from core.types import ValidationError

    err = ValidationError("test message", raw_output="raw llm output")
    assert err.raw_output == "raw llm output"
    assert str(err) == "test message"


def test_textresult_validate_and_parse_strips_thinking_tags():
    """validate_and_parse strips <thinking> tags before splitting lines."""
    from core.types import TextResult

    raw = "<thinking>reasoning</thinking>\nHello.\nWorld."
    result = TextResult.validate_and_parse(raw, expected_count=2)
    assert result.generated_texts == ["Hello.", "World."]


def test_textresult_validate_and_parse_enforces_count():
    """validate_and_parse raises ValidationError when count mismatches."""
    from core.types import TextResult, ValidationError

    raw = "Line one.\nLine two."
    with pytest.raises(ValidationError) as exc_info:
        TextResult.validate_and_parse(raw, expected_count=5)
    assert "Expected 5 sentences but got 2" in str(exc_info.value)
    assert exc_info.value.raw_output == raw


def test_textresult_validate_and_parse_empty_raises():
    """validate_and_parse raises ValidationError on empty output after tag stripping."""
    from core.types import TextResult, ValidationError

    raw = "<thinking>only reasoning</thinking>"
    with pytest.raises(ValidationError):
        TextResult.validate_and_parse(raw, expected_count=1)


def test_textresult_validate_and_parse_no_expected_count():
    """validate_and_parse returns all lines when expected_count is None."""
    from core.types import TextResult

    raw = "A.\nB.\nC."
    result = TextResult.validate_and_parse(raw, expected_count=None)
    assert len(result.generated_texts) == 3
```

---

### Task 3: cards_test.py — Card HTML Rendering

**Files:**
- Create: `tests/cards_test.py`

```python
"""Tests for frontend.ui.cards card rendering functions."""

from pathlib import Path
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
from frontend.ui.cards import render_card_html, generate_cards_html, generate_progress_html


@pytest.fixture
def mock_audio_paths():
    audio_dir = PROJECT_ROOT / "tests" / "test_outputs" / "audio"
    return [str(audio_dir / f"audio_{i}.wav") for i in range(3)]


@pytest.fixture
def mock_image_paths():
    image_dir = PROJECT_ROOT / "tests" / "test_outputs" / "images"
    return [str(image_dir / f"image_{i}.png") for i in range(3)]


# ── render_card_html ──────────────────────────────────────────────

def test_render_card_html_placeholder_mode():
    """Placeholder mode: English on front, dashed placeholder back."""
    card = {
        "text": "Hello world.",
        "translation": "",
        "cefr_level": "A1",
    }
    html = render_card_html(card, include_image=False, include_audio=False, rotation=0, placeholder_back=True)
    assert "Hello world." in html
    assert "card-placeholder-back" in html


def test_render_card_html_normal_mode():
    """Normal mode: translation on front, English on back."""
    card = {
        "text": "Hello world.",
        "translation": "Sveiki pasaule.",
        "cefr_level": "A1",
    }
    html = render_card_html(card, include_image=False, include_audio=False, rotation=0, placeholder_back=False)
    assert "Sveiki pasaule." in html
    assert "Hello world." in html


def test_render_card_html_with_existing_image(mock_image_paths):
    """Existing image file → <img> tag in HTML."""
    card = {
        "text": "A cat.",
        "translation": "Kaķis.",
        "image_path": mock_image_paths[0],
    }
    html = render_card_html(card, include_image=True, include_audio=False, rotation=0, placeholder_back=False)
    assert "<img" in html


def test_render_card_html_with_missing_image():
    """Missing image file → placeholder emoji."""
    card = {
        "text": "A cat.",
        "translation": "Kaķis.",
        "image_path": "/nonexistent/path.png",
    }
    html = render_card_html(card, include_image=True, include_audio=False, rotation=0, placeholder_back=False)
    assert "<img" not in html


def test_render_card_html_with_existing_audio(mock_audio_paths):
    """Existing audio file → <audio> element in HTML."""
    card = {
        "text": "Hello.",
        "translation": "Sveiki.",
        "audio_path": mock_audio_paths[0],
    }
    html = render_card_html(card, include_image=False, include_audio=True, rotation=0, placeholder_back=False)
    assert "<audio" in html


def test_render_card_html_with_missing_audio():
    """Missing audio file → play button."""
    card = {
        "text": "Hello.",
        "translation": "Sveiki.",
        "audio_path": "/nonexistent/path.wav",
    }
    html = render_card_html(card, include_image=False, include_audio=True, rotation=0, placeholder_back=False)
    assert "<audio" not in html
    assert "media-btn" in html


def test_render_card_html_rotation_applied():
    """Rotation parameter applied to transform style."""
    card = {"text": "Hello", "translation": ""}
    html = render_card_html(card, include_image=False, include_audio=False, rotation=3.5, placeholder_back=False)
    assert "rotate(3.5deg)" in html


# ── generate_cards_html ──────────────────────────────────────────

def test_generate_cards_html_empty_list():
    """Empty cards list → 'No cards' message."""
    html = generate_cards_html([], include_image=False, include_audio=False)
    assert "No cards" in html or "<div" in html


def test_generate_cards_html_single_card():
    """Single card renders without rotation variation issues."""
    cards = [{"text": "Hello", "translation": "Sveiki"}]
    html = generate_cards_html(cards, include_image=False, include_audio=False)
    assert "Hello" in html
    assert "Sveiki" in html


def test_generate_cards_html_multi_card_rotation_distribution():
    """Multiple cards get varied rotation angles for spread-on-desk effect."""
    cards = [{"text": f"Sentence {i}", "translation": f"Tulkojums {i}"} for i in range(5)]
    html = generate_cards_html(cards, include_image=False, include_audio=False)
    # All sentences present
    for i in range(5):
        assert f"Sentence {i}" in html


def test_generate_cards_html_image_only():
    """include_image=True, include_audio=False → images only."""
    cards = [{"text": "A.", "translation": "B.", "image_path": PROJECT_ROOT / "tests" / "test_outputs" / "images" / "image_0.png"}]
    html = generate_cards_html(cards, include_image=True, include_audio=False)
    assert "<img" in html


def test_generate_cards_html_audio_only():
    """include_image=False, include_audio=True → audio only."""
    cards = [{"text": "A.", "translation": "B.", "audio_path": PROJECT_ROOT / "tests" / "test_outputs" / "audio" / "audio_0.wav"}]
    html = generate_cards_html(cards, include_image=False, include_audio=True)
    assert "<audio" in html


def test_generate_cards_html_both_media():
    """Both image and audio toggles → both media boxes present."""
    cards = [{
        "text": "A.", "translation": "B.",
        "image_path": PROJECT_ROOT / "tests" / "test_outputs" / "images" / "image_0.png",
        "audio_path": PROJECT_ROOT / "tests" / "test_outputs" / "audio" / "audio_0.wav",
    }]
    html = generate_cards_html(cards, include_image=True, include_audio=True)
    assert "<img" in html
    assert "<audio" in html


def test_generate_cards_html_neither_media():
    """Both toggles off → no media boxes."""
    cards = [{"text": "A.", "translation": "B."}]
    html = generate_cards_html(cards, include_image=False, include_audio=False)
    assert "<img" not in html
    assert "<audio" not in html


def test_generate_cards_html_placeholder_back_mode():
    """placeholder_back=True → dashed placeholder instead of translation."""
    cards = [{"text": "Hello", "translation": ""}]
    html = generate_cards_html(cards, include_image=False, include_audio=False, placeholder_back=True)
    assert "card-placeholder-back" in html


# ── generate_progress_html ───────────────────────────────────────

def test_generate_progress_html_zero_percent():
    """0% → empty string (hidden by Gradio)."""
    result = generate_progress_html(0, "")
    assert result == ""


def test_generate_progress_html_mid_progress_color():
    """10-59% → brown bar."""
    html = generate_progress_html(50, "Working...")
    assert "width: 50%" in html


def test_generate_progress_html_60_percent_dark_brown():
    """60%+ → dark brown bar."""
    html = generate_progress_html(60, "Almost done...")
    assert "#8b7355" in html or "#6b5e4a" in html


def test_generate_progress_html_100_percent_complete():
    """100% → dark brown bar, green 'complete' text."""
    html = generate_progress_html(100, "Complete!")
    assert "width: 100%" in html
    assert "#4CAF50" in html or "green" in html.lower()
```

---

### Task 4: widgets_test.py — Widget Creation + UI State Helpers

**Files:**
- Create: `tests/widgets_test.py`

```python
"""Tests for frontend.ui.widgets widget creation and UI state helpers."""

import pytest
from unittest.mock import patch, MagicMock

# Patch gradio at module level before importing widgets
mock_gr = MagicMock()
mock_gr.Blocks = MagicMock()
mock_gr.Checkbox = MagicMock()
mock_gr.Button = MagicMock()
mock_gr.Dropdown = MagicMock()

with patch.dict('sys.modules', {'gradio': mock_gr}):
    from frontend.ui.widgets import (
        create_toggle,
        create_voice_dropdown,
        _VOICE_MAP,
        _enable_phase2,
        _reset_to_idle,
        _enable_language_dropdown_on_audio,
    )


def test_create_toggle_label_with_emoji():
    """Toggle label includes the provided emoji prefix."""
    checkbox = create_toggle("🖼️ Images", value=True, elem_id="toggle-images")
    mock_gr.Checkbox.assert_called()
    call_kwargs = mock_gr.Checkbox.call_args[1]
    assert "Images" in str(call_kwargs.get("label", ""))


def test_create_toggle_default_value():
    """Toggle respects the default value parameter."""
    checkbox_false = create_toggle("🔊 Audio", value=False, elem_id="toggle-audio")
    call_kwargs = mock_gr.Checkbox.call_args[1]
    assert call_kwargs.get("value") is False


def test_create_toggle_elem_id_generation():
    """elem_id follows the pattern toggle-<label-without-emoji>."""
    create_toggle("🖼️ Images", value=True, elem_id="toggle-images")
    call_kwargs = mock_gr.Checkbox.call_args[1]
    assert call_kwargs.get("elem_id") == "toggle-images"


def test_create_voice_dropdown_all_choices():
    """All 6 voice choices present in dropdown."""
    dropdown = create_voice_dropdown()
    call_kwargs = mock_gr.Dropdown.call_args[1]
    choices = call_kwargs.get("choices", [])
    assert len(choices) == 6


def test_create_voice_dropdown_default_value():
    """Default value matches the first choice."""
    create_voice_dropdown()
    call_kwargs = mock_gr.Dropdown.call_args[1]
    default = call_kwargs.get("value")
    choices = call_kwargs.get("choices", [])
    assert default == choices[0]


def test_create_voice_dropdown_elem_id():
    """Voice dropdown elem_id is 'voice-dropdown'."""
    create_voice_dropdown()
    call_kwargs = mock_gr.Dropdown.call_args[1]
    assert call_kwargs.get("elem_id") == "voice-dropdown"


def test_voice_map_all_six_entries():
    """_VOICE_MAP has exactly 6 entries mapping display labels to instruct strings."""
    assert len(_VOICE_MAP) == 6


def test_voice_map_instruct_strings_format():
    """All _VOICE_MAP values are comma-separated gender, age format."""
    for label, instruct in _VOICE_MAP.items():
        parts = instruct.split(", ")
        assert len(parts) == 2
        assert parts[0] in ("female", "male")
        assert parts[1] in ("young adult", "middle-aged", "senior")


def test_enable_phase2_returns_tuple():
    """_enable_phase2() returns tuple of (Checkbox, Checkbox, Button, Dropdown, "") with interactive=True."""
    result = _enable_phase2()
    assert isinstance(result, tuple)
    assert len(result) == 5
    # Check that interactive=True was passed for each widget
    for i in range(4):
        mock_gr.__getitem__.assert_called()


def test_reset_to_idle_returns_tuple():
    """_reset_to_idle() returns tuple with interactive=False, disabled CSS string."""
    result = _reset_to_idle()
    assert isinstance(result, tuple)
    assert len(result) == 5
    # Last element should be a CSS string (non-empty)
    assert isinstance(result[4], str)
    assert len(result[4]) > 0


def test_enable_language_dropdown_on_audio_true():
    """Audio toggle ON → removes disabled CSS, enables dropdown."""
    result = _enable_language_dropdown_on_audio(True)
    assert isinstance(result, tuple)
    # Should return (dropdown_update, "") — empty CSS means enabled
    assert result[1] == "" or len(result[1]) == 0


def test_enable_language_dropdown_on_audio_false():
    """Audio toggle OFF → applies disabled CSS to voice dropdown."""
    result = _enable_language_dropdown_on_audio(False)
    assert isinstance(result, tuple)
    # Should return (dropdown_update, css_string) — non-empty CSS means disabled
    assert isinstance(result[1], str)
    assert len(result[1]) > 0
    assert "europalex-btn-disabled" in result[1]
```

---

### Task 5: app_test.py — App Helpers + Async Generators

**Files:**
- Create: `tests/app_test.py`

```python
"""Tests for app.py helper functions and async generator handlers."""

from pathlib import Path
import types
import pytest
from unittest.mock import patch, MagicMock

PROJECT_ROOT = Path(__file__).resolve().parent.parent


# ── transform_mock_cards ─────────────────────────────────────────

def test_transform_mock_cards_legacy_to_new_format():
    """Legacy {"front": X, "back": Y} → new {"text": Y, "translation": X}."""
    from app import transform_mock_cards

    raw = [
        {"front": "Sveiki", "back": "Hello"},
        {"front": "Paldies", "back": "Thank you"},
    ]
    result = transform_mock_cards(raw)
    assert result[0]["text"] == "Hello"
    assert result[0]["translation"] == "Sveiki"
    assert result[1]["text"] == "Thank you"
    assert result[1]["translation"] == "Paldies"


def test_transform_mock_cards_empty_input():
    """Empty input returns empty list."""
    from app import transform_mock_cards

    assert transform_mock_cards([]) == []


def test_transform_mock_cards_preserves_order():
    """Multiple cards preserved in order."""
    from app import transform_mock_cards

    raw = [
        {"front": "A1", "back": "B1"},
        {"front": "A2", "back": "B2"},
        {"front": "A3", "back": "B3"},
    ]
    result = transform_mock_cards(raw)
    assert len(result) == 3
    assert result[0]["text"] == "B1"
    assert result[1]["text"] == "B2"
    assert result[2]["text"] == "B3"


# ── _progress_pct ────────────────────────────────────────────────

def test_progress_pct_single_sentence():
    """Single sentence (total=1): always 100% with 'complete' label."""
    from app import _progress_pct

    pct, label = _progress_pct(0, total=1)
    assert pct == 70.0  # end_pct default
    assert "complete" in label.lower()


def test_progress_pct_two_sentences():
    """Two sentences: step 0 → ~50%, step 1 → 100%."""
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
    assert types.isgeneratorfunction(generate_text_async)


def test_generate_text_async_yields_progress_and_cards(mock_llm_response_factory):
    """Generator yields progress updates then card HTML when engine succeeds."""
    from unittest.mock import patch, MagicMock
    from app import generate_text_async

    mock_engine = MagicMock()
    mock_engine.generate.return_value = MagicMock(
        generated_texts=["Hello.", "World."]
    )

    mock_pool = MagicMock()
    mock_pool.get_english_engine.return_value = mock_engine

    with patch("app.EnginePool", mock_pool):
        with patch("app.EngineConfig.from_settings_yaml") as mock_config:
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

    with patch("app.EnginePool") as mock_pool:
        mock_pool.side_effect = FileNotFoundError("model.gguf not found")
        yields = list(generate_text_async("test", "A1", 2))

    assert len(yields) >= 1
    _, output = yields[0]
    assert "Model file not found" in output or "model" in output.lower()


def test_generate_text_async_general_exception():
    """General exception path → error message in output."""
    from app import generate_text_async

    with patch("app.EnginePool") as mock_pool:
        mock_pool.side_effect = RuntimeError("GPU out of memory")
        yields = list(generate_text_async("test", "A1", 2))

    assert len(yields) >= 1
    _, output = yields[0]
    assert "Failed to initialize" in output or "Setup error" in output


# ── generate_media_async ─────────────────────────────────────────

def test_generate_media_async_is_generator():
    """generate_media_async is a generator function."""
    from app import generate_media_async
    assert types.isgeneratorfunction(generate_media_async)


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

        mock_pool = MagicMock()
        mock_pool.get_translation_engine.return_value = mock_engine

        with patch("app.EnginePool", mock_pool):
            with patch("app.EngineConfig.from_settings_yaml") as mock_config:
                mock_config.return_value.batch_size = 3
                yields = list(generate_media_async("test", "A1", 3))

        # Each translation step yields (progress, cards)
        # At least 3 yields for 3 sentences + final yield
        card_yields = [(p, c) for p, c in yields if "translation" in c.lower() or "Sveiki" in c]
        assert len(card_yields) >= 1
    finally:
        app_module._phase1_texts = original


def test_generate_media_async_tts_toggle():
    """Audio toggle ON → yields audio generation progress at 70%."""
    from unittest.mock import patch, MagicMock
    from app import generate_media_async

    import app as app_module
    original = list(app_module._phase1_texts)
    app_module._phase1_texts = ["Hello."]

    try:
        mock_trans_engine = MagicMock()
        mock_trans_engine._translate_single.return_value = "Sveiki."

        mock_audio_result = MagicMock()
        mock_audio_result.audio_paths = ["/tmp/audio_0.wav"]

        mock_tts_engine = MagicMock()
        mock_tts_engine.synthesize.return_value = mock_audio_result

        mock_pool = MagicMock()
        mock_pool.get_translation_engine.return_value = mock_trans_engine
        mock_pool.get_tts_engine.return_value = mock_tts_engine

        with patch("app.EnginePool", mock_pool):
            with patch("app.EngineConfig.from_settings_yaml") as mock_config:
                mock_config.return_value.batch_size = 1
                yields = list(generate_media_async(
                    "test", "A1", 1,
                    target_language="Latvian",
                    include_audio=True,
                    include_images=False,
                    voice="female, young adult",
                ))

        # Check that audio generation progress was yielded
        progress_labels = [p for p, _ in yields]
        assert any("audio" in str(p).lower() for p in progress_labels)
    finally:
        app_module._phase1_texts = original


def test_generate_media_async_images_toggle():
    """Images toggle ON → yields image generation progress at 85%."""
    from unittest.mock import patch, MagicMock
    from app import generate_media_async

    import app as app_module
    original = list(app_module._phase1_texts)
    app_module._phase1_texts = ["Hello."]

    try:
        mock_trans_engine = MagicMock()
        mock_trans_engine._translate_single.return_value = "Sveiki."

        mock_img_result = MagicMock()
        mock_img_result.image_paths = ["/tmp/image_0.png"]

        mock_pool = MagicMock()
        mock_pool.get_translation_engine.return_value = mock_trans_engine

        with patch("app.EnginePool", mock_pool):
            with patch("app.EngineConfig.from_settings_yaml") as mock_config:
                mock_config.return_value.batch_size = 1
                yields = list(generate_media_async(
                    "test", "A1", 1,
                    target_language="Latvian",
                    include_audio=False,
                    include_images=True,
                ))

        progress_labels = [p for p, _ in yields]
        assert any("image" in str(p).lower() for p in progress_labels)
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
```

---

### Task 6: audio_gen_test.py — TTSEngine

**Files:**
- Create: `tests/audio_gen_test.py`

```python
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
```

---

### Task 7: image_gen_test.py — ImageGenEngine

**Files:**
- Create: `tests/image_gen_test.py`

```python
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
    mock_pipeline.return_value = [mock_image]

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
    mock_pipeline.return_value = []  # Empty output

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
```

---

### Task 8: text_gen_test.py — extract_sentences + generate_sentences

**Files:**
- Create: `tests/text_gen_test.py`

```python
"""Tests for core.text_gen.extract_sentences and generate_sentences.

Merged from count_enforcement_test.py and extract_sentences_test.py.
All tests use mocking — no LLM inference needed.
"""

import pytest
from unittest.mock import MagicMock

from core.text_gen import extract_sentences, generate_sentences
from core.types import CEFRLevel, ValidationError


# ── extract_sentences ────────────────────────────────────────────

def test_extract_sentences_basic_numbered_format():
    """Basic numbered format: '1. Hello.\n2. World.' → ['Hello.', 'World.']"""
    result = extract_sentences("1. Hello world.\n2. Goodbye world.")
    assert len(result) == 2
    assert result[0] == "Hello world."
    assert result[1] == "Goodbye world."


def test_extract_sentences_thinking_tag_stripping():
    """Strips <thinking> tags before parsing."""
    raw = "<thinking>some thoughts\nmore thoughts</thinking>\n1. Sentence one.\n2. Sentence two."
    result = extract_sentences(raw)
    assert len(result) == 2
    assert result[0] == "Sentence one."
    assert result[1] == "Sentence two."


def test_extract_sentences_mixed_punctuation():
    """Sentences ending with ., ?, ! all recognized."""
    raw = "1. Hello.\n2. How are you?\n3. What a day!"
    result = extract_sentences(raw)
    assert len(result) == 3
    assert result[0] == "Hello."
    assert result[1] == "How are you?"
    assert result[2] == "What a day!"


def test_extract_sentences_zero_sentences_raises():
    """Zero numbered sentences raises ValidationError."""
    with pytest.raises(ValidationError):
        extract_sentences("No numbered lines here.\nJust plain text.")


def test_extract_sentences_uncapped_20_sentences():
    """20 numbered sentences all returned — no upper cap."""
    lines = "\n".join(f"{i}. Sentence {i}." for i in range(1, 21))
    result = extract_sentences(lines)
    assert len(result) == 20
    assert result[0] == "Sentence 1."
    assert result[19] == "Sentence 20."


def test_extract_sentences_ignores_non_numbered_lines():
    """Non-numbered lines silently ignored, not discarded."""
    raw = "Some intro text.\n1. Valid sentence.\nMore text.\n2. Another valid."
    result = extract_sentences(raw)
    assert len(result) == 2
    assert result[0] == "Valid sentence."
    assert result[1] == "Another valid."


def test_extract_sentences_dot_numbering_format():
    """Dot numbering (1., 2.) format recognized."""
    raw = "1. First.\n2. Second.\n3. Third."
    result = extract_sentences(raw)
    assert len(result) == 3
    assert result == ["First.", "Second.", "Third."]


def test_extract_sentences_paren_numbering_format():
    """Paren numbering (1), 2)) format recognized."""
    raw = "1) First.\n2) Second.\n3) Third."
    result = extract_sentences(raw)
    assert len(result) == 3
    assert result == ["First.", "Second.", "Third."]


def test_extract_sentences_empty_after_tag_stripping_raises():
    """Raw text contains only thinking tags → ValidationError."""
    with pytest.raises(ValidationError):
        extract_sentences("<thinking>only reasoning</thinking>")


# ── generate_sentences ───────────────────────────────────────────

def test_generate_sentences_success_first_try(mock_llm_response_factory):
    """Success on first try with exact batch_size."""
    mock_llm = MagicMock()
    mock_llm.create_chat_completion.return_value = mock_llm_response_factory(
        "1. Hello.\n2. World."
    )

    result = generate_sentences(
        scenario="test",
        cefr_level=CEFRLevel.A1,
        batch_size=2,
        llm=mock_llm,
    )
    assert len(result) == 2
    assert result[0] == "Hello."
    assert result[1] == "World."


def test_generate_sentences_uncapped_extraction():
    """More sentences than batch_size: returns all extracted (up to batch_size cap)."""
    mock_llm = MagicMock()
    mock_llm.create_chat_completion.return_value = {
        "choices": [{"message": {"content": "1. First.\n2. Second.\n3. Third.\n4. Fourth."}}]
    }

    result = generate_sentences(
        scenario="test",
        cefr_level=CEFRLevel.A1,
        batch_size=2,
        llm=mock_llm,
    )
    # batch_size is a cap: returns first 2
    assert len(result) == 2


def test_generate_sentences_retry_on_fewer_than_batch():
    """Retries when fewer than batch_size sentences on first call."""
    mock_llm = MagicMock()
    mock_llm.create_chat_completion.side_effect = [
        {"choices": [{"message": {"content": "1. Only one sentence."}}]},
        {"choices": [{"message": {"content": "2. Second.\n3. Third.\n4. Fourth."}}]},
    ]

    result = generate_sentences(
        scenario="greetings",
        cefr_level=CEFRLevel.A1,
        batch_size=3,
        llm=mock_llm,
    )
    assert len(result) == 3
    assert mock_llm.create_chat_completion.call_count == 2


def test_generate_sentences_fallback_after_exhausted_retries():
    """Returns whatever was produced after retries exhausted."""
    mock_llm = MagicMock()
    # First call: 1 sentence. Second call: 2 sentences (still < batch_size=3)
    mock_llm.create_chat_completion.side_effect = [
        {"choices": [{"message": {"content": "1. Only one."}}]},
        {"choices": [{"message": {"content": "2. Second.\n3. Third."}}]},
    ]

    result = generate_sentences(
        scenario="greetings",
        cefr_level=CEFRLevel.A1,
        batch_size=3,
        llm=mock_llm,
    )
    assert len(result) == 2


def test_generate_sentences_thinking_tags_handled():
    """LLM output containing thinking tags handled correctly."""
    mock_llm = MagicMock()
    mock_llm.create_chat_completion.return_value = {
        "choices": [{"message": {"content": "<thinking>reasoning</thinking>\n1. Hello.\n2. World."}}]
    }

    result = generate_sentences(
        scenario="test",
        cefr_level=CEFRLevel.A1,
        batch_size=2,
        llm=mock_llm,
    )
    assert len(result) == 2
    assert result[0] == "Hello."


def test_generate_sentences_question_sentences_preserved():
    """Question sentences preserved in output."""
    mock_llm = MagicMock()
    mock_llm.create_chat_completion.return_value = {
        "choices": [{"message": {"content": "1. What is this?\n2. It is a cat."}}]
    }

    result = generate_sentences(
        scenario="test",
        cefr_level=CEFRLevel.A1,
        batch_size=2,
        llm=mock_llm,
    )
    assert len(result) == 2
    assert result[0] == "What is this?"
```

---

### Task 9: engine_test.py — MiniCPMTextEngine, LlamaCppTextEngine, EnginePool

**Files:**
- Create: `tests/engine_test.py`

```python
"""Tests for core.engine engines: MiniCPMTextEngine, LlamaCppTextEngine, EnginePool.

Merged from translation_retry_test.py. All tests mock the LLM — no model inference.
"""

import pytest
from unittest.mock import patch, MagicMock

from core.types import CEFRLevel, TextResult, ValidationError
from core.engine import MiniCPMTextEngine, LlamaCppTextEngine, EnginePool


# ── MiniCPMTextEngine ────────────────────────────────────────────

def test_minicpm_generate_calls_llm(mock_llm_response_factory):
    """generate() calls llm.create_chat_completion and wraps in TextResult."""
    mock_llm = MagicMock()
    mock_llm.create_chat_completion.return_value = mock_llm_response_factory(
        "1. Hello.\n2. World."
    )

    with patch.object(MiniCPMTextEngine, "_load_model"):
        engine = MiniCPMTextEngine.__new__(MiniCPMTextEngine)
        engine._llm = mock_llm
        engine._loaded = True

        result = engine.generate(
            texts=[],  # empty = generation mode
            scenario="test",
            cefr_level=CEFRLevel.A1,
            batch_size=2,
        )

    assert isinstance(result, TextResult)
    assert len(result.generated_texts) == 2
    assert result.generated_texts[0] == "Hello."
    mock_llm.create_chat_completion.assert_called_once()


def test_minicpm_generate_propagates_validation_error():
    """ValidationError from text_gen propagate through generate()."""
    from core.text_gen import ValidationError as TextGenValidationError

    mock_llm = MagicMock()
    # LLM returns content that yields 0 sentences after parsing
    mock_llm.create_chat_completion.return_value = {"choices": [{"message": {"content": "no numbers here"}}]}

    with patch.object(MiniCPMTextEngine, "_load_model"):
        engine = MiniCPMTextEngine.__new__(MiniCPMTextEngine)
        engine._llm = mock_llm
        engine._loaded = True

        # Should raise ValidationError after retries exhausted
        with pytest.raises((ValidationError, TextGenValidationError)):
            engine.generate(
                texts=[],
                scenario="test",
                cefr_level=CEFRLevel.A1,
                batch_size=2,
            )


# ── LlamaCppTextEngine._is_valid_translation ─────────────────────

def test_is_valid_translation_valid():
    """Valid: non-empty single line, no English words."""
    with patch.object(LlamaCppTextEngine, "_load_model"):
        engine = LlamaCppTextEngine.__new__(LlamaCppTextEngine)
        engine._loaded = True

    assert engine._is_valid_translation("Sveiki.") is True
    assert engine._is_valid_translation("Labrīt!") is True
    assert engine._is_valid_translation("Paldies, ka jautāji.") is True


def test_is_valid_translation_invalid_empty():
    """Invalid: empty string or whitespace-only."""
    with patch.object(LlamaCppTextEngine, "_load_model"):
        engine = LlamaCppTextEngine.__new__(LlamaCppTextEngine)
        engine._loaded = True

    assert engine._is_valid_translation("") is False
    assert engine._is_valid_translation("   ") is False


def test_is_valid_translation_invalid_english_words():
    """Invalid: contains English words (model echoed back)."""
    with patch.object(LlamaCppTextEngine, "_load_model"):
        engine = LlamaCppTextEngine.__new__(LlamaCppTextEngine)
        engine._loaded = True

    assert engine._is_valid_translation("This is the translation") is False
    assert engine._is_valid_translation("Translate this sentence") is False


def test_is_valid_translation_invalid_multiline():
    """Invalid: multiline output."""
    with patch.object(LlamaCppTextEngine, "_load_model"):
        engine = LlamaCppTextEngine.__new__(LlamaCppTextEngine)
        engine._loaded = True

    assert engine._is_valid_translation("Line1\nLine2") is False


# ── LlamaCppTextEngine._translate_single ─────────────────────────

def test_translate_single_success():
    """Valid translation returned on first attempt."""
    mock_llm = MagicMock()
    mock_llm.create_chat_completion.return_value = {"choices": [{"message": {"content": "Sveiki."}}]}

    with patch.object(LlamaCppTextEngine, "_load_model"):
        engine = LlamaCppTextEngine.__new__(LlamaCppTextEngine)
        engine._llm = mock_llm
        engine._loaded = True

        result = engine._translate_single("Hello.", CEFRLevel.A1)

    assert result == "Sveiki."
    assert mock_llm.create_chat_completion.call_count == 1


def test_translate_single_retry_on_invalid():
    """Retry when first output invalid (contains English word), second succeeds."""
    mock_llm = MagicMock()
    mock_llm.create_chat_completion.side_effect = [
        {"choices": [{"message": {"content": "This is the English text"}}]},
        {"choices": [{"message": {"content": "Paldies."}}]},
    ]

    with patch.object(LlamaCppTextEngine, "_load_model"):
        engine = LlamaCppTextEngine.__new__(LlamaCppTextEngine)
        engine._llm = mock_llm
        engine._loaded = True

        result = engine._translate_single("Thank you.", CEFRLevel.A1)

    assert result == "Paldies."
    assert mock_llm.create_chat_completion.call_count == 2


def test_translate_single_exhausted_retries_fallback():
    """Exhausted retries → fallback to original English text."""
    mock_llm = MagicMock()
    mock_llm.create_chat_completion.return_value = {"choices": [{"message": {"content": ""}}]}

    with patch.object(LlamaCppTextEngine, "_load_model"):
        engine = LlamaCppTextEngine.__new__(LlamaCppTextEngine)
        engine._llm = mock_llm
        engine._loaded = True

        result = engine._translate_single("Hello.", CEFRLevel.A1)

    assert result == "Hello."  # fallback to original English
    assert mock_llm.create_chat_completion.call_count == 3


def test_translate_single_multiline_rejected():
    """Multiline output rejected, triggers retry."""
    mock_llm = MagicMock()
    mock_llm.create_chat_completion.side_effect = [
        {"choices": [{"message": {"content": "Line1\nLine2"}}]},  # invalid: multiline
        {"choices": [{"message": {"content": "Valid translation."}}]},  # valid
    ]

    with patch.object(LlamaCppTextEngine, "_load_model"):
        engine = LlamaCppTextEngine.__new__(LlamaCppTextEngine)
        engine._llm = mock_llm
        engine._loaded = True

        result = engine._translate_single("Hello.", CEFRLevel.A1)

    assert result == "Valid translation."
    assert mock_llm.create_chat_completion.call_count == 2


# ── LlamaCppTextEngine.generate ──────────────────────────────────

def test_generate_calls_per_sentence():
    """generate() calls _translate_single for each input text."""
    mock_llm = MagicMock()
    responses = [
        {"choices": [{"message": {"content": "Sveiki."}}]},
        {"choices": [{"message": {"content": "Kā tu esi?"}}]},
        {"choices": [{"message": {"content": "Paldies."}}]},
    ]
    mock_llm.create_chat_completion.side_effect = responses

    with patch.object(LlamaCppTextEngine, "_load_model"):
        engine = LlamaCppTextEngine.__new__(LlamaCppTextEngine)
        engine._llm = mock_llm
        engine._loaded = True

        result = engine.generate(
            texts=["Hello.", "How are you?", "Thank you."],
            scenario="greetings",
            cefr_level=CEFRLevel.A1,
            batch_size=3,
        )

    assert len(result.generated_texts) == 3
    assert result.generated_texts[0] == "Sveiki."
    assert result.generated_texts[1] == "Kā tu esi?"
    assert result.generated_texts[2] == "Paldies."
    assert mock_llm.create_chat_completion.call_count == 3


# ── EnginePool ───────────────────────────────────────────────────

def test_engine_pool_get_creates_singleton():
    """First get() creates a new EnginePool instance."""
    from core.types import EngineConfig

    config = EngineConfig(batch_size=3, target_language="Latvian")
    pool = EnginePool.get(config)
    assert isinstance(pool, EnginePool)


def test_engine_pool_get_returns_same_instance():
    """Second get() returns the same instance."""
    from core.types import EngineConfig

    config1 = EngineConfig(batch_size=3, target_language="Latvian")
    pool1 = EnginePool.get(config1)
    pool2 = EnginePool.get(config1)
    assert pool1 is pool2


def test_engine_pool_reset_clears_singleton():
    """reset() clears singleton and unloads engines."""
    from core.types import EngineConfig

    config = EngineConfig(batch_size=3, target_language="Latvian")
    pool1 = EnginePool.get(config)

    # Create a second reference
    pool2 = EnginePool.get(config)
    assert pool1 is pool2

    EnginePool.reset()

    # After reset, new get() should return a different instance
    pool3 = EnginePool.get(config)
    assert pool3 is not pool1
```

---

### Task 10: pipeline_test.py — Phase 2 Orchestration

**Files:**
- Create: `tests/pipeline_test.py`

```python
"""Tests for core.pipeline.generate_phase2() orchestration.

Mocks EnginePool and individual engines. Verifies orchestration flow,
progress percentages, and CardData assembly.
"""

import pytest
from unittest.mock import patch, MagicMock, PropertyMock
import types

from core.types import CEFRLevel


def test_generate_phase2_is_generator():
    """generate_phase2 is a generator function."""
    from core.pipeline import generate_phase2
    assert types.isgeneratorfunction(generate_phase2)


def test_generate_phase2_translation_only(mock_english_texts, mock_spanish_translations):
    """Translation-only: yields progress updates per sentence, final CardData list with translations."""
    from core.pipeline import generate_phase2
    from core.types import CardData

    # Build mock engine that returns translated texts
    mock_engine = MagicMock()
    mock_engine.generate.return_value = MagicMock(
        generated_texts=list(mock_spanish_translations)
    )

    mock_pool = MagicMock()
    mock_pool.get_translation_engine.return_value = mock_engine

    with patch("core.pipeline.EnginePool", mock_pool):
        with patch("core.pipeline.EngineConfig.from_settings_yaml") as mock_config:
            mock_config.return_value.batch_size = 3
            yields = list(generate_phase2(
                english_texts=list(mock_english_texts),
                scenario="test",
                cefr_level=CEFRLevel.A1,
                batch_size=3,
                target_language="Spanish",
                include_audio=False,
                include_images=False,
            ))

    # Should yield at least: progress prepare, progress per sentence, final complete
    assert len(yields) >= 5  # 20% prepare + 3 translation steps + final

    # Last yield should have CardData list
    last_progress, last_result = yields[-1]
    assert isinstance(last_result, list)
    assert len(last_result) == 3
    assert all(isinstance(card, CardData) for card in last_result)


def test_generate_phase2_translation_plus_tts(mock_english_texts, mock_spanish_translations):
    """Translation+TTS: additional yield at 70% for audio generation, CardData includes audio_paths."""
    from core.pipeline import generate_phase2
    from core.types import AudioResult

    mock_engine = MagicMock()
    mock_engine.generate.return_value = MagicMock(
        generated_texts=list(mock_spanish_translations)
    )

    mock_audio_result = MagicMock()
    mock_audio_result.audio_paths = ["/tmp/audio_0.wav", "/tmp/audio_1.wav", "/tmp/audio_2.wav"]

    mock_tts_engine = MagicMock()
    mock_tts_engine.synthesize.return_value = mock_audio_result

    mock_pool = MagicMock()
    mock_pool.get_translation_engine.return_value = mock_engine
    mock_pool.get_tts_engine.return_value = mock_tts_engine

    with patch("core.pipeline.EnginePool", mock_pool):
        with patch("core.pipeline.EngineConfig.from_settings_yaml") as mock_config:
            mock_config.return_value.batch_size = 3
            yields = list(generate_phase2(
                english_texts=list(mock_english_texts),
                scenario="test",
                cefr_level=CEFRLevel.A1,
                batch_size=3,
                target_language="Spanish",
                include_audio=True,
                include_images=False,
            ))

    # Check that audio generation progress was yielded
    progress_labels = [p for p, _ in yields]
    assert any("audio" in str(p).lower() for p in progress_labels)

    # Final CardData should have audio_paths
    last_progress, last_result = yields[-1]
    assert len(last_result) == 3
    assert all(card.audio_path is not None for card in last_result)


def test_generate_phase2_progress_percentages():
    """Progress percentages: 20% prepare, 15-70% translation steps, 100% complete."""
    from core.pipeline import generate_phase2

    mock_engine = MagicMock()
    mock_engine.generate.return_value = MagicMock(generated_texts=["A.", "B."])

    mock_pool = MagicMock()
    mock_pool.get_translation_engine.return_value = mock_engine

    with patch("core.pipeline.EnginePool", mock_pool):
        with patch("core.pipeline.EngineConfig.from_settings_yaml") as mock_config:
            mock_config.return_value.batch_size = 2
            yields = list(generate_phase2(
                english_texts=["A.", "B."],
                scenario="test",
                cefr_level=CEFRLevel.A1,
                batch_size=2,
                target_language="Spanish",
                include_audio=False,
                include_images=False,
            ))

    # First yield should be ~20% (prepare)
    first_progress, _ = yields[0]
    assert "20" in str(first_progress) or "Preparing" in str(first_progress).lower()

    # Progress values increase during translation
    progress_values = []
    for p, _ in yields:
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
    mock_engine.generate.side_effect = ValidationError("Translation failed", raw_output="bad output")

    mock_pool = MagicMock()
    mock_pool.get_translation_engine.return_value = mock_engine

    with patch("core.pipeline.EnginePool", mock_pool):
        with patch("core.pipeline.EngineConfig.from_settings_yaml") as mock_config:
            mock_config.return_value.batch_size = 1
            with pytest.raises(ValidationError):
                list(generate_phase2(
                    english_texts=["A."],
                    scenario="test",
                    cefr_level=CEFRLevel.A1,
                    batch_size=1,
                    target_language="Spanish",
                    include_audio=False,
                    include_images=False,
                ))
```

---

### Task 11: Update AGENTS.md — Testing Expectations Section

**Files:**
- Modify: `AGENTS.md` (Testing Expectations section)

Replace the existing "Testing Expectations" section with:

```markdown
## Testing Expectations

### Pytest Test Suite

All tests use pytest. Run the full suite before committing:

```bash
uv run pytest tests/ -v
```

**Test file naming convention:** `*_test.py` — one file per source module, flat structure in `tests/`:

| Test File | Covers |
|---|---|
| `conftest.py` | Shared fixtures (mock data, paths, temp dirs) |
| `smoke_test.py` | Import validation + Pydantic model construction |
| `cards_test.py` | Card HTML rendering functions |
| `widgets_test.py` | Widget creation and UI state helpers |
| `app_test.py` | App async generators and helper functions |
| `audio_gen_test.py` | TTSEngine (TTS audio generation) |
| `image_gen_test.py` | ImageGenEngine (image generation) |
| `engine_test.py` | MiniCPMTextEngine, LlamaCppTextEngine, EnginePool |
| `pipeline_test.py` | Phase 2 orchestration |
| `text_gen_test.py` | Sentence extraction + text generation |

### Writing Tests

- Use fixtures from `tests/conftest.py` for mock data and paths.
- Mock all GPU/model code via `unittest.mock.patch` — no real inference needed.
- Use assertions (`assert`, `pytest.raises`) instead of print statements.
- Generator functions consumed via `list(handler(...))` to capture all yields.
- Real `.wav` and `.png` files from `tests/test_outputs/` serve as file-existence fixtures.

### Smoke Tests

Run `uv run pytest tests/smoke_test.py -v` for a quick sanity check: imports all modules, validates Pydantic models, and checks that the Gradio app can be constructed without errors.

### Inline Tests (Legacy)

The old `if __name__ == "__main__":` inline test pattern is deprecated. All tests should be in `*_test.py` files under `tests/`. Do not add new inline tests.
```

---

### Task 12: Update README.md — Add Running Tests Section

**Files:**
- Modify: `README.md` (add after setup/installation section)

Add a new "Running Tests" section:

```markdown
### Running Tests

All tests use pytest. Run the full suite:

```bash
# Run all tests
uv run pytest tests/ -v

# Run specific test file
uv run pytest tests/cards_test.py -v

# Run with coverage
uv run pytest tests/ -v --cov=core --cov=frontend --cov=app.py
```

The test suite mocks all GPU/model code — no model weights or GPU required to run tests.
```

---

## Execution Order

1. **conftest.py** (Task 1) — foundation for all other tests
2. **smoke_test.py** (Task 2) — validates imports before testing dependent modules
3. **cards_test.py** (Task 3) — pure HTML rendering, no dependencies
4. **widgets_test.py** (Task 4) — widget creation, independent of app logic
5. **app_test.py** (Task 5) — depends on cards_test patterns for generator testing
6. **audio_gen_test.py** (Task 6) — engine mocking pattern established
7. **image_gen_test.py** (Task 7) — mirrors audio_gen pattern
8. **text_gen_test.py** (Task 8) — merges old tests, pure functions
9. **engine_test.py** (Task 9) — merges translation_retry_test, complex mocking
10. **pipeline_test.py** (Task 10) — highest-level orchestration test
11. **AGENTS.md update** (Task 11) — documentation
12. **README.md update** (Task 12) — documentation

## Post-Migration Cleanup (after all tasks pass)

After the full test suite passes (`uv run pytest tests/ -v`):

```bash
# Remove old inline test files
rm tests/count_enforcement_test.py
rm tests/extract_sentences_test.py
rm tests/translation_retry_test.py
rm tests/progression_test.py
```

Then update `README.md` file tree section to reflect new test file structure.

## Verification Checklist

- [ ] `uv run pytest tests/ -v` passes with 0 failures
- [ ] All old inline test files removed
- [ ] AGENTS.md testing section updated
- [ ] README.md has "Running Tests" section
- [ ] No import errors in any test file (verified by smoke_test.py)
