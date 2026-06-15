# Image Generation Feature — Design Spec

**Date:** 2026-06-12  
**Status:** Approved  

## Overview

Wire image generation into EuropaLex's Phase 2 pipeline, switching the model source from GGUF (ComfyUI) to the diffusers-based `black-forest-labs/FLUX.2-klein-4B` model. Both Audio and Images toggles default to ON after Phase 1 completes.

## Changes

### 1. Model Source (`models/download_models.py`)

Replace the existing `flux` entry which downloads a single GGUF file from `unsloth/FLUX.2-klein-4B-GGUF` with the diffusers-compatible model from Hugging Face Hub:

- **Repo:** `black-forest-labs/FLUX.2-klein-4B`
- **Files:** All safetensors weights, scheduler configs, tokenizer files (~10–12 GB total)
- **Description update:** "FLUX.2-klein 4B image gen (diffusers)"

### 2. Toggle Defaults (`app.py`)

Both toggles start OFF during Phase 1 (disabled via CSS), then turn ON when Phase 2 is enabled:

```python
audio_toggle = create_toggle("🔊 Audio", value=True, elem_id="toggle-audio")
images_toggle = create_toggle("🖼️ Images", value=True, elem_id="toggle-images")
```

### 3. Image Generation in Pipeline (`app.py` + `core/pipeline.py`)

**Approach: Batch after translation** (mirrors existing TTS pattern)

After the translation loop completes and before audio generation:

1. If `include_images` is True, call `ImageGenEngine.generate()` with a batch of prompts
2. Each prompt is built from the Phase 1 English text + CEFR level:
   ```
   "Simple educational illustration for language learning: [english_text]. Level: [cefr_level]. No text in image."
   ```
3. Images are saved as `image_{i}.png` in `{models_dir}/output/images/`
4. Attach `image_path` to each card dict, update progress bar (70% → 85%)
5. Then generate audio (85% → 100%) if toggled ON

Both `app.py:generate_media_async()` and `core/pipeline.py:generate_phase2()` receive the `include_images` parameter for consistency.

### 4. Card Layout (`frontend/ui/cards.py`)

Updated card heights to accommodate 600×400 landscape images in a ~180px wide container (~120px tall):

| Media | Width | Height |
|---|---|---|
| Image + Audio | 190px | 350px |
| Image only | 180px | 310px |
| Audio only | 180px | 270px |
| No media | 160px | 90px |

Image box rendered on the front side alongside translation, same pattern as audio.

### 5. ImageGenEngine (`core/engine.py`) — no changes needed

The existing `ImageGenEngine` already loads from `black-forest-labs/FLUX.2-klein-4B` via diffusers. It uses:
- `Flux2KleinPipeline.from_pretrained()` with bfloat16
- `enable_model_cpu_offload()` for VRAM management
- `num_inference_steps=28`, `guidance_scale=3.5`

Only minor update: accept a target resolution parameter (default 600×400) and pass it through to the pipeline's generator if supported.

## Data Flow

```
Phase 1: MiniCPM generates English text → cards shown with placeholder back
Phase 2:
  1. tiny-aya translates all sentences (streaming progress, 15%→70%)
  2. FLUX.2-klein generates images in batch if toggled ON (70%→85%)
  3. OmniVoice generates audio in batch if toggled ON (85%→100%)
  4. Cards render with translation + image + audio on front, English on back
```

## Error Handling

- Image generation failure per card is tracked as `None` in `ImageResult` (same pattern as TTS)
- Failed images don't block audio generation or card rendering
- Cards still display without images if generation fails — user can retry

## Testing

- Smoke test must pass (`python scripts/smoke_test.py`)
- Verify toggle defaults: both ON after Phase 1, OFF/disabled before
- Verify image paths resolve correctly in card HTML
