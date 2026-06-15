# OmniVoice TTS Integration into Phase 2

**Date:** 2026-06-12
**Status:** Approved
**Project:** EuropaLex — AI-powered flashcard generator for European languages

## Problem Statement

Phase 2 of EuropaLex translates English text into target languages but does not generate audio. The `TTSEngine` class exists in `core/engine.py` and uses the correct model (`k2-fsa/OmniVoice`), but it is never called during Phase 2. The UI has an audio toggle that currently does nothing. Audio fields on all cards remain `None`.

## Goal

Wire OmniVoice text-to-speech into Phase 2 so that translated sentences are converted to speech audio and attached to flashcards. Users select a target language, toggle audio on, and get cards with both translation and generated TTS audio.

## Voice Design Specification

OmniVoice supports three voice modes:
1. **Voice clone** — requires reference audio (not used)
2. **Voice design** — uses an `instruct` text to describe the desired voice style (used)
3. **Auto** — model picks a voice randomly (current behavior, not desired)

The design will use **voice design mode** with the instruction `"female speaking"` to produce a consistent female voice across all generated audio. This eliminates the randomness of auto mode without requiring reference audio files.

## Architecture

### Current State

```
Phase 1: MiniCPM5-1B → English text cards (placeholder back)
     ↓
Phase 2: tiny-aya-water → Translation only → Cards with translation, no audio
```

TTSEngine exists but is dead code. The `settings.yaml` references an old GGUF variant (`Serveurperso/OmniVoice-GGUF`) that is not the model being used — the Python package auto-loads `k2-fsa/OmniVoice` from HuggingFace Hub.

### Target State

```
Phase 1: MiniCPM5-1B → English text cards (placeholder back)
     ↓
Phase 2: tiny-aya-water → Translations → OmniVoice → Audio → Cards with translation + audio
```

The pipeline becomes sequential: translate all sentences first, then generate TTS for the full batch in one call. This keeps the model loaded for efficiency rather than loading/unloading per-sentence.

## Data Flow

```
User input → app.py media handler → pipeline.generate_phase2()
  ├─ Step 1: Translate all sentences (tiny-aya engine)
  ├─ Step 2: TTS all translations (OmniVoice, "female speaking")
  └─ Step 3: Yield CardData objects with translation + audio_path
```

## File Changes

### 1. `core/engine.py` — TTSEngine.synthesize()

**Change:** Add voice design parameters to the `generate()` call.

Add an optional `language` parameter to the method signature:

```python
def synthesize(self, texts: list[str], output_dir: Path, language: str | None = None) -> AudioResult:
```

Update the inner `generate()` call:

```python
audio_data = self._model.generate(
    text=text,
    instruct="female speaking",
    language=language,
)
```

The `instruct` parameter puts OmniVoice into voice design mode. The `language` parameter is optional but improves synthesis quality when the target language is known (e.g., "Latvian", "Spanish").

### 2. `core/pipeline.py` — generate_phase2()

**Change:** Add TTS step after translation, new parameters for control.

New function signature:

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

**New flow:**

| Step | Progress | Label | Action |
|---|---|---|---|
| 1 | 20% | "Preparing translation..." | Load engines |
| 2 | 15–70% | "Translating... (N/total)" | Per-sentence translation loop |
| 3 | 70% | "Generating audio..." | Before TTS starts (if include_audio=True) |
| 4 | 95% | "Audio complete!" + cards | After TTS batch |
| 5 | 100% | "Translation and audio complete!" | Final yield |

If `include_audio=False`, steps 3–4 are skipped entirely — behavior matches current implementation.

TTS is called after the translation loop completes:

```python
if include_audio:
    yield 70, "Generating audio...", []
    tts_engine = pool.get_tts_engine()
    audio_result = tts_engine.synthesize(translations, output_dir, language=target_language)
    audio_paths = audio_result.audio_paths
```

CardData construction incorporates audio paths:

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

### 3. `app.py` — generate_media_async() and UI wiring

**Change:** Wire audio toggle into pipeline call and card rendering.

Update `generate_media_async()` to accept and pass the audio toggle:

```python
def generate_media_async(
    scenario, cefr_level, batch_size, target_language="Latvian", include_audio=False
):
```

Pass `include_audio` to `pipeline.generate_phase2()`.

Update card rendering calls to use actual toggle values instead of hardcoded `False`:

```python
# Before (hardcoded):
generate_cards_html(cards, include_image=False, include_audio=False, placeholder_back=False)

# After (from toggle state):
generate_cards_html(cards, include_image=False, include_audio=include_audio, placeholder_back=False)
```

Update the media generation button handler to read the audio toggle value and pass it through.

### 4. `configs/settings.yaml` — Clean up old OmniVoice config

**Change:** Remove the GGUF variant entry for OmniVoice.

Remove:
```yaml
omnivoice:
  repo: Serveurperso/OmniVoice-GGUF
  files:
    - omnivoice-base-Q8_0.gguf
    - omnivoice-tokenizer-Q8_0.gguf
  runtime: omnivoice.cpp
  quant: Q8_0
```

The Python model `k2-fsa/OmniVoice` is auto-loaded from HuggingFace Hub by the `omnivoice` package — no config entry needed.

## Audio Storage

Generated WAV files are saved to a temporary directory created at the start of Phase 2 media generation. Files are named sequentially (e.g., `audio_0.wav`, `audio_1.wav`). The temp directory is cleaned up when the Python process exits. This matches the existing pattern used by `TTSEngine.synthesize()` which accepts an `output_dir` parameter.

## Error Handling

- **TTS failure per sentence:** Individual failures are tracked as `None` in `AudioResult.audio_paths` (existing behavior). The card renders without audio for that sentence.
- **Complete TTS failure:** If all audio paths are `None`, the cards still display with translations — just no audio controls.
- **Model load failure:** EnginePool's mutual exclusion handles GPU memory conflicts. If OmniVoice fails to load, a clear error is logged and the UI shows an error message.

## Progress Tracking

Progress percentages are scaled to account for both translation and TTS:

- Translation: 15% → 70% (55% of total time)
- Audio generation: 70% → 95% (25% of total time)
- Final yield: 95% → 100% (5% for card assembly)

The audio progress label uses `"Generating audio..."` as a distinct phase indicator from translation.

## Testing

- Run `python scripts/smoke_test.py` — must pass with no tracebacks
- Verify audio toggle activates/deactivates TTS generation
- Verify voice design instruction produces consistent female voice output
- Verify cards render with audio controls when TTS succeeds

## Out of Scope

- Image generation integration (separate feature)
- Voice cloning from reference audio
- Per-card voice customization
- Audio quality tuning parameters (speed, duration, guidance scale)
- Anki export of audio files (future enhancement)
