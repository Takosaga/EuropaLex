# Image Generation Pipeline Integration — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire FLUX.2-klein image generation into EuropaLex's Phase 2 pipeline, switch model source from GGUF to diffusers, and make both Audio and Images toggles default ON after Phase 1.

**Architecture:** Image generation is added as a batch step between translation (Phase 2) and TTS audio in `app.py:generate_media_async()`. The existing `ImageGenEngine` already loads the correct model via diffusers — no engine changes needed. Model download entry and config are updated to point to the diffusers-compatible safetensors repo. Card dimensions are updated to accommodate landscape images.

**Tech Stack:** Python 3.12+, diffusers (Flux2KleinPipeline), Gradio 6, Pydantic

---

### Task 1: Update Model Download Script

**Files:**
- Modify: `models/download_models.py`

Change the `flux` model entry from GGUF (ComfyUI) to diffusers-compatible safetensors. The new repo `black-forest-labs/FLUX.2-klein-4B` contains many files (~10–12 GB). Use `allow_patterns` to download all safetensors weights plus scheduler/tokenizer configs.

- [ ] **Step 1: Replace the flux entry in MODELS dict**

Change lines 38-42 from:
```python
    "flux": {
        "repo": "unsloth/FLUX.2-klein-4B-GGUF",
        "files": ["flux-2-klein-4b-Q4_K_M.gguf"],
        "description": "FLUX.2-klein 4B Q4_K_M image gen (ComfyUI-GGUF)",
    },
```
to:
```python
    "flux": {
        "repo": "black-forest-labs/FLUX.2-klein-4B",
        "files": None,  # Download all files — safetensors weights + configs (~10–12 GB)
        "description": "FLUX.2-klein 4B image gen (diffusers)",
    },
```

Also update the module docstring line that says `flux            — FLUX.2-klein 4B Q4_K_M image gen (ComfyUI-GGUF)` to:
```
    flux            — FLUX.2-klein 4B image gen (diffusers)
```

- [ ] **Step 2: Update download_model() to handle None files**

In the `download_model` function, when `info["files"]` is `None`, skip the file listing and use `allow_patterns=None` (which downloads everything):

```python
def download_model(name: str, target_dir: Path) -> None:
    """Download a single model from HF Hub using Python API."""
    info = MODELS[name]
    output_dir = target_dir / name

    print(f"Downloading {info['description']} ({info['repo']})...")
    print(f"  Target: {output_dir}")
    if info["files"]:
        for f in info["files"]:
            print(f"  📦 {f}")
    else:
        print(f"  📦 All files ({info['description']} is ~10–12 GB)")
    print()

    from huggingface_hub import snapshot_download

    snapshot_download(
        repo_id=info["repo"],
        allow_patterns=info["files"] or ["*"],  # None → download all
        local_dir=str(output_dir),
        resume_download=True,
    )
    print(f"  ✓ Done — {output_dir}\n")
```

- [ ] **Step 3: Commit**

```bash
git add models/download_models.py
git commit -m "refactor: switch flux model from GGUF to diffusers safetensors"
```

---

### Task 2: Update Settings Configuration

**Files:**
- Modify: `configs/settings.yaml`

Update the `flux` section to reflect the new diffusers-compatible model path and runtime.

- [ ] **Step 1: Replace the flux config block**

Change lines 19-23 from:
```yaml
  flux:
    repo: unsloth/FLUX.2-klein-4B-GGUF
    file: flux-2-klein-4b-Q4_K_M.gguf
    runtime: ComfyUI-GGUF
    quant: Q4_K_M
```
to:
```yaml
  flux:
    repo: black-forest-labs/FLUX.2-klein-4B
    file: null  # diffuses model — no single GGUF file
    runtime: diffusers
    quant: null
```

Note: The `EngineConfig.from_settings_yaml()` method does not currently read the `flux` section, so these fields are informational only. Setting them to `null` keeps the YAML valid without breaking existing code.

- [ ] **Step 2: Commit**

```bash
git add configs/settings.yaml
git commit -m "docs: update flux config for diffusers runtime"
```

---

### Task 3: Update Toggle Defaults in app.py

**Files:**
- Modify: `app.py`

Both toggles start OFF during Phase 1 (disabled via CSS), then turn ON when Phase 2 is enabled. Change the default values from `False` to `True`.

- [ ] **Step 1: Change toggle creation defaults**

Find the toggle creation lines (~line 240 in app.py) and change both from `value=False` to `value=True`:

```python
# Before:
audio_toggle = create_toggle("🔊 Audio", value=False, elem_id="toggle-audio")
images_toggle = create_toggle("🖼️ Images", value=False, elem_id="toggle-images")

# After:
audio_toggle = create_toggle("🔊 Audio", value=True, elem_id="toggle-audio")
images_toggle = create_toggle("🖼️ Images", value=True, elem_id="toggle-images")
```

- [ ] **Step 2: Update _enable_phase2() return values**

The `_enable_phase2()` function returns Gradio component states. Change both Checkbox values from `False` to `True`:

```python
# Before:
def _enable_phase2():
    return (
        gr.Checkbox(interactive=True, value=False),
        gr.Checkbox(interactive=True, value=False),
        gr.Button(interactive=True),
        gr.Dropdown(interactive=True),
        "",
    )

# After:
def _enable_phase2():
    return (
        gr.Checkbox(interactive=True, value=True),
        gr.Checkbox(interactive=True, value=True),
        gr.Button(interactive=True),
        gr.Dropdown(interactive=True),
        "",
    )
```

The `_reset_to_idle()` function should keep `value=False` — when the user changes parameters and the UI resets, toggles should be OFF (disabled). Only after Phase 1 completes should they become ON.

- [ ] **Step 3: Commit**

```bash
git add app.py
git commit -m "style: set Audio and Images toggle defaults to ON"
```

---

### Task 4: Add Image Generation to generate_media_async()

**Files:**
- Modify: `app.py` (in `generate_media_async()` function)

Add image generation as a batch step between translation completion and TTS audio generation. Mirrors the existing TTS pattern exactly.

- [ ] **Step 1: Update _progress_pct to use spec progress ranges**

The translation phase should occupy 15%→70%, images 70%→85%, audio 85%→100%. Modify `_progress_pct` to accept a configurable range (defaulting to the new ranges):

```python
# Before (existing function):
def _progress_pct(translated_idx: int, total: int) -> tuple[float, str]:
    if total <= 1:
        return 100.0, "Translation complete!"
    pct = ((translated_idx + 1) / total) * 100
    remaining = total - (translated_idx + 1)
    if pct >= 100:
        return 100.0, "Translation complete!"
    return round(pct, 1), f"Translated {translated_idx + 1}/{total} — {remaining} remaining..."

# After:
def _progress_pct(
    translated_idx: int,
    total: int,
    start_pct: float = 15.0,
    end_pct: float = 70.0,
) -> tuple[float, str]:
    """Calculate progress percentage for translation within a given range."""
    if total <= 1:
        return end_pct, "Translation complete!"
    pct = start_pct + ((translated_idx + 1) / total) * (end_pct - start_pct)
    remaining = total - (translated_idx + 1)
    if pct >= end_pct:
        return end_pct, "Translation complete!"
    return round(pct, 1), f"Translated {translated_idx + 1}/{total} — {remaining} remaining..."
```

- [ ] **Step 2: Update the translation loop to use new progress range**

In `generate_media_async()`, find the call to `_progress_pct` inside the translation loop and add the explicit range parameters:

```python
# Change from:
pct, label = _progress_pct(i, total)

# To:
pct, label = _progress_pct(i, total, start_pct=15.0, end_pct=70.0)
```

- [ ] **Step 3: Add image generation between translation and audio**

After the translation loop completes (after `for i, english_text in enumerate(_current_texts):`), add the image generation block before the existing TTS block. Insert this code right after the translation loop ends and before the `tts_generated = False` line:

```python
    # Generate images for all translations if requested
    image_paths: list[str | None] = [None] * len(cards)
    if include_images and cards:
        yield generate_progress_html(70, "Generating images..."), generate_cards_html(
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

- [ ] **Step 4: Update the TTS progress start point**

Change the TTS audio progress from 70% to 85% (since image generation now occupies 70-85):

```python
# Before:
yield generate_progress_html(70, "Generating audio..."), generate_cards_html(
    cards, include_image=include_images, include_audio=True, placeholder_back=False
)

# After:
yield generate_progress_html(85, "Generating audio..."), generate_cards_html(
    cards, include_image=include_images, include_audio=tts_generated, placeholder_back=False
)
```

- [ ] **Step 5: Update the final yield to reflect image generation**

The final yield already passes `include_image=include_images` — this is correct. No change needed for the final yield line itself. However, update the completion label to mention images when they were generated:

```python
# Before:
final_label = "Translation and audio complete!" if tts_generated else "Translation complete!"

# After:
if include_images:
    if tts_generated:
        final_label = "Translation, images, and audio complete!"
    else:
        final_label = "Translation and images complete!"
else:
    final_label = "Translation and audio complete!" if tts_generated else "Translation complete!"
```

- [ ] **Step 6: Commit**

```bash
git add app.py
git commit -m "feat: add image generation to Phase 2 pipeline"
```

---

### Task 5: Update Card Dimensions for Images

**Files:**
- Modify: `frontend/ui/cards.py` (in `render_card_html()` function)

Update the adaptive card dimensions to accommodate 600×400 landscape images. The image box renders at ~120px tall in a ~180px wide container.

- [ ] **Step 1: Update min_height values**

Find the dimension block in `render_card_html()` (~lines 79-87) and update:

```python
# Before:
    if include_image and include_audio:
        width = 190
        min_height = 200
    elif include_image:
        width = 180
        min_height = 170
    elif include_audio:
        width = 180
        min_height = 160
    else:
        width = 160
        min_height = 90

# After (matching spec table):
    if include_image and include_audio:
        width = 190
        min_height = 350
    elif include_image:
        width = 180
        min_height = 310
    elif include_audio:
        width = 180
        min_height = 270
    else:
        width = 160
        min_height = 90
```

- [ ] **Step 2: Commit**

```bash
git add frontend/ui/cards.py
git commit -m "style: update card dimensions for landscape image layout"
```

---

### Task 6: Verify with Smoke Test

**Files:**
- Run: `python scripts/smoke_test.py`

- [ ] **Step 1: Run smoke test**

```bash
python scripts/smoke_test.py
```

Expected output: clean exit with all checks passing (no traceback). Specifically verify:
- `✓ core.types imports OK`
- `✓ core.engine imports OK`
- `✓ CardData validation OK`
- `✓ TextResult validation OK`
- `✓ AudioResult validation OK`
- `✓ ImageResult validation OK`
- `✓ TextResult.validate_and_parse gate OK`
- `✓ frontend.ui imports OK`
- `✓ app module loads OK`

- [ ] **Step 2: If smoke test passes, commit**

```bash
git add -A
git commit -m "test: verify image generation changes with smoke test"
```

- [ ] **Step 3: Manual verification (optional but recommended)**

Start the Gradio app and verify:
```bash
python app.py
```

Check in browser at `http://localhost:7860`:
1. Both Audio and Images toggles are checked after Phase 1 text generation
2. Toggles are disabled (dimmed) before Phase 1
3. Clicking "Generate Cards" with Images ON shows image placeholders on cards during translation, then actual images after generation
4. Progress bar flows: preparing → translating → generating images → generating audio → complete
5. Cards display at the correct height for each media combination

---

## Self-Review Checklist

**1. Spec coverage:**
- ✅ Model source change (Task 1 + Task 2): flux entry updated from GGUF to diffusers safetensors repo
- ✅ Toggle defaults ON (Task 3): both toggles set to `value=True` in creation and `_enable_phase2()`
- ✅ Image generation in pipeline (Task 4): batch generation after translation, before audio; prompts built from English text + CEFR level; image paths attached to cards; progress 70%→85%; error handling tracks None per card
- ✅ Card layout dimensions (Task 5): updated min_height values matching spec table
- ✅ Error handling: failed images tracked as None in list, don't block audio or rendering

**2. Placeholder scan:** No placeholders found. All code is concrete.

**3. Type consistency:**
- `include_images` parameter flows from Gradio handler → `_handle_media_generation_v2` → `generate_media_async()` — all use the same name and boolean type
- `image_path` dict key matches what `render_card_html()` reads via `card_data.get("image_path")`
- `cefr.value` used for prompt string (CEFRLevel enum → "B1" etc.)
- `ImageResult.image_paths` pattern mirrors `AudioResult.audio_paths` (already exists in types.py)

**4. No engine.py changes needed:** The existing `ImageGenEngine` already loads from `black-forest-labs/FLUX.2-klein-4B` via diffusers with bfloat16 + CPU offload. Resolution parameter not added — FLUX pipeline handles it internally.

---

## Files Changed Summary

| File | Change |
|---|---|
| `models/download_models.py` | Replace flux entry: GGUF → diffusers safetensors repo; handle None files in download |
| `configs/settings.yaml` | Update flux section: new repo, null file/runtime/quant (informational) |
| `app.py` | Toggle defaults → True; progress ranges 15-70/70-85/85-100; image generation batch step |
| `frontend/ui/cards.py` | Update min_height: 200→350, 170→310, 160→270 for media combos |
