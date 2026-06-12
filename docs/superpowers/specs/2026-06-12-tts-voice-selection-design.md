# TTS Voice Selection — Design Spec

**Date:** 2026-06-12  
**Status:** Approved  
**Scope:** Add a voice selection dropdown to the TTS audio generation workflow in EuropaLex.

---

## Problem

`TTSEngine.synthesize()` currently hardcodes `instruct="female"` when calling OmniVoice's `model.generate()`. Users have no control over which voice is used for TTS audio generation. OmniVoice supports rich voice design via comma-separated speaker attributes in the `instruct` parameter, but this capability is not exposed to users.

## Goal

Provide a dropdown of 6 pre-built voice presets (3 age groups × 2 genders) that users can select when enabling TTS audio generation. The selected voice is passed through to OmniVoice's `instruct` parameter.

---

## Voice Presets

Six presets, ordered by gender first then age from oldest to youngest:

| # | Display Label | `instruct` Value |
|---|---|---|
| 1 | Female — Middle-Aged | `"female, middle-aged"` |
| 2 | Female — Young Adult | `"female, young adult"` |
| 3 | Female — Teenager | `"female, teenager"` |
| 4 | Male — Middle-Aged | `"male, middle-aged"` |
| 5 | Male — Young Adult | `"male, young adult"` |
| 6 | Male — Teenager | `"male, teenager"` |

**Default:** `"female, young adult"` (closest match to the current hardcoded `"female"`).

---

## UI Design

### Placement

The voice dropdown appears **under the Audio toggle**, only when the audio toggle is enabled (`value=True`). It is hidden (`visible=False`) otherwise.

```
[🖼️ Images]  (checkbox toggle)
[🔊 Audio]    (checkbox toggle)
├─ Voice: [▼ Female — Young Adult]  (dropdown, appears only when Audio is ON)
[Generate Cards]  (button)
```

### Visibility Logic

- **Audio OFF** → voice dropdown hidden (`visible=False`)
- **Audio ON** → voice dropdown visible (`visible=True`)
- **Input params change** (scenario, CEFR, batch size, language) → reset via `_reset_to_idle()` which hides the dropdown and resets audio toggle to OFF

### Event Wiring

When user toggles Audio ON/OFF:
1. If ON → show voice dropdown with default selection
2. If OFF → hide voice dropdown

The dropdown's `visible` state is part of the outputs returned by `_enable_phase2()` and `_reset_to_idle()`.

---

## Code Changes

### 1. `frontend/ui/widgets.py` — Add `create_voice_dropdown()`

New widget factory following the existing `create_toggle()` pattern:

```python
def create_voice_dropdown(default_voice: str = "female, young adult") -> "gr.Dropdown":
    """Create a voice selection dropdown for TTS audio generation.

    Args:
        default_voice: Default OmniVoice instruct string.

    Returns:
        Configured gr.Dropdown with 6 voice presets.
    """
```

The dropdown has `elem_id="voice-dropdown"` for CSS targeting in the phase state machine.

### 2. `app.py` — Wire Dropdown + Pass Voice to Pipeline

**Addition to Phase 2 controls area:**
- Create voice dropdown widget with `create_voice_dropdown()`
- Initial state: `visible=False` (hidden until Audio toggle is ON)

**Update `_enable_phase2()`:**
- Return the voice dropdown in its interactive/visible state when audio is enabled

**Update `_reset_to_idle()`:**
- Include voice dropdown in outputs — hide it and reset to default

**Update `generate_media_async()` signature:**
- Add `voice: str = "female, young adult"` parameter

**Update click handler wiring:**
- Pass `voice_dropdown` value as the `voice` argument to `generate_media_async()`

### 3. `core/engine.py` — Accept `instruct` Parameter in `TTSEngine.synthesize()`

Current code (hardcoded):
```python
audio_data = self._model.generate(
    text=text,
    instruct="female",  # <-- hardcoded
    language=language,
)
```

New code:
```python
audio_data = self._model.generate(
    text=text,
    instruct=instruct or "female, young adult",
    language=language,
)
```

The `synthesize()` method gains an optional `instruct: str | None = None` parameter. When `None`, defaults to `"female, young adult"`.

### 4. `app.py` — Pass Voice Through Pipeline

In `generate_media_async()`, the voice string is passed to `pool.get_tts_engine().synthesize()` via the new `instruct` parameter:

```python
audio_result = tts_engine.synthesize(
    translations_list, output_dir, language=target_language, instruct=voice,
)
```

---

## Data Flow

```
User toggles Audio ON  →  voice dropdown becomes visible
User selects voice      →  dropdown value captured in Gradio state
User clicks Generate Cards
  ↓
_handle_media_generation() receives voice_dropdown value
  ↓
generate_media_async(voice=selected_voice)
  ↓
TTSEngine.synthesize(instruct=selected_voice)
  ↓
OmniVoice.generate(text, instruct=selected_voice, language=...)
  ↓
Audio files generated with selected voice
```

---

## State Machine Integration

The voice dropdown participates in the two-phase state machine:

| Phase | Dropdown State |
|---|---|
| Idle (before text generation) | Hidden (`visible=False`) |
| After text generation, Audio ON | Visible, interactive, default selection |
| After text generation, Audio OFF | Hidden (`visible=False`) |
| Input params changed (reset) | Hidden (`visible=False`), audio toggle reset to OFF |

The dropdown's `elem_id="voice-dropdown"` is included in CSS selectors for disabled state management (though it's hidden rather than disabled when audio is off, keeping the CSS simpler).

---

## Error Handling

- **Invalid voice string:** OmniVoice auto-normalizes attributes case-insensitively. Invalid combinations are silently handled by the model (may ignore unknown attributes). No validation needed in EuropaLex.
- **TTS failure with selected voice:** Same as current behavior — card renders without audio, user can retry.

---

## Testing

- **Smoke test:** `python scripts/smoke_test.py` must pass after changes
- **Manual verification:** Start Gradio app → toggle Audio ON → verify dropdown appears with 6 options → select different voices → generate cards → listen to generated audio for voice differences
- **Reset verification:** Change scenario/CEFR/batch/language → verify dropdown hides and audio toggle resets

---

## Files Modified

| File | Lines Changed (est.) | Type |
|---|---|---|
| `core/engine.py` | ~5 | Core logic — add `instruct` param to `TTSEngine.synthesize()` |
| `frontend/ui/widgets.py` | ~12 | UI component — add `create_voice_dropdown()` |
| `app.py` | ~20 | Wiring — add dropdown widget, update handlers, pass voice through pipeline |

**Total:** ~37 lines changed across 3 files. No new files needed. No breaking changes — the `instruct` parameter is optional with a sensible default.
