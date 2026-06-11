# Phase 2 Translation — Design Spec

**Date:** 2026-06-11
**Status:** Approved
**Topic:** Wire tiny-aya translation into EuropaLex two-phase workflow

## Context

EuropaLex is in Phase 1: English text generation via MiniCPM5-1B. Cards render with English on the front and a dashed placeholder on the back. Phase 2 must translate those English sentences into Latvian using the existing `LlamaCppTextEngine` (tiny-aya-water Q4_K_M), while images and audio toggles remain unchecked by default.

## Architecture Overview

The two-phase workflow stays intact:

1. **Phase 1** — User enters scenario → MiniCPM5-1B generates English sentences → cards render with placeholder back
2. **Phase 2** — User clicks "Generate Cards" → tiny-aya translates the English text → cards re-render with Latvian on front, English on back

Images and audio toggles default to unchecked (`value=False`). Media parameters are absent from the pipeline API for now but will be added later when TTS and image engines are wired.

## Components to Modify

### `core/pipeline.py` — Phase 2 orchestration (new)

A single function that receives Phase 1 English texts and produces translated `CardData` objects:

```python
def generate_phase2(
    texts: list[str],
    scenario: str,
    cefr_level: CEFRLevel,
    batch_size: int,
) -> Iterator[tuple[int, str, list[CardData]]]:
    """Yields (progress_percent, phase_label, cards) at each step."""
```

- Calls `EnginePool.get_translation_engine().generate()` for translation
- Yields progress updates: 20% (preparing), 60% (translating), 100% (complete)
- Returns `CardData` objects with `translation` populated, `audio_path`/`image_path` empty

### `core/engine.py` — Extend `LlamaCppTextEngine`

Add sentence-count validation and retry loop mirroring `MiniCPMTextEngine`:

- Wrap existing `generate()` body in a loop (max 3 attempts)
- If output line count == batch_size → return `TextResult(generated_texts=lines)`
- If mismatch → `_build_retry_prompt(actual_count, expected_count)` appended to conversation context, increment counter, retry
- After 3 failures → raise `ValidationError(raw_output=text)`
- `_build_retry_prompt` constructs a stricter prompt referencing the actual vs expected count

### `app.py` — Wire Phase 2 via pipeline

- `generate_media_async()` calls `pipeline.generate_phase2(...)` instead of using mock data
- Cards built from returned `CardData` objects with `placeholder_back=False`
- Images/audio toggles default to `value=False`
- `_enable_phase2()` and `_reset_to_idle()` updated for unchecked defaults

## Data Flow

```
User enters scenario → Phase 1 generates English (MiniCPM5-1B)
       ↓
Cards render: English front, placeholder back
       ↓
User clicks "Generate Cards" → generate_media_async()
       ↓
pipeline.generate_phase2(texts, scenario, cefr_level, batch_size)
       ↓
EnginePool.get_translation_engine().generate() with retry loop
       ↓
CardData objects: {text: <English>, translation: <Latvian>, audio_path: None, image_path: None}
       ↓
Cards re-render: Latvian front, English back (placeholder_back=False)
```

## Error Handling

- `ValidationError` from `LlamaCppTextEngine` → caught in `app.py` → rendered as error message (same pattern as Phase 1)
- Model not found → same fallback as Phase 1
- EnginePool mutual exclusion still enforced — translation engine gets exclusive VRAM access

## Constraints

- No unit test framework change — inline tests or smoke test only
- Follow existing import conventions: absolute imports from project root
- Max line length: 100 characters
- Type hints on all public functions
- Docstrings: one-line summary + args/returns for multi-arg functions
