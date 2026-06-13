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


class TestPackageGeneration:
    """Tests for _create_package function."""

    def test_package_returns_path(self, tmp_path):
        """_create_package returns an absolute path string."""
        model = _create_model()
        notes = [
            _create_note(model, "Hola", "Hello"),
            _create_note(model, "Adios", "Goodbye"),
        ]
        pkg_path = _create_package(notes, scenario="greetings", cefr_level="A1", target_language="Spanish")
        assert isinstance(pkg_path, str)
        assert Path(pkg_path).is_absolute()

    def test_package_is_valid_zip(self, tmp_path):
        """Generated .apkg is a valid zip file."""
        model = _create_model()
        notes = [_create_note(model, "Hola", "Hello")]
        pkg_path = _create_package(notes, scenario="test", cefr_level="A1", target_language="Spanish")
        assert zipfile.is_zipfile(pkg_path)

    def test_package_has_collection_anki2(self, tmp_path):
        """Package contains collection.anki2 database."""
        model = _create_model()
        notes = [_create_note(model, "Hola", "Hello")]
        pkg_path = _create_package(notes, scenario="test", cefr_level="A1", target_language="Spanish")
        with zipfile.ZipFile(pkg_path, 'r') as zf:
            assert 'collection.anki2' in zf.namelist()

    def test_package_has_media_manifest(self, tmp_path):
        """Package contains media JSON manifest."""
        model = _create_model()
        notes = [_create_note(model, "Hola", "Hello")]
        pkg_path = _create_package(notes, scenario="test", cefr_level="A1", target_language="Spanish")
        with zipfile.ZipFile(pkg_path, 'r') as zf:
            assert 'media' in zf.namelist()
            manifest = json.loads(zf.read('media'))
            assert isinstance(manifest, dict)

    def test_package_deck_name_includes_scenario(self, tmp_path):
        """Deck name derives from scenario with CEFR and language abbreviation."""
        model = _create_model()
        notes = [_create_note(model, "Hola", "Hello")]
        pkg_path = _create_package(notes, scenario="ordering coffee", cefr_level="A2", target_language="Latvian")
        import sqlite3
        with zipfile.ZipFile(pkg_path, 'r') as zf:
            db_bytes = zf.read('collection.anki2')
        tmp_db = tmp_path / "temp.db"
        tmp_db.write_bytes(db_bytes)
        conn = sqlite3.connect(str(tmp_db))
        cur = conn.cursor()
        # Decks are stored as JSON in the 'decks' column of the 'col' table
        # Structure: {deck_id_str: {name: "...", ...}}
        cur.execute("SELECT decks FROM col")
        row = cur.fetchone()
        if row and row[0]:
            decks_data = json.loads(row[0])
            # Find any deck with 'ordering_coffee' in its name
            found = any(
                isinstance(v, dict) and 'ordering_coffee' in v.get('name', '').lower()
                for v in decks_data.values()
            )
            assert found, f"Deck name not found. Decks data: {decks_data}"
        conn.close()

    def test_package_contains_all_notes(self, tmp_path):
        """Package database contains the correct number of notes."""
        model = _create_model()
        notes = [
            _create_note(model, "A", "1"),
            _create_note(model, "B", "2"),
            _create_note(model, "C", "3"),
        ]
        pkg_path = _create_package(notes, scenario="test", cefr_level="A1", target_language="Spanish")
        import sqlite3
        with zipfile.ZipFile(pkg_path, 'r') as zf:
            db_bytes = zf.read('collection.anki2')
        tmp_db = tmp_path / "temp.db"
        tmp_db.write_bytes(db_bytes)
        conn = sqlite3.connect(str(tmp_db))
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM notes")
        count = cur.fetchone()[0]
        conn.close()
        assert count == 3

    def test_package_no_media_files_when_none(self, tmp_path):
        """Package has no media files when all audio/image paths are None."""
        model = _create_model()
        notes = [_create_note(model, "Hola", "Hello")]
        pkg_path = _create_package(notes, scenario="test", cefr_level="A1", target_language="Spanish")
        with zipfile.ZipFile(pkg_path, 'r') as zf:
            names = zf.namelist()
            # Should only have collection.anki2 and media — no numbered files or .wav/.png
            assert len([n for n in names if n.endswith('.wav') or n.endswith('.png')]) == 0
