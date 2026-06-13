# Export Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix two-click download bug, rename media files with meaningful names, flatten folder structure, and remove export status label clutter.

**Architecture:** Three small, focused changes across two source files plus one test file. The export engine gets a simpler naming scheme and removes subfolders. The UI handler switches from a generator to a sync function so Gradio's DownloadButton receives the file path on first click. The unused status label is stripped entirely.

**Tech Stack:** Python 3.12+, Gradio 6, pytest, stdlib `csv`/`shutil`.

---

## Task 1: Flatten folder structure and rename media files in csv_export.py

**Files:**
- Modify: `export/csv_export.py:70-115`
- Test: `tests/csv_export_test.py:media_file_copying, zip_creation`

### Step 1: Rewrite the media copy section to use flat naming

Replace the subfolder-based media copying logic in `export_csv_zip()` with flat-folder naming.

**Current code (lines ~70-115):**
```python
    # Create subfolders for media
    audio_dir = export_dir / "audio"
    images_dir = export_dir / "images"
    audio_dir.mkdir(exist_ok=True)
    images_dir.mkdir(exist_ok=True)

    # Copy media files and build CSV rows
    csv_path = export_dir / "cards.csv"
    with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile, quoting=csv.QUOTE_ALL)
        # Header row
        writer.writerow([
            'scenario', 'cefr_level', 'target_language',
            'english_text', 'translated_text',
            'audio_filename', 'image_filename'
        ])
        for i, card in enumerate(cards):
            audio_path = card.get('audio_path')
            image_path = card.get('image_path')

            # Copy audio file if it exists
            audio_filename = ''
            if audio_path and Path(audio_path).exists():
                audio_dst = audio_dir / f"audio_{i}.wav"
                shutil.copy2(audio_path, audio_dst)
                audio_filename = f"audio/audio_{i}.wav"

            # Copy image file if it exists
            image_filename = ''
            if image_path and Path(image_path).exists():
                image_dst = images_dir / f"image_{i}.png"
                shutil.copy2(image_path, image_dst)
                image_filename = f"images/image_{i}.png"

            writer.writerow([
                scenario,
                cefr_level,
                target_language,
                card.get('text', ''),
                card.get('translation', ''),
                audio_filename,
                image_filename,
            ])
```

**New code:**
```python
    # Copy media files and build CSV rows (flat folder — no subfolders)
    csv_path = export_dir / "cards.csv"
    with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile, quoting=csv.QUOTE_ALL)
        # Header row
        writer.writerow([
            'scenario', 'cefr_level', 'target_language',
            'english_text', 'translated_text',
            'audio_filename', 'image_filename'
        ])
        for i, card in enumerate(cards):
            audio_path = card.get('audio_path')
            image_path = card.get('image_path')

            # Build the common prefix: {scenario_slug}_{CEFR}_{LANG_ABBREV}
            base_name = f"{scenario_slug}_{cefr_level}_{lang_abbrev}"

            # Copy audio file if it exists — flat naming
            audio_filename = ''
            if audio_path and Path(audio_path).exists():
                audio_dst = export_dir / f"{base_name}_{i}.wav"
                shutil.copy2(audio_path, audio_dst)
                audio_filename = f"{base_name}_{i}.wav"

            # Copy image file if it exists — flat naming
            image_filename = ''
            if image_path and Path(image_path).exists():
                image_dst = export_dir / f"{base_name}_{i}.png"
                shutil.copy2(image_path, image_dst)
                image_filename = f"{base_name}_{i}.png"

            writer.writerow([
                scenario,
                cefr_level,
                target_language,
                card.get('text', ''),
                card.get('translation', ''),
                audio_filename,
                image_filename,
            ])
```

**Changes summary:**
- Remove `audio_dir` and `images_dir` subfolder creation entirely
- Build `base_name = f"{scenario_slug}_{cefr_level}_{lang_abbrev}"` once per card iteration
- Copy files directly into `export_dir` with names like `{base_name}_{i}.wav` / `{base_name}_{i}.png`
- CSV columns store bare filenames (no path prefix)

### Step 2: Run existing tests to verify they catch the breaking changes

```bash
uv run pytest tests/csv_export_test.py -v
```

Expected: `test_media_file_copying` and `test_zip_creation` will fail because they assert on subfolder structure (`audio/`, `images/`). This confirms the behavior changed. We'll fix them in Task 2.

### Step 3: Commit

```bash
git add export/csv_export.py
git commit -m "refactor: flatten export folder and rename media files with meaningful names"
```

---

## Task 2: Update csv_export tests for flat structure and new naming

**Files:**
- Modify: `tests/csv_export_test.py`

### Step 1: Fix `test_media_file_copying` — assert flat files, not subfolders

Replace the subfolder assertions with flat-folder checks:

```python
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
```

### Step 2: Fix `test_zip_creation` — assert no subfolder paths in zip

Replace the subfolder assertions with flat-file checks:

```python
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
```

### Step 3: Add test for CSV column values — verify bare filenames (no path prefix)

Add a new test method to `TestExportCsvZip`:

```python
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
```

### Step 4: Run tests to verify all pass

```bash
uv run pytest tests/csv_export_test.py -v
```

Expected: All tests PASS.

### Step 5: Commit

```bash
git add tests/csv_export_test.py
git commit -m "test: update csv_export tests for flat folder structure and meaningful filenames"
```

---

## Task 3: Fix two-click download + remove export status label in widgets.py

**Files:**
- Modify: `frontend/ui/widgets.py` (~150-200 line range)

### Step 1: Convert `_handle_export_csv_event` from generator to sync function

**Current code:**
```python
        def _handle_export_csv_event(scenario: str, cefr_level: str, target_language: str):
            """Export current cards as CSV + media zip and trigger browser download.

            Uses a generator to show progress before the download button returns the file path.
            Each yield produces (progress_html, download_button_value) matching outputs.
            """
            from frontend.ui.cards import generate_progress_html

            if not _app_module._current_cards:
                yield (generate_progress_html(0, "\u26a0\ufe0f No cards to export."), None)
                return

            try:
                zip_path = _app_module._handle_export_csv(scenario, cefr_level, target_language)
                if zip_path is None:
                    yield (generate_progress_html(0, "\u26a0\ufe0f Export failed."), None)
                    return
                yield (generate_progress_html(100, "Export complete!"), zip_path)
            except Exception as e:
                logger = logging.getLogger(__name__)
                logger.error("CSV export failed: %s", e, exc_info=True)
                yield (generate_progress_html(0, f"\u26a0\ufe0f Export failed: {e}"), None)

        # Download CSV button click — triggers browser download of zip file
        download_csv_btn.click(
            fn=_handle_export_csv_event,
            inputs=[scenario_input, cefr_dropdown, language_dropdown],
            outputs=[progress_html, download_csv_btn],
        )
```

**New code:**
```python
        def _handle_export_csv_event(scenario: str, cefr_level: str, target_language: str):
            """Export current cards as CSV + media zip and trigger browser download.

            Returns (progress_html, zip_path) directly so Gradio's DownloadButton
            receives the file path on first click and triggers the save dialog immediately.
            """
            from frontend.ui.cards import generate_progress_html

            if not _app_module._current_cards:
                return generate_progress_html(0, "\u26a0\ufe0f No cards to export."), None

            try:
                zip_path = _app_module._handle_export_csv(scenario, cefr_level, target_language)
                if zip_path is None:
                    return generate_progress_html(0, "\u26a0\ufe0f Export failed."), None
                return generate_progress_html(100, "Export complete!"), zip_path
            except Exception as e:
                logger = logging.getLogger(__name__)
                logger.error("CSV export failed: %s", e, exc_info=True)
                return generate_progress_html(0, f"\u26a0\ufe0f Export failed: {e}"), None

        # Download CSV button click — triggers browser download of zip file
        download_csv_btn.click(
            fn=_handle_export_csv_event,
            inputs=[scenario_input, cefr_dropdown, language_dropdown],
            outputs=[progress_html, download_csv_btn],
        )
```

**Key change:** `yield` → `return`. The function is no longer a generator — Gradio treats it as a regular function that returns a tuple matching the two output components. No intermediate `None` yield means the DownloadButton never gets cleared before receiving the path.

### Step 2: Remove `export_status` widget from UI layout

Remove these lines from the UI layout section (around line ~145):
```python
                # Export status label
                export_status = gr.Label(label="Export Status", visible=False)
```

### Step 3: Remove `export_status` from `_reset_to_idle()` return tuple

**Current:**
```python
def _reset_to_idle() -> tuple:
    ...
    return (
        gr.Button(visible=True, interactive=True),          # generate_text_btn
        gr.Checkbox(interactive=False, value=False),       # images_toggle
        gr.Checkbox(interactive=False, value=False),       # audio_toggle
        gr.Button(visible=True, interactive=False, variant="secondary"),  # generate_cards_btn
        gr.Dropdown(visible=True, interactive=False),      # voice_dropdown
        """<style id="phase-css">...</style>""",            # phase_css
        gr.DownloadButton(visible=False),                  # download_csv_btn
        gr.Label(visible=False),                           # export_status   ← REMOVE THIS LINE
    )
```

**New:** Remove the `gr.Label(visible=False),  # export_status` line entirely.

### Step 4: Remove `export_status` from `_on_media_generation_complete()` return tuple

**Current:**
```python
        def _on_media_generation_complete():
            import gradio as gr
            return (
                gr.Button(visible=False),        # generate_text_btn
                gr.Button(visible=False),       # generate_cards_btn
                gr.DownloadButton(visible=True), # download_csv_btn
                gr.Label(visible=True),         # export_status   ← REMOVE THIS LINE
            )
```

**New:** Remove the `gr.Label(visible=True),  # export_status` line entirely.

### Step 5: Update all event wiring to remove `export_status` from output lists

Remove `export_status` from every `.then()` / `.change()` call that references it. There are four places:

1. **`.then(_on_media_generation_complete, ...)` outputs:**
```python
        # Before:
        outputs=[generate_text_btn, generate_cards_btn, download_csv_btn, export_status],
        # After:
        outputs=[generate_text_btn, generate_cards_btn, download_csv_btn],
```

2. **`scenario_input.change(_reset_to_idle, ...)` outputs:**
```python
        # Before:
        outputs=[generate_text_btn, images_toggle, audio_toggle, generate_cards_btn, voice_dropdown, phase_css, download_csv_btn, export_status]
        # After:
        outputs=[generate_text_btn, images_toggle, audio_toggle, generate_cards_btn, voice_dropdown, phase_css, download_csv_btn]
```

3. **`cefr_dropdown.change(_reset_to_idle, ...)` outputs:**
```python
        # Before:
        outputs=[generate_text_btn, images_toggle, audio_toggle, generate_cards_btn, phase_css, download_csv_btn, export_status]
        # After:
        outputs=[generate_text_btn, images_toggle, audio_toggle, generate_cards_btn, phase_css, download_csv_btn]
```

4. **`batch_slider.change(_reset_to_idle, ...)` outputs:**
```python
        # Before:
        outputs=[generate_text_btn, images_toggle, audio_toggle, generate_cards_btn, voice_dropdown, phase_css, download_csv_btn, export_status]
        # After:
        outputs=[generate_text_btn, images_toggle, audio_toggle, generate_cards_btn, voice_dropdown, phase_css, download_csv_btn]
```

### Step 6: Run smoke test to verify app constructs without errors

```bash
uv run pytest tests/smoke_test.py -v
```

Expected: All PASS. The Gradio app must construct without `ValueError: didn't return enough output values` errors from mismatched tuple sizes.

### Step 7: Commit

```bash
git add frontend/ui/widgets.py
git commit -m "fix: single-click export download and remove export status label"
```

---

## Task 4: Final verification

### Step 1: Run full test suite

```bash
uv run pytest tests/ -v
```

Expected: All tests PASS.

### Step 2: Quick smoke check of the app

```bash
# Just verify it starts — don't need to actually run generation
timeout 5 uv run python app.py 2>&1 || true
```

Expected: App launches on port 7860 without import or construction errors.

### Step 3: Final commit (if any leftover changes)

```bash
git add -A
git commit -m "chore: final verification after export fix"
```

---

## Self-Review Checklist

1. **Spec coverage:**
   - Two-click download fix → Task 3, Step 1 (generator → sync) ✓
   - Flat folder + meaningful filenames → Task 1 (csv_export.py rewrite) ✓
   - Remove export status label → Task 3, Steps 2-5 (widget removal + tuple updates) ✓

2. **Placeholder scan:** No "TBD", "TODO", "implement later", or vague references. Every code change shows exact before/after snippets.

3. **Type consistency:** All function signatures match existing code. The `_handle_export_csv_event` return type stays `tuple[str, str | None]` — same shape as the generator yields, just returned instead of yielded.

4. **Test coverage:** Task 2 adds a new test (`test_csv_media_columns_have_bare_filenames`) that explicitly verifies CSV columns contain bare filenames, not paths. This is a regression guard for the flat-folder change.
