# Reorder Phase 2 Pipeline & Reduce Image Size Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reorder Phase 2 media generation so audio runs before images, and reduce image output dimensions to 450×300.

**Architecture:** Two targeted edits across two files — swap the audio/image blocks in `app.py` with updated progress percentages, and add `width`/`height` parameters to the Flux pipeline call in `core/engine.py`. No new code, no new types, no tests beyond smoke test verification.

**Tech Stack:** Python 3.12+, Gradio 6, diffusers (Flux2KleinPipeline), omnivoice, llama-cpp-python

---

### Task 1: Swap Audio and Image Generation Blocks in `app.py`

**Files:**
- Modify: `app.py:298-354` — reorder audio/image blocks

The media generation function currently runs images at progress 70% then audio at 85%. Swap them: audio first (70–85%), images last (85–95%).

**Step 1: Replace the image-then-audio sequence with audio-then-images**

Find the section starting at line 298 (`# Generate images for all translations if requested`) through the end of the audio block (~line 354). Replace the entire two-block sequence with the reordered version below.

Replace lines 298–354 (from `# Generate images...` through the end of the TTS excepts block) with:

```python
    # Generate TTS audio for all translations if requested
    image_paths: list[str | None] = [None] * len(cards)
    tts_generated = False
    if include_audio and cards:
        yield generate_progress_html(70, "Generating audio..."), generate_cards_html(
            cards, include_image=include_images, include_audio=True, placeholder_back=False
        )
        try:
            tts_engine = pool.get_tts_engine()
            output_dir = Path(config.models_dir) / "output" / "audio"
            translations_list = [c["translation"] for c in cards]
            audio_result = tts_engine.synthesize(translations_list, output_dir, language=target_language, instruct=voice)
            audio_paths = audio_result.audio_paths

            # Attach audio paths to cards
            for i, path in enumerate(audio_paths):
                if path is not None:
                    cards[i]["audio_path"] = path
            tts_generated = True
        except Exception as e:
            logger.error("TTS generation failed: %s", e, exc_info=True)
            # Cards remain without audio — user can retry
            tts_generated = False

    # Generate images for all translations if requested
    if include_images and cards:
        yield generate_progress_html(85, "Generating images..."), generate_cards_html(
            cards, include_image=True, include_audio=tts_generated, placeholder_back=False
        )
        try:
            img_engine = pool.get_image_engine()
            output_dir = Path(config.models_dir) / "output" / "images"
            # Build prompts from English text + CEFR level
            prompts = []
            for card in cards:
                prompt = (
                    f"Simple educational illustration for language learning: {card['text']}. "
                    f"Level: {cefr.value}. No text in image."
                )
                prompts.append(prompt)
            image_result = img_engine.generate(prompts, output_dir)
            image_paths = image_result.image_paths
            # Attach image paths to cards
            for i, path in enumerate(image_paths):
                if path is not None:
                    cards[i]["image_path"] = path
        except Exception as e:
            logger.error("Image generation failed: %s", e, exc_info=True)
            # Cards remain without images — user can retry
```

Key changes in this block:
- Audio block now yields at progress 70% (was image block's old position)
- Image block now yields at progress 85% (was audio block's old position)
- Comment headers swapped to match new positions
- `image_paths` and `tts_generated` variable declarations moved to the top before either block

**Step 2: Update the final completion label logic**

At line ~360–367, replace the final label construction. Find this code:

```python
    else:
        if include_images:
            if tts_generated:
                final_label = "Translation, images, and audio complete!"
            else:
                final_label = "Translation and images complete!"
        else:
            final_label = "Translation and audio complete!" if tts_generated else "Translation complete!"
```

Replace with:

```python
    else:
        if include_images:
            if tts_generated:
                final_label = "Translation, audio, and images complete!"
            else:
                final_label = "Translation and images complete!"
        else:
            final_label = "Translation and audio complete!" if tts_generated else "Translation complete!"
```

Only the first label changes: `"Translation, images, and audio complete!"` → `"Translation, audio, and images complete!"` to reflect the new order.

**Step 3: Commit**

```bash
git add app.py
git commit -m "refactor: reorder Phase 2 media generation — audio before images"
```

---

### Task 2: Reduce Image Size to 450×300 in `core/engine.py`

**Files:**
- Modify: `core/engine.py:551-556` — add width/height to Flux pipeline call

**Step 1: Add width and height parameters to the pipeline call**

Find the `_pipeline()` call inside `ImageGenEngine.generate()` (around line 551). It currently looks like:

```python
                images = self._pipeline(
                    prompt=prompt,
                    num_inference_steps=28,
                    guidance_scale=3.5,
                )
```

Replace with:

```python
                images = self._pipeline(
                    prompt=prompt,
                    num_inference_steps=28,
                    guidance_scale=3.5,
                    width=450,
                    height=300,
                )
```

**Step 2: Commit**

```bash
git add core/engine.py
git commit -m "feat: reduce image generation size to 450x300"
```

---

### Task 3: Verify with Smoke Test

**Files:**
- Run: `python scripts/smoke_test.py`

**Step 1: Run smoke test**

```bash
python scripts/smoke_test.py
```

Expected: clean exit (no traceback). This verifies all modules import correctly and the Gradio app constructs without errors.

**Step 2: Verify Gradio app starts**

```bash
timeout 5 python app.py 2>&1 || true
```

Expected: Gradio launches on port 7860, then times out after 5 seconds (or Ctrl+C). No import errors or runtime exceptions.

**Step 3: Commit (no code changes needed)**

```bash
git add -A
git commit -m "test: verify smoke test passes after pipeline reorder" --allow-empty
```

---

## Plan Self-Review

**Spec coverage:**
- Spec Change 1 (reorder pipeline): covered by Task 1 (all three sub-steps)
- Spec Change 2 (image size): covered by Task 2
- Spec Change 3 (prompt no action): confirmed — prompt already has "No text in image."

**Placeholder scan:** No TBD, TODO, or vague placeholders. Every step has exact code and commands.

**Type consistency:** No new types introduced. Existing variable names (`image_paths`, `tts_generated`, `cards`) preserved. Method signatures unchanged.

**Scope check:** Focused — two files, no new dependencies, no architectural changes. Fits single implementation cycle.
