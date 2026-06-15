# OmniVoice TTS Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire OmniVoice text-to-speech into Phase 2 so translated sentences are converted to speech audio and attached to flashcards, using voice design mode with "female speaking" instruction.

**Architecture:** The TTSEngine already uses `k2-fsa/OmniVoice` from HuggingFace Hub but is dead code — never called during Phase 2. This plan adds the `instruct="female speaking"` parameter to put OmniVoice into voice design mode (consistent female voice without reference audio), wires TTS into `pipeline.generate_phase2()` as a sequential step after translation, and updates `app.py` to pass the audio toggle value through to both the pipeline and card rendering.

**Tech Stack:** Python 3.12+, omnivoice package (PyTorch-based), Gradio 6, Pydantic >=2.0.0

---

### Task 1: Update TTSEngine.synthesize() — Add voice design parameters

**Files:**
- Modify: `core/engine.py:452-463`

The TTSEngine already loads the correct model (`k2-fsa/OmniVoice`). The inner `generate()` call currently uses auto mode (random voice). Update it to use voice design mode with a consistent female voice, and add an optional `language` parameter for better quality.

- [ ] **Step 1: Add `language` parameter to method signature**

Change the method signature from:
```python
def synthesize(self, texts: list[str], output_dir: Path) -> AudioResult:
```
to:
```python
def synthesize(self, texts: list[str], output_dir: Path, language: str | None = None) -> AudioResult:
```

- [ ] **Step 2: Update inner `generate()` call to use voice design mode**

In the synthesis loop, replace:
```python
audio_data = self._model.generate(text=text)
```
with:
```python
audio_data = self._model.generate(
    text=text,
    instruct="female speaking",
    language=language,
)
```

The `instruct` parameter puts OmniVoice into voice design mode. The `language` parameter is optional but improves synthesis quality when the target language is known (e.g., "Latvian", "Spanish").

- [ ] **Step 3: Run smoke test to verify no import errors**

Run: `python scripts/smoke_test.py`
Expected: Clean exit, no traceback. The method signature change is backward-compatible (language defaults to None).

- [ ] **Step 4: Commit**

```bash
git add core/engine.py
git commit -m "feat: add voice design mode to TTSEngine with female speaking instruction"
```

---

### Task 2: Wire TTS into pipeline.generate_phase2()

**Files:**
- Modify: `core/pipeline.py`

Add a TTS step after translation completes. The pipeline becomes: translate all sentences → TTS all translations → yield final cards. Progress tracking spans both phases (15–70% translation, 70–95% audio, 95–100% final).

- [ ] **Step 1: Update function signature**

Change the function signature from:
```python
def generate_phase2(
    texts: list[str],
    scenario: str,
    cefr_level: CEFRLevel,
    batch_size: int,
) -> Iterator[tuple[int, str, list[CardData]]]:
```
to:
```python
def generate_phase2(
    texts: list[str],
    scenario: str,
    cefr_level: CEFRLevel,
    batch_size: int,
    target_language: str = "Latvian",
    include_audio: bool = False,
) -> Iterator[tuple[int, str, list[CardData]]]:
```

- [ ] **Step 2: Update docstring**

Replace the existing docstring with:
```python
"""Generate translations and optional TTS audio for Phase 1 English texts.

Orchestrates the translation pipeline: gets the tiny-aya engine,
calls generate with retry validation, optionally generates TTS audio
for all translations via OmniVoice (voice design mode), and yields CardData objects.

Yields (progress_percent, phase_label, cards) at each step.

Args:
    texts: English sentences generated in Phase 1.
    scenario: Original scenario/topic description.
    cefr_level: CEFR proficiency level.
    batch_size: Number of translations expected.
    target_language: Target language name for TTS (e.g., "Latvian"). Used to improve synthesis quality.
    include_audio: If True, generate TTS audio for all translations after translation completes.

Yields:
    (20, "Preparing translation...", []) — before engine call
    (15-70, "Translating... (N/total)", []) — during per-sentence translation
    (70, "Generating audio...", []) — before TTS starts (if include_audio=True)
    (95, "Audio complete!", cards) — after TTS batch (if include_audio=True)
    (100, "Translation and audio complete!", cards) — with final CardData list

Raises:
    ValidationError: If translation fails after max retries.
"""
```

- [ ] **Step 3: Remove placeholder comment**

Delete the line at the top of the file that reads:
```python
Images and audio are not yet wired — those fields remain empty.
```

- [ ] **Step 4: Add TTS step after translation loop, before card construction**

After the existing translation loop ends (after `yield progress, f"Translating... ({i + 1}/{total})", []`), and before the `cards = [...]` block, insert:

```python
    audio_paths: list[str | None] = [None] * len(translations)

    if include_audio:
        yield 70, "Generating audio...", []
        try:
            tts_engine = pool.get_tts_engine()
            output_dir = Path(config.models_dir) / "output" / "audio"
            audio_result = tts_engine.synthesize(translations, output_dir, language=target_language)
            audio_paths = audio_result.audio_paths
        except Exception as e:
            logger.error("TTS generation failed: %s", e, exc_info=True)
            # Continue with None audio paths — cards still render with translations
```

This creates an `audio_paths` list initialized to all-None (matching current behavior when TTS is disabled), then populates it from the TTS engine if `include_audio=True`. Failures are logged but don't break the pipeline.

- [ ] **Step 5: Update CardData construction to include audio paths**

Replace the existing card construction block:
```python
    cards = [
        CardData(
            text=text,
            translation=translation,
            audio_path=None,
            image_path=None,
            cefr_level=cefr_level,
        )
        for text, translation in zip(texts, translations)
    ]
```
with:
```python
    cards = [
        CardData(
            text=text,
            translation=translation,
            audio_path=audio_paths[i] if include_audio else None,
            image_path=None,
            cefr_level=cefr_level,
        )
        for i, (text, translation) in enumerate(zip(texts, translations))
    ]
```

- [ ] **Step 6: Update final yield label**

Change the last yield from:
```python
    yield 100, "Translation complete!", cards
```
to:
```python
    if include_audio:
        yield 100, "Translation and audio complete!", cards
    else:
        yield 100, "Translation complete!", cards
```

- [ ] **Step 7: Run smoke test**

Run: `python scripts/smoke_test.py`
Expected: Clean exit. The new parameters have defaults so existing callers won't break.

- [ ] **Step 8: Commit**

```bash
git add core/pipeline.py
git commit -m "feat: wire TTS into Phase 2 pipeline with voice design mode"
```

---

### Task 3: Wire audio toggle into app.py — Pipeline call and card rendering

**Files:**
- Modify: `app.py`

Update `generate_media_async()` to accept the `include_audio` parameter, pass it through to `pipeline.generate_phase2()`, and update all `generate_cards_html()` calls to use actual toggle values instead of hardcoded `False`.

- [ ] **Step 1: Update `generate_media_async()` signature**

Change from:
```python
def generate_media_async(
    scenario: str,
    cefr_level: str,
    batch_size: int,
    target_language: str = "Latvian",
):
```
to:
```python
def generate_media_async(
    scenario: str,
    cefr_level: str,
    batch_size: int,
    target_language: str = "Latvian",
    include_audio: bool = False,
):
```

- [ ] **Step 2: Update the docstring**

Replace the existing docstring:
```python
    """Phase 2: Translate Phase 1 English text to Latvian via tiny-aya.

    Reads the English texts from _phase1_texts (set by Phase 1 handler),
    translates each sentence one-by-one, and yields progressive card updates
    so cards appear incrementally as translations complete.
    Images and audio toggles are not yet active — media fields remain empty.
    """
```
with:
```python
    """Phase 2: Translate Phase 1 English text and optionally generate TTS audio.

    Reads the English texts from _phase1_texts (set by Phase 1 handler),
    translates each sentence one-by-one via tiny-aya, optionally generates
    TTS audio for all translations via OmniVoice (voice design mode), and
    yields progressive card updates so cards appear incrementally.
    """
```

- [ ] **Step 3: Update the pipeline call to pass `include_audio`**

Find the line in `generate_media_async()` that calls `pipeline.generate_phase2()`. Since `app.py` currently doesn't import or call `pipeline.generate_phase2()` directly (it uses inline translation logic), we need to update the inline translation loop. 

Actually, looking at `app.py`, it does NOT use `pipeline.generate_phase2()` — it has its own inline translation logic in `generate_media_async()`. The pipeline function exists but is never called from the app. We need to:

a) Update the inline translation loop to track progress correctly for the new TTS step
b) Add TTS generation after the translation loop completes
c) Pass audio paths into card rendering

Replace the existing translation loop and final yield in `generate_media_async()` with:

```python
    # Build cards one-by-one — each sentence translated individually
    cards: list[dict] = []
    total = len(_phase1_texts)

    for i, english_text in enumerate(_phase1_texts):
        try:
            translation = translation_engine._translate_single(
                english_text, cefr,
                topic_description=scenario,
                target_language=target_language,
            )
        except Exception as e:
            logger.error("Translation failed for sentence %d: %s", i, e, exc_info=True)
            # Fallback: use English text as translation
            translation = english_text

        cards.append({
            "text": english_text,
            "translation": translation,
            "cefr_level": cefr,
            "topic_description": scenario,
        })

        pct, label = _progress_pct(i, total)
        yield generate_progress_html(pct, label), generate_cards_html(
            cards, include_image=False, include_audio=include_audio, placeholder_back=False
        )

    # Generate TTS audio for all translations if requested
    if include_audio and cards:
        yield generate_progress_html(70, "Generating audio..."), generate_cards_html(
            cards, include_image=False, include_audio=True, placeholder_back=False
        )
        try:
            tts_engine = pool.get_tts_engine()
            output_dir = Path(config.models_dir) / "output" / "audio"
            translations_list = [c["translation"] for c in cards]
            audio_result = tts_engine.synthesize(translations_list, output_dir, language=target_language)
            audio_paths = audio_result.audio_paths

            # Attach audio paths to cards
            for i, path in enumerate(audio_paths):
                if path is not None:
                    cards[i]["audio_path"] = path
        except Exception as e:
            logger.error("TTS generation failed: %s", e, exc_info=True)
            # Cards remain without audio — user can retry

    # Final yield with 100%
    if not cards:
        yield generate_progress_html(0, "\u26a0\ufe0f No translations produced."), (
            '<div style="color:#c44; padding:20px;">'
            '<strong>Translation failed.</strong><br>No translations were produced. '
            'Check the terminal for error details.'
            '</div>'
        )
    else:
        final_label = "Translation and audio complete!" if include_audio else "Translation complete!"
        yield generate_progress_html(100, final_label), generate_cards_html(
            cards, include_image=False, include_audio=include_audio, placeholder_back=False
        )
```

- [ ] **Step 4: Add missing import for Path**

Add `from pathlib import Path` at the top of `app.py` near the other imports (after `import logging`).

- [ ] **Step 5: Update `_handle_media_generation()` wrapper to accept and pass `include_audio`**

Change from:
```python
    def _handle_media_generation(scenario, cefr_level, batch_size, target_language):
        """Wrapper for generate_media_async that handles empty scenario and missing Phase 1 texts."""
        if not scenario.strip():
            yield generate_progress_html(0, "⚠️ Please enter a scenario or topic."), '<div style="color:#c44; padding:20px;">Please enter a scenario or topic to generate cards.</div>'
            return
        for result in generate_media_async(scenario, cefr_level, batch_size, target_language):
            yield result
```
to:
```python
    def _handle_media_generation(scenario, cefr_level, batch_size, target_language, include_audio):
        """Wrapper for generate_media_async that handles empty scenario and missing Phase 1 texts."""
        if not scenario.strip():
            yield generate_progress_html(0, "⚠️ Please enter a scenario or topic."), '<div style="color:#c44; padding:20px;">Please enter a scenario or topic to generate cards.</div>'
            return
        for result in generate_media_async(scenario, cefr_level, batch_size, target_language, include_audio):
            yield result
```

- [ ] **Step 6: Update the Gradio event binding to pass audio toggle**

Find the `generate_cards_btn.click(...)` line and update the inputs list to include the audio toggle. Change from:
```python
    generate_cards_btn.click(
        fn=_handle_media_generation,
        inputs=[scenario_input, cefr_dropdown, batch_slider, language_dropdown],
        outputs=[progress_html, card_output],
    )
```
to:
```python
    generate_cards_btn.click(
        fn=_handle_media_generation,
        inputs=[scenario_input, cefr_dropdown, batch_slider, language_dropdown, audio_toggle],
        outputs=[progress_html, card_output],
    )
```

Note: `audio_toggle` is a Gradio Checkbox widget. When passed as an input, it yields its boolean `value` property (True/False), which maps directly to the `include_audio` parameter.

- [ ] **Step 7: Run smoke test**

Run: `python scripts/smoke_test.py`
Expected: Clean exit. The new parameter has a default value so the function remains callable without it.

- [ ] **Step 8: Commit**

```bash
git add app.py
git commit -m "feat: wire audio toggle into Phase 2 media generation and card rendering"
```

---

### Task 4: Clean up settings.yaml — Remove old GGUF OmniVoice config

**Files:**
- Modify: `configs/settings.yaml`

The Python model `k2-fsa/OmniVoice` is auto-loaded from HuggingFace Hub by the omnivoice package. The old GGUF config entry (`Serveurperso/OmniVoice-GGUF`) references a different runtime (omnivoice.cpp) that is not being used. Remove it to avoid confusion.

- [ ] **Step 1: Remove the omnivoice GGUF config block**

Delete this entire block from `configs/settings.yaml`:
```yaml
  omnivoice:
    repo: Serveurperso/OmniVoice-GGUF
    files:
      - omnivoice-base-Q8_0.gguf
      - omnivoice-tokenizer-Q8_0.gguf
    runtime: omnivoice.cpp
    quant: Q8_0
```

Keep the rest of the file intact (minicpm, tiny_aya, flux entries).

- [ ] **Step 2: Run smoke test**

Run: `python scripts/smoke_test.py`
Expected: Clean exit. The settings loader doesn't require an omnivoice entry since the Python package handles model loading internally.

- [ ] **Step 3: Commit**

```bash
git add configs/settings.yaml
git commit -m "docs: remove obsolete GGUF OmniVoice config — Python model loads from HF Hub"
```

---

### Task 5: Verify TTS card rendering with audio paths in cards.py

**Files:**
- Modify: `frontend/ui/cards.py` (minor)

The current `render_card_html()` renders a generic play button (`▶`) for audio but doesn't actually render an `<audio>` HTML element that plays the file. Update it to embed actual audio playback when an `audio_path` is available in the card data.

- [ ] **Step 1: Add audio element rendering**

In `render_card_html()`, update the audio HTML block from:
```python
    # Build audio button HTML (conditional, for front side)
    audio_html = ""
    if include_audio:
        audio_html = '<span class="media-btn" title="Play audio">▶</span>'
```
to:
```python
    # Build audio button HTML (conditional, for front side)
    audio_html = ""
    if include_audio:
        audio_path = card_data.get("audio_path")
        if audio_path and Path(audio_path).exists():
            audio_html = f'<audio controls preload="none" style="height:28px;"><source src="{audio_path}" type="audio/wav">Audio</audio>'
        else:
            audio_html = '<span class="media-btn" title="Generating audio...">▶</span>'
```

This adds an actual `<audio>` HTML element when the audio file exists, falling back to a placeholder button if the file is still being generated or missing.

- [ ] **Step 2: Add `Path` import**

Add `from pathlib import Path` at the top of `frontend/ui/cards.py` near the existing imports.

- [ ] **Step 3: Run smoke test**

Run: `python scripts/smoke_test.py`
Expected: Clean exit. The new code is backward-compatible — cards without audio_path render the same as before.

- [ ] **Step 4: Commit**

```bash
git add frontend/ui/cards.py
git commit -m "feat: render actual audio playback element in card HTML when audio_path available"
```

---

### Task 6: Final verification and integration test

**Files:**
- All modified files

- [ ] **Step 1: Run smoke test one final time**

Run: `python scripts/smoke_test.py`
Expected: Clean exit, no traceback.

- [ ] **Step 2: Verify the app launches without errors**

Run: `python app.py`
Expected: Gradio app starts on port 7860, no import errors, no runtime errors in console.

- [ ] **Step 3: Commit any remaining changes**

```bash
git add -A
git commit -m "test: final verification of OmniVoice TTS integration"
```

---

## Self-Review Checklist

1. **Spec coverage:** Every requirement from the design spec has a corresponding task:
   - TTSEngine voice design mode → Task 1
   - Pipeline TTS step with progress tracking → Task 2
   - App.py audio toggle wiring → Task 3
   - Settings cleanup → Task 4
   - Card HTML audio playback → Task 5
   - Final verification → Task 6

2. **Placeholder scan:** No "TBD", "TODO", "implement later", or vague instructions. Every step contains actual code, exact file paths, and specific commands.

3. **Type consistency:** All method signatures use the same parameter names across tasks (`language`, `include_audio`, `target_language`). The `AudioResult` type from `core/types.py` is used consistently. Path handling uses `pathlib.Path` throughout.

4. **Backward compatibility:** All new parameters have defaults:
   - `TTSEngine.synthesize(language=None)` — existing callers unchanged
   - `generate_phase2(target_language="Latvian", include_audio=False)` — existing callers unchanged
   - `generate_media_async(include_audio=False)` — existing callers unchanged

5. **No scope creep:** Image generation is explicitly out of scope (mentioned in spec, not touched). Voice cloning and per-card voice customization are out of scope. Only TTS for translated sentences is implemented.
