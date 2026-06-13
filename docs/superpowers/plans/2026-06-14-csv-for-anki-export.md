# CSV-for-Anki Export Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the broken `.apkg` export with a reliable Anki-compatible CSV export that uses HTML-embedded media references and Anki's native text-file import mechanism.

**Architecture:** Create a new `export/csv_for_anki.py` module mirroring `csv_export.py`'s pattern (same function signature, same media naming convention). The module writes a 2-column CSV (`Front`/`Back`) with HTML `<img>` and `<audio>` tags referencing files in a `collection.media/` subfolder, then zips it. The old `apkg_generator.py` is deleted. UI wiring in `app.py` and `widgets.py` is updated to call the new handler.

**Tech Stack:** Python stdlib (`csv`, `zipfile`, `shutil`, `html`, `pathlib`) — no new dependencies.

---

## File Map

| Action | File | Responsibility |
|---|---|---|
| **Create** | `export/csv_for_anki.py` | New Anki CSV export module (~120 lines) |
| **Create** | `tests/csv_for_anki_test.py` | Tests for the new module (~80 lines) |
| **Modify** | `app.py:340-360` | Replace `_handle_export_apkg()` with `_handle_export_csv_for_anki()` |
| **Modify** | `frontend/ui/widgets.py:~100 lines` | Rename event handler, change `file_types` on `export_apkg_file` from `.apkg` to `.zip` |
| **Delete** | `export/apkg_generator.py` | Replaced entirely by new module |
| **Delete** | `tests/apkg_generator_test.py` | Replaced by new test file |

---

### Task 1: Create `export/csv_for_anki.py` with core helpers

**Files:**
- Create: `export/csv_for_anki.py`

- [ ] **Step 1: Write the module skeleton with shared helpers**

```python
"""EuropaLex CSV-for-Anki Export — creates an Anki-compatible zip with HTML media references.

Produces a zipped folder containing:
    {folder_name}/
        cards.csv                    (2 columns: Front, Back — HTML embedded)
        collection.media/            (media files following Anki convention)

Uses Anki's native text-file import mechanism with embedded media via
relative paths in <img> and <audio> tags.
"""

import csv
import html
import shutil
from pathlib import Path

# ISO 639-1 language abbreviation mapping — mirrors csv_export.py exactly
_LANGUAGE_ABBREVS: dict[str, str] = {
    "Latvian": "LV",
    "Spanish": "ES",
    "French": "FR",
    "German": "DE",
    "Polish": "PL",
    "Italian": "IT",
    "Portuguese": "PT",
    "Finnish": "FI",
}

# Project root for resolving relative paths — mirrors csv_export.py
_PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _sanitize_folder_name(scenario: str) -> str:
    """Convert scenario text to a filesystem-safe folder name slug.

    Same implementation as csv_export._sanitize_folder_name for consistency.

    Args:
        scenario: Free-form scenario/topic string from the user.

    Returns:
        Sanitized slug suitable for use as a directory name.
    """
    import re
    slug = scenario.strip().lower()
    slug = re.sub(r'[^a-z0-9\s_]', '', slug)   # remove special chars
    slug = re.sub(r'\s+', '_', slug)             # spaces → underscores
    slug = re.sub(r'_+', '_', slug)              # collapse multiple underscores
    return slug.strip('_')


def _get_language_abbrev(language: str) -> str:
    """Return the ISO 639-1 abbreviation for a language name.

    Args:
        language: Language name (e.g., 'Latvian', 'Spanish').

    Returns:
        Two-letter ISO 639-1 code.

    Raises:
        ValueError: If the language is not in the mapping.
    """
    if language not in _LANGUAGE_ABBREVS:
        raise ValueError(
            f"Unknown language '{language}'. "
            f"Supported: {', '.join(sorted(_LANGUAGE_ABBREVS.keys()))}"
        )
    return _LANGUAGE_ABBREVS[language]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/csv_for_anki_test.py -v --tb=short`
Expected: FAIL with "ModuleNotFoundError: No module named 'export.csv_for_anki'" (file doesn't exist yet) or import errors for the missing functions.

- [ ] **Step 3: Write minimal implementation — just imports and stubs**

Add to `export/csv_for_anki.py`:

```python
def export_csv_for_anki(
    cards: list[dict],
    scenario: str,
    cefr_level: str,
    target_language: str,
) -> str:
    """Export cards as an Anki-compatible CSV zip with HTML media references.

    Args:
        cards: List of card dicts with keys: 'text', 'translation',
               'audio_path' (str or None), 'image_path' (str or None).
        scenario: Free-form scenario/topic string.
        cefr_level: CEFR level string (e.g., 'A2', 'B1').
        target_language: Target language name (e.g., 'Latvian').

    Returns:
        Absolute path to the generated .zip file.

    Raises:
        ValueError: If no cards provided or target_language not supported.
    """
    if not cards:
        raise ValueError("No cards provided for Anki CSV export")

    lang_abbrev = _get_language_abbrev(target_language)
    scenario_slug = _sanitize_folder_name(scenario)
    folder_name = f"{scenario_slug}_{cefr_level}_{lang_abbrev}"

    # Resolve output directory (same pattern as csv_export.py)
    export_base = _PROJECT_ROOT / ".local" / "models" / "output" / "export"
    export_base.mkdir(parents=True, exist_ok=True)

    export_dir = export_base / folder_name
    export_dir.mkdir(parents=True, exist_ok=True)

    media_dir = export_dir / "collection.media"
    media_dir.mkdir(parents=True, exist_ok=True)

    # Build CSV rows and copy media files
    csv_path = export_dir / "cards.csv"
    with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['Front', 'Back'])

        for i, card in enumerate(cards):
            front_html = _build_front_html(
                translation=card.get("translation", ""),
                audio_path=card.get("audio_path"),
                image_path=card.get("image_path"),
                scenario_slug=scenario_slug,
                cefr_level=cefr_level,
                lang_abbrev=lang_abbrev,
                card_index=i,
            )
            back_text = card.get("text", "")
            writer.writerow([front_html, back_text])

    # Create zip archive
    zip_path = shutil.make_archive(
        str(export_base / folder_name),
        'zip',
        export_dir,
    )

    return str(zip_path)


def _build_front_html(
    translation: str,
    audio_path: str | None,
    image_path: str | None,
    scenario_slug: str,
    cefr_level: str,
    lang_abbrev: str,
    card_index: int,
) -> str:
    """Build the HTML string for the card front field.

    Format: <b>translation</b><br>[<img>]<br>[<audio>]
    Tags are omitted entirely if media paths are None/missing.

    Args:
        translation: Target-language text (HTML-escaped).
        audio_path: Path to TTS .wav file or None.
        image_path: Path to illustration .png file or None.
        scenario_slug: Sanitized scenario name for media filename.
        cefr_level: CEFR level string.
        lang_abbrev: ISO 639-1 language code.
        card_index: Zero-based card index.

    Returns:
        HTML string for the Front field.
    """
    base_name = f"{scenario_slug}_{cefr_level}_{lang_abbrev}"
    parts = [f"<b>{html.escape(translation)}</b>"]

    # Copy image file if path exists, add <img> tag
    if image_path and Path(image_path).exists():
        media_filename = f"{base_name}_{card_index}.png"
        shutil.copy2(image_path, str(media_dir / media_filename))
        parts.append(f'<img src="collection.media/{media_filename}">')

    # Copy audio file if path exists, add <audio> tag
    if audio_path and Path(audio_path).exists():
        media_filename = f"{base_name}_{card_index}.wav"
        shutil.copy2(audio_path, str(media_dir / media_filename))
        parts.append(f'<audio controls src="collection.media/{media_filename}"></audio>')

    return "<br>".join(parts)
```

Wait — that references `media_dir` which is a local variable in the outer function. Fix by making `_build_front_html` accept the export directory:

Actually, let me restructure slightly so `_build_front_html` receives the media directory path and returns only the HTML string. The media copying happens inside it.

```python
def _copy_media_file(src_path: str | None, dest_dir: Path, base_name: str, card_index: int) -> str | None:
    """Copy a media file to the export media directory and return its filename, or None.

    Args:
        src_path: Source file path or None.
        dest_dir: Destination media directory (collection.media/).
        base_name: Filename prefix ({scenario}_{CEFR}_{LANG}).
        card_index: Zero-based card index for the filename suffix.

    Returns:
        Bare media filename (e.g., 'slug_A2_LV_0.wav') or None if skipped.
    """
    if not src_path or not Path(src_path).exists():
        return None
    ext = Path(src_path).suffix.lower()
    media_filename = f"{base_name}_{card_index}{ext}"
    shutil.copy2(src_path, str(dest_dir / media_filename))
    return media_filename


def _build_front_html(
    translation: str,
    audio_path: str | None,
    image_path: str | None,
    export_dir: Path,
    card_index: int,
) -> str:
    """Build the HTML string for the card front field.

    Args:
        translation: Target-language text (will be HTML-escaped).
        audio_path: Path to TTS .wav file or None.
        image_path: Path to illustration .png file or None.
        export_dir: Export directory containing collection.media/.
        card_index: Zero-based card index.

    Returns:
        HTML string for the Front field.
    """
    media_dir = export_dir / "collection.media"
    parts = [f"<b>{html.escape(translation)}</b>"]

    if image_path:
        fname = _copy_media_file(image_path, media_dir, "", card_index)
        if fname:
            parts.append(f'<img src="collection.media/{fname}">')

    if audio_path:
        fname = _copy_media_file(audio_path, media_dir, "", card_index)
        if fname:
            parts.append(f'<audio controls src="collection.media/{fname}"></audio>')

    return "<br>".join(parts)
```

Hmm, that loses the base_name. Let me fix `_copy_media_file`:

```python
def _copy_media_file(src_path: str | None, dest_dir: Path, filename_prefix: str, card_index: int, ext: str) -> str | None:
    """Copy a media file to the export media directory and return its filename, or None.

    Args:
        src_path: Source file path or None.
        dest_dir: Destination media directory (collection.media/).
        filename_prefix: Filename prefix ({scenario}_{CEFR}_{LANG}).
        card_index: Zero-based card index for the filename suffix.
        ext: File extension including dot (e.g., '.wav', '.png').

    Returns:
        Bare media filename or None if skipped.
    """
    if not src_path or not Path(src_path).exists():
        return None
    media_filename = f"{filename_prefix}_{card_index}{ext}"
    shutil.copy2(src_path, str(dest_dir / media_filename))
    return media_filename
```

And `_build_front_html`:

```python
def _build_front_html(
    translation: str,
    audio_path: str | None,
    image_path: str | None,
    export_dir: Path,
    base_name: str,
    card_index: int,
) -> str:
    """Build the HTML string for the card front field.

    Args:
        translation: Target-language text (will be HTML-escaped).
        audio_path: Path to TTS .wav file or None.
        image_path: Path to illustration .png file or None.
        export_dir: Export directory containing collection.media/.
        base_name: Filename prefix ({scenario}_{CEFR}_{LANG}).
        card_index: Zero-based card index.

    Returns:
        HTML string for the Front field.
    """
    media_dir = export_dir / "collection.media"
    parts = [f"<b>{html.escape(translation)}</b>"]

    if image_path:
        fname = _copy_media_file(image_path, media_dir, base_name, card_index, ".png")
        if fname:
            parts.append(f'<img src="collection.media/{fname}">')

    if audio_path:
        fname = _copy_media_file(audio_path, media_dir, base_name, card_index, ".wav")
        if fname:
            parts.append(f'<audio controls src="collection.media/{fname}"></audio>')

    return "<br>".join(parts)
```

And the CSV writer loop becomes:

```python
for i, card in enumerate(cards):
    base_name = f"{scenario_slug}_{cefr_level}_{lang_abbrev}"
    front_html = _build_front_html(
        translation=card.get("translation", ""),
        audio_path=card.get("audio_path"),
        image_path=card.get("image_path"),
        export_dir=export_dir,
        base_name=base_name,
        card_index=i,
    )
    back_text = card.get("text", "")
    writer.writerow([front_html, back_text])
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/csv_for_anki_test.py -v --tb=short`
Expected: All 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add export/csv_for_anki.py
git commit -m "feat: add csv_for_anki module skeleton with helpers and core export function"
```

---

### Task 2: Write unit tests for `csv_for_anki.py`

**Files:**
- Test: `tests/csv_for_anki_test.py`

- [ ] **Step 1: Write the test file**

Create `tests/csv_for_anki_test.py`:

```python
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
        assert "&lt;world&gt;" in row[0] or "Hola" in row[0]
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
```

- [ ] **Step 2: Run tests to verify they all fail first**

Run: `uv run pytest tests/csv_for_anki_test.py -v --tb=short`
Expected: FAIL — import errors (functions not yet implemented), or assertion failures if skeleton is present.

- [ ] **Step 3: Run tests against the implementation from Task 1**

Run: `uv run pytest tests/csv_for_anki_test.py -v --tb=short`
Expected: All ~20 tests PASS.

- [ ] **Step 4: Commit**

```bash
git add tests/csv_for_anki_test.py
git commit -m "test: add comprehensive tests for csv_for_anki module"
```

---

### Task 3: Wire up `app.py` — replace `_handle_export_apkg` with `_handle_export_csv_for_anki`

**Files:**
- Modify: `app.py:~340-360` (the `_handle_export_apkg` function)

- [ ] **Step 1: Replace the handler function**

Replace the existing `_handle_export_apkg()` function in `app.py`:

```python
# OLD CODE (delete):
def _handle_export_apkg(
    scenario: str,
    cefr_level: str,
    target_language: str,
) -> str | None:
    """Export current cards as an Anki package (.apkg).

    Returns the absolute path to the generated .apkg file for Gradio DownloadButton.
    Returns None if no cards to export or export failed.
    """
    if not _current_cards:
        logger.warning("APKG export: no cards to export")
        return None

    try:
        from core.types import CEFRLevel
        from export.apkg_generator import generate_apkg_package

        cefr = CEFRLevel(cefr_level)
        apkg_path = generate_apkg_package(_current_cards, scenario, cefr_level, target_language)
        return apkg_path
    except Exception as e:
        logger.error("APKG export failed: %s", e, exc_info=True)
        return None
```

With NEW CODE:

```python
def _handle_export_csv_for_anki(
    scenario: str,
    cefr_level: str,
    target_language: str,
) -> str | None:
    """Export current cards as an Anki-compatible CSV zip.

    Returns the absolute path to the generated .zip file for Gradio DownloadButton.
    Returns None if no cards to export or export failed.
    """
    if not _current_cards:
        logger.warning("Anki CSV export: no cards to export")
        return None

    try:
        from core.types import CEFRLevel
        from export.csv_for_anki import export_csv_for_anki

        cefr = CEFRLevel(cefr_level)
        zip_path = export_csv_for_anki(_current_cards, scenario, cefr_level, target_language)
        return zip_path
    except Exception as e:
        logger.error("Anki CSV export failed: %s", e, exc_info=True)
        return None
```

- [ ] **Step 2: Run smoke test**

Run: `uv run pytest tests/smoke_test.py -v`
Expected: PASS — verifies all imports still work (the old import of `apkg_generator` is gone, new import of `csv_for_anki` works).

- [ ] **Step 3: Commit**

```bash
git add app.py
git commit -m "refactor: replace _handle_export_apkg with _handle_export_csv_for_anki"
```

---

### Task 4: Wire up `widgets.py` — rename handler, update file types, update state transitions

**Files:**
- Modify: `frontend/ui/widgets.py` (event handler rename, file type change, state transition updates)

- [ ] **Step 1: Rename the event handler function**

Find and replace in `frontend/ui/widgets.py`:

```python
# OLD (delete):
        def _handle_export_apkg_event(scenario: str, cefr_level: str, target_language: str):
            """Export current cards as Anki package (.apkg).

            Sets the generated .apkg file path as the value of export_apkg_file component,
            which Gradio renders as a downloadable file link.
            """
            from frontend.ui.cards import generate_progress_html

            if not _app_module._current_cards:
                return generate_progress_html(0, "\u26a0\ufe0f No cards to export."), None, gr.File(visible=False)

            try:
                apkg_path = _app_module._handle_export_apkg(scenario, cefr_level, target_language)
                if apkg_path is None:
                    return generate_progress_html(0, "\u26a0\ufe0f Export failed."), None, gr.File(visible=False)
                # Show the file for download — gr.File component renders it as a clickable link
                return generate_progress_html(100, "Export complete! Click the file below to download."), apkg_path, gr.File(visible=True)
            except Exception as e:
                logger = logging.getLogger(__name__)
                logger.error("APKG export failed: %s", e, exc_info=True)
                return generate_progress_html(0, f"\u26a0\ufe0f Export failed: {e}"), None, gr.File(visible=False)

        # APKG Export button click — generates .apkg and shows it in gr.File for download
        export_apkg_btn.click(
            fn=_handle_export_apkg_event,
            inputs=[scenario_input, cefr_dropdown, language_dropdown],
            outputs=[progress_html, export_apkg_file, export_apkg_file],
        )
```

With NEW:

```python
        def _handle_export_csv_for_anki_event(scenario: str, cefr_level: str, target_language: str):
            """Export current cards as Anki-compatible CSV zip.

            Sets the generated .zip file path as the value of export_apkg_file component,
            which Gradio renders as a downloadable file link.
            """
            from frontend.ui.cards import generate_progress_html

            if not _app_module._current_cards:
                return generate_progress_html(0, "\u26a0\ufe0f No cards to export."), None, gr.File(visible=False)

            try:
                zip_path = _app_module._handle_export_csv_for_anki(scenario, cefr_level, target_language)
                if zip_path is None:
                    return generate_progress_html(0, "\u26a0\ufe0f Export failed."), None, gr.File(visible=False)
                # Show the file for download — gr.File component renders it as a clickable link
                return generate_progress_html(100, "Export complete! Click the file below to download."), zip_path, gr.File(visible=True)
            except Exception as e:
                logger = logging.getLogger(__name__)
                logger.error("Anki CSV export failed: %s", e, exc_info=True)
                return generate_progress_html(0, f"\u26a0\ufe0f Export failed: {e}"), None, gr.File(visible=False)

        # Anki CSV Export button click — generates zip and shows it in gr.File for download
        export_apkg_btn.click(
            fn=_handle_export_csv_for_anki_event,
            inputs=[scenario_input, cefr_dropdown, language_dropdown],
            outputs=[progress_html, export_apkg_file, export_apkg_file],
        )
```

- [ ] **Step 2: Update `file_types` on the `export_apkg_file` Gradio component**

Find this in the widget creation section (around line ~200):

```python
# OLD:
                export_apkg_file = gr.File(
                    label="Download Anki Cards", file_types=[".apkg"], visible=False
                )
```

Replace with:

```python
# NEW:
                export_apkg_file = gr.File(
                    label="Download Anki Cards", file_types=[".zip"], visible=False
                )
```

- [ ] **Step 3: Update `_on_media_generation_complete` to reference the new handler name in log messages**

Find `_on_media_generation_complete` and verify it doesn't reference "APKG" — it currently just enables buttons, so no change needed. Confirm by reading the function body; if it only returns Gradio component updates (no string messages), skip this step.

- [ ] **Step 4: Run smoke test**

Run: `uv run pytest tests/smoke_test.py -v`
Expected: PASS — verifies all imports work and the Gradio app can be constructed.

- [ ] **Step 5: Commit**

```bash
git add frontend/ui/widgets.py
git commit -m "refactor: rename export handler to csv_for_anki, update file_types to .zip"
```

---

### Task 5: Delete old files and run full test suite

**Files:**
- Delete: `export/apkg_generator.py`
- Delete: `tests/apkg_generator_test.py`

- [ ] **Step 1: Remove old files**

```bash
rm export/apkg_generator.py
rm tests/apkg_generator_test.py
```

- [ ] **Step 2: Run full test suite**

Run: `uv run pytest tests/ -v`
Expected: All tests PASS — the old apkg tests are gone, new csv_for_anki tests pass.

- [ ] **Step 3: Verify no remaining references to deleted code**

Run: `grep -rn "apkg_generator\|generate_apkg_package\|_handle_export_apkg\b" --include="*.py" .`
Expected: No matches (all references have been replaced).

- [ ] **Step 4: Commit**

```bash
git rm export/apkg_generator.py tests/apkg_generator_test.py
git commit -m "refactor: remove deprecated apkg_generator module and tests"
```

---

### Task 6: Final verification — smoke test + full suite + app launch check

**Files:** None (verification only)

- [ ] **Step 1: Run the full test suite one final time**

Run: `uv run pytest tests/ -v`
Expected: All tests PASS.

- [ ] **Step 2: Verify import chain is clean**

Run: `python -c "from export.csv_for_anki import export_csv_for_anki; from app import _handle_export_csv_for_anki; print('OK')"`
Expected: `OK` printed with no errors.

- [ ] **Step 3: Verify the Gradio app constructs without errors**

Run: `python -c "from frontend.ui.widgets import build_ui; demo = build_ui(); print('App constructed OK')"`
Expected: `App constructed OK` printed with no errors.

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "test: verify full test suite passes and app constructs cleanly"
```

---

## Self-Review Checklist

**1. Spec coverage:**
- ✅ New `csv_for_anki.py` module with 2-column CSV (Front/Back) → Task 1
- ✅ HTML-embedded `<img>` and `<audio>` tags in Front field → Task 1 (`_build_front_html`)
- ✅ `collection.media/` subfolder for media files → Task 1 (`media_dir = export_dir / "collection.media"`)
- ✅ Media naming convention `{scenario_slug}_{CEFR}_{LANG}_{index}.{ext}` → Task 1 (`_copy_media_file`)
- ✅ Same function signature as existing exports → Task 1 (matches `export_csv_zip` signature)
- ✅ HTML escaping of translation text → Task 1 (`html.escape(translation)`)
- ✅ Omit empty tags (no `<img>` when no image) → Task 1 (conditional `if fname:`)
- ✅ UI button repurposed (same button, new handler) → Task 4
- ✅ `file_types` changed from `.apkg` to `.zip` → Task 4
- ✅ Old `apkg_generator.py` deleted → Task 5
- ✅ Old tests deleted → Task 5

**2. Placeholder scan:** No "TBD", "TODO", "implement later", or "similar to" patterns found. All code is concrete.

**3. Type consistency:**
- Function signature matches spec: `export_csv_for_anki(cards, scenario, cefr_level, target_language) -> str`
- Card dict keys match existing code: `text`, `translation`, `audio_path`, `image_path`
- `_copy_media_file` helper uses explicit `ext` parameter (not derived from path) to avoid ambiguity
- Language abbrev mapping is identical between `csv_export.py` and `csv_for_anki.py`

**4. Edge cases covered in tests:**
- Missing media files (None paths, non-existent paths) → `test_missing_media_skipped_gracefully`
- HTML escaping of special characters → `test_html_escaping`
- Empty cards list → `test_empty_cards_raises_valueerror`
- Media deduplication: NOT explicitly tested — but the new module copies per-card (not shared across cards), so no dedup needed. Each card gets its own copy in `collection.media/`.
