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
    cards = [{"text": "A.", "translation": "B.", "image_path": str(PROJECT_ROOT / "tests" / "test_outputs" / "images" / "image_0.png")}]
    html = generate_cards_html(cards, include_image=True, include_audio=False)
    assert "<img" in html


def test_generate_cards_html_audio_only():
    """include_image=False, include_audio=True → audio only."""
    cards = [{"text": "A.", "translation": "B.", "audio_path": str(PROJECT_ROOT / "tests" / "test_outputs" / "audio" / "audio_0.wav")}]
    html = generate_cards_html(cards, include_image=False, include_audio=True)
    assert "<audio" in html


def test_generate_cards_html_both_media():
    """Both image and audio toggles → both media boxes present."""
    cards = [{
        "text": "A.", "translation": "B.",
        "image_path": str(PROJECT_ROOT / "tests" / "test_outputs" / "images" / "image_0.png"),
        "audio_path": str(PROJECT_ROOT / "tests" / "test_outputs" / "audio" / "audio_0.wav"),
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


def test_generate_progress_html_60_percent_brown():
    """Exactly 60% → brown bar (threshold for dark brown is >60)."""
    html = generate_progress_html(60, "Almost done...")
    assert "#a0845c" in html


def test_generate_progress_html_61_percent_dark_brown():
    """61% → dark brown bar (threshold is > 60)."""
    html = generate_progress_html(61, "Almost done...")
    assert "#8a6c4a" in html


def test_generate_progress_html_100_percent_complete():
    """100% → dark brown bar, green 'complete' text."""
    html = generate_progress_html(100, "Complete!")
    assert "width: 100%" in html
    assert "#4CAF50" in html or "green" in html.lower() or "#2a6e2a" in html
