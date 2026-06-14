# Design: Replace csv_for_anki with Direct genanki .apkg Export

## Overview

Replace the current `csv_for_anki.py` module (which builds a CSV + media folder zip for Anki's text-file import) with a new `apkg_export.py` module that uses `genanki` to build cards in-memory and produce a proper `.apkg` file. The existing `create_anki_deck.py` reference script serves as the styling and behavior template.

## Architecture

| Change | Detail |
|---|---|
| **New file** | `export/apkg_export.py` — genanki-based .apkg generator |
| **Deleted file** | `export/csv_for_anki.py` — replaced entirely |
| **Unchanged** | `export/csv_export.py` — regular CSV + flat media export (unaffected) |
| **Dependency** | `genanki>=0.13.0` already in `pyproject.toml` |

The new module builds cards directly in-memory using genanki's API (`Model`, `Deck`, `Package`). Media files are copied into a temp `collection.media/` directory and bundled by genanki into the `.apkg` output. No intermediate CSV file is written.

## Card Styling & Template

The model uses 4 fields matching the reference script:

| Field | Content |
|---|---|
| `TargetText` | Target-language translation (front of card) |
| `EnglishText` | English source text (back of card) |
| `Image` | `<img src="{filename}">` HTML tag or empty string |
| `Audio` | `[sound:{filename}]` genanki markup or empty string |

**Card template:** Image → Translation (large, bold) → Audio player. Back shows front side + divider + English text (italic). CSS uses Segoe UI / Arial, rounded images up to 280px, centered layout.

## Data Flow & API

The function signature is **unchanged** from the current `csv_for_anki.py`:

```python
def export_csv_for_anki(
    cards: list[dict],
    scenario: str,
    cefr_level: str,
    target_language: str,
) -> str:
```

- **Input:** Same card dict format (`text`, `translation`, `audio_path`, `image_path`)
- **Output:** Path to `.apkg` file (instead of `.zip`)
- **Export path:** `.local/models/output/export/{scenario_slug}_{CEFR}_{LANG}.apkg`
- **No app.py changes needed** — handler function name stays the same

## Error Handling

| Scenario | Behavior |
|---|---|
| No cards provided | Returns `None` (handled in `_handle_export_csv_for_anki`) |
| Missing media file | Silently skipped — field left empty |
| Unknown language | Raises `ValueError` with supported list |
| genanki failure | Catch-all `except Exception` returns error to user |

No new error cases introduced beyond what the current module handles.

## Files Modified

| File | Action |
|---|---|
| `export/apkg_export.py` | **Create** — new genanki-based export module |
| `export/csv_for_anki.py` | **Delete** — replaced by apkg_export.py |
| `app.py` | Update `_handle_export_csv_for_anki` import from `csv_for_anki` to `apkg_export` |
| `frontend/ui/widgets.py` | Update `export_apkg_file` file_types from `.zip` to `.apkg` |
| `AGENTS.md` | Update project docs to reference `apkg_export` instead of `csv_for_anki` |
| `README.md` | Update export documentation |

## Files Created/Deleted in Export Directory

```
export/
├── __init__.py
├── csv_export.py          # unchanged
├── apkg_export.py         # NEW (replaces csv_for_anki)
└── csv_for_anki.py        # DELETED
```
