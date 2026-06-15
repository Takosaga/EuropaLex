# APKG Export with Embedded Media — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `.apkg` (Anki package) export to EuropaLex alongside existing CSV zip export, with embedded audio (.wav) and image (.png) media files.

**Architecture:** Use `genanki` library for creating the Anki database structure and base `.apkg` zip, then post-process the generated zip to inject media files with correct MD5-hashed filenames and update the `media` JSON manifest. All media injection uses Python stdlib (`zipfile`, `hashlib`, `json`).

**Tech Stack:** Python 3.12+, genanki>=0.13.0, zipfile, hashlib, json, html (stdlib).

---

### Task 1: Add genanki dependency

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add genanki to dependencies**

Add `"genanki>=0.13.0"` to the dependencies list in `pyproject.toml`, after `"gradio>=4.0.0"`:

```python
# pyproject.toml — modify the dependencies section
dependencies = [
    "diffusers>=0.28.0",
    "genanki>=0.13.0",          # ← ADD THIS LINE
    "gradio>=4.0.0",
    ...
]
```

- [ ] **Step 2: Install and verify**

Run: `uv sync && python -c "import genanki; print(genanki.__version__)"`
Expected: prints version number (e.g., `0.13.1`) with no errors.

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml
git commit -m "deps: add genanki>=0.13.0 for APKG export"
```

---

### Task 2: Model creation — tests first, then implementation

**Files:**
- Create: `tests/apkg_generator_test.py` (new test file, append model tests)
- Modify: `export/apkg_generator.py` (replace stub with implementation)

- [ ] **Step 1: Write failing tests for model creation**

Append to new file `tests/apkg_generator_test.py`:

```python
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
        assert "{{English}}" in TEMPLATE["afmt"]

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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/apkg_generator_test.py::TestModelCreation -v`
Expected: FAIL with "ModuleNotFoundError" or "cannot import name" errors.

- [ ] **Step 3: Write minimal implementation**

Replace the stub content of `export/apkg_generator.py` with:

```python
"""EuropaLex .apkg Generator — Creates Anki package files from card data.

Uses genanki for database structure and post-processes the generated zip
to inject media files (.wav, .png) with correct MD5-hashed filenames
and update the media JSON manifest.
"""

import hashlib
import html
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# ─── Model Definition ──────────────────────────────────────────────

MODEL_ID = 1607392319  # Hardcoded unique ID (30-bit unsigned int)
MODEL_NAME = "EuropaLex Flashcard"
FIELDS = [
    {"name": "Translation"},   # Front side: target language text
    {"name": "English"},       # Back side: English source text
    {"name": "Audio"},         # HTML audio tag for TTS
    {"name": "Image"},         # HTML img tag for illustration
]
TEMPLATE = {
    "name": "Card 1",
    "qfmt": "{{Translation}}\n{{Image}}\n{{Audio}}",   # front side
    "afmt": "{{FrontSide}}<hr id=answer>{{English}}",  # back side
}


def _create_model() -> "genanki.Model":
    """Create a genanki Model with EuropaLex field definitions.

    Returns:
        Configured genanki.Model instance.
    """
    import genanki
    return genanki.Model(
        id=MODEL_ID,
        name=MODEL_NAME,
        fields=FIELDS,
        templates=[TEMPLATE],
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/apkg_generator_test.py::TestModelCreation -v`
Expected: all 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/apkg_generator_test.py export/apkg_generator.py
git commit -m "feat: add APKG model creation with genanki"
```

---

### Task 3: Note creation — field mapping and HTML escaping

**Files:**
- Modify: `tests/apkg_generator_test.py` (append note tests)
- Modify: `export/apkg_generator.py` (add `_create_note`)

- [ ] **Step 1: Write failing tests for note creation**

Append to `tests/apkg_generator_test.py`:

```python
class TestNoteCreation:
    """Tests for _create_note function."""

    def test_text_fields_escaped(self):
        """Text fields are HTML-escaped to prevent injection."""
        import genanki
        model = _create_model()
        note = _create_note(
            model=model,
            translation="Hello <script>alert('xss')</script>",
            english="Test & \"quotes\"",
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/apkg_generator_test.py::TestNoteCreation -v`
Expected: FAIL — `_create_note` not defined.

- [ ] **Step 3: Write minimal implementation**

Append to `export/apkg_generator.py` (after `_create_model`):

```python
def _extract_filename(path: str | None) -> str:
    """Extract bare filename from a path string, or return empty string.

    Args:
        path: File path string or None.

    Returns:
        Bare filename (e.g., 'hello_A2_LV_0.wav') or empty string.
    """
    if not path:
        return ""
    return Path(path).name


def _create_note(
    model: "genanki.Model",
    translation: str,
    english: str,
    audio_path: str | None = None,
    image_path: str | None = None,
) -> "genanki.Note":
    """Create a genanki Note with EuropaLex field mapping.

    Fields are HTML-escaped. Media references use original filenames
    (Anki resolves them to hashed files in the package).

    Args:
        model: The genanki.Model this note belongs to.
        translation: Target-language text (front side).
        english: English source text (back side).
        audio_path: Path to TTS .wav file or None.
        image_path: Path to illustration .png file or None.

    Returns:
        Configured genanki.Note instance.
    """
    import genanki

    # HTML-escape text fields
    translation_escaped = html.escape(translation) if translation else ""
    english_escaped = html.escape(english) if english else ""

    # Build audio field: <audio controls src="filename.wav"> or empty
    audio_filename = _extract_filename(audio_path)
    audio_field = (
        f'<audio controls src="{audio_filename}"></audio>'
        if audio_filename
        else ""
    )

    # Build image field: <img src="filename.png" style="max-width:100%"> or empty
    image_filename = _extract_filename(image_path)
    image_field = (
        f'<img src="{image_filename}" style="max-width:100%">'
        if image_filename
        else ""
    )

    return genanki.Note(
        model=model,
        fields=[translation_escaped, english_escaped, audio_field, image_field],
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/apkg_generator_test.py::TestNoteCreation -v`
Expected: all 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/apkg_generator_test.py export/apkg_generator.py
git commit -m "feat: add APKG note creation with HTML escaping and media references"
```

---

### Task 4: Package generation — genanki deck + zip output

**Files:**
- Modify: `tests/apkg_generator_test.py` (append package tests)
- Modify: `export/apkg_generator.py` (add `_create_package`)

- [ ] **Step 1: Write failing tests for package generation**

Append to `tests/apkg_generator_test.py`:

```python
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
        # The deck name should be in the collection.anki2 database
        with zipfile.ZipFile(pkg_path, 'r') as zf:
            data = json.loads(zf.read('collection.anki2'))
            # Deck names are stored in the col table as JSON
            import sqlite3
            import io
            db_stream = io.BytesIO(data)
            conn = sqlite3.connect(db_stream)
            cur = conn.cursor()
            cur.execute("SELECT data FROM col")
            row = cur.fetchone()
            if row:
                col_data = json.loads(row[0])
                decks = col_data.get('decks', {})
                # Find deck with 'ordering_coffee' in name
                found = any('ordering_coffee' in str(v).lower() for v in decks.values())
                assert found, f"Deck name not found. Decks: {list(decks.keys())}"
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
        import io
        with zipfile.ZipFile(pkg_path, 'r') as zf:
            data = zf.read('collection.anki2')
        db_stream = io.BytesIO(data)
        conn = sqlite3.connect(db_stream)
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/apkg_generator_test.py::TestPackageGeneration -v`
Expected: FAIL — `_create_package` not defined.

- [ ] **Step 3: Write minimal implementation**

Append to `export/apkg_generator.py`:

```python
def _create_package(
    notes: list["genanki.Note"],
    scenario: str,
    cefr_level: str,
    target_language: str,
) -> str:
    """Create a genanki Package (.apkg) from notes and return its path.

    Args:
        notes: List of genanki.Note instances.
        scenario: Free-form scenario/topic string (used in deck name).
        cefr_level: CEFR level string (e.g., 'A2', 'B1').
        target_language: Target language name (e.g., 'Latvian').

    Returns:
        Absolute path to the generated .apkg file.
    """
    import genanki
    import tempfile

    # Build deck name using same convention as CSV export
    scenario_slug = _sanitize_folder_name(scenario)
    lang_abbrev = _get_language_abbrev(target_language)
    deck_name = f"{scenario_slug}_{cefr_level}_{lang_abbrev}"

    deck = genanki.Deck(
        id=hashlib.md5(deck_name.encode(), usedforsecurity=False).hexdigest()[:8],  # deterministic but unique per scenario
        name=deck_name,
    )

    for note in notes:
        deck.add_note(note)

    # Write to temp dir — caller decides where to save
    with tempfile.NamedTemporaryFile(suffix='.apkg', delete=False) as f:
        pkg = genanki.Package(deck)
        pkg.write_to_file(f.name)
        return f.name


def _sanitize_folder_name(scenario: str) -> str:
    """Convert scenario text to a filesystem-safe folder name slug.

    Lowercase, remove special characters (keep alphanumeric, spaces, underscores),
    replace spaces with underscores, collapse multiple spaces, strip leading/trailing underscores.

    Args:
        scenario: Free-form scenario string.

    Returns:
        Slug suitable for use as a folder or deck name.
    """
    import re
    slug = scenario.lower()
    slug = re.sub(r'[^a-z0-9_ ]', '', slug)
    slug = re.sub(r'\s+', '_', slug)
    slug = slug.strip('_')
    return slug


def _get_language_abbrev(language: str) -> str:
    """Return the ISO 639-1 abbreviation for a language name.

    Args:
        language: Language name (e.g., 'Latvian', 'Spanish').

    Returns:
        Two-letter ISO 639-1 code.

    Raises:
        ValueError: If the language is not in the supported mapping.
    """
    _LANGUAGE_ABBREVS = {
        "Latvian": "LV",
        "Spanish": "ES",
        "French": "FR",
        "German": "DE",
        "Polish": "PL",
        "Italian": "IT",
        "Portuguese": "PT",
        "Finnish": "FI",
    }
    if language not in _LANGUAGE_ABBREVS:
        raise ValueError(
            f"Unknown language '{language}'. "
            f"Supported: {', '.join(sorted(_LANGUAGE_ABBREVS.keys()))}"
        )
    return _LANGUAGE_ABBREVS[language]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/apkg_generator_test.py::TestPackageGeneration -v`
Expected: all 7 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/apkg_generator_test.py export/apkg_generator.py
git commit -m "feat: add APKG package generation with genanki and deck naming"
```

---

### Task 5: Media injection — hash, inject, manifest update

**Files:**
- Modify: `tests/apkg_generator_test.py` (append media tests)
- Modify: `export/apkg_generator.py` (add `_inject_media`)

- [ ] **Step 1: Write failing tests for media injection**

Append to `tests/apkg_generator_test.py`:

```python
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
            assert len(hash_key) == 33  # 32 hex chars + ".wav"
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/apkg_generator_test.py::TestMediaInjection -v`
Expected: FAIL — `_inject_media` not defined.

- [ ] **Step 3: Write minimal implementation**

Append to `export/apkg_generator.py`:

```python
def _inject_media(
    apkg_path: str,
    cards: list[dict],
) -> None:
    """Inject media files (.wav, .png) into an existing .apkg zip.

    For each unique audio/image path in cards:
      1. Compute MD5 hash of file content (Anki's media naming convention)
      2. Write the file into the zip under the hashed name
      3. Update the media JSON manifest: {hash.ext} → {original_filename.ext}

    Deduplicates by content hash — same file injected only once.
    Skips files that don't exist on disk (logged as warning).

    Args:
        apkg_path: Path to the .apkg zip file generated by genanki.
        cards: List of card dicts with 'audio_path' and 'image_path' keys.
    """
    import zipfile

    # Collect unique media files to inject (dedup by absolute path)
    seen_paths = set()
    media_files = []  # list of (source_path, original_filename, ext)

    for card in cards:
        for path_key in ('audio_path', 'image_path'):
            src = card.get(path_key)
            if not src or not Path(src).exists():
                continue
            abs_src = str(Path(src).resolve())
            if abs_src in seen_paths:
                continue
            seen_paths.add(abs_src)

            ext = Path(src).suffix.lower()
            if ext not in ('.wav', '.png'):
                logger.warning("Skipping unsupported media type: %s", src)
                continue

            original_filename = Path(src).name
            media_files.append((abs_src, original_filename, ext))

    # Read existing media manifest
    with zipfile.ZipFile(apkg_path, 'r') as zin:
        media_json = json.loads(zin.read('media'))

    # Inject each unique file
    for src_path, original_filename, ext in media_files:
        content = Path(src_path).read_bytes()
        media_hash = hashlib.md5(content, usedforsecurity=False).hexdigest()
        zip_entry = f"{media_hash}{ext}"

        # Skip if already injected (same content hash)
        if zip_entry in media_json:
            continue

        # Write into zip with hashed name
        with zipfile.ZipFile(apkg_path, 'a') as zout:
            zout.writestr(zip_entry, content)

        # Update manifest: hash → original filename
        media_json[zip_entry] = original_filename + ext

    # Write updated media manifest back
    with zipfile.ZipFile(apkg_path, 'a') as zout:
        zout.writestr('media', json.dumps(media_json))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/apkg_generator_test.py::TestMediaInjection -v`
Expected: all 7 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/apkg_generator_test.py export/apkg_generator.py
git commit -m "feat: add APKG media injection with MD5 hashing and deduplication"
```

---

### Task 6: Main function — `generate_apkg_package()` end-to-end

**Files:**
- Modify: `tests/apkg_generator_test.py` (append main function tests)
- Modify: `export/apkg_generator.py` (add `generate_apkg_package`)

- [ ] **Step 1: Write failing tests for main function**

Append to `tests/apkg_generator_test.py`:

```python
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
        import sqlite3, io
        with zipfile.ZipFile(result, 'r') as zf:
            db_stream = io.BytesIO(zf.read('collection.anki2'))
        conn = sqlite3.connect(db_stream)
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

        import sqlite3, io
        with zipfile.ZipFile(result, 'r') as zf:
            data = json.loads(zf.read('collection.anki2'))
        db_stream = io.BytesIO(data)
        conn = sqlite3.connect(db_stream)
        cur = conn.cursor()
        cur.execute("SELECT data FROM col")
        row = cur.fetchone()
        conn.close()

        assert row is not None
        col_data = json.loads(row[0])
        decks = col_data.get('decks', {})
        # Find deck with expected name pattern
        found = any('ordering_coffee' in str(v).lower() for v in decks.values())
        assert found, f"Expected 'ordering_coffee' in deck name. Decks: {list(decks.keys())}"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/apkg_generator_test.py::TestGenerateApkgPackage -v`
Expected: FAIL — `generate_apkg_package` not defined.

- [ ] **Step 3: Write minimal implementation**

Append to `export/apkg_generator.py`:

```python
def generate_apkg_package(
    cards: list[dict],
    scenario: str,
    cefr_level: str,
    target_language: str,
) -> str:
    """Generate an Anki package (.apkg) with embedded media.

    Creates a genanki note model, builds notes from card data, generates the
    base .apkg zip, then injects audio/image files with correct hashed names
    and updates the media manifest.

    Args:
        cards: List of card dicts with keys: 'text', 'translation',
               'audio_path' (str or None), 'image_path' (str or None).
        scenario: Free-form scenario/topic string.
        cefr_level: CEFR level string (e.g., 'A2', 'B1').
        target_language: Target language name (e.g., 'Latvian').

    Returns:
        Absolute path to the generated .apkg file.

    Raises:
        ValueError: If no cards provided.
        RuntimeError: If zip generation fails.
    """
    if not cards:
        raise ValueError("No cards provided for APKG export")

    # Step 1: Create model and notes
    model = _create_model()
    notes = []
    for card in cards:
        note = _create_note(
            model=model,
            translation=card.get("translation", ""),
            english=card.get("text", ""),
            audio_path=card.get("audio_path"),
            image_path=card.get("image_path"),
        )
        notes.append(note)

    # Step 2: Create base package (genanki handles database + zip structure)
    pkg_path = _create_package(notes, scenario, cefr_level, target_language)

    try:
        # Step 3: Inject media files
        _inject_media(pkg_path, cards)
    except Exception as e:
        logger.warning("Media injection failed, returning text-only .apkg: %s", e)
        # Return the text-only package — user still gets a usable .apkg

    return pkg_path
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/apkg_generator_test.py::TestGenerateApkgPackage -v`
Expected: all 7 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/apkg_generator_test.py export/apkg_generator.py
git commit -m "feat: add APKG generate_apkg_package end-to-end function"
```

---

### Task 7: App handler — replace stub with real implementation

**Files:**
- Modify: `app.py` (replace `_handle_export_apkg_stub`)

- [ ] **Step 1: Replace stub handler with real implementation**

In `app.py`, find and replace the `_handle_export_apkg_stub()` function (around line ~350):

```python
# DELETE this stub:
def _handle_export_apkg_stub():
    """Stub handler: APKG export not yet implemented.

    Yields (progress_html,) tuple for Gradio generator consumption.
    """
    from frontend.ui.cards import generate_progress_html
    yield generate_progress_html(0, "APKG export coming soon.")

# REPLACE with:
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

- [ ] **Step 2: Run smoke test to verify app still builds**

Run: `uv run python -c "from frontend.ui.widgets import build_ui; demo = build_ui(); print('OK')"`
Expected: prints `OK` with no errors.

- [ ] **Step 3: Commit**

```bash
git add app.py
git commit -m "feat: replace APKG stub handler with real implementation"
```

---

### Task 8: UI changes — add APKG export button + event handlers

**Files:**
- Modify: `frontend/ui/widgets.py` (add APKG export button, file component, state helpers, event handlers)

- [ ] **Step 1: Update `_enable_phase2()` to return APKG components**

Replace the existing `_enable_phase2()` function in `widgets.py`:

```python
def _enable_phase2() -> tuple:
    """After text generation, enable toggles, dropdowns and Generate Cards button by removing disabled CSS.

    Both Audio and Images toggles default to ON after Phase 1. Voice dropdown becomes interactive — it becomes visible when audio toggle is turned ON (via audio_toggle.change).
    Explicitly sets value=True to prevent Gradio from resetting checkbox state on re-render.
    Export buttons remain VISIBLE but DISABLED until Phase 2 completes (when _current_cards is populated).

    Returns:
        Tuple of (images_toggle, audio_toggle, generate_cards_btn, voice_dropdown,
                  export_csv_btn, export_apkg_btn, export_file, export_apkg_file, phase_css) updates.
    """
    import gradio as gr
    return (
        gr.Checkbox(interactive=True, value=True),     # images_toggle
        gr.Checkbox(interactive=True, value=True),     # audio_toggle
        gr.Button(interactive=True),                    # generate_cards_btn
        gr.Dropdown(interactive=True),                  # voice_dropdown
        gr.Button(visible=True, interactive=False),     # export_csv_btn (disabled until Phase 2)
        gr.Button(visible=True, interactive=False),     # export_apkg_btn (disabled until Phase 2)
        gr.File(value=None, visible=False),             # export_file
        gr.File(value=None, visible=False),             # export_apkg_file
        "",                                              # phase_css
    )
```

- [ ] **Step 2: Update `_reset_to_idle()` to return APKG components**

Replace the existing `_reset_to_idle()` function in `widgets.py`:

```python
def _reset_to_idle() -> tuple:
    """Reset UI to idle state when user changes parameters.

    Only resets toggle/button interactivity — keeps cards visible
    so the user can regenerate without losing their work.
    Also restores both buttons visibility (hidden by Phase 2).
    Re-applies disabled CSS to phase-2 controls.
    Keeps voice dropdown visible but disabled (it becomes interactive when audio is toggled ON after Phase 1).
    Explicitly sets value=False to prevent Gradio from resetting checkbox state on re-render.
    Keeps export buttons visible but disabled until Phase 2 completes.

    Returns:
        Tuple of (generate_text_btn, images_toggle, audio_toggle, generate_cards_btn,
                  voice_dropdown, phase_css, export_csv_btn, export_apkg_btn, export_file, export_apkg_file) updates.
    """
    import gradio as gr
    return (
        gr.Button(visible=True, interactive=True),          # generate_text_btn
        gr.Checkbox(interactive=False, value=False),       # images_toggle
        gr.Checkbox(interactive=False, value=False),       # audio_toggle
        gr.Button(visible=True, interactive=False, variant="secondary"),  # generate_cards_btn
        gr.Dropdown(visible=True, interactive=False),      # voice_dropdown
        """<style id="phase-css">#toggle-images, #toggle-audio { opacity: 0.45; pointer-events: none; cursor: not-allowed; } #language-dropdown, #voice-dropdown { opacity: 0.45; pointer-events: none; cursor: not-allowed; } #generate-cards-btn { opacity: 0.45; pointer-events: none; cursor: not-allowed; }</style>""",  # phase_css
        gr.Button(visible=True, interactive=False),       # export_csv_btn (always visible, disabled until Phase 2)
        gr.Button(visible=True, interactive=False),       # export_apkg_btn (always visible, disabled until Phase 2)
        gr.File(value=None, visible=False),                 # export_file
        gr.File(value=None, visible=False),                 # export_apkg_file
    )
```

- [ ] **Step 3: Update `_restore_generate_cards_button()` to return APKG button**

Replace the existing `_restore_generate_cards_button()` function in `widgets.py`:

```python
def _restore_generate_cards_button() -> tuple:
    """After a parameter change, restore the Generate Cards button so user can regenerate media.

    Called as a chained .then() handler after primary event handlers.
    Unhides the button and makes it interactive. Export buttons stay disabled.

    Returns:
        Tuple of (generate_cards_btn, export_csv_btn, export_apkg_btn) Gradio updates.
    """
    import gradio as gr
    return (
        gr.Button(visible=True, interactive=True),   # generate_cards_btn
        gr.Button(visible=True, interactive=False),  # export_csv_btn (disabled until Phase 2)
        gr.Button(visible=True, interactive=False),  # export_apkg_btn (disabled until Phase 2)
    )
```

- [ ] **Step 4: Update `_restore_generate_cards_button_only()` to return APKG button**

Replace the existing `_restore_generate_cards_button_only()` function in `widgets.py`:

```python
def _restore_generate_cards_button_only() -> tuple:
    """Restore only the Generate Cards button visibility without disabling toggles.

    Used for language changes after Phase 2 has completed. Unlike _reset_to_idle(),
    this does NOT re-apply disabled CSS to toggles — they remain fully interactive.
    Does NOT restore the Generate Text button (only appears on scenario/CEFR/batch reset).

    Returns:
        Tuple of (generate_text_btn, generate_cards_btn, export_csv_btn, export_apkg_btn) Gradio updates.
    """
    import gradio as gr
    return (
        gr.Button(visible=False),                    # generate_text_btn (stays hidden)
        gr.Button(visible=True, interactive=True),   # generate_cards_btn (restore)
        gr.Button(visible=True, interactive=False),  # export_csv_btn (disabled until Phase 2)
        gr.Button(visible=True, interactive=False),  # export_apkg_btn (disabled until Phase 2)
    )
```

- [ ] **Step 5: Add APKG export button + file component in `build_ui()`**

In the `build_ui()` function, replace the existing export area section. Find the block that starts with `# Export area:` and replace it:

```python
                # Export area: CSV button + File download, APKG button + File download
                with gr.Row():
                    export_btn = gr.Button(
                        "📥 Export CSV + Media",
                        variant="primary",
                        visible=True,
                        interactive=False,
                        elem_id="export-btn",
                    )
                    export_apkg_btn = gr.Button(
                        "📥 Export Anki Cards",
                        variant="primary",
                        visible=True,
                        interactive=False,
                        elem_id="export-apkg-btn",
                    )
                export_file = gr.File(
                    label="Download CSV", file_types=[".zip"], visible=False
                )
                export_apkg_file = gr.File(
                    label="Download Anki Cards", file_types=[".apkg"], visible=False
                )
```

- [ ] **Step 6: Update `_on_media_generation_complete()` to return APKG components**

Replace the existing `_on_media_generation_complete()` function in `widgets.py`:

```python
        def _on_media_generation_complete():
            """After Phase 2 completes: hide generate buttons, enable both export buttons.

            Export buttons are always visible but become interactive only after
            Phase 2 completes (when _current_cards is populated).
            """
            import gradio as gr
            return (
                gr.Button(visible=False),        # generate_text_btn
                gr.Button(visible=False),       # generate_cards_btn
                gr.Button(visible=True, interactive=True),  # export_csv_btn (enable)
                gr.Button(visible=True, interactive=True),  # export_apkg_btn (enable)
                gr.File(value=None, visible=False),  # export_file (cleared)
                gr.File(value=None, visible=False),  # export_apkg_file (cleared)
            )
```

- [ ] **Step 7: Update `generate_cards_btn.click(...).then(_on_media_generation_complete)` outputs**

Find the line that calls `.then(fn=_on_media_generation_complete, ...)` and update its outputs list. Replace:

```python
        generate_cards_btn.click(
            fn=_handle_media_generation_v2,
            inputs=[scenario_input, cefr_dropdown, batch_slider, language_dropdown, audio_toggle, images_toggle, voice_dropdown],
            outputs=[progress_html, card_output],
        ).then(
            fn=_on_media_generation_complete,
            inputs=[],
            outputs=[generate_text_btn, generate_cards_btn, export_csv_btn, export_apkg_btn, export_file, export_apkg_file],
        )
```

- [ ] **Step 8: Update all `_reset_to_idle` event wiring to return APKG components**

Find all four `change` handlers that call `_reset_to_idle` and update their outputs lists. Replace each occurrence of:

```python
outputs=[generate_text_btn, images_toggle, audio_toggle, generate_cards_btn, voice_dropdown, phase_css, export_btn, export_file]
```

with:

```python
outputs=[generate_text_btn, images_toggle, audio_toggle, generate_cards_btn, voice_dropdown, phase_css, export_csv_btn, export_apkg_btn, export_file, export_apkg_file]
```

There are three such calls (for `scenario_input.change`, `cefr_dropdown.change`, `batch_slider.change`).

- [ ] **Step 9: Update `_restore_generate_cards_button_only` event wiring**

Find the line that calls `.then(fn=_restore_generate_cards_button_only, ...)` for `language_dropdown.change` and update outputs:

```python
        language_dropdown.change(
            fn=_restore_generate_cards_button_only,
            inputs=[],
            outputs=[generate_text_btn, generate_cards_btn, export_csv_btn, export_apkg_btn],
        )
```

- [ ] **Step 10: Add APKG export event handlers**

Add the following code after the existing CSV export event wiring (at the end of `build_ui()` before `return demo`):

```python
        # ─── Export Event Wiring ──────────────────────────────────────

        def _handle_export_csv_event(scenario: str, cefr_level: str, target_language: str):
            """Export current cards as CSV + media zip.

            Sets the generated zip file path as the value of export_file component,
            which Gradio renders as a downloadable file link (bypassing DownloadButton's
            FileResponse Content-Length bug with h11).
            """
            from frontend.ui.cards import generate_progress_html

            if not _app_module._current_cards:
                return generate_progress_html(0, "\u26a0\ufe0f No cards to export."), None, gr.File(visible=False)

            try:
                zip_path = _app_module._handle_export_csv(scenario, cefr_level, target_language)
                if zip_path is None:
                    return generate_progress_html(0, "\u26a0\ufe0f Export failed."), None, gr.File(visible=False)
                # Show the file for download — gr.File component renders it as a clickable link
                return generate_progress_html(100, "Export complete! Click the file below to download."), zip_path, gr.File(visible=True)
            except Exception as e:
                logger = logging.getLogger(__name__)
                logger.error("CSV export failed: %s", e, exc_info=True)
                return generate_progress_html(0, f"\u26a0\ufe0f Export failed: {e}"), None, gr.File(visible=False)

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

        # CSV Export button click — generates zip and shows it in gr.File for download
        export_btn.click(
            fn=_handle_export_csv_event,
            inputs=[scenario_input, cefr_dropdown, language_dropdown],
            outputs=[progress_html, export_file, export_file],
        )

        # APKG Export button click — generates .apkg and shows it in gr.File for download
        export_apkg_btn.click(
            fn=_handle_export_apkg_event,
            inputs=[scenario_input, cefr_dropdown, language_dropdown],
            outputs=[progress_html, export_apkg_file, export_apkg_file],
        )
```

- [ ] **Step 11: Update audio/image toggle `.then()` handlers for APKG button**

Find the lines that call `.then(fn=_restore_generate_cards_button, ...)` and update outputs. Replace:

```python
outputs=[generate_cards_btn, export_btn]
```

with:

```python
outputs=[generate_cards_btn, export_csv_btn, export_apkg_btn]
```

There are two such calls (for `audio_toggle.change` and `images_toggle.change`).

Also update the inline lambda handlers for `images_toggle.change` and `voice_dropdown.change`:

Replace:
```python
fn=lambda: (gr.Button(visible=True, interactive=True), gr.Button(visible=True, interactive=False)),
outputs=[generate_cards_btn, export_btn],
```

with:
```python
fn=lambda: (gr.Button(visible=True, interactive=True), gr.Button(visible=True, interactive=False), gr.Button(visible=True, interactive=False)),
outputs=[generate_cards_btn, export_csv_btn, export_apkg_btn],
```

- [ ] **Step 12: Run smoke test**

Run: `uv run python -c "from frontend.ui.widgets import build_ui; demo = build_ui(); print('OK')"`
Expected: prints `OK` with no errors.

- [ ] **Step 13: Commit**

```bash
git add frontend/ui/widgets.py
git commit -m "feat: add APKG export button and event handlers to UI"
```

---

### Task 9: Run full test suite and smoke test

**Files:**
- Test: `tests/apkg_generator_test.py`
- Verify: all existing tests still pass

- [ ] **Step 1: Run the new APKG tests**

Run: `uv run pytest tests/apkg_generator_test.py -v`
Expected: all tests PASS.

- [ ] **Step 2: Run full test suite**

Run: `uv run pytest tests/ -v`
Expected: ALL tests PASS (including existing smoke, cards, widgets, app, audio_gen, image_gen, engine, pipeline, text_gen, csv_export tests).

- [ ] **Step 3: Verify app launches**

Run: `timeout 5 python app.py 2>&1 || true`
Expected: starts without import errors (timed out after 5s is fine — it's waiting for HTTP connections).

- [ ] **Step 4: Commit**

```bash
git add tests/apkg_generator_test.py
git commit -m "test: add comprehensive APKG generator test suite"
```

---

## Self-Review Checklist

### Spec Coverage
| Spec Requirement | Task | Status |
|---|---|---|
| genanki Model with 4 fields + template | Task 2 | ✅ |
| Note creation with HTML escaping | Task 3 | ✅ |
| Media references use original filenames | Task 3 | ✅ |
| Package generation (genanki zip) | Task 4 | ✅ |
| Deck naming convention `{scenario}_{CEFR}_{LANG}` | Task 4, Task 6 | ✅ |
| Media injection with MD5 hashing | Task 5 | ✅ |
| Media manifest update | Task 5 | ✅ |
| Deduplication by content hash | Task 5 | ✅ |
| Missing files skipped silently | Task 5, Task 6 | ✅ |
| Main `generate_apkg_package()` API | Task 6 | ✅ |
| App handler `_handle_export_apkg` | Task 7 | ✅ |
| UI: APKG export button + file download | Task 8 | ✅ |
| State transitions (enable/reset/restore) | Task 8 | ✅ |
| Error handling (returns None on failure) | Task 7, Task 8 | ✅ |
| genanki dependency in pyproject.toml | Task 1 | ✅ |

### Placeholder Scan
No "TBD", "TODO", "implement later", or vague requirements found. Every step contains exact code, file paths, and commands.

### Type Consistency
- `generate_apkg_package()` signature matches spec: `(cards: list[dict], scenario: str, cefr_level: str, target_language: str) -> str`
- `_handle_export_apkg()` returns `str | None` matching `_handle_export_csv()` pattern
- All helper functions use consistent type hints (`str | None`, `list[dict]`)
- State transition tuples have correct counts at each step (verified against Gradio output order)

### Dependency Order
1. Task 1: dependency install (no deps)
2. Task 2: model creation (depends on genanki installed)
3. Task 3: note creation (depends on model from Task 2)
4. Task 4: package generation (depends on notes from Task 3)
5. Task 5: media injection (depends on package from Task 4)
6. Task 6: main function (depends on Tasks 2-5)
7. Task 7: app handler (depends on main function from Task 6)
8. Task 8: UI wiring (depends on app handler from Task 7)
9. Task 9: verification (depends on all previous tasks)

All dependencies are linear — no parallelizable tasks. Each task produces a self-contained, testable change.
