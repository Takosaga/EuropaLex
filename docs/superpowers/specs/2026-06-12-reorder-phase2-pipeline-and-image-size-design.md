# Reorder Phase 2 Pipeline & Reduce Image Size — Design Spec

**Date:** 2026-06-12
**Status:** Approved
**Scope:** `app.py`, `core/engine.py` — two files, three changes

## Goal

Reorder the Phase 2 media generation sequence so audio (TTS) runs before images, and reduce generated image dimensions from default (~1024×1024) to 450×300 for flashcard-appropriate sizing.

## Change 1: Reorder Generation Pipeline

**File:** `app.py` — media generation function (`generate_media_async`)

### Current Order
1. Translation (progress 15–70%)
2. Images (progress 70%)
3. Audio (progress 85%)

### New Order
1. Translation (progress 15–70%)
2. Audio (progress 70–85%)
3. Images (progress 85–95%)

### Details
- Move the TTS audio generation block (currently yielding at 85%) to the position where image generation currently lives (yielding at 70%).
- Move the image generation block (currently yielding at 70%) to the position where TTS audio currently lives (yielding at 85%).
- Update progress percentages: audio uses 70–85%, images uses 85–95%.
- Update final completion label from "Translation, images, and audio complete!" → "Translation, audio, and images complete!".

### Progress Flow Table

| Step | Progress Range | Label Template |
|---|---|---|
| Translation | 15–70% | "Translating... (N/total)" |
| Audio | 70–85% | "Generating audio..." |
| Images | 85–95% | "Generating images..." |
| Complete | 100% | "Translation, audio, and images complete!" |

## Change 2: Reduce Image Size to 450×300

**File:** `core/engine.py` — `ImageGenEngine.generate()` method

Add `width=450, height=300` parameters to the `Flux2KleinPipeline.__call__()` invocation. This resizes output from the default square (1024×1024) to a landscape format better suited for flashcard illustrations.

```python
images = self._pipeline(
    prompt=prompt,
    num_inference_steps=28,
    guidance_scale=3.5,
    width=450,
    height=300,
)
```

## Change 3: Image Prompt (No Action Required)

The image generation prompt in `app.py` line 313 already includes the "no text" constraint:

```python
f"Simple educational illustration for language learning: {card['text']}. Level: {cefr.value}. No text in image."
```

No changes needed.

## Files Modified

| File | Lines Changed | Type |
|---|---|---|
| `app.py` | ~15 lines (swap + label updates) | Refactor |
| `core/engine.py` | 2 lines (add width/height) | Enhancement |

## Testing

- Run `python scripts/smoke_test.py` — must pass.
- Verify Gradio app starts on port 7860.
- Manual test: generate cards with both Audio and Images toggled ON; confirm audio generates before images, and images are landscape (450×300).
