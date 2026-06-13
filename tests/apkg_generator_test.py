"""Tests for export/apkg_generator.py — APKG generation with embedded media."""

import json
import zipfile
from pathlib import Path

import pytest

# Import functions under test
from export.apkg_generator import (
    MODEL_ID,
    MODEL_NAME,
    FIELDS,
    TEMPLATE,
    _create_model,
    _create_note,
    _create_package,
    _inject_media,
    generate_apkg_package,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class TestModelCreation:
    """Tests for model constants and _create_model function."""

    def test_model_id_is_in_range(self):
        """MODEL_ID is a valid genanki model ID (30-bit unsigned integer)."""
        assert 1 << 30 <= MODEL_ID < 1 << 31

    def test_model_name(self):
        assert MODEL_NAME == "EuropaLex Flashcard"

    def test_fields_have_four_entries(self):
        assert len(FIELDS) == 4
        expected_names = ["Translation", "English", "Audio", "Image"]
        for i, field in enumerate(FIELDS):
            assert field["name"] == expected_names[i]

    def test_template_structure(self):
        """Template has correct name and field references."""
        assert TEMPLATE["name"] == "Card 1"
        assert "{{Translation}}" in TEMPLATE["qfmt"]
        assert "{{Image}}" in TEMPLATE["qfmt"]
        assert "{{Audio}}" in TEMPLATE["qfmt"]
        assert "{{FrontSide}}" in TEMPLATE["afmt"]

    def test_create_model_returns_genanki_model(self):
        """_create_model returns a genanki.Model instance with correct attributes."""
        import genanki
        model = _create_model()
        assert isinstance(model, genanki.Model)
        assert model.name == MODEL_NAME
        assert len(model.fields) == 4
        assert len(model.templates) == 1

    def test_create_model_field_names(self):
        """Model fields have correct names in order."""
        import genanki
        model = _create_model()
        field_names = [f["name"] for f in model.fields]
        assert field_names == ["Translation", "English", "Audio", "Image"]

    def test_create_model_template_order(self):
        """Template qfmt order: Translation, Image, Audio (matching spec)."""
        import genanki
        model = _create_model()
        qfmt = model.templates[0]["qfmt"]
        # Translation should come before Image, which comes before Audio
        ord_translation = qfmt.index("{{Translation}}")
        ord_image = qfmt.index("{{Image}}")
        ord_audio = qfmt.index("{{Audio}}")
        assert ord_translation < ord_image < ord_audio


class TestNoteCreation:
    """Tests for _create_note function."""

    def test_text_fields_escaped(self):
        """Text fields are HTML-escaped to prevent injection."""
        import genanki
        model = _create_model()
        note = _create_note(
            model=model,
            translation="Hello <script>alert('xss')</script>",
            english='Test & "quotes"',
            audio_path=None,
            image_path=None,
        )
        assert isinstance(note, genanki.Note)
        # HTML entities should be escaped
        assert "&lt;script&gt;" in note.fields[0]
        assert "&amp;" in note.fields[1]

    def test_audio_field_with_path(self):
        """Audio field contains <audio> tag with original filename."""
        import genanki
        model = _create_model()
        note = _create_note(
            model=model,
            translation="Hola",
            english="Hello",
            audio_path="/some/path/hello_A2_LV_0.wav",
            image_path=None,
        )
        assert "<audio controls src=" in note.fields[2]
        assert "hello_A2_LV_0.wav" in note.fields[2]

    def test_image_field_with_path(self):
        """Image field contains <img> tag with original filename."""
        import genanki
        model = _create_model()
        note = _create_note(
            model=model,
            translation="Hola",
            english="Hello",
            audio_path=None,
            image_path="/some/path/hello_A2_LV_0.png",
        )
        assert "<img src=" in note.fields[3]
        assert "hello_A2_LV_0.png" in note.fields[3]

    def test_empty_media_paths_become_empty_strings(self):
        """None audio/image paths produce empty string fields."""
        import genanki
        model = _create_model()
        note = _create_note(
            model=model,
            translation="Hello",
            english="Hola",
            audio_path=None,
            image_path=None,
        )
        assert note.fields[2] == ""  # Audio field
        assert note.fields[3] == ""  # Image field

    def test_note_has_correct_field_count(self):
        """Note has exactly 4 fields matching model definition."""
        import genanki
        model = _create_model()
        note = _create_note(
            model=model,
            translation="A",
            english="B",
            audio_path=None,
            image_path=None,
        )
        assert len(note.fields) == 4
