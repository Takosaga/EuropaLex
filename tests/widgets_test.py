"""Tests for frontend.ui.widgets widget creation and UI state helpers."""

import sys
import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture(autouse=True)
def _mock_gradio():
    """Mock gradio module before any widget functions are called."""
    mock_gr = MagicMock()
    mock_gr.Blocks = MagicMock()
    mock_gr.Checkbox = MagicMock()
    mock_gr.Button = MagicMock()
    mock_gr.Dropdown = MagicMock()
    with patch.dict('sys.modules', {'gradio': mock_gr}):
        yield mock_gr


def test_create_toggle_label_with_emoji(_mock_gradio):
    """Toggle label includes the provided emoji prefix."""
    from frontend.ui.widgets import create_toggle

    checkbox = create_toggle("🖼️ Images", value=True, elem_id="toggle-images")
    _mock_gradio.Checkbox.assert_called()
    call_kwargs = _mock_gradio.Checkbox.call_args[1]
    assert "Images" in str(call_kwargs.get("label", ""))


def test_create_toggle_default_value(_mock_gradio):
    """Toggle respects the default value parameter."""
    from frontend.ui.widgets import create_toggle

    checkbox_false = create_toggle("🔊 Audio", value=False, elem_id="toggle-audio")
    call_kwargs = _mock_gradio.Checkbox.call_args[1]
    assert call_kwargs.get("value") is False


def test_create_toggle_elem_id_generation(_mock_gradio):
    """elem_id follows the pattern toggle-<label-without-emoji>."""
    from frontend.ui.widgets import create_toggle

    create_toggle("🖼️ Images", value=True, elem_id="toggle-images")
    call_kwargs = _mock_gradio.Checkbox.call_args[1]
    assert call_kwargs.get("elem_id") == "toggle-images"


def test_create_voice_dropdown_all_choices(_mock_gradio):
    """All 6 voice choices present in dropdown."""
    from frontend.ui.widgets import create_voice_dropdown

    dropdown = create_voice_dropdown()
    call_kwargs = _mock_gradio.Dropdown.call_args[1]
    choices = call_kwargs.get("choices", [])
    assert len(choices) == 6


def test_create_voice_dropdown_default_value(_mock_gradio):
    """Default value is 'female, young adult' (instruct string)."""
    from frontend.ui.widgets import create_voice_dropdown

    create_voice_dropdown()
    call_kwargs = _mock_gradio.Dropdown.call_args[1]
    default = call_kwargs.get("value")
    assert default == "female, young adult"


def test_create_voice_dropdown_elem_id(_mock_gradio):
    """Voice dropdown elem_id is 'voice-dropdown'."""
    from frontend.ui.widgets import create_voice_dropdown

    create_voice_dropdown()
    call_kwargs = _mock_gradio.Dropdown.call_args[1]
    assert call_kwargs.get("elem_id") == "voice-dropdown"


def test_voice_map_all_six_entries():
    """_VOICE_MAP has exactly 6 entries mapping display labels to instruct strings."""
    from frontend.ui.widgets import _VOICE_MAP

    assert len(_VOICE_MAP) == 6


def test_voice_map_instruct_strings_format():
    """All _VOICE_MAP values are comma-separated gender, age format."""
    from frontend.ui.widgets import _VOICE_MAP

    for label, instruct in _VOICE_MAP.items():
        parts = instruct.split(", ")
        assert len(parts) == 2
        assert parts[0] in ("female", "male")
        assert parts[1] in ("young adult", "middle-aged", "senior", "teenager")


def test_enable_phase2_returns_tuple(_mock_gradio):
    """_enable_phase2() returns tuple of (Checkbox, Checkbox, Button, Dropdown, CSS).

    Export buttons are NOT enabled here — they are enabled after Phase 2 completes
    (when _current_cards is populated) via _on_media_generation_complete().
    """
    from frontend.ui.widgets import _enable_phase2

    result = _enable_phase2()
    assert isinstance(result, tuple)
    assert len(result) == 5


def test_reset_to_idle_returns_tuple(_mock_gradio):
    """_reset_to_idle() returns tuple with interactive=False, disabled CSS string, and download CSV button."""
    from frontend.ui.widgets import _reset_to_idle

    result = _reset_to_idle()
    assert isinstance(result, tuple)
    assert len(result) == 7
    # Element at index 5 should be a CSS string (non-empty)
    assert isinstance(result[5], str)
    assert len(result[5]) > 0
    # Last element should be the download CSV button mock
    assert isinstance(result[6], MagicMock)


def test_reset_to_idle_disabled_css_content(_mock_gradio):
    """_reset_to_idle() CSS targets the right elem_ids."""
    from frontend.ui.widgets import _reset_to_idle

    result = _reset_to_idle()
    css = result[5]
    assert "europalex-btn-disabled" in css or "toggle-images" in css
    assert "#voice-dropdown" in css


def test_enable_language_dropdown_on_audio_true(_mock_gradio):
    """Audio toggle ON → removes disabled CSS, enables dropdown."""
    from frontend.ui.widgets import _enable_language_dropdown_on_audio

    result = _enable_language_dropdown_on_audio(True)
    assert isinstance(result, tuple)
    # Should return (dropdown_update, "") — empty CSS means enabled
    assert result[1] == ""


def test_enable_language_dropdown_on_audio_false(_mock_gradio):
    """Audio toggle OFF → applies disabled CSS to voice dropdown."""
    from frontend.ui.widgets import _enable_language_dropdown_on_audio

    result = _enable_language_dropdown_on_audio(False)
    assert isinstance(result, tuple)
    # Should return (dropdown_update, css_string) — non-empty CSS means disabled
    assert isinstance(result[1], str)
    assert len(result[1]) > 0
    assert "#voice-dropdown" in result[1]
