# CSV Export Design

## Overview

Replace the stub `.csv` and `.apkg` buttons with a real CSV export that produces a downloadable `.zip` archive containing a CSV file and all associated media files (audio, images). Remove the "Sync to Anki" button from the UI. Export buttons become clickable after Phase 2 (translation + media generation) completes.

## Architecture

```
User clicks "Export CSV" (after Phase 2)
    → app.py: _handle_export_csv() click handler
        → csv_export.py: export_csv_zip()
            ├── Creates folder: {scenario_slug}_{CEFR}_{LANG_ABBREV}/
            ├── Writes CSV with columns: scenario, cefr_level, target_language, english_text, translated_text, audio_filename, image_filename
            ├── Copies media files into the folder
            └── Zips the folder → returns .zip path
        → Gradio gr.File component updates → user downloads zip
```

## Components

### 1. `export/csv_export.py` — Real Implementation

A single public function:

```python
def export_csv_zip(
    cards: list[dict],
    scenario: str,
    cefr_level: CEFRLevel,
    target_language: str,
) -> str:
```

**Responsibilities:**

- Create an output directory under `{models_dir}/output/export/` (configurable via settings.yaml, default `.local/models/output/export/`)
- Generate folder name by sanitizing the scenario string (lowercase, spaces → underscores, remove special characters), then append CEFR level and language abbreviation: `ordering_coffee_A2_LV`
- Write CSV using Python's `csv` module with RFC 4180 double-quote quoting
- Copy media files into subfolders (`audio/`, `images/`) within the export folder
- Zip the entire folder and return the `.zip` path

**Language abbreviation mapping (ISO 639-1):**

| Language | Abbreviation |
|---|---|
| Latvian | LV |
| Spanish | ES |
| French | FR |
| German | DE |
| Polish | PL |
| Italian | IT |
| Portuguese | PT |
| Finnish | FI |

**CSV columns:** `scenario,cefr_level,target_language,english_text,translated_text,audio_filename,image_filename`

- `audio_filename` / `image_filename`: relative path within the export folder (e.g., `audio/audio_0.wav`) or empty string if no media
- Fields containing commas, quotes, or newlines are automatically double-quote escaped by the `csv` module

**Sanitization rules for folder names:**

```python
def _sanitize_folder_name(scenario: str) -> str:
    """Convert scenario text to a filesystem-safe folder name slug."""
    slug = scenario.strip().lower()
    slug = re.sub(r'[^a-z0-9\s_]', '', slug)   # remove special chars
    slug = re.sub(r'\s+', '_', slug)             # spaces → underscores
    slug = re.sub(r'_+', '_', slug)              # collapse multiple underscores
    return slug.strip('_')
```

### 2. UI Changes in `frontend/ui/widgets.py`

**Button row changes:**

Before (3 buttons):
```
[.apkg] [.csv] [Sync to Anki]
```

After (2 buttons + file download):
```
[.apkg] [.csv]    [gr.File for zip download — hidden until export]
```

- Remove "Sync to Anki" button entirely
- `.csv` button: enabled after Phase 2, triggers `export_csv_zip()`
- `.apkg` button: enabled after Phase 2, stub handler shows "Coming soon" message
- Add a `gr.File` component (hidden by default) that displays the downloaded zip file

**Button enabling logic:**

Both export buttons are disabled during idle/Phase 1 state. They become interactive in `_enable_phase2()`:

```python
def _enable_phase2() -> tuple:
    return (
        gr.Checkbox(interactive=True, value=True),
        gr.Checkbox(interactive=True, value=True),
        gr.Button(interactive=True),       # generate_cards_btn
        gr.Dropdown(interactive=True),    # voice_dropdown
        "",                                # phase_css
        gr.Button(interactive=True),      # NEW: export_csv_btn
        gr.Button(interactive=True),      # NEW: export_apkg_btn
    )
```

**Event wiring:**

```python
# Export CSV handler (generator — yields progress + file path)
def _handle_export_csv():
    if not cards_exist():
        yield "No cards to export.", None
        return
    zip_path = csv_export.export_csv_zip(...)
    yield "Export complete!", zip_path

# Export APKG stub handler
def _handle_export_apkg_stub():
    yield "APKG export coming soon.", ""
```

### 3. `app.py` — Click Handlers

Two new generator functions in `app.py`:

```python
def _handle_export_csv(scenario, cefr_level, target_language):
    """Export current cards as a zipped CSV folder."""
    from frontend.ui.cards import generate_progress_html
    from export.csv_export import export_csv_zip
    # ... validate cards exist, call export_csv_zip, return zip path

def _handle_export_apkg_stub():
    """Stub: APKG export not yet implemented."""
    from frontend.ui.cards import generate_progress_html
    yield generate_progress_html(0, "APKG export coming soon."), ""
```

### 4. Tests — `tests/csv_export_test.py`

| Test | What it verifies |
|---|---|
| `test_folder_name_generation` | Scenario/CEFR/lang → correct folder name (e.g., `"ordering coffee"` + A2 + Latvian → `ordering_coffee_A2_LV`) |
| `test_csv_content_columns` | CSV has the 7 expected columns in order |
| `test_csv_content_row_count` | Row count matches number of cards |
| `test_csv_quoting` | Fields with commas/accents are properly double-quote escaped |
| `test_media_file_copying` | Audio/image files are copied into `audio/` and `images/` subfolders |
| `test_zip_creation` | Zip is created, extractable, contains expected structure |
| `test_language_abbreviation_mapping` | All 8 languages map to correct ISO 639-1 codes |
| `test_sanitize_folder_name` | Special chars removed, spaces → underscores, no leading/trailing `_` |

## Data Flow

```
Phase 2 completes → cards list populated with text, translation, audio_path, image_path
    ↓
User clicks "Export CSV"
    ↓
_handle_export_csv() reads current card data from app state
    ↓
export_csv_zip(cards, scenario, cefr_level, target_language)
    ↓
Creates: .local/models/output/export/{folder}/
    ├── {folder}.csv          (7 columns, one row per card)
    ├── audio/audio_0.wav     (copied from TTS output)
    ├── images/image_0.png    (copied from image generation)
    └── {folder}.zip          (zipped archive of the above)
    ↓
Gradio gr.File component receives zip path → triggers browser download
```

## Error Handling

- **No cards to export:** Show warning message, no file generated
- **Missing media files:** Skip missing files silently (don't fail the export). CSV entries for missing media remain empty strings.
- **Zip creation failure:** Catch `shutil.make_archive` exceptions, show error message in progress HTML
- **IO errors (disk full, permissions):** Catch and display user-friendly error

## Files Changed

| File | Action |
|---|---|
| `export/csv_export.py` | Implement `export_csv_zip()` and helpers |
| `frontend/ui/widgets.py` | Remove Sync button, add export buttons + gr.File, update `_enable_phase2()` outputs |
| `app.py` | Add `_handle_export_csv()` and `_handle_export_apkg_stub()` generator functions |
| `tests/csv_export_test.py` | New test file (8 tests) |
| `export/anki_tunnel.py` | Keep as stub (unused, not deleted) |

## Out of Scope

- Real `.apkg` implementation (button is stub only)
- CSV import into Anki (user handles manually via Anki's Import feature)
- Configurable output directory (uses default `models_dir/output/export/`)
- Incremental export (export always captures current card state)
