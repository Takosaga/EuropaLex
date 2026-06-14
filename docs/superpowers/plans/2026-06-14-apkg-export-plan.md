# Replace csv_for_anki with Direct genanki .apkg Export

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the CSV+media-folder zip export (Anki text-file import) with a direct genanki-based `.apkg` generator that builds cards in-memory and produces a proper Anki package file.

**Architecture:** Create `export/apkg_export.py` using genanki's Model/Deck/Package API to build cards in-memory, copy media files into a temp `collection.media/` directory, and write a `.apkg` file. Delete the old `csv_for_anki.py`. Update app.py import and widgets.py file_types. No changes to card generation logic or Phase 2 pipeline.

**Tech Stack:** Python 3.12+, genanki>=0.13.0 (already in pyproject.toml), pytest, pathlib

---

### Task 1: Write failing tests for apkg_export.py

**Files:**
- Create: `tests/apkg_export_test.py`

- [ ] **Step 1: Write the failing test file**

```python
"""Tests for export/apkg_export.py — Direct genanki .apkg export."""

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
        """An .apkg file is a valid zip archive (genanki format)."""
        apkg_path = export_csv_for_anki(
            cards=sample_cards,
            scenario="ordering coffee",
            cefr_level="A2",
            target_language="Latvian",
        )
        with zipfile.ZipFile(apkg_path, 'r') as zf:
            # Should contain notes.json and deck.json (genanki internals)
            names = zf.namelist()
            assert any('notes' in n for n in names)
            assert any('deck' in n for n in names)

    def test_apkg_contains_media_files(self, sample_cards):
        """Media files are bundled into the .apkg archive."""
        apkg_path = export_csv_for_anki(
            cards=sample_cards,
            scenario="ordering coffee",
            cefr_level="A2",
            target_language="Latvian",
        )
        with zipfile.ZipFile(apkg_path, 'r') as zf:
            names = zf.namelist()
            # Card 0 has both audio and image
            assert any('ordering_coffee_A2_LV_0.wav' in n for n in names)
            assert any('ordering_coffee_A2_LV_0.png' in n for n in names)
            # Card 1 has only image
            assert any('ordering_coffee_A2_LV_1.png' in n for n in names)
            # Card 2 has only audio
            assert any('ordering_coffee_A2_LV_2.wav' in n for n in names)

    def test_apkg_note_count_matches_cards(self, sample_cards):
        """One note per card — verify via notes.json content."""
        apkg_path = export_csv_for_anki(
            cards=sample_cards,
            scenario="ordering coffee",
            cefr_level="A2",
            target_language="Latvian",
        )
        import json
        with zipfile.ZipFile(apkg_path, 'r') as zf:
            notes_data = json.loads(zf.read('notes.json'))
            # notes.json format: {"notes": [...]}
            assert len(notes_data['notes']) == 3

    def test_apkg_note_fields_correct(self, sample_cards):
        """Notes contain correct TargetText and EnglishText."""
        apkg_path = export_csv_for_anki(
            cards=sample_cards,
            scenario="ordering coffee",
            cefr_level="A2",
            target_language="Latvian",
        )
        import json
        with zipfile.ZipFile(apkg_path, 'r') as zf:
            notes_data = json.loads(zf.read('notes.json'))
            # First note fields: [TargetText, EnglishText, Image, Audio]
            first_note_fields = notes_data['notes'][0]['fields']
            assert "Me encanta comer frutas frescas." in first_note_fields[0]
            assert "I love eating fresh fruits." in first_note_fields[1]

    def test_apkg_deck_name(self, sample_cards):
        """Deck name matches the DECK_NAME constant."""
        apkg_path = export_csv_for_anki(
            cards=sample_cards,
            scenario="ordering coffee",
            cefr_level="A2",
            target_language="Latvian",
        )
        import json
        with zipfile.ZipFile(apkg_path, 'r') as zf:
            deck_data = json.loads(zf.read('deck.json'))
            assert deck_data['name'] == "EuropaLex Flashcards"

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
        import json
        with zipfile.ZipFile(apkg_path, 'r') as zf:
            notes_data = json.loads(zf.read('notes.json'))
            assert len(notes_data['notes']) == 1

    def test_apkg_structure_has_deck_and_model(self, sample_cards):
        """The .apkg contains both deck and model definitions."""
        apkg_path = export_csv_for_anki(
            cards=sample_cards,
            scenario="ordering coffee",
            cefr_level="A2",
            target_language="Latvian",
        )
        with zipfile.ZipFile(apkg_path, 'r') as zf:
            names = zf.namelist()
            assert any('deck.json' in n for n in names)
            assert any('model' in n for n in names)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/takosaga/Projects/EuropaLex && uv run pytest tests/apkg_export_test.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'export.apkg_export'" or similar import error.

- [ ] **Step 3: Commit (tests should fail)**

```bash
cd /home/takosaga/Projects/EuropaLex
git add tests/apkg_export_test.py
git commit -m "test: add failing tests for apkg_export module"
```

---

### Task 2: Implement apkg_export.py

**Files:**
- Create: `export/apkg_export.py`

- [ ] **Step 1: Write the apkg_export.py module**

The module uses genanki to build cards in-memory. It follows the card styling from `create_anki_deck.py` reference script.

```python
"""EuropaLex .apkg Export — creates an Anki package using genanki.

Produces a proper .apkg file (Anki's native format) with HTML-styled cards,
embedded audio, and images. Uses genanki to build the package in-memory
and bundle media files automatically.

Usage:
    from export.apkg_export import export_csv_for_anki
    apkg_path = export_csv_for_anki(cards, scenario, cefr_level, target_language)
"""

import json
import os
import random
import re
import shutil
from pathlib import Path

import genanki

# ── Configuration ──────────────────────────────────────────────────────────────

DECK_NAME = "EuropaLex Flashcards"

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


def _stable_id(seed: str) -> int:
    """Generate a stable numeric ID from a string seed."""
    rng = random.Random(seed)
    return rng.randint(1_000_000_000, 9_999_999_999)


# ── Card template ──────────────────────────────────────────────────────────────

FRONT_TEMPLATE = """
<div class="card-front">
  {{Image}}
  <div class="target-text">{{TargetText}}</div>
  {{Audio}}
</div>
"""

BACK_TEMPLATE = """
{{FrontSide}}
<hr class="divider">
<div class="card-back">
  <div class="english-text">{{EnglishText}}</div>
</div>
"""

CSS = """
.card {
  font-family: 'Segoe UI', Arial, sans-serif;
  text-align: center;
  color: #1a1a1a;
  background: #fafafa;
  padding: 20px;
  max-width: 500px;
  margin: 0 auto;
}

.media-image img {
  max-width: 280px;
  max-height: 280px;
  border-radius: 12px;
  margin-bottom: 16px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.15);
}

.target-text {
  font-size: 2em;
  font-weight: 700;
  color: #2c3e50;
  margin: 12px 0;
  letter-spacing: 0.02em;
}

.audio {
  margin: 10px 0;
}

.divider {
  border: none;
  border-top: 2px solid #e0e0e0;
  margin: 20px auto;
  width: 60%;
}

.english-text {
  font-size: 1.4em;
  color: #555;
  font-style: italic;
  margin-top: 10px;
}
"""


# ── Export function ────────────────────────────────────────────────────────────

def export_csv_for_anki(
    cards: list[dict],
    scenario: str,
    cefr_level: str,
    target_language: str,
) -> str:
    """Export cards as an Anki-compatible .apkg file using genanki.

    Builds cards in-memory with genanki and bundles media files into the package.
    Produces a proper .apkg file that Anki imports via File → Import.

    Args:
        cards: List of card dicts with keys: 'text', 'translation',
               'audio_path' (str or None), 'image_path' (str or None).
        scenario: Free-form scenario/topic string.
        cefr_level: CEFR level string (e.g., 'A2', 'B1').
        target_language: Target language name (e.g., 'Latvian').

    Returns:
        Absolute path to the generated .apkg file.

    Raises:
        ValueError: If no cards provided or target_language not supported.
    """
    if not cards:
        raise ValueError("No cards provided for Anki export")

    lang_abbrev = _get_language_abbrev(target_language)
    scenario_slug = _sanitize_folder_name(scenario)

    # Resolve output directory (same pattern as csv_export.py)
    export_base = _PROJECT_ROOT / ".local" / "models" / "output" / "export"
    export_base.mkdir(parents=True, exist_ok=True)

    apkg_path = export_base / f"{scenario_slug}_{cefr_level}_{lang_abbrev}.apkg"

    # Build genanki model (note type) with 4 fields
    model_id = _stable_id(DECK_NAME + "_model")
    model = genanki.Model(
        model_id=model_id,
        name="EuropaLex Card",
        fields=[
            {"name": "TargetText"},
            {"name": "EnglishText"},
            {"name": "Image"},
            {"name": "Audio"},
        ],
        templates=[
            {
                "name": "Card 1",
                "qfmt": FRONT_TEMPLATE,
                "afmt": BACK_TEMPLATE,
            }
        ],
        css=CSS,
    )

    # Build genanki deck
    deck_id = _stable_id(DECK_NAME)
    deck = genanki.Deck(
        deck_id=deck_id,
        name=DECK_NAME,
    )

    media_files: list[str] = []

    # Create notes for each card
    for i, card in enumerate(cards):
        target_text = card.get("translation", "")
        english_text = card.get("text", "")
        audio_path = card.get("audio_path")
        image_path = card.get("image_path")

        # Build Image field: bare filename if media exists, empty string otherwise
        img_field = ""
        if image_path and Path(image_path).exists():
            media_filename = f"{scenario_slug}_{cefr_level}_{lang_abbrev}_{i}.png"
            shutil.copy2(str(image_path), str(export_base / media_filename))
            img_field = f'<img src="{media_filename}">'
            media_files.append(str(image_path))

        # Build Audio field: [sound:{filename}] if media exists, empty string otherwise
        aud_field = ""
        if audio_path and Path(audio_path).exists():
            media_filename = f"{scenario_slug}_{cefr_level}_{lang_abbrev}_{i}.wav"
            shutil.copy2(str(audio_path), str(export_base / media_filename))
            aud_field = f"[sound:{media_filename}]"
            media_files.append(str(audio_path))

        note = genanki.Note(
            model=model,
            fields=[target_text, english_text, img_field, aud_field],
        )
        deck.add_note(note)

    # Package and save — genanki handles bundling media into .apkg
    package = genanki.Package(deck)
    package.media_files = list(dict.fromkeys(media_files))  # deduplicate, preserve order
    package.write_to_file(str(apkg_path))

    return str(apkg_path)
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `cd /home/takosaga/Projects/EuropaLex && uv run pytest tests/apkg_export_test.py -v`
Expected: All 11 tests PASS.

- [ ] **Step 3: Commit**

```bash
cd /home/takosaga/Projects/EuropaLex
git add export/apkg_export.py tests/apkg_export_test.py
git commit -m "feat: add apkg_export module with direct genanki .apkg generation"
```

---

### Task 3: Update app.py import

**Files:**
- Modify: `app.py:471-480` (the `_handle_export_csv_for_anki` function)

- [ ] **Step 1: Change the import inside `_handle_export_csv_for_anki`**

Replace the existing code at lines ~471-480:

```python
def _handle_export_csv_for_anki(
    scenario: str,
    cefr_level: str,
    target_language: str,
) -> str | None:
    """Export current cards as an Anki-compatible .apkg file.

    Returns the absolute path to the generated .apkg file for Gradio DownloadButton.
    Returns None if no cards to export or export failed.
    """
    if not _current_cards:
        logger.warning("Anki export: no cards to export")
        return None

    try:
        from core.types import CEFRLevel
        from export.apkg_export import export_csv_for_anki

        cefr = CEFRLevel(cefr_level)
        apkg_path = export_csv_for_anki(_current_cards, scenario, cefr_level, target_language)
        return apkg_path
    except Exception as e:
        logger.error("Anki export failed: %s", e, exc_info=True)
        return None
```

Key changes:
1. Import changed from `csv_for_anki` to `apkg_export`
2. Docstring updated to say ".apkg file" instead of "CSV zip"
3. Variable renamed from `zip_path` to `apkg_path` for clarity (no functional change)

- [ ] **Step 2: Verify the import is correct**

Run: `cd /home/takosaga/Projects/EuropaLex && python -c "from app import _handle_export_csv_for_anki; print('OK')"`
Expected: `OK` (no import errors).

- [ ] **Step 3: Commit**

```bash
cd /home/takosaga/Projects/EuropaLex
git add app.py
git commit -m "refactor: update Anki export import from csv_for_anki to apkg_export"
```

---

### Task 4: Update widgets.py file_types

**Files:**
- Modify: `frontend/ui/widgets.py` — the `export_apkg_file` Gradio component definition

- [ ] **Step 1: Change the file_types hint from `.zip` to `.apkg`**

Find this block (around line ~230 in build_ui):

```python
                export_apkg_file = gr.File(
                    label="Download Anki Cards", file_types=[".apkg"], visible=False
                )
```

Change `file_types=[".zip"]` to `file_types=[".apkg"]`.

- [ ] **Step 2: Verify no other `.zip` references for apkg exist in widgets.py**

Run: `grep -n "zip" frontend/ui/widgets.py | grep -i "apkg\|anki"`
Expected: No matches (the change was the only one).

- [ ] **Step 3: Commit**

```bash
cd /home/takosaga/Projects/EuropaLex
git add frontend/ui/widgets.py
git commit -m "style: update Anki export file_types from .zip to .apkg"
```

---

### Task 5: Delete old csv_for_anki module and tests

**Files:**
- Delete: `export/csv_for_anki.py`
- Delete: `tests/csv_for_anki_test.py`

- [ ] **Step 1: Remove the old files**

```bash
cd /home/takosaga/Projects/EuropaLex
rm export/csv_for_anki.py tests/csv_for_anki_test.py
```

- [ ] **Step 2: Verify no remaining imports of csv_for_anki exist**

Run: `grep -rn "csv_for_anki" --include="*.py" .`
Expected: Only matches in AGENTS.md and README.md (to be updated later), NOT in any Python source file.

- [ ] **Step 3: Commit**

```bash
cd /home/takosaga/Projects/EuropaLex
git rm export/csv_for_anki.py tests/csv_for_anki_test.py
git commit -m "refactor: remove deprecated csv_for_anki module and tests"
```

---

### Task 6: Update AGENTS.md references

**Files:**
- Modify: `AGENTS.md` — multiple locations

- [ ] **Step 1: Update the project overview paragraph (line ~9)**

Replace:
```
Cards export as an Anki-compatible CSV zip (with HTML-embedded media references) or a zipped CSV folder with flat media files.
```
With:
```
Cards export as a proper .apkg Anki package file or a zipped CSV folder with flat media files.
```

- [ ] **Step 2: Update the module table (line ~38)**

Replace:
```
- `export/` — Anki-compatible CSV export with HTML media references (`csv_for_anki.py`), CSV zip export with flat media files (`csv_export.py`), Anki tunnel sync (unused)
```
With:
```
- `export/` — Direct .apkg Anki package generation (`apkg_export.py`), CSV zip export with flat media files (`csv_export.py`)
```

- [ ] **Step 3: Update the module boundaries table (line ~51)**

Replace:
```
| `export/` | Generate Anki-compatible CSV zip (`csv_for_anki.py`) and standard CSV zip (`csv_export.py`) with media files | Import from `frontend/` |
```
With:
```
| `export/` | Generate .apkg Anki packages (`apkg_export.py`) and standard CSV zip (`csv_export.py`) with media files | Import from `frontend/` |
```

- [ ] **Step 4: Update the module naming convention (line ~72)**

Replace:
```
- **Modules (lowercase, underscore):** `csv_for_anki`, `csv_export`, `anki_tunnel`, `download_models`
```
With:
```
- **Modules (lowercase, underscore):** `apkg_export`, `csv_export`, `download_models`
```

- [ ] **Step 5: Update the test table (line ~261)**

Replace:
```
| `csv_for_anki_test.py` | Anki-compatible CSV export (2-column Front/Back CSV, HTML-embedded `<img>` and `<audio>` tags, `collection.media/` subfolder, media copying) |
```
With:
```
| `apkg_export_test.py` | Direct .apkg generation via genanki (in-memory card building, media bundling into .apkg, deck/model definitions) |
```

- [ ] **Step 6: Update the known pitfalls section (line ~379)**

Replace:
```
Anki CSV export via `csv_for_anki.py` produces a zipped folder containing a 2-column CSV (`Front`/`Back`) with HTML-embedded `<img>` and `<audio>` tags referencing files in a `collection.media/` subfolder. Anki imports this via its native text-file import mechanism, resolving relative paths to media files automatically.
```
With:
```
Anki export via `apkg_export.py` produces a proper `.apkg` file using genanki with HTML-styled card templates (front: image + translation + audio; back: front side + divider + English text). The .apkg is Anki's native import format — use File → Import in Anki.
```

- [ ] **Step 7: Commit**

```bash
cd /home/takosaga/Projects/EuropaLex
git add AGENTS.md
git commit -m "docs: update AGENTS.md references from csv_for_anki to apkg_export"
```

---

### Task 7: Update README.md references

**Files:**
- Modify: `README.md` — multiple locations

- [ ] **Step 1: Update the export section (line ~102)**

Replace:
```
**Anki CSV export:** Click **Export Anki Cards** after Phase 2 completes. The app creates a `.zip` archive containing:
```
With:
```
**Anki export:** Click **Export Anki Cards** after Phase 2 completes. The app creates a `.apkg` file that you import into Anki via File → Import.
```

- [ ] **Step 2: Update the note about sync (line ~109)**

Replace:
```
> **Note:** The "Sync to Anki" button has been removed. Use CSV export for all imports into Anki (Anki supports CSV import natively).
```
With:
```
> **Note:** The "Sync to Anki" button has been removed. Use the .apkg export for all imports into Anki (File → Import in Anki).
```

- [ ] **Step 3: Update the workflow step (line ~143)**

Replace:
```
3. Import into Anki via Anki's native text-file import feature (for Anki CSV export) or open the standard CSV zip for manual use
```
With:
```
3. Import into Anki via File → Import (for .apkg export) or open the standard CSV zip for manual use
```

- [ ] **Step 4: Update the module table in Architecture section (line ~154)**

Replace:
```
| `export/` | Anki-compatible CSV export with HTML media references (`csv_for_anki.py`), standard CSV zip export with flat media files (`csv_export.py`), Anki tunnel sync (unused) |
```
With:
```
| `export/` | Direct .apkg Anki package generation (`apkg_export.py`), standard CSV zip export with flat media files (`csv_export.py`) |
```

- [ ] **Step 5: Update the development notes (line ~172)**

Replace:
```
- **Export:** `export/csv_for_anki.py` builds Anki-compatible CSV zips with HTML-embedded `<img>` and `<audio>` tags referencing `collection.media/`; `export/csv_export.py` creates zipped folders containing CSV + flat media files; `export/anki_tunnel.py` is unused.
```
With:
```
- **Export:** `export/apkg_export.py` builds .apkg Anki packages via genanki with HTML-styled card templates and bundled media; `export/csv_export.py` creates zipped folders containing CSV + flat media files.
```

- [ ] **Step 6: Update the directory tree (line ~208)**

Replace:
```
│   ├── csv_for_anki.py     # Anki-compatible CSV export (2-column Front/Back, HTML-embedded media, collection.media/)
```
With:
```
│   ├── apkg_export.py      # Direct .apkg Anki package generation via genanki (HTML-styled cards, bundled media)
```

- [ ] **Step 7: Commit**

```bash
cd /home/takosaga/Projects/EuropaLex
git add README.md
git commit -m "docs: update README.md references from csv_for_anki to apkg_export"
```

---

### Task 8: Run full test suite and smoke test

**Files:**
- No file changes — verification only

- [ ] **Step 1: Run the full pytest suite**

Run: `cd /home/takosaga/Projects/EuropaLex && uv run pytest tests/ -v`
Expected: All tests PASS, including new `apkg_export_test.py` tests and all existing tests. No failures from deleted `csv_for_anki_test.py`.

- [ ] **Step 2: Run the smoke test**

Run: `cd /home/takosaga/Projects/EuropaLex && uv run pytest tests/smoke_test.py -v`
Expected: All imports succeed, Gradio app constructs without errors.

- [ ] **Step 3: Verify app starts without errors**

Run: `cd /home/takosaga/Projects/EuropaLex && timeout 5 python app.py 2>&1 || true`
Expected: App starts and prints launch message (or times out after 5s — that's fine, just no import errors).

- [ ] **Step 4: Final commit**

```bash
cd /home/takosaga/Projects/EuropaLex
git add -A
git commit -m "test: verify full test suite passes with apkg_export"
```

---

## Self-Review Checklist

**Spec coverage:** Every requirement from the design doc has a corresponding task. Architecture → Task 2, Card styling → Task 2 (templates/CSS in module), Data flow/API → Tasks 3-4 (same function signature, no app.py logic changes), Error handling → Task 2 (ValueError on empty cards, graceful media skipping).

**Placeholder scan:** No TBD, TODO, or vague requirements. All code blocks are complete. All file paths are exact. All commands include full paths.

**Type consistency:** Function signature `export_csv_for_anki(cards, scenario, cefr_level, target_language) -> str` is identical across all tasks. The return type stays `str` (path string), just the extension changes from `.zip` to `.apkg`.

**Scope check:** Focused on a single replacement — one module swapped for another. No new features, no pipeline changes, no UI layout changes beyond file type hint.
