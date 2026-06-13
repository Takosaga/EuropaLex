# Export Fix — Single-Click Download, Flat Folder, Meaningful Filenames

**Date:** 2026-06-13  
**Status:** Approved  

## Problem Statement

Three issues with the CSV export feature:

1. **Two-click download bug:** The export handler is a generator that yields progress first (with `None` path), then yields the zip path on a second yield. Gradio's DownloadButton only triggers a browser download when it receives a file path — the first yield sets its value to `None`, so the user must click again.

2. **Meaningless file names:** Media files are named `audio_0.wav`, `image_0.png` inside subfolders, giving no context about which scenario or language they belong to.

3. **Export status label clutter:** A `gr.Label("Export Status")` widget is shown under the download button, adding noise to an already clean UI.

## Design

### 1. Fix Two-Click Download

**File:** `frontend/ui/widgets.py`  
**Change:** Convert `_handle_export_csv_event` from a generator to a sync function.

The current handler yields twice:
```python
# Current (broken): two yields, first with None path
yield (progress_html_0, None)        # Gradio sets DownloadButton value → None
yield (progress_html_1, zip_path)    # User must click again to trigger download
```

The new handler returns once:
```python
# New (fixed): single return
return (progress_html_final, zip_path)  # Gradio sets path → triggers download immediately
```

Since the export is fast (<1 second), a progress bar update is unnecessary. The function writes the zip, then returns `(progress_html, zip_path)` in one shot. Gradio's DownloadButton receives the path and triggers the browser save dialog on the first click.

### 2. Flat Folder + Meaningful Filenames

**File:** `export/csv_export.py`  
**Changes:**
- Remove `audio_dir` and `images_dir` subfolder creation
- Rename media files to `{scenario_slug}_{cefr_level}_{lang_abbr}_{card_index}.{ext}`
  - Example: `ordering_coffee_A2_LV_0.wav`, `ordering_coffee_A2_LV_1.png`
- Update CSV `audio_filename` and `image_filename` columns to contain just the filename (not a path like `audio/audio_0.wav`)

**Before:**
```
ordering_coffee_A2_LV/
  cards.csv          # audio_filename="audio/audio_0.wav"
  audio/
    audio_0.wav
  images/
    image_0.png
```

**After:**
```
ordering_coffee_A2_LV/
  cards.csv          # audio_filename="ordering_coffee_A2_LV_0.wav"
  ordering_coffee_A2_LV_0.wav
  ordering_coffee_A2_LV_1.png
```

Language abbreviations already have no periods (LV, ES, FR, DE, PL, IT, PT, FI) — confirmed from `_LANGUAGE_ABBREVS` mapping.

### 3. Remove Export Status Label

**File:** `frontend/ui/widgets.py`  
**Changes:**
- Remove `export_status = gr.Label(...)` widget from UI layout
- Remove `export_status` from all tuple returns in `_reset_to_idle()` and `_on_media_generation_complete()`
- Remove `export_status` from all `.then()` / `.change()` output lists in event wiring

## Files Modified

| File | Lines Changed | Type |
|---|---|---|
| `export/csv_export.py` | ~15 lines | Logic change (rename + flatten) |
| `frontend/ui/widgets.py` | ~20 lines | Event handler rewrite + widget removal |

No new files. No dependencies added. No API changes to existing modules.

## Testing Impact

- `tests/csv_export_test.py` — needs updates for new file naming and flat folder structure assertions
- `tests/widgets_test.py` — may need updates if `_reset_to_idle()` or `_on_media_generation_complete()` output counts change
