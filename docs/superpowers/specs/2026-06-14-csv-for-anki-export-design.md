# CSV-for-Anki Export — Design Spec

**Date:** 2026-06-14
**Status:** Approved
**Replaces:** `.apkg` export via `genanki` + manual media injection (`export/apkg_generator.py`)

---

## Problem Statement

The current `.apkg` export uses `genanki` to build an Anki package, then post-processes the generated zip to inject media files (`.wav`, `.png`) with MD5-hashed filenames and updates a JSON manifest. This approach has import reliability issues — Anki fails or produces corrupt/missing cards when importing the generated `.apkg`.

The user wants a simpler, more reliable export method using Anki's native CSV text-file import with embedded HTML media references.

## Solution Overview

Replace `export/apkg_generator.py` entirely with a new `export/csv_for_anki.py` module that produces an Anki-compatible zip containing:
- A 2-column CSV (`Front` / `Back`) with HTML-embedded `<img>` and `<audio>` tags
- A `collection.media/` subfolder with all media files

This leverages Anki's documented text-file import mechanism, which supports embedded media when media files are placed alongside the CSV.

---

## Architecture

### File Structure (After Changes)

```
export/
├── csv_export.py          # existing — unchanged (general-purpose 7-column CSV)
├── csv_for_anki.py        # NEW — Anki-optimized 2-column CSV + media zip
└── apkg_generator.py      # DELETED
```

### Module: `csv_for_anki.py`

**Public function:**

```python
def export_csv_for_anki(
    cards: list[dict],
    scenario: str,
    cefr_level: str,
    target_language: str,
) -> str:
```

- **Input:** Same card data format as existing exports — list of dicts with keys `text`, `translation`, `audio_path` (str|None), `image_path` (str|None).
- **Output:** Absolute path to a `.zip` file containing the Anki-ready folder.
- **Same signature** as `export_csv_zip()` and `generate_apkg_package()` for consistent wiring in `app.py`.

### Output Zip Structure

```
{scenario_slug}_{CEFR}_{LANG}.zip
└── {scenario_slug}_{CEFR}_{LANG}/
    ├── cards.csv                    # 2 columns: Front, Back
    └── collection.media/            # media files (Anki convention)
        ├── {slug}_{CEFR}_{LANG}_0.wav
        ├── {slug}_{CEFR}_{LANG}_0.png
        ├── {slug}_{CEFR}_{LANG}_1.wav
        └── ...
```

The `collection.media/` folder name follows Anki's own media directory convention. When the user extracts the zip and imports `cards.csv` into Anki, they place (or point to) this folder as their collection's media directory.

### CSV Format

**Columns:** `Front`, `Back`

| Front | Back |
|---|---|
| `<b>translation text</b><br><img src="collection.media/{filename}.png"><br><audio controls src="collection.media/{filename}.wav"></audio>` | `English source text` |

**Rules:**
- If no image: omit the `<img>` tag entirely (not an empty tag)
- If no audio: omit the `<audio>` tag entirely
- Both present: translation heading, then image, then audio player — each on its own line
- Text is HTML-escaped where needed (e.g., `&`, `<`, `>` in translations)
- CEFR level and target language stored as Anki tags: `cefr_B1;language_Latvian`

### Media File Naming

Uses the same naming convention as `csv_export.py`:
```
{scenario_slug}_{CEFR}_{LANG}_{card_index}.{ext}
```

Example: `ordering_coffee_A2_LV_0.wav`, `ordering_coffee_A2_LV_0.png`

Media files are copied from their runtime paths to the export folder (same pattern as existing CSV export). Missing or None media paths are silently skipped.

---

## UI Changes

### Button Wiring

The existing "📥 Export Anki Cards" button (`export_apkg_btn`) is repurposed:

| Before | After |
|---|---|
| Calls `_handle_export_apkg()` | Calls `_handle_export_csv_for_anki()` |
| Imports `apkg_generator` | Imports `csv_for_anki` |
| Returns `.apkg` path | Returns `.zip` path |
| Downloads as `.apkg` file | Downloads as `.zip` file (label: "Anki Cards") |

### UI Components Affected

- `export_apkg_btn` — same button, different handler function
- `export_apkg_file` — same `gr.File` component, now receives a `.zip` path instead of `.apkg`
- All state transitions (enable/disable after Phase 2, reset on parameter change) remain unchanged
- Button label stays "📥 Export Anki Cards" — user-facing behavior is the same

### app.py Changes

```python
# BEFORE:
def _handle_export_apkg(...):
    from export.apkg_generator import generate_apkg_package
    apkg_path = generate_apkg_package(...)
    return apkg_path

# AFTER:
def _handle_export_csv_for_anki(...):
    from export.csv_for_anki import export_csv_for_anki
    zip_path = export_csv_for_anki(...)
    return zip_path
```

### frontend/ui/widgets.py Changes

The `_handle_export_apkg_event()` wrapper is renamed to `_handle_export_csv_for_anki_event()`. It calls the renamed handler in `app.py` but otherwise behaves identically — yields progress HTML and sets the file component value.

---

## Code Removed

| File | Lines | Reason |
|---|---|---|
| `export/apkg_generator.py` | 383 | Replaced by `csv_for_anki.py` |
| `_handle_export_apkg()` in `app.py` | ~20 | Replaced by `_handle_export_csv_for_anki()` |
| `_handle_export_apkg_event()` in `widgets.py` | ~25 | Renamed to `_handle_export_csv_for_anki_event()` |
| `tests/apkg_generator_test.py` | ~180 | Replaced by `tests/csv_for_anki_test.py` |

---

## Code Added

| File | Lines (est.) | Purpose |
|---|---|---|
| `export/csv_for_anki.py` | ~120 | New Anki CSV export module |
| `tests/csv_for_anki_test.py` | ~80 | Tests for new module |

Total net change: approximately **~200 lines removed**, **~200 lines added** — roughly neutral.

---

## Testing

### Unit Tests (`tests/csv_for_anki_test.py`)

| Test | Verifies |
|---|---|
| `test_export_returns_zip_path` | Function returns a valid file path |
| `test_zip_contains_cards_csv` | CSV exists in the zip archive |
| `test_csv_has_front_back_columns` | Header row is `Front,Back` |
| `test_csv_row_count_matches_cards` | One data row per card |
| `test_front_field_contains_translation` | Front HTML includes translation text |
| `test_front_field_contains_image_tag` | `<img>` tag present when image exists |
| `test_front_field_contains_audio_tag` | `<audio>` tag present when audio exists |
| `test_back_field_contains_english` | Back field has English source text |
| `test_media_files_copied_to_export` | `.wav` and `.png` files in zip |
| `test_media_in_collection_media_folder` | Files are under `collection.media/` |
| `test_missing_media_skipped_gracefully` | No error when audio/image path is None |
| `test_html_escaping` | Special characters in text are properly escaped |
| `test_empty_cards_raises_valueerror` | Raises for empty input |

### Smoke Test

Run `uv run pytest tests/smoke_test.py -v` — must pass (verifies all imports still work).

### Manual Verification

1. Generate cards with text + audio + images
2. Click "Export Anki Cards" → download zip
3. Extract zip, verify folder structure
4. Import `cards.csv` into Anki (enable "Allow HTML")
5. Verify cards display correctly with image and audio playback

---

## Migration Notes

### User Impact

- Exported files will be `.zip` instead of `.apkg` — users must extract and import the CSV into Anki manually (or use Anki's "Import" dialog to select the folder)
- The workflow is: export → extract → open Anki → Tools → Import → select `cards.csv` → enable "Allow HTML" → Import
- Existing exported `.apkg` files are unaffected — only new exports change format

### No Breaking Changes to Existing Export

The general-purpose CSV export (`csv_export.py`) remains unchanged. Users who relied on the 7-column format for other tools continue to get the same output.

---

## Decisions Made

| Decision | Choice | Rationale |
|---|---|---|
| Replace or augment `.apkg`? | Replace entirely | Simpler codebase, one export path for Anki |
| CSV column format? | 2-column Front/Back | Matches Anki's native import pattern; minimal and clear |
| Audio syntax? | `<audio controls src="...">` | User preference; works on modern Anki (23+) using Chromium |
| Dedicated module or extend existing? | New `csv_for_anki.py` | Single responsibility; mirrors existing `csv_export.py` pattern |
| Output format? | `.zip` (not `.apkg`) | CSV-based import requires a folder with media alongside CSV |
| Media folder name? | `collection.media/` | Follows Anki's own convention for media directories |

---

## Open Questions

None. All decisions captured above.
