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


class TestMediaInjection:
    """Tests for _inject_media function."""

    def test_inject_audio_updates_manifest(self, tmp_path):
        """Audio file is hashed and added to media manifest."""
        model = _create_model()
        # Create a real .wav file in temp dir
        wav_dir = tmp_path / "audio"
        wav_dir.mkdir()
        wav_path = str(wav_dir / "test_A2_LV_0.wav")
        Path(wav_path).write_bytes(b'\x00' * 100)  # dummy WAV content

        notes = [_create_note(model, "Hola", "Hello", audio_path=wav_path)]
        pkg_path = _create_package(notes, scenario="test", cefr_level="A2", target_language="Latvian")

        # Inject media
        cards_for_inject = [{"audio_path": wav_path, "image_path": None}]
        _inject_media(pkg_path, cards_for_inject)

        with zipfile.ZipFile(pkg_path, 'r') as zf:
            manifest = json.loads(zf.read('media'))
            # Manifest should have an entry with a 32-char hex hash key
            assert len(manifest) == 1
            hash_key = list(manifest.keys())[0]
            assert len(hash_key) == 36  # 32 hex chars + ".wav"
            assert hash_key.endswith(".wav")
            assert manifest[hash_key] == "test_A2_LV_0.wav"

    def test_inject_image_updates_manifest(self, tmp_path):
        """Image file is hashed and added to media manifest."""
        model = _create_model()
        png_dir = tmp_path / "images"
        png_dir.mkdir()
        png_path = str(png_dir / "test_A2_LV_0.png")
        Path(png_path).write_bytes(b'\x89PNG\r\n\x1a\n' + b'\x00' * 100)  # fake PNG header

        notes = [_create_note(model, "Hola", "Hello", image_path=png_path)]
        pkg_path = _create_package(notes, scenario="test", cefr_level="A2", target_language="Latvian")

        cards_for_inject = [{"audio_path": None, "image_path": png_path}]
        _inject_media(pkg_path, cards_for_inject)

        with zipfile.ZipFile(pkg_path, 'r') as zf:
            manifest = json.loads(zf.read('media'))
            assert len(manifest) == 1
            hash_key = list(manifest.keys())[0]
            assert hash_key.endswith(".png")

    def test_inject_media_file_in_zip(self, tmp_path):
        """Injected media file exists in the zip under hashed name."""
        model = _create_model()
        wav_dir = tmp_path / "audio"
        wav_dir.mkdir()
        wav_path = str(wav_dir / "test_A2_LV_0.wav")
        Path(wav_path).write_bytes(b'\x00' * 100)

        notes = [_create_note(model, "Hola", "Hello", audio_path=wav_path)]
        pkg_path = _create_package(notes, scenario="test", cefr_level="A2", target_language="Latvian")

        cards_for_inject = [{"audio_path": wav_path, "image_path": None}]
        _inject_media(pkg_path, cards_for_inject)

        with zipfile.ZipFile(pkg_path, 'r') as zf:
            names = zf.namelist()
            # Should have the hashed .wav file
            assert any(n.endswith('.wav') for n in names)

    def test_inject_deduplicates_same_file(self, tmp_path):
        """Same media file referenced by multiple cards is injected only once."""
        model = _create_model()
        wav_dir = tmp_path / "audio"
        wav_dir.mkdir()
        wav_path = str(wav_dir / "shared_A2_LV_0.wav")
        Path(wav_path).write_bytes(b'\x00' * 100)

        notes = [
            _create_note(model, "A", "1", audio_path=wav_path),
            _create_note(model, "B", "2", audio_path=wav_path),  # same file
        ]
        pkg_path = _create_package(notes, scenario="test", cefr_level="A2", target_language="Latvian")

        cards_for_inject = [
            {"audio_path": wav_path, "image_path": None},
            {"audio_path": wav_path, "image_path": None},  # duplicate reference
        ]
        _inject_media(pkg_path, cards_for_inject)

        with zipfile.ZipFile(pkg_path, 'r') as zf:
            manifest = json.loads(zf.read('media'))
            # Only one entry for the shared file
            assert len(manifest) == 1

    def test_inject_skips_missing_files(self, tmp_path):
        """Injection skips files that don't exist on disk."""
        model = _create_model()
        notes = [_create_note(model, "Hola", "Hello")]
        pkg_path = _create_package(notes, scenario="test", cefr_level="A2", target_language="Latvian")

        cards_for_inject = [{"audio_path": "/nonexistent/path.wav", "image_path": None}]
        _inject_media(pkg_path, cards_for_inject)

        # Should not crash; manifest stays empty
        with zipfile.ZipFile(pkg_path, 'r') as zf:
            manifest = json.loads(zf.read('media'))
            assert len(manifest) == 0

    def test_inject_preserves_existing_files(self, tmp_path):
        """Media injection doesn't corrupt the collection.anki2 database."""
        model = _create_model()
        notes = [_create_note(model, "Hola", "Hello")]
        pkg_path = _create_package(notes, scenario="test", cefr_level="A2", target_language="Latvian")

        # Record original database size and content hash
        with zipfile.ZipFile(pkg_path, 'r') as zf:
            original_db = zf.read('collection.anki2')

        wav_dir = tmp_path / "audio"
        wav_dir.mkdir()
        wav_path = str(wav_dir / "test_A2_LV_0.wav")
        Path(wav_path).write_bytes(b'\x00' * 100)

        cards_for_inject = [{"audio_path": wav_path, "image_path": None}]
        _inject_media(pkg_path, cards_for_inject)

        with zipfile.ZipFile(pkg_path, 'r') as zf:
            new_db = zf.read('collection.anki2')
            assert new_db == original_db  # database unchanged

    def test_hash_is_content_based(self, tmp_path):
        """MD5 hash is computed from file content, not filename."""
        model = _create_model()
        wav_dir = tmp_path / "audio"
        wav_dir.mkdir()
        # Two files with different names but identical content
        path1 = str(wav_dir / "name_a.wav")
        path2 = str(wav_dir / "name_b.wav")
        Path(path1).write_bytes(b'\x00' * 100)
        Path(path2).write_bytes(b'\x00' * 100)

        notes = [_create_note(model, "Hola", "Hello", audio_path=path1)]
        pkg_path = _create_package(notes, scenario="test", cefr_level="A2", target_language="Latvian")

        cards_for_inject = [
            {"audio_path": path1, "image_path": None},
            {"audio_path": path2, "image_path": None},  # same content, different name
        ]
        _inject_media(pkg_path, cards_for_inject)

        with zipfile.ZipFile(pkg_path, 'r') as zf:
            manifest = json.loads(zf.read('media'))
            # Only one entry because content is identical (dedup by hash)
            assert len(manifest) == 1


class TestGenerateApkgPackage:
    """Tests for the main generate_apkg_package function."""

    def test_returns_path(self, tmp_path):
        """Returns absolute path to .apkg file."""
        cards = [
            {
                "text": "Hello",
                "translation": "Hola",
                "audio_path": None,
                "image_path": None,
            },
        ]
        result = generate_apkg_package(cards, "greetings", "A1", "Spanish")
        assert isinstance(result, str)
        assert Path(result).is_absolute()

    def test_returns_valid_zip(self, tmp_path):
        """Return value is a valid zip file."""
        cards = [{"text": "Hello", "translation": "Hola", "audio_path": None, "image_path": None}]
        result = generate_apkg_package(cards, "greetings", "A1", "Spanish")
        assert zipfile.is_zipfile(result)

    def test_contains_note_data(self, tmp_path):
        """Package database contains correct number of notes."""
        cards = [
            {"text": "One", "translation": "Uno", "audio_path": None, "image_path": None},
            {"text": "Two", "translation": "Dos", "audio_path": None, "image_path": None},
            {"text": "Three", "translation": "Tres", "audio_path": None, "image_path": None},
        ]
        result = generate_apkg_package(cards, "numbers", "A1", "Spanish")
        import sqlite3
        with zipfile.ZipFile(result, 'r') as zf:
            db_bytes = zf.read('collection.anki2')
        tmp_db = tmp_path / "temp.db"
        tmp_db.write_bytes(db_bytes)
        conn = sqlite3.connect(str(tmp_db))
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM notes")
        count = cur.fetchone()[0]
        conn.close()
        assert count == 3

    def test_media_injected_when_paths_exist(self, tmp_path):
        """Audio/image files are injected into package when paths exist."""
        wav_dir = tmp_path / "audio"
        wav_dir.mkdir()
        wav_path = str(wav_dir / "test_A2_LV_0.wav")
        Path(wav_path).write_bytes(b'\x00' * 100)

        cards = [
            {
                "text": "Hello",
                "translation": "Hola",
                "audio_path": wav_path,
                "image_path": None,
            },
        ]
        result = generate_apkg_package(cards, "test", "A2", "Latvian")

        with zipfile.ZipFile(result, 'r') as zf:
            manifest = json.loads(zf.read('media'))
            assert len(manifest) == 1
            hash_key = list(manifest.keys())[0]
            assert hash_key.endswith(".wav")

    def test_no_media_when_all_none(self, tmp_path):
        """No media files in package when all paths are None."""
        cards = [{"text": "Hello", "translation": "Hola", "audio_path": None, "image_path": None}]
        result = generate_apkg_package(cards, "test", "A1", "Spanish")

        with zipfile.ZipFile(result, 'r') as zf:
            names = zf.namelist()
            assert not any(n.endswith('.wav') or n.endswith('.png') for n in names)

    def test_missing_media_files_skipped(self, tmp_path):
        """Function succeeds even when media files don't exist on disk."""
        cards = [
            {
                "text": "Hello",
                "translation": "Hola",
                "audio_path": "/nonexistent/path.wav",
                "image_path": None,
            },
        ]
        result = generate_apkg_package(cards, "test", "A1", "Spanish")
        assert Path(result).exists()

    def test_empty_cards_raises_valueerror(self):
        """Raises ValueError when no cards provided."""
        with pytest.raises(ValueError, match="No cards"):
            generate_apkg_package([], "test", "A1", "Spanish")

    def test_deck_name_in_output(self, tmp_path):
        """Deck name in package matches expected pattern."""
        cards = [{"text": "Hello", "translation": "Hola", "audio_path": None, "image_path": None}]
        result = generate_apkg_package(cards, "ordering coffee", "A2", "Latvian")

        import sqlite3
        with zipfile.ZipFile(result, 'r') as zf:
            db_bytes = zf.read('collection.anki2')
        tmp_db = tmp_path / "temp.db"
        tmp_db.write_bytes(db_bytes)
        conn = sqlite3.connect(str(tmp_db))
        cur = conn.cursor()
        cur.execute("SELECT decks FROM col")
        row = cur.fetchone()
        conn.close()

        assert row is not None
        decks_data = json.loads(row[0])
        # Find deck with expected name pattern
        found = any(
            isinstance(v, dict) and 'ordering_coffee' in v.get('name', '').lower()
            for v in decks_data.values()
        )
        assert found, f"Expected 'ordering_coffee' in deck name. Decks: {list(decks_data.keys())}"
