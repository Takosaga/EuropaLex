"""Tests for export/csv_for_anki.py — Anki-compatible CSV export with HTML media references."""

import csv
import zipfile
from pathlib import Path

import pytest

# Import functions under test
from export.csv_for_anki import (
    _LANGUAGE_ABBREVS,
    _copy_media_file,
    _get_language_abbrev,
    _sanitize_folder_name,
    export_csv_for_anki,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent


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
    """Fixture that patches _PROJECT_ROOT to tmp_path and returns the export base dir.

    The code creates .local/models/output/export/ under _PROJECT_ROOT,
    so files end up at tmp_path/.local/models/output/export/{folder}/cards.csv.
    This fixture returns that export base for easy test assertions.
    """
    import export.csv_for_anki as mod
    monkeypatch.setattr(mod, '_PROJECT_ROOT', tmp_path)
    return tmp_path / ".local" / "models" / "output" / "export"


class TestSanitizeFolderName:
    """Tests for _sanitize_folder_name helper."""

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


class TestCopyMediaFile:
    """Tests for _copy_media_file helper."""

    def test_copies_file_with_correct_name(self, tmp_path):
        src = PROJECT_ROOT / "tests" / "test_outputs" / "audio" / "audio_0.wav"
        dest_dir = tmp_path / "media"
        dest_dir.mkdir()
        result = _copy_media_file(str(src), dest_dir, "slug_A2_LV", 0, ".wav")
        assert result == "slug_A2_LV_0.wav"
        assert (dest_dir / "slug_A2_LV_0.wav").exists()

    def test_returns_none_for_missing_path(self, tmp_path):
        dest_dir = tmp_path / "media"
        dest_dir.mkdir()
        result = _copy_media_file("/nonexistent/file.wav", dest_dir, "prefix", 0, ".wav")
        assert result is None

    def test_returns_none_for_none_path(self, tmp_path):
        dest_dir = tmp_path / "media"
        dest_dir.mkdir()
        result = _copy_media_file(None, dest_dir, "prefix", 0, ".wav")
        assert result is None


class TestExportCsvForAnki:
    """Tests for the main export_csv_for_anki function."""

    def test_export_returns_zip_path(self, sample_cards, tmp_export_base):
        """Function returns a valid file path string."""
        zip_path = export_csv_for_anki(
            cards=sample_cards,
            scenario="ordering coffee",
            cefr_level="A2",
            target_language="Latvian",
        )
        assert isinstance(zip_path, str)
        assert Path(zip_path).is_absolute()
        assert zip_path.endswith('.zip')

    def test_zip_contains_cards_csv(self, sample_cards, tmp_export_base):
        """CSV file exists inside the zip archive."""
        zip_path = export_csv_for_anki(
            cards=sample_cards,
            scenario="ordering coffee",
            cefr_level="A2",
            target_language="Latvian",
        )
        with zipfile.ZipFile(zip_path, 'r') as zf:
            names = zf.namelist()
            assert any('cards.csv' in n for n in names)

    def test_csv_has_front_back_columns(self, sample_cards, tmp_export_base):
        """CSV header row is exactly ['Front', 'Back']."""
        export_csv_for_anki(
            cards=sample_cards,
            scenario="test topic",
            cefr_level="B1",
            target_language="Spanish",
        )
        csv_file = tmp_export_base / "test_topic_B1_ES" / "cards.csv"
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            header = next(reader)
        assert header == ['Front', 'Back']

    def test_csv_row_count_matches_cards(self, sample_cards, tmp_export_base):
        """One data row per card (excluding header)."""
        export_csv_for_anki(
            cards=sample_cards,
            scenario="test topic",
            cefr_level="B1",
            target_language="Spanish",
        )
        csv_file = tmp_export_base / "test_topic_B1_ES" / "cards.csv"
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            next(reader)  # skip header
            rows = list(reader)
        assert len(rows) == 3

    def test_front_field_contains_translation(self, sample_cards, tmp_export_base):
        """Front HTML contains the translated text."""
        export_csv_for_anki(
            cards=sample_cards,
            scenario="test topic",
            cefr_level="B1",
            target_language="Spanish",
        )
        csv_file = tmp_export_base / "test_topic_B1_ES" / "cards.csv"
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            next(reader)  # skip header
            row = next(reader)
        assert "Me encanta comer frutas frescas." in row[0]

    def test_front_field_contains_image_tag(self, sample_cards, tmp_export_base):
        """Front HTML contains <img> tag when image path exists."""
        export_csv_for_anki(
            cards=sample_cards,
            scenario="ordering coffee",
            cefr_level="A2",
            target_language="Latvian",
        )
        csv_file = tmp_export_base / "ordering_coffee_A2_LV" / "cards.csv"
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            next(reader)  # skip header
            row = next(reader)  # card 0 has image
        assert '<img src="collection.media/' in row[0]

    def test_front_field_contains_audio_tag(self, sample_cards, tmp_export_base):
        """Front HTML contains <audio> tag when audio path exists."""
        export_csv_for_anki(
            cards=sample_cards,
            scenario="ordering coffee",
            cefr_level="A2",
            target_language="Latvian",
        )
        csv_file = tmp_export_base / "ordering_coffee_A2_LV" / "cards.csv"
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            next(reader)  # skip header
            row = next(reader)  # card 0 has audio
        assert '<audio controls src="collection.media/' in row[0]

    def test_back_field_contains_english(self, sample_cards, tmp_export_base):
        """Back field contains the English source text."""
        export_csv_for_anki(
            cards=sample_cards,
            scenario="test topic",
            cefr_level="B1",
            target_language="Spanish",
        )
        csv_file = tmp_export_base / "test_topic_B1_ES" / "cards.csv"
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            next(reader)  # skip header
            row = next(reader)
        assert "I love eating fresh fruits." in row[1]

    def test_media_files_copied_to_export(self, sample_cards, tmp_export_base):
        """Media files are copied into the zip archive."""
        zip_path = export_csv_for_anki(
            cards=sample_cards,
            scenario="ordering coffee",
            cefr_level="A2",
            target_language="Latvian",
        )
        with zipfile.ZipFile(zip_path, 'r') as zf:
            names = zf.namelist()
            # Card 0 has both audio and image
            assert any('ordering_coffee_A2_LV_0.wav' in n for n in names)
            assert any('ordering_coffee_A2_LV_0.png' in n for n in names)
            # Card 1 has only image
            assert any('ordering_coffee_A2_LV_1.png' in n for n in names)
            # Card 2 has only audio
            assert any('ordering_coffee_A2_LV_2.wav' in n for n in names)

    def test_media_in_collection_media_folder(self, sample_cards, tmp_export_base):
        """Media files are placed under collection.media/ inside the zip."""
        zip_path = export_csv_for_anki(
            cards=sample_cards,
            scenario="ordering coffee",
            cefr_level="A2",
            target_language="Latvian",
        )
        with zipfile.ZipFile(zip_path, 'r') as zf:
            names = zf.namelist()
            media_files = [n for n in names if n.startswith('collection.media/')]
            assert len(media_files) > 0
            # All media files should be under collection.media/
            assert all(n.startswith('collection.media/') for n in media_files)

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
        zip_path = export_csv_for_anki(
            cards=cards_no_media,
            scenario="no media test",
            cefr_level="A1",
            target_language="Spanish",
        )
        assert Path(zip_path).exists()

    def test_html_escaping(self, tmp_export_base):
        """Special characters in translation text are properly HTML-escaped."""
        cards_with_special = [
            {
                "text": "Hello <world>",
                "translation": "¡Hola & mundo!",
                "audio_path": None,
                "image_path": None,
            },
        ]
        export_csv_for_anki(
            cards=cards_with_special,
            scenario="greetings",
            cefr_level="A1",
            target_language="Spanish",
        )
        csv_file = tmp_export_base / "greetings_A1_ES" / "cards.csv"
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            next(reader)  # skip header
            row = next(reader)
        # Translation should be HTML-escaped in the <b> tag
        assert "&lt;world&gt;" not in row[0] or "<b>" in row[0]
        assert "&amp;" in row[0]

    def test_empty_cards_raises_valueerror(self):
        """Raises ValueError when no cards provided."""
        with pytest.raises(ValueError, match="No cards"):
            export_csv_for_anki([], "test", "A1", "Spanish")

    def test_zip_structure_has_folder_inside(self, sample_cards, tmp_export_base):
        """Zip contains a top-level folder (not just flat files)."""
        zip_path = export_csv_for_anki(
            cards=sample_cards,
            scenario="ordering coffee",
            cefr_level="A2",
            target_language="Latvian",
        )
        with zipfile.ZipFile(zip_path, 'r') as zf:
            names = zf.namelist()
            # Should have folder prefix like ordering_coffee_A2_LV/cards.csv
            assert any('ordering_coffee_A2_LV' in n for n in names)
