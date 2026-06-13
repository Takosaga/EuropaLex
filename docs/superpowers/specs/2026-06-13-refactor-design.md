# Refactor: Module Separation and Test Reorganization

**Date:** 2026-06-13
**Status:** Approved
**Scope:** app.py, core/engine.py, frontend/ui/widgets.py, scripts/ → tests/

---

## Problem Statement

EuropaLex has two structural issues:

1. **`app.py` (552 lines) mixes business logic with Gradio UI construction.** Widget creation, layout assembly, and event wiring are interleaved with `generate_text_async()` and `generate_media_async()`. This violates the project convention that `app.py` should wire modules together, not contain business logic.

2. **`core/engine.py` (728 lines) bundles four unrelated engine classes.** MiniCPMTextEngine and LlamaCppTextEngine share llama-cpp-python patterns, but TTSEngine (omnivoice/PyTorch) and ImageGenEngine (diffusers/PyTorch) are independent concerns with no shared code.

Additionally:
- **`scripts/` mixes test files with utility scripts.** `download_models.py` is a model downloader, not a test.
- **Test naming doesn't follow the project convention** of `{module}_test.py`.
- **`core/test_text_engine.py` tests a deprecated `TextEngine` class** that was replaced by MiniCPMTextEngine/LlamaCppTextEngine.

---

## Target Directory Structure

```
EuropaLex/
├── app.py (~100 lines)              # Business logic handlers only
│                                    #   generate_text_async, generate_media_async, _VOICE_MAP
├── core/
│   ├── engine.py (~400 lines)       # MiniCPMTextEngine + LlamaCppTextEngine + EnginePool
│   ├── audio_gen.py (~120 lines)    # TTSEngine extracted here
│   ├── image_gen.py (~100 lines)    # ImageGenEngine extracted here
│   └── test_text_engine.py          # DELETED (tests deprecated TextEngine class)
├── frontend/ui/
│   ├── widgets.py (~250 lines)      # Widget factories + build_ui() layout function
│   └── cards.py                     # Unchanged
├── tests/                           # Renamed from scripts/
│   ├── smoke_test.py                # Integration test (kept as-is)
│   ├── count_enforcement_test.py    # Tests TextResult.validate_and_parse
│   ├── extract_sentences_test.py    # Tests core.text_gen.extract_sentences
│   ├── progression_test.py          # Tests _progress_pct helper
│   └── translation_retry_test.py    # Tests LlamaCppTextEngine retry loop
├── models/download_models.py        # Moved from scripts/
└── scripts/                         # REMOVED entirely
```

---

## Module Responsibilities After Refactor

| File | Does | Doesn't |
|---|---|---|
| `app.py` | Business logic (generate_text_async, generate_media_async), event handler wrappers | Gradio widget creation, UI layout |
| `core/engine.py` | MiniCPMTextEngine, LlamaCppTextEngine, EnginePool | TTS, image generation |
| `core/audio_gen.py` | TTSEngine only | Anything else |
| `core/image_gen.py` | ImageGenEngine only | Anything else |
| `frontend/ui/widgets.py` | create_toggle, create_voice_dropdown, build_ui() layout function | Business logic, engine calls |
| `tests/` | Pytest-compatible test scripts | Utility scripts (download_models moved) |

---

## Component Details

### app.py (after extraction)

- Keeps `generate_text_async()` and `generate_media_async()` **exactly as they are** — no signature changes
- `_VOICE_MAP` stays here (business data, not UI)
- Event handlers (`_handle_text_generation`, `_handle_media_generation_v2`) stay here
- `_enable_phase2()`, `_reset_to_idle()`, `_enable_language_dropdown_on_audio()` move to `widgets.py` — they return Gradio component updates but are part of the UI state machine
- The `with gr.Blocks() as demo:` block and all widget creation moves into `widgets.build_ui()` which returns the `demo` object
- `__main__` block becomes ~10 lines:

```python
from frontend.ui.widgets import build_ui
app = build_ui()
app.launch(server_name="0.0.0.0", server_port=7860, css=css_content)
```

### frontend/ui/widgets.py (after expansion)

- Keeps `create_toggle()` and `create_voice_dropdown()` unchanged
- Adds `build_ui()` — a single function that constructs the entire Gradio Blocks layout and returns it
- `_VOICE_MAP` moves to `widgets.py` — it maps voice display labels to OmniVoice instruct strings, consumed by the layout builder and event handlers
- Returns `(demo, generate_text_btn, generate_cards_btn, images_toggle, audio_toggle, voice_dropdown, phase_css)` — all elements that app.py's click handlers need to reference

### core/audio_gen.py

- Contains only `TTSEngine` — exactly the class as-is in engine.py
- No signature changes to `__init__`, `synthesize()`, or `unload()`
- EnginePool import updated: `from core.audio_gen import TTSEngine`

### core/image_gen.py

- Contains only `ImageGenEngine` — exactly the class as-is in engine.py
- No signature changes to `__init__`, `generate()`, or `unload()`
- EnginePool import updated: `from core.image_gen import ImageGenEngine`

---

## Data Flow (Unchanged)

The core data flow stays exactly the same — this is a refactor, not a feature change:

```
User input → app.py click handler → EnginePool.get(config)
  → MiniCPMTextEngine.generate() → TextResult
  → LlamaCppTextEngine.translate() → AudioResult/ImageResult (optional)
  → frontend.ui.cards.render_card_html() → Gradio output
```

The only change is **which file each engine class lives in** — the data flow, error handling patterns, retry loops, and generator yields are all preserved verbatim.

---

## Error Handling (Unchanged)

- `generate_text_async`: catches FileNotFoundError for missing models, logs with exc_info, yields user-friendly HTML
- `generate_media_async`: same pattern per phase (translation → TTS → images), each failure is isolated — cards render without that media type and user can retry
- Engine retry loops: MiniCPMTextEngine and LlamaCppTextEngine both retry 3 times with stricter prompts on count mismatch, raise ValidationError on exhaustion

No new error paths are introduced.

---

## Testing Strategy

### Pytest Configuration

Add a minimal `pyproject.toml` at project root for pytest discovery:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = "*_test.py"
```

This lets pytest discover all `*_test.py` files in the `tests/` directory automatically.

### Test File Renames

| Before | After | Tests |
|---|---|---|
| `scripts/test_count_enforcement.py` | `tests/count_enforcement_test.py` | TextResult.validate_and_parse() thinking-tag stripping, line-count enforcement |
| `scripts/test_extract_sentences.py` | `tests/extract_sentences_test.py` | core.text_gen.extract_sentences() pure function |
| `scripts/test_progression.py` | `tests/progression_test.py` | _progress_pct() helper, progressive card generation |
| `scripts/test_translation_retry.py` | `tests/translation_retry_test.py` | LlamaCppTextEngine._translate_single() retry loop, fallback |
| `scripts/smoke_test.py` | `tests/smoke_test.py` | Module imports, Gradio app construction (integration) |

### Deleted Files

- `core/test_text_engine.py` — tests deprecated `TextEngine` class that was replaced by MiniCPMTextEngine/LlamaCppTextEngine

---

## Implementation Steps

1. Create `core/audio_gen.py` — copy TTSEngine from engine.py
2. Create `core/image_gen.py` — copy ImageGenEngine from engine.py
3. Update `core/engine.py` — remove TTSEngine/ImageGenEngine, add imports for EnginePool
4. Update `app.py` — import TTSEngine/ImageGenEngine from new modules, move UI layout to widgets.build_ui()
5. Create `frontend/ui/widgets.py` expanded version with build_ui()
6. Rename `scripts/` → `tests/`, rename files per convention, move `download_models.py` to `models/`
7. Delete `core/test_text_engine.py` (stale)
8. Add pytest config
9. Run smoke test

---

## Files Updated

- `README.md` — update module structure diagram and test instructions
- `AGENTS.md` — update EnginePool table, import conventions, and testing section
