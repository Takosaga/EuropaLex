# APKG Export with Embedded Media — Design

## Overview

Add `.apkg` (Anki package) export to EuropaLex alongside the existing CSV zip export. Each generated flashcard deck exports as a self-contained Anki file with embedded audio (.wav) and image (.png) media files, ready to import directly into Anki desktop or mobile.

## Architecture & Components

### New File

**`export/apkg_generator.py`** — replaces the current stub. Contains all APKG generation logic.

```
app.py (_handle_export_apkg) ──┐
                                │
export/apkg_generator.py        │
  generate_apkg_package()       │
    ├── genanki.Model (note type)
    ├── genanki.Note × N (cards)
    ├── genanki.Package → .apkg zip
    ├── inject_media()          │
    │   ├── hash each .wav/.png
    │   ├── write into zip
    │   └── update media JSON
    └── return path to .apkg
```

### Existing Files Modified

| File | Change |
|---|---|
| `app.py` | Replace `_handle_export_apkg_stub()` with real handler that reads `_current_cards` and returns `.apkg` path |
| `frontend/ui/widgets.py` | Add second export button (`export_apkg_btn`) + second file download component (`export_apkg_file`) |
| `pyproject.toml` | Add `genanki` dependency |

### No Changes To

- `core/` modules (no new types, engines, or pipeline changes)
- `configs/settings.yaml`
- `_current_cards` global (same data source as CSV export)

## Note Model & Card Fields

### genanki Model Definition

```python
MODEL_ID = 1607392319  # hardcoded unique ID (random.randrange(1 << 30, 1 << 31))
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
```

### Note Creation Per Card

For each card in `_current_cards`:

| Anki Field | Source | Content |
|---|---|---|
| `Translation` | `card["translation"]` | Translated text (HTML-safe) |
| `English` | `card["text"]` | English source text (HTML-safe) |
| `Audio` | `card.get("audio_path")` | `<audio controls src="anki_hash.wav">` or empty string |
| `Image` | `card.get("image_path")` | `<img src="anki_hash.png" style="max-width:100%">` or empty string |

HTML escaping uses `html.escape()` for text content. Media references use Anki's hashed filenames (see Media Injection section).

### Deck Naming

Same convention as CSV export: `{scenario_slug}_{CEFR}_{LANG_ABBREV}`.

Example: `ordering_coffee_A2_LV`

## Media Injection

After genanki creates the base `.apkg` (zip with database + empty media manifest), media files are injected programmatically:

### Process

1. Open the generated `.apkg` zip in read mode
2. Read and parse the `media` JSON manifest (`{"filename": "original_name.ext"}`)
3. For each card, collect unique audio/image paths that exist on disk
4. For each unique file:
   - Read file content as bytes
   - Compute MD5 hash of content (Anki's media naming convention): `hashlib.md5(content, usedforsecurity=False).hexdigest()`
   - Append the original extension (`.wav` or `.png`) → zip entry name: `{hash}.{ext}`
   - Write into the zip in append mode with the hashed entry name
   - Update manifest: `{hash}.{ext}` → `{original_filename}.{ext}`
5. Write updated `media` JSON back into the zip

### HTML References in Cards

Card fields reference media using Anki's original filename (not the hash):

```html
<audio controls src="ordering_coffee_A2_LV_0.wav"></audio>
<img src="ordering_coffee_A2_LV_0.png" style="max-width:100%">
```

Anki resolves these to the hashed files in the package.

### Deduplication

Each unique source file is injected only once, regardless of how many cards reference it (handles repeated TTS outputs or shared images).

## API Signature

```python
def generate_apkg_package(
    cards: list[dict],
    scenario: str,
    cefr_level: str,
    target_language: str,
) -> str:
    """Generate an Anki package (.apkg) with embedded media.

    Args:
        cards: List of card dicts with keys: 'text', 'translation',
               'audio_path' (str or None), 'image_path' (str or None).
        scenario: Free-form scenario/topic string.
        cefr_level: CEFR level string (e.g., 'A2', 'B1').
        target_language: Target language name (e.g., 'Latvian').

    Returns:
        Absolute path to the generated .apkg file.

    Raises:
        ValueError: If no cards provided or media files missing.
        RuntimeError: If zip generation fails.
    """
```

## UI Changes

### New Components in `widgets.py`

Two export buttons + two file download components (parallel to existing CSV export):

| Component | elem_id | Initial State |
|---|---|---|
| `export_csv_btn` | `export-csv-btn` | visible=False, interactive=False |
| `export_apkg_btn` | `export-apkg-btn` | visible=False, interactive=False |
| `export_file` | — (existing) | value=None, visible=False |
| `export_apkg_file` | — (new) | value=None, visible=False |

### State Transitions

Both export buttons follow the same pattern as CSV export:
- **Phase 1 complete:** both hidden
- **Phase 2 complete:** both visible, interactive=True
- **Parameter reset:** both hidden again
- `_enable_phase2()` returns `(csv_btn, apkg_btn, csv_file, apkg_file)` — four outputs instead of three
- `_reset_to_idle()` returns `(csv_btn, apkg_btn, csv_file, apkg_file)` — same

### Gradio Event Handlers

```python
# CSV export
export_csv_btn.click(
    _handle_export_csv, [scenario_input, cefr_dropdown, language_dropdown],
    [export_file]
).then(lambda: (gr.Button(visible=False), gr.File(visible=False)), outputs=[export_csv_btn, export_file])

# APKG export
export_apkg_btn.click(
    _handle_export_apkg, [scenario_input, cefr_dropdown, language_dropdown],
    [export_apkg_file]
).then(lambda: (gr.Button(visible=False), gr.File(visible=False)), outputs=[export_apkg_btn, export_apkg_file])
```

## Error Handling

- **No cards:** handler returns `None` → Gradio shows nothing
- **Missing media files:** silently skipped (same as CSV export behavior)
- **genanki errors:** caught and logged, returns `None` with error message in progress bar
- **Media injection failures:** caught and logged, returns `.apkg` without media (text-only fallback)

## Testing

New test file: `tests/apkg_generator_test.py`

Tests:
1. Model creation (unique ID, field names, template structure)
2. Note creation (field mapping, HTML escaping)
3. Package generation (zip structure, database integrity)
4. Media injection (hash correctness, manifest update, deduplication)
5. Handler integration (`_handle_export_apkg` returns valid path)
6. Smoke test: generated `.apkg` can be opened by Anki (file exists, valid zip)

Mock all file I/O with `tempfile` and `unittest.mock`. No real model inference needed.

## Dependencies

Add to `pyproject.toml`:
```toml
genanki>=0.13.0
```

No other new dependencies. Uses only Python stdlib (`zipfile`, `hashlib`, `json`, `pathlib`, `html`) for media injection.
