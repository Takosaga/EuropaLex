"""Tests for export/csv_export.py — CSV zip export functionality."""

import csv
import zipfile
from pathlib import Path

import pytest

# Import functions under test
from export.csv_export import export_csv_zip
from export._constants import _LANGUAGE_ABBREVS, get_language_abbrev as _get_language_abbrev, sanitize_folder_name as _sanitize_folder_name

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
            "translation": "El chef prepar\u00f3 una comida deliciosa.",
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
    import export.csv_export as mod
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

    def test_leading_trailing_stripped(self):
        assert _sanitize_folder_name("  hello world  ") == "hello_world"


class TestLanguageAbbrevMapping:
    """Tests for _get_language_abbreviation helper."""

    def test_all_languages_mapped(self):
        expected = {
            "Bulgarian": "BG", "Croatian": "HR", "Czech": "CS",
            "Danish": "DA", "Dutch": "NL", "Estonian": "ET",
            "Finnish": "FI", "French": "FR", "German": "DE",
            "Greek": "EL", "Hungarian": "HU", "Irish": "GA",
            "Italian": "IT", "Latvian": "LV", "Lithuanian": "LT",
            "Maltese": "MT", "Polish": "PL", "Portuguese": "PT",
            "Romanian": "RO", "Slovak": "SK", "Slovenian": "SL",
            "Spanish": "ES", "Swedish": "SV",
        }
        assert _LANGUAGE_ABBREVS == expected

    def test_invalid_language_raises(self):
        with pytest.raises(ValueError, match="Unknown language"):
            _get_language_abbrev("Japanese")


class TestExportCsvZip:
    """Tests for the main export_csv_zip function."""

    def test_folder_name_generation(self, sample_cards, tmp_export_base):
        """Folder name matches expected pattern: scenario_cefr_lang."""
        zip_path = export_csv_zip(
            cards=sample_cards,
            scenario="ordering coffee",
            cefr_level="A2",
            target_language="Latvian",
        )
        assert "ordering_coffee_A2_LV" in zip_path

    def test_csv_content_columns(self, sample_cards, tmp_export_base):
        """CSV has the 7 expected columns in order."""
        export_csv_zip(
            cards=sample_cards,
            scenario="test topic",
            cefr_level="B1",
            target_language="Spanish",
        )
        csv_file = tmp_export_base / "test_topic_B1_ES" / "cards.csv"
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            header = next(reader)
        assert header == [
            'scenario', 'cefr_level', 'target_language',
            'english_text', 'translated_text',
            'audio_filename', 'image_filename'
        ]

    def test_csv_content_row_count(self, sample_cards, tmp_export_base):
        """CSV row count matches number of cards (excluding header)."""
        export_csv_zip(
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

    def test_csv_quoting(self, tmp_export_base):
        """Fields with commas/accents are properly double-quote escaped."""
        cards_with_special = [
            {
                "text": "Hello, world!",
                "translation": "\u00a1Hola, mundo!",
                "audio_path": None,
                "image_path": None,
            },
        ]

        export_csv_zip(
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
        assert row[3] == "Hello, world!"   # english_text
        assert row[4] == "\u00a1Hola, mundo!"   # translated_text

    def test_media_file_copying(self, sample_cards, tmp_export_base):
        """Audio and image files are copied into the export folder as flat files with meaningful names."""
        export_csv_zip(
            cards=sample_cards,
            scenario="ordering coffee",
            cefr_level="A2",
            target_language="Latvian",
        )

        export_dir = tmp_export_base / "ordering_coffee_A2_LV"

        # Card 0 has both audio and image — flat naming with base prefix
        assert (export_dir / "ordering_coffee_A2_LV_0.wav").exists()
        assert (export_dir / "ordering_coffee_A2_LV_0.png").exists()
        # Card 1 has only image
        assert not (export_dir / "ordering_coffee_A2_LV_1.wav").exists()
        assert (export_dir / "ordering_coffee_A2_LV_1.png").exists()
        # Card 2 has only audio
        assert (export_dir / "ordering_coffee_A2_LV_2.wav").exists()
        assert not (export_dir / "ordering_coffee_A2_LV_2.png").exists()

    def test_zip_creation(self, sample_cards, tmp_export_base):
        """Zip is created and extractable with expected flat structure."""
        zip_path = export_csv_zip(
            cards=sample_cards,
            scenario="ordering coffee",
            cefr_level="A2",
            target_language="Latvian",
        )

        assert Path(zip_path).exists()
        assert zip_path.endswith('.zip')

        with zipfile.ZipFile(zip_path, 'r') as zf:
            names = zf.namelist()
            assert any('cards.csv' in n for n in names)
            # Verify flat structure — no audio/ or images/ subfolders
            assert not any('audio/' in n for n in names)
            assert not any('images/' in n for n in names)
            # Verify meaningful filenames present
            assert any('ordering_coffee_A2_LV_0.wav' in n for n in names)
            assert any('ordering_coffee_A2_LV_0.png' in n for n in names)

    def test_csv_media_columns_have_bare_filenames(self, sample_cards, tmp_export_base):
        """CSV audio_filename and image_filename columns contain bare filenames, not paths."""
        export_csv_zip(
            cards=sample_cards,
            scenario="ordering coffee",
            cefr_level="A2",
            target_language="Latvian",
        )

        csv_file = tmp_export_base / "ordering_coffee_A2_LV" / "cards.csv"
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            next(reader)  # skip header
            rows = list(reader)

        # Card 0: has both audio and image
        assert rows[0][5] == "ordering_coffee_A2_LV_0.wav"   # audio_filename
        assert rows[0][6] == "ordering_coffee_A2_LV_0.png"   # image_filename
        # Card 1: only image
        assert rows[1][5] == ""                                # audio_filename
        assert rows[1][6] == "ordering_coffee_A2_LV_1.png"   # image_filename
        # Card 2: only audio
        assert rows[2][5] == "ordering_coffee_A2_LV_2.wav"   # audio_filename
        assert rows[2][6] == ""                                # image_filename

    def test_missing_media_files_handled(self, tmp_export_base):
        """Export succeeds even when media files don't exist."""
        cards_no_media = [
            {
                "text": "No media card",
                "translation": "Sin multimedia",
                "audio_path": "/nonexistent/path.wav",
                "image_path": "/nonexistent/path.png",
            },
        ]

        zip_path = export_csv_zip(
            cards=cards_no_media,
            scenario="no media test",
            cefr_level="A1",
            target_language="Spanish",
        )

        assert Path(zip_path).exists()

        csv_file = tmp_export_base / "no_media_test_A1_ES" / "cards.csv"
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            next(reader)  # skip header
            row = next(reader)
        assert row[5] == ''   # audio_filename
        assert row[6] == ''   # image_filename

    def test_return_path_is_absolute(self, sample_cards, tmp_export_base):
        """Return value is an absolute path string."""
        result = export_csv_zip(
            cards=sample_cards,
            scenario="ordering coffee",
            cefr_level="A2",
            target_language="Latvian",
        )
        assert Path(result).is_absolute()

    def test_all_languages_work(self, tmp_export_base):
        """Export works for all 8 supported languages."""
        cards = [{"text": "test", "translation": "test", "audio_path": None, "image_path": None}]
        for lang in _LANGUAGE_ABBREVS:
            zip_path = export_csv_zip(
                cards=cards,
                scenario="lang test",
                cefr_level="A1",
                target_language=lang,
            )
            assert Path(zip_path).exists()
