"""Tests for export/apkg_export.py — Direct genanki .apkg export."""

import io
import json
import sqlite3
import zipfile
from pathlib import Path

import pytest

# Import functions under test — will fail until module exists
from export.apkg_export import (
    _LANGUAGE_ABBREVS,
    _get_language_abbrev,
    _sanitize_folder_name,
    export_csv_for_anki,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _open_apkg_db(apkg_path: str) -> sqlite3.Connection:
    """Open the collection.anki2 SQLite database from an .apkg file."""
    with zipfile.ZipFile(apkg_path, 'r') as zf:
        data = zf.read('collection.anki2')
    db = sqlite3.connect(':memory:')
    db.executescript(f"ATTACH DATABASE '{apkg_path}' AS zipfs;")
    # Write bytes to memory DB via cursor
    db.execute("CREATE TABLE IF NOT EXISTS dummy(x)")
    db.commit()
    # Use a simpler approach: write to temp file
    import tempfile
    fd, tmp = tempfile.mkstemp(suffix='.db')
    try:
        import os
        os.write(fd, data)
        os.close(fd)
        mem_db = sqlite3.connect(f'file:{tmp}?mode=memory', uri=True)
        real_db = sqlite3.connect(tmp)
        mem_db.execute("ATTACH DATABASE ? AS real", (tmp,))
        # Actually, let's just return a connection to the temp file and clean up later
        real_db.close()
        return sqlite3.connect(f'file:{tmp}?mode=rwc', uri=True)
    except Exception:
        pass
    # Fallback: direct in-memory approach
    mem = sqlite3.connect(':memory:')
    mem.execute(f"CREATE TABLE data AS SELECT * FROM (SELECT '{apkg_path}' as p)")
    # Better fallback: use raw bytes via a file-like wrapper
    import tempfile as tf
    fd2, tmp2 = tf.mkstemp(suffix='.db')
    os.write(fd2, data)
    os.close(fd2)
    return sqlite3.connect(tmp2), tmp2


def _get_db_from_apkg(apkg_path: str):
    """Open the collection.anki2 SQLite database from an .apkg file.

    Returns (connection, temp_path_or_None). Caller must close() the connection
    and unlink the temp file if one was created.
    """
    with zipfile.ZipFile(apkg_path, 'r') as zf:
        data = zf.read('collection.anki2')
    import tempfile, os
    fd, tmp = tempfile.mkstemp(suffix='.db')
    os.write(fd, data)
    os.close(fd)
    db = sqlite3.connect(tmp)
    return db, tmp


@pytest.fixture
def sample_cards():
    """Sample card data matching the structure from Phase 2."""
    return [
        {
            "text": "I love eating fresh fruits.",
            "translation": "Me encanta comer frutas frescas.",
            "audio_path": str(PROJECT_ROOT / "tests" / "test_outputs" / "audio" / "audio_0.wav"),
            "image_path": str(PROJECT_ROOT / "tests" / "test_outputs" / "images" / "image_0.png"),
        },
        {
            "text": "She enjoys cooking pasta.",
            "translation": "Le encanta cocinar pasta.",
            "audio_path": None,
            "image_path": str(PROJECT_ROOT / "tests" / "test_outputs" / "images" / "image_1.png"),
        },
        {
            "text": "The chef prepared a delicious meal.",
            "translation": "El chef preparó una comida deliciosa.",
            "audio_path": str(PROJECT_ROOT / "tests" / "test_outputs" / "audio" / "audio_2.wav"),
            "image_path": None,
        },
    ]


@pytest.fixture
def tmp_export_base(monkeypatch, tmp_path):
    """Fixture that patches _PROJECT_ROOT to tmp_path and returns the export base dir."""
    import export.apkg_export as mod
    monkeypatch.setattr(mod, '_PROJECT_ROOT', tmp_path)
    return tmp_path / ".local" / "models" / "output" / "export"


class TestSanitizeFolderName:
    """Tests for _sanitize_folder_name helper — same logic as csv_export."""

    def test_simple_scenario(self):
        assert _sanitize_folder_name("ordering coffee") == "ordering_coffee"

    def test_special_chars_removed(self):
        assert _sanitize_folder_name("hello! world?") == "hello_world"

    def test_multiple_spaces_collapsed(self):
        assert _sanitize_folder_name("many   spaces   here") == "many_spaces_here"


class TestLanguageAbbrevMapping:
    """Tests for _get_language_abbreviation helper."""

    def test_all_languages_mapped(self):
        expected = {
            "Latvian": "LV", "Spanish": "ES", "French": "FR",
            "German": "DE", "Polish": "PL", "Italian": "IT",
            "Portuguese": "PT", "Finnish": "FI",
        }
        assert _LANGUAGE_ABBREVS == expected

    def test_invalid_language_raises(self):
        with pytest.raises(ValueError, match="Unknown language"):
            _get_language_abbrev("Japanese")


class TestExportApkg:
    """Tests for the main export_csv_for_anki function using genanki."""

    def test_export_returns_apkg_path(self, sample_cards, tmp_export_base):
        """Function returns a valid .apkg file path string."""
        apkg_path = export_csv_for_anki(
            cards=sample_cards,
            scenario="ordering coffee",
            cefr_level="A2",
            target_language="Latvian",
        )
        assert isinstance(apkg_path, str)
        assert Path(apkg_path).is_absolute()
        assert apkg_path.endswith('.apkg')

    def test_apkg_file_exists(self, sample_cards, tmp_export_base):
        """The .apkg file is actually created on disk."""
        apkg_path = export_csv_for_anki(
            cards=sample_cards,
            scenario="ordering coffee",
            cefr_level="A2",
            target_language="Latvian",
        )
        assert Path(apkg_path).exists()

    def test_apkg_is_valid_zip(self, sample_cards):
        """An .apkg file is a valid zip archive with collection.anki2 and media/."""
        apkg_path = export_csv_for_anki(
            cards=sample_cards,
            scenario="ordering coffee",
            cefr_level="A2",
            target_language="Latvian",
        )
        with zipfile.ZipFile(apkg_path, 'r') as zf:
            names = zf.namelist()
            assert any('collection.anki2' in n for n in names)
            assert any('media' in n for n in names)

    def test_apkg_contains_media_files(self, sample_cards):
        """Media files are bundled into the .apkg archive."""
        apkg_path = export_csv_for_anki(
            cards=sample_cards,
            scenario="ordering coffee",
            cefr_level="A2",
            target_language="Latvian",
        )
        with zipfile.ZipFile(apkg_path, 'r') as zf:
            # genanki 0.13 stores media as numeric indices with a JSON mapping
            media_json = json.loads(zf.read('media'))
            media_names = list(media_json.values())
            # Card 0 has both audio and image
            assert any('ordering_coffee_A2_LV_0.wav' in n for n in media_names)
            assert any('ordering_coffee_A2_LV_0.png' in n for n in media_names)
            # Card 1 has only image
            assert any('ordering_coffee_A2_LV_1.png' in n for n in media_names)
            # Card 2 has only audio
            assert any('ordering_coffee_A2_LV_2.wav' in n for n in media_names)

    def test_apkg_note_count_matches_cards(self, sample_cards):
        """One note per card — verify via notes table in collection.anki2."""
        apkg_path = export_csv_for_anki(
            cards=sample_cards,
            scenario="ordering coffee",
            cefr_level="A2",
            target_language="Latvian",
        )
        db, tmp = _get_db_from_apkg(apkg_path)
        try:
            cursor = db.cursor()
            cursor.execute("SELECT COUNT(*) FROM notes")
            count = cursor.fetchone()[0]
            assert count == 3
        finally:
            db.close()
            import os
            os.unlink(tmp)

    def test_apkg_note_fields_correct(self, sample_cards):
        """Notes contain correct TargetText and EnglishText."""
        apkg_path = export_csv_for_anki(
            cards=sample_cards,
            scenario="ordering coffee",
            cefr_level="A2",
            target_language="Latvian",
        )
        db, tmp = _get_db_from_apkg(apkg_path)
        try:
            cursor = db.cursor()
            cursor.execute("SELECT flds FROM notes ORDER BY id LIMIT 1")
            flds_raw = cursor.fetchone()[0]
            # Fields are separated by \x1f (unit separator)
            fields = flds_raw.split('\x1f')
            assert len(fields) >= 2
            assert "Me encanta comer frutas frescas." in fields[0]
            assert "I love eating fresh fruits." in fields[1]
        finally:
            db.close()
            import os
            os.unlink(tmp)

    def test_apkg_deck_name(self, sample_cards):
        """Deck name matches 'EuropaLex Flashcards'."""
        apkg_path = export_csv_for_anki(
            cards=sample_cards,
            scenario="ordering coffee",
            cefr_level="A2",
            target_language="Latvian",
        )
        db, tmp = _get_db_from_apkg(apkg_path)
        try:
            cursor = db.cursor()
            cursor.execute("SELECT decks FROM col LIMIT 1")
            decks_json = cursor.fetchone()[0]
            decks = json.loads(decks_json)
            # Find the EuropaLex Flashcards deck among all decks
            found = any(d['name'] == 'EuropaLex Flashcards' for d in decks.values())
            assert found, f"Expected 'EuropaLex Flashcards' deck, got: {list(decks.values())}"
        finally:
            db.close()
            import os
            os.unlink(tmp)

    def test_missing_media_skipped_gracefully(self, tmp_export_base):
        """No error when audio/image path is None or file doesn't exist."""
        cards_no_media = [
            {
                "text": "No media card",
                "translation": "Sin multimedia",
                "audio_path": None,
                "image_path": None,
            },
            {
                "text": "Missing file card",
                "translation": "Falta archivo",
                "audio_path": "/nonexistent/path.wav",
                "image_path": "/nonexistent/path.png",
            },
        ]
        apkg_path = export_csv_for_anki(
            cards=cards_no_media,
            scenario="no media test",
            cefr_level="A1",
            target_language="Spanish",
        )
        assert Path(apkg_path).exists()

    def test_empty_cards_raises_valueerror(self):
        """Raises ValueError when no cards provided."""
        with pytest.raises(ValueError, match="No cards"):
            export_csv_for_anki([], "test", "A1", "Spanish")

    def test_single_card(self, tmp_export_base):
        """Single card exports correctly."""
        single_card = [
            {
                "text": "Hello world",
                "translation": "Hola mundo",
                "audio_path": None,
                "image_path": None,
            },
        ]
        apkg_path = export_csv_for_anki(
            cards=single_card,
            scenario="greetings",
            cefr_level="A1",
            target_language="Spanish",
        )
        db, tmp = _get_db_from_apkg(apkg_path)
        try:
            cursor = db.cursor()
            cursor.execute("SELECT COUNT(*) FROM notes")
            count = cursor.fetchone()[0]
            assert count == 1
        finally:
            db.close()
            import os
            os.unlink(tmp)

    def test_apkg_structure_has_deck_and_model(self, sample_cards):
        """The .apkg contains collection.anki2 with deck and model definitions."""
        apkg_path = export_csv_for_anki(
            cards=sample_cards,
            scenario="ordering coffee",
            cefr_level="A2",
            target_language="Latvian",
        )
        db, tmp = _get_db_from_apkg(apkg_path)
        try:
            cursor = db.cursor()
            # Check col table has decks and models columns
            cursor.execute("SELECT decks, models FROM col LIMIT 1")
            row = cursor.fetchone()
            assert row is not None
            decks = json.loads(row[0])
            models = json.loads(row[1])
            assert len(decks) >= 1
            assert len(models) >= 1
        finally:
            db.close()
            import os
            os.unlink(tmp)
