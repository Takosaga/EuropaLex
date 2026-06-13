# Pytest Migration Design

**Status:** Approved
**Date:** 2026-06-13

## Overview

Migrate all EuropaLex tests from `if __name__ == "__main__":` + `print()` style to proper pytest test files. Create new test files for modules that currently have no test coverage. Use `unittest.mock` for all model/engine mocking. Real audio and image files from `tests/test_outputs/` serve as file-existence fixtures.

## Test File Structure

Flat structure in `tests/`, one file per source module:

```
tests/
├── conftest.py                        # Shared fixtures (mock data, paths, temp dirs)
├── smoke_test.py                      # Pytest rewrite: import validation + model construction
├── cards_test.py                      # Card HTML rendering functions
├── widgets_test.py                    # Widget creation and UI state helpers
├── app_test.py                        # App async generators and helpers
├── audio_gen_test.py                  # TTSEngine (audio generation)
├── image_gen_test.py                  # ImageGenEngine (image generation)
├── engine_test.py                     # MiniCPMTextEngine, LlamaCppTextEngine, EnginePool
├── pipeline_test.py                   # Phase 2 orchestration
└── text_gen_test.py                   # Merged: extract_sentences + generate_sentences
```

## Existing Files Consolidated

| Old File | Destination | Notes |
|---|---|---|
| `count_enforcement_test.py` | `text_gen_test.py` | Same module, overlapping tests — merged |
| `extract_sentences_test.py` | `text_gen_test.py` | Same module — merged |
| `translation_retry_test.py` | `engine_test.py` | Tests LlamaCppTextEngine |
| `progression_test.py` | Split: `_progress_pct` → `app_test.py`, card progression → `cards_test.py` | Two distinct concerns |

## Mock Data (conftest.py fixtures)

### English Text (Phase 1)
```python
mock_english_texts = [
    "I love eating fresh fruits.",
    "She enjoys cooking pasta.",
    "The chef prepared a delicious meal.",
]
```

### Spanish Translation (Phase 2)
```python
mock_spanish_translations = [
    "Me encanta comer frutas frescas.",
    "Le encanta cocinar pasta.",
    "El chef preparó una comida deliciosa.",
]
```

### Real Media Files
- `mock_audio_paths`: Real `.wav` paths from `tests/test_outputs/audio/` (3 files)
- `mock_image_paths`: Real `.png` paths from `tests/test_outputs/images/` (3 files)

Used for file-existence assertions in card HTML tests and as return values for mocked TTS/image engines.

## Mocking Strategy

### Gradio (`widgets.py`)
- Patch `import gradio as gr` at module level using `conftest.py` fixtures or per-test mocks
- Test non-Gradio parts directly: `_VOICE_MAP`, CSS helper return values
- `build_ui()` tested by verifying it returns a `gr.Blocks` instance with expected widget types

### GPU Engines (`engine.py`, `audio_gen.py`, `image_gen.py`)
- All model loading (`_load_model()`, `_load_pipeline()`) patched via `unittest.mock.patch`
- Tests verify: correct method calls, retry loop behavior (side_effect chains), result wrapper correctness, unload behavior
- No actual GPU or model weights needed

### Pipeline (`pipeline.py`)
- EnginePool and individual engines mocked
- Tests verify orchestration flow: translation → TTS → CardData assembly
- Progress percentage calculations verified at each step

### App Async Generators (`app.py`)
- Generator functions consumed via `list()` to capture all yields
- Engine methods mocked; tests assert on sequence of `(progress_html, cards_html)` tuples
- Error handling paths tested by raising exceptions in mock engines

## Fixture Strategy (conftest.py)

| Fixture | Type | Purpose |
|---|---|---|
| `mock_english_texts` | list[str] | Phase 1 English sentences |
| `mock_spanish_translations` | list[str] | Phase 2 Spanish translations |
| `mock_audio_paths` | list[str] | Real .wav paths for file-existence tests |
| `mock_image_paths` | list[str] | Real .png paths for file-existence tests |
| `temp_output_dir` | Path (tmp_path) | Temp dir for TTS/image generation tests, auto-cleaned |
| `mock_llm_response_factory` | callable | Helper to build LLM response dicts: `{"choices": [{"message": {"content": "..."}}]}` |

## Detailed Test Coverage Per File

### `conftest.py`
- All shared fixtures listed above

### `smoke_test.py` (pytest rewrite)
- Import validation for all modules
- Pydantic model construction: CardData, TextResult, AudioResult, ImageResult, EngineConfig
- `TextResult.validate_and_parse()` gate: thinking-tag stripping, count enforcement, ValidationError on mismatch

### `cards_test.py`
**`render_card_html()`:**
- Placeholder mode (English front, dashed back)
- Normal mode (translation front, English back)
- With image (existing file → `<img>` tag; missing file → placeholder emoji)
- With audio (existing file → `<audio>` element; missing file → play button)
- Rotation parameter applied to transform style

**`generate_cards_html()`:**
- Empty cards list → "No cards" message
- Single card, multi-card rotation distribution
- Media toggle combinations: image-only, audio-only, both, neither
- Placeholder back mode

**`generate_progress_html()`:**
- 0% → empty string (hidden)
- Mid-progress: color transitions at 10%/60%/100%
- 100%: dark brown bar, green "complete" text

### `widgets_test.py`
**`create_toggle()`:**
- Label rendering with emoji
- Default value (True/False)
- elem_id generation from label text

**`create_voice_dropdown()`:**
- All 6 voice choices present
- Default value matches first choice
- elem_id = "voice-dropdown"

**`_VOICE_MAP`:**
- All 6 display labels map to correct instruct strings

**State helpers:**
- `_enable_phase2()`: returns tuple of (Checkbox, Checkbox, Button, Dropdown, "") with interactive=True
- `_reset_to_idle()`: returns tuple with interactive=False, disabled CSS string
- `_enable_language_dropdown_on_audio(True)`: removes disabled CSS, enables dropdown
- `_enable_language_dropdown_on_audio(False)`: applies disabled CSS to voice dropdown

### `app_test.py`
**`transform_mock_cards()`:**
- Legacy format → new format: `{"front": "X", "back": "Y"}` → `{"text": "Y", "translation": "X"}`
- Empty input returns empty list
- Multiple cards preserved in order

**`_progress_pct()`:**
- Single sentence (total=1): always 100% with "complete" label
- Two sentences: step 0 → ~50%, step 1 → 100%
- Five sentences: all steps verified for percentage and remaining count in label

**`generate_text_async()`:**
- Generator function structure (isgeneratorfunction check)
- Mock engine integration: yields progress updates then card HTML
- Error handling: FileNotFoundError path, general exception path

**`generate_media_async()`:**
- Generator function structure
- Per-sentence card progression: cards grow with each yield
- TTS toggle: yields audio generation progress when enabled
- Images toggle: yields image generation progress when enabled
- Missing Phase 1 texts error path

### `audio_gen_test.py`
**`TTSEngine.synthesize()`:**
- Success path: mock model returns audio data → .wav file written, path in result
- Failure path: mock model raises exception → None in result list
- Empty input list: returns empty AudioResult
- Language and instruct parameters passed to model.generate()

**`TTSEngine.unload()`:**
- Model deleted, _loaded reset to False
- torch.cuda.empty_cache() called

### `image_gen_test.py`
**`ImageGenEngine.generate()`:**
- Success path: mock pipeline returns images → .png file written, path in result
- Failure path: mock pipeline raises exception → None in result list
- Empty input list: returns empty ImageResult

**`ImageGenEngine.unload()`:**
- Pipeline deleted, _loaded reset to False
- torch.cuda.empty_cache() called

### `engine_test.py`
**`MiniCPMTextEngine.generate()`:**
- Mock LLM integration: generate() calls generate_sentences which calls llm.create_chat_completion
- TextResult wrapping with generated_texts field
- ValidationError propagation from text_gen

**`LlamaCppTextEngine._translate_single()`:**
- Success on first attempt
- Invalid output retry (contains "english", empty, multiline)
- Exhausted retries → fallback to original English text

**`LlamaCppTextEngine._is_valid_translation()`:**
- Valid: non-empty single line, no English words
- Invalid: empty string, whitespace-only, contains "translate"/"translation"/"english", multiline

**`LlamaCppTextEngine.generate()`:**
- Per-sentence translation loop: calls _translate_single for each input text
- TextResult wrapping
- Batch size matching

**`EnginePool.get()` / `.reset()`:**
- Singleton creation via get(config)
- Second get() returns same instance
- reset() clears singleton and unloads engines

### `pipeline_test.py`
**`generate_phase2()`:**
- Translation-only: yields progress updates per sentence, final CardData list with translations
- Translation+TTS: additional yield at 70% for audio generation, CardData includes audio_paths
- Progress percentages: 20% (prepare), 15-70% (translation steps), 70% (audio start if enabled), 100% (complete)

**`ValidationError` propagation:**
- If translation fails after retries, ValidationError is raised and not caught by pipeline

### `text_gen_test.py` (merged from count_enforcement_test.py + extract_sentences_test.py)
**`extract_sentences()`:**
- Basic numbered format: "1. Hello.\n2. World." → ["Hello.", "World."]
- Thinking tag stripping: `<thinking>...</thinking>\n1. A.\n2. B.` → ["A.", "B."]
- Mixed punctuation: sentences ending with `.`, `?`, `!`
- Zero sentences raises ValidationError
- Uncapped extraction: 20 numbered sentences all returned
- Non-numbered lines ignored silently
- Dot numbering (`1.`) and paren numbering (`1)`) formats
- Empty after tag stripping raises ValidationError

**`generate_sentences()`:**
- Success on first try with exact batch_size
- Retry when fewer than batch_size: second call provides enough
- Exhausted retries: returns what was produced (fewer than batch_size)
- Thinking tags in LLM output handled correctly
- Question sentences preserved

## Running Tests

```bash
cd /home/takosaga/Projects/EuropaLex
uv run pytest tests/ -v
```

The `pyproject.toml` already has `[tool.pytest.ini_options]` with `testpaths = ["tests"]` and `python_files = "*_test.py"`. No config changes needed.

## Out of Scope

- Testing actual model inference (all engines mocked)
- Testing Anki export (`export/` module) — not in current scope
- Integration tests with real Gradio server
- Performance benchmarks
