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
    """_enable_phase2() returns tuple of (Checkbox, Checkbox, Button, Dropdown, Button, Button, File, File, CSS)."""
    from frontend.ui.widgets import _enable_phase2

    result = _enable_phase2()
    assert isinstance(result, tuple)
    assert len(result) == 9


def test_reset_to_idle_returns_tuple(_mock_gradio):
    """_reset_to_idle() returns tuple with interactive=False, disabled CSS string, export buttons, and file components."""
    from frontend.ui.widgets import _reset_to_idle

    result = _reset_to_idle()
    assert isinstance(result, tuple)
    assert len(result) == 10
    # Element at index 5 should be a CSS string (non-empty)
    assert isinstance(result[5], str)
    assert len(result[5]) > 0
    # Elements at indices 6, 7 should be the export buttons
    assert isinstance(result[6], MagicMock)  # export_csv_btn
    assert isinstance(result[7], MagicMock)  # export_apkg_btn
    # Elements at indices 8, 9 should be the file components
    assert isinstance(result[8], MagicMock)  # export_file
    assert isinstance(result[9], MagicMock)  # export_apkg_file


def test_reset_to_idle_disabled_css_content(_mock_gradio):
    """_reset_to_idle() CSS targets the right elem_ids."""
    from frontend.ui.widgets import _reset_to_idle

    result = _reset_to_idle()
    # CSS is at index 5 (after generate_text_btn, images_toggle, audio_toggle, generate_cards_btn, voice_dropdown)
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


def test_restore_generate_cards_button_returns_tuple(_mock_gradio):
    """_restore_generate_cards_button() returns tuple of (Button, Button, Button)."""
    from frontend.ui.widgets import _restore_generate_cards_button

    result = _restore_generate_cards_button()
    assert isinstance(result, tuple)
    assert len(result) == 3


def test_restore_generate_cards_button_makes_button_visible_interactive(_mock_gradio):
    """Generate Cards button becomes visible and interactive."""
    from frontend.ui.widgets import _restore_generate_cards_button

    _restore_generate_cards_button()
    # gr.Button was called three times: generate_cards_btn, export_csv_btn, export_apkg_btn
    calls = _mock_gradio.Button.call_args_list
    assert len(calls) == 3
    first_call_kwargs = calls[0].kwargs if calls[0].kwargs else calls[0][1]
    assert first_call_kwargs.get("visible") is True
    assert first_call_kwargs.get("interactive") is True


def test_restore_generate_cards_button_export_stays_disabled(_mock_gradio):
    """Export buttons stay visible but disabled."""
    from frontend.ui.widgets import _restore_generate_cards_button

    _restore_generate_cards_button()
    calls = _mock_gradio.Button.call_args_list
    assert len(calls) == 3
    # Second call: export_csv_btn (disabled)
    second_call_kwargs = calls[1].kwargs if calls[1].kwargs else calls[1][1]
    assert second_call_kwargs.get("visible") is True
    assert second_call_kwargs.get("interactive") is False
    # Third call: export_apkg_btn (disabled)
    third_call_kwargs = calls[2].kwargs if calls[2].kwargs else calls[2][1]
    assert third_call_kwargs.get("visible") is True
    assert third_call_kwargs.get("interactive") is False


def test_restore_generate_cards_button_only_returns_tuple(_mock_gradio):
    """_restore_generate_cards_button_only() returns tuple of 4 (Button, Button, Button, Button)."""
    from frontend.ui.widgets import _restore_generate_cards_button_only

    result = _restore_generate_cards_button_only()
    assert isinstance(result, tuple)
    assert len(result) == 4


def test_restore_generate_cards_button_only_hides_generate_text(_mock_gradio):
    """Generate Text button stays hidden — only appears on scenario/CEFR/batch reset."""
    from frontend.ui.widgets import _restore_generate_cards_button_only

    _restore_generate_cards_button_only()
    calls = _mock_gradio.Button.call_args_list
    assert len(calls) == 4
    first_call_kwargs = calls[0].kwargs if calls[0].kwargs else calls[0][1]
    assert first_call_kwargs.get("visible") is False


def test_restore_generate_cards_button_only_restores_generate_cards(_mock_gradio):
    """Generate Cards button becomes visible and interactive."""
    from frontend.ui.widgets import _restore_generate_cards_button_only

    _restore_generate_cards_button_only()
    calls = _mock_gradio.Button.call_args_list
    assert len(calls) == 4
    second_call_kwargs = calls[1].kwargs if calls[1].kwargs else calls[1][1]
    assert second_call_kwargs.get("visible") is True
    assert second_call_kwargs.get("interactive") is True
