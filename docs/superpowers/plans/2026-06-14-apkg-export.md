# apkg Export Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace `csv_for_anki.py` with a new `apkg_export.py` module that produces proper `.apkg` files using genanki, following the two-phase approach (CSV temp-file then genanki packaging).

**Architecture:** The new module creates a temp export directory with `collection.media/`, copies media files, writes an intermediate CSV matching `working_anki_example/cards.csv` format, then reads it back and packages via genanki into a `.apkg` file. The function signature remains unchanged so app.py integration is minimal.

**Tech Stack:** Python 3.12+, genanki>=0.13.0 (already in pyproject.toml), pytest for testing

---

### Task 1: Create apkg_export.py with helper functions

**Files:**
- Create: `export/apkg_export.py` — new module with shared helpers

- [ ] **Step 1: Write the failing test**

Create `tests/apkg_export_test.py` (if not already present). The existing file at `tests/apkg_export_test.py` already has comprehensive tests. Verify it exists and imports from `export.apkg_export`.

```python
# tests/apkg_export_test.py already exists with these imports:
from export.apkg_export import (
    _LANGUAGE_ABBREVS,
    _get_language_abbrev,
    _sanitize_folder_name,
    export_csv_for_anki,
)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/apkg_export_test.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'export.apkg_export'" or "ImportError"

- [ ] **Step 3: Write minimal implementation — constants and helpers**

Create `export/apkg_export.py` with the same helper functions as `csv_for_anki.py`:

```python
"""EuropaLex .apkg Export — creates a proper Anki package via genanki.

Two-phase approach:
    Phase 1: Build CSV + media folder (matching working_anki_example/cards.csv format)
    Phase 2: Package with genanki into .apkg file

Produces: .local/models/output/export/{scenario_slug}_{CEFR}_{LANG}.apkg
"""

import csv
import os
import re
import random
import shutil
from pathlib import Path

import genanki

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


def _copy_media_file(
    src_path: str | None,
    dest_dir: Path,
    filename_prefix: str,
    card_index: int,
    ext: str,
) -> str | None:
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


def _build_front_html(
    translation: str,
    audio_path: str | None,
    image_path: str | None,
    export_dir: Path,
    base_name: str,
    card_index: int,
) -> tuple[str, str]:
    """Build the HTML/markup strings for the card front fields.

    Returns both Image markup and Audio markup as a tuple.

    Args:
        translation: Target-language text (will be HTML-escaped).
        audio_path: Path to TTS .wav file or None.
        image_path: Path to illustration .png file or None.
        export_dir: Export directory containing collection.media/.
        base_name: Filename prefix ({scenario}_{CEFR}_{LANG}).
        card_index: Zero-based card index.

    Returns:
        Tuple of (image_markup, audio_markup) strings.
        image_markup: '<img src="{filename}">' or empty string
        audio_markup: '[sound:{filename}]' or empty string
    """
    media_dir = export_dir / "collection.media"
    media_dir.mkdir(parents=True, exist_ok=True)

    image_markup = ""
    if image_path:
        fname = _copy_media_file(image_path, media_dir, base_name, card_index, ".png")
        if fname:
            image_markup = f'<img src="{fname}">'

    audio_markup = ""
    if audio_path:
        fname = _copy_media_file(audio_path, media_dir, base_name, card_index, ".wav")
        if fname:
            audio_markup = f"[sound:{fname}]"

    return image_markup, audio_markup


# Card template and CSS from create_anki_deck.py reference script
FRONT_TEMPLATE = """
<div class="card-front">
  {{#Image}}<div class="media-image">{{Image}}</div>{{/Image}}
  <div class="target-text">{{TargetText}}</div>
  {{#Audio}}<div class="audio">{{Audio}}</div>{{/Audio}}
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


def stable_id(seed: str) -> int:
    """Generate a stable numeric ID from a string seed."""
    rng = random.Random(seed)
    return rng.randint(1_000_000_000, 9_999_999_999)


def export_csv_for_anki(
    cards: list[dict],
    scenario: str,
    cefr_level: str,
    target_language: str,
) -> str:
    """Export cards as a proper Anki .apkg package via genanki.

    Two-phase approach:
        Phase 1: Build CSV + media folder (matching working_anki_example/cards.csv format)
        Phase 2: Package with genanki into .apkg file

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
    folder_name = f"{scenario_slug}_{cefr_level}_{lang_abbrev}"

    # Resolve output directory (same pattern as csv_export.py)
    export_base = _PROJECT_ROOT / ".local" / "models" / "output" / "export"
    export_base.mkdir(parents=True, exist_ok=True)

    export_dir = export_base / folder_name
    export_dir.mkdir(parents=True, exist_ok=True)

    media_dir = export_dir / "collection.media"
    media_dir.mkdir(parents=True, exist_ok=True)

    # ── Phase 1: Build CSV + media folder ──────────────────────────────

    csv_path = export_dir / "cards.csv"
    with open(csv_path, 'w', newline='', encoding='utf-8-sig') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['Front', 'Audio', 'Image', 'Back'])

        for i, card in enumerate(cards):
            base_name = f"{scenario_slug}_{cefr_level}_{lang_abbrev}"
            translation = card.get("translation", "")
            image_markup, audio_markup = _build_front_html(
                translation=translation,
                audio_path=card.get("audio_path"),
                image_path=card.get("image_path"),
                export_dir=export_dir,
                base_name=base_name,
                card_index=i,
            )
            back_text = card.get("text", "")
            writer.writerow([translation, audio_markup, image_markup, back_text])

    # ── Phase 2: Package with genanki ───────────────────────────────────

    model = genanki.Model(
        model_id=stable_id(folder_name + "_model"),
        name="Language Card (Text + Image + Audio)",
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

    deck = genanki.Deck(
        deck_id=stable_id(folder_name),
        name="EuropaLex Flashcards",
    )

    media_files = []
    card_count = 0

    # Read CSV back (same logic as create_anki_deck.py)
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        csv_lines = [l for l in f if not l.strip().startswith("#")]

    reader = csv.DictReader(csv_lines)
    reader.fieldnames = [h.strip().lower() for h in reader.fieldnames]

    for i, row in enumerate(reader, start=2):
        target = row.get("front", "").strip()
        english = row.get("back", "").strip()
        img_raw = row.get("image", "").strip()
        aud_raw = row.get("audio", "").strip()

        if not target or not english:
            continue

        # Extract bare filename from image markup: <img src="collection.media/foo.png">
        img_fn = ""
        if img_raw:
            match = re.search(r'src=["\']collection\.media/([^"\']+)["\']', img_raw)
            if match:
                img_fn = match.group(1)

        # Extract bare filename from audio markup: [sound:collection.media/foo.wav]
        aud_fn = ""
        if aud_raw:
            match = re.search(r'\[sound:collection\.media/([^\]]+)\]', aud_raw)
            if match:
                aud_fn = match.group(1)

        # Build image field with bare filename
        img_field = ""
        if img_fn:
            img_path = os.path.join(media_dir, img_fn)
            if os.path.exists(img_path):
                img_field = f'<img src="{img_fn}">'
                media_files.append(img_path)

        # Build audio field with bare filename
        aud_field = ""
        if aud_fn:
            aud_path = os.path.join(media_dir, aud_fn)
            if os.path.exists(aud_path):
                aud_field = f"[sound:{aud_fn}]"
                media_files.append(aud_path)

        note = genanki.Note(
            model=model,
            fields=[target, english, img_field, aud_field],
        )
        deck.add_note(note)
        card_count += 1

    if card_count == 0:
        raise ValueError("No valid cards found after processing")

    # Package and save
    package = genanki.Package(deck)
    package.media_files = list(dict.fromkeys(media_files))   # deduplicate, preserve order
    apkg_path = str(export_base / f"{folder_name}.apkg")
    package.write_to_file(apkg_path)

    return apkg_path
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/apkg_export_test.py -v`
Expected: All tests PASS (11 test classes covering helpers, export, media handling, edge cases)

- [ ] **Step 5: Commit**

```bash
git add export/apkg_export.py tests/apkg_export_test.py
git commit -m "feat: add apkg_export.py with genanki-based .apkg export"
```

---

### Task 2: Update app.py to import from apkg_export

**Files:**
- Modify: `app.py` — change import in `_handle_export_csv_for_anki`

- [ ] **Step 1: Write the failing test (integration check)**

Verify the current handler imports from `csv_for_anki` and will break:

```python
# Current code in app.py around line 484:
from export.csv_for_anki import export_csv_for_anki
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -c "from app import _handle_export_csv_for_anki"`
Expected: FAIL with "ModuleNotFoundError: No module named 'export.csv_for_anki'" (or the old import still works — we're about to change it)

- [ ] **Step 3: Update import in `_handle_export_csv_for_anki`**

In `app.py`, find the function around line 468 and update the import:

```python
# BEFORE (line ~484):
        from export.csv_for_anki import export_csv_for_anki

# AFTER:
        from export.apkg_export import export_csv_for_anki
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python -c "from app import _handle_export_csv_for_anki; print('OK')"`
Expected: PASS — no import errors

- [ ] **Step 5: Commit**

```bash
git add app.py
git commit -m "fix: update apkg export import from csv_for_anki to apkg_export"
```

---

### Task 3: Update frontend UI for .apkg file type

**Files:**
- Modify: `frontend/ui/widgets.py` — update `export_apkg_file` component

- [ ] **Step 1: Write the failing test (visual check)**

Check current export_apkg_file definition in widgets.py around line 299:

```python
# Current code:
                export_apkg_file = gr.File(
                    label="Download Anki Export",
                    file_types=[".zip"],  # ← needs to be .apkg
                    visible=False,
                )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `grep -n 'file_types=\["\.zip"\]' frontend/ui/widgets.py`
Expected: Found — confirms current value is `.zip`

- [ ] **Step 3: Update file_types to .apkg**

In `frontend/ui/widgets.py`, find the `export_apkg_file` definition and update:

```python
# BEFORE (~line 299):
                export_apkg_file = gr.File(
                    label="Download Anki Export",
                    file_types=[".zip"],
                    visible=False,
                )

# AFTER:
                export_apkg_file = gr.File(
                    label="Download Anki Export",
                    file_types=[".apkg"],
                    visible=False,
                )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `grep -n 'file_types=\["\.apkg"\]' frontend/ui/widgets.py`
Expected: Found — confirms updated value is `.apkg`

Also run smoke test:
```bash
uv run pytest tests/smoke_test.py -v
```
Expected: PASS — app still constructs without errors

- [ ] **Step 5: Commit**

```bash
git add frontend/ui/widgets.py
git commit -m "fix: update Anki export file type from .zip to .apkg"
```

---

### Task 4: Delete csv_for_anki.py and update docs

**Files:**
- Delete: `export/csv_for_anki.py` — replaced by apkg_export.py
- Modify: `AGENTS.md` — update references from csv_for_anki to apkg_export
- Modify: `README.md` — update export documentation (if present)

- [ ] **Step 1: Verify no remaining imports of csv_for_anki**

Run:
```bash
grep -rn "csv_for_anki\|from export.csv_for_anki" --include="*.py" .
```
Expected: Only `tests/csv_for_anki_test.py` should reference it (that test file will be deleted next)

- [ ] **Step 2: Delete csv_for_anki.py**

Run:
```bash
rm export/csv_for_anki.py
```

- [ ] **Step 3: Update AGENTS.md references**

In `AGENTS.md`, find all references to `csv_for_anki` and replace with `apkg_export`:

```markdown
# BEFORE (example):
| `export/` | Generate Anki-compatible CSV zip (`csv_for_anki.py`) ... |

# AFTER:
| `export/` | Generate Anki-compatible .apkg package (`apkg_export.py`) ... |
```

Also update the Architecture table and any mentions of "CSV for Anki" → ".apkg via genanki".

- [ ] **Step 4: Update README.md if it references csv_for_anki**

Run: `grep -n "csv_for_anki\|Anki.*CSV" README.md`
If found, update references to match new `.apkg` export behavior.

- [ ] **Step 5: Run test to verify no broken imports**

Run:
```bash
uv run python -c "from app import build_ui; print('OK')"
```
Expected: PASS — no ModuleNotFoundError

- [ ] **Step 6: Commit**

```bash
git rm export/csv_for_anki.py
git add AGENTS.md README.md
git commit -m "refactor: remove csv_for_anki.py, update docs for apkg_export"
```

---

### Task 5: Remove old csv_for_anki_test.py and run full suite

**Files:**
- Delete: `tests/csv_for_anki_test.py` — tests moved to apkg_export_test.py
- Verify: `tests/apkg_export_test.py` covers all cases

- [ ] **Step 1: Verify apkg_export_test.py has equivalent coverage**

Run:
```bash
grep -c "def test_" tests/apkg_export_test.py
```
Expected: 11+ tests (matching the comprehensive test suite already written)

- [ ] **Step 2: Delete old test file**

Run:
```bash
rm tests/csv_for_anki_test.py
```

- [ ] **Step 3: Run full test suite**

Run:
```bash
uv run pytest tests/ -v
```
Expected: All tests PASS (smoke + apkg_export + all other existing tests)

- [ ] **Step 4: Verify app starts correctly**

Run:
```bash
timeout 5 python app.py 2>&1 || true
```
Expected: "Running on local URL" or similar launch message (no import errors)

- [ ] **Step 5: Commit**

```bash
git rm tests/csv_for_anki_test.py
git add tests/
git commit -m "test: remove obsolete csv_for_anki_test.py, keep apkg_export_test.py"
```

---

### Task 6: Final verification and cleanup

**Files:**
- All files (full project scan)

- [ ] **Step 1: Verify no stale references**

Run:
```bash
grep -rn "csv_for_anki\|\.zip.*anki\|Anki.*CSV" --include="*.py" --include="*.md" --include="*.yaml" .
```
Expected: No remaining references to `csv_for_anki` or `.zip` Anki export

- [ ] **Step 2: Verify apkg_export_test.py passes standalone**

Run:
```bash
uv run pytest tests/apkg_export_test.py -v
```
Expected: All 11 tests PASS

- [ ] **Step 3: Run full test suite one final time**

Run:
```bash
uv run pytest tests/ -v
```
Expected: All tests PASS

- [ ] **Step 4: Verify working example still works (manual)**

Run the reference script to confirm format compatibility:
```bash
cd export/working_anki_example && python create_anki_deck.py && ls my_deck.apkg
```
Expected: "✅ Created 'my_deck.apkg'" with card count and media count

- [ ] **Step 5: Final commit**

```bash
git add .
git commit -m "test: verify apkg export works end-to-end"
```

---

## Self-Review Checklist

1. **Spec coverage:** 
   - ✅ Two-phase approach (CSV + genanki) — Task 1 implements both phases
   - ✅ Card model with 4 fields — Task 1 defines genanki.Model with TargetText, EnglishText, Image, Audio
   - ✅ CSS and template from create_anki_deck.py — Task 1 copies FRONT_TEMPLATE, BACK_TEMPLATE, CSS
   - ✅ Function signature unchanged — Task 1 preserves `export_csv_for_anki(cards, scenario, cefr_level, target_language) -> str`
   - ✅ Export path `.apkg` — Task 1 writes to `{folder_name}.apkg`
   - ✅ Error handling — Task 1 raises ValueError for empty cards; app.py wraps in try/except
   - ✅ UI file_types update — Task 3

2. **Placeholder scan:** No TBD/TODO/implement later phrases found. All code is complete and inline.

3. **Type consistency:** Function signature matches spec exactly. Return type is `str` (path to .apkg). Card dict keys are `text`, `translation`, `audio_path`, `image_path`.

4. **Test coverage:** Existing `tests/apkg_export_test.py` has 11 tests covering:
   - Helper functions (sanitize, language abbrev)
   - Export path and file existence
   - Valid zip structure (notes.json, deck.json)
   - Media file bundling
   - Note count and field content
   - Deck name
   - Missing media graceful handling
   - Empty cards ValueError
   - Single card edge case
   - Deck/model structure

5. **Task ordering:** Dependencies are correct — module must exist before app.py import, UI update must happen after module works, deletion of old files must happen after new code is verified.

---

**Plan complete and saved to `docs/superpowers/plans/2026-06-14-apkg-export.md`. Two execution options:**

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
