# Regenerate Cards on Parameter Change — Design Spec

**Date:** 2026-06-13
**Status:** Approved

## Problem

After Phase 2 (translation + media generation) completes, both the **Generate Text** and **Generate Cards** buttons are hidden by `_on_media_generation_complete()`. The user cannot regenerate cards with different parameters — changing language, toggles, or voice has no effect because the Generate Cards button is invisible.

The `_phase1_texts` global is preserved through Phase 2 (never cleared), so the English source text remains available. The `generate_media_async()` function already supports all needed parameters (language, audio, images, voice). The missing piece is UI event wiring to restore the Generate Cards button when any parameter changes.

## Solution Overview

Add chained `.then()` handlers to four events that affect Phase 2 output. Each chain restores the Generate Cards button's visibility and interactivity after the primary handler completes.

### Events to Wire

| # | Event | Primary Handler | New Chained Handler |
|---|---|---|---|
| 1 | Language dropdown `.change()` | `_reset_to_idle()` | `_restore_generate_cards_button()` |
| 2 | Audio toggle `.change()` | `_on_audio_toggle_change()` | `_restore_generate_cards_button()` |
| 3 | Image toggle `.change()` | *(none)* | `_restore_generate_cards_button()` |
| 4 | Voice dropdown `.change()` | *(none)* | `_restore_generate_cards_button()` |

### Output Changes

**`_reset_to_idle()` returns tuple:** Currently outputs 8 elements:
`(generate_text_btn, images_toggle, audio_toggle, generate_cards_btn, voice_dropdown, phase_css, export_btn, export_file)`

The `generate_cards_btn` is already set to `visible=True, interactive=False`. The chained handler will update it to `visible=True, interactive=True`.

**Current event chains:**
- Language change: `.change(_reset_to_idle, outputs=[...8 elements...])` — no `.then()`
- Audio toggle: `.change(fn=_on_audio_toggle_change, inputs=[audio_toggle], outputs=[voice_dropdown, phase_css])` — no `.then()`, does NOT include `generate_cards_btn`
- Image toggle: **not wired**
- Voice dropdown: **not wired**

### New Code in `widgets.py`

#### 1. New helper function `_restore_generate_cards_button()`

```python
def _restore_generate_cards_button():
    """After a parameter change, restore the Generate Cards button so user can regenerate media.

    Called as a chained .then() handler after primary event handlers.
    Unhides the button and makes it interactive. Export button stays disabled.

    Returns:
        Tuple of (generate_cards_btn, export_btn) Gradio updates.
    """
    import gradio as gr
    return (
        gr.Button(visible=True, interactive=True),   # generate_cards_btn
        gr.Button(visible=True, interactive=False),  # export_btn (disabled until Phase 2)
    )
```

#### 2. Updated event chains in `build_ui()`

**Language dropdown — add `.then()`:**
```python
language_dropdown.change(
    fn=_reset_to_idle,
    inputs=[],
    outputs=[generate_text_btn, images_toggle, audio_toggle, generate_cards_btn, voice_dropdown, phase_css, export_btn, export_file],
).then(
    fn=_restore_generate_cards_button,
    inputs=[],
    outputs=[generate_cards_btn, export_btn],
)
```

**Audio toggle — add `generate_cards_btn` and `export_btn` to outputs + `.then()`:**
```python
audio_toggle.change(
    fn=_on_audio_toggle_change,
    inputs=[audio_toggle],
    outputs=[voice_dropdown, phase_css, generate_cards_btn, export_btn],
).then(
    fn=_restore_generate_cards_button,
    inputs=[],
    outputs=[generate_cards_btn, export_btn],
)
```

**Image toggle — new event wire:**
```python
images_toggle.change(
    fn=lambda: (gr.Button(visible=True, interactive=True), gr.Button(visible=True, interactive=False)),
    inputs=[],
    outputs=[generate_cards_btn, export_btn],
)
```

**Voice dropdown — new event wire:**
```python
voice_dropdown.change(
    fn=lambda: (gr.Button(visible=True, interactive=True), gr.Button(visible=True, interactive=False)),
    inputs=[],
    outputs=[generate_cards_btn, export_btn],
)
```

### Files Changed

| File | Changes |
|---|---|
| `frontend/ui/widgets.py` | Add `_restore_generate_cards_button()` helper; update language dropdown event chain; update audio toggle event chain with new outputs and `.then()`; add image toggle event wire; add voice dropdown event wire. |
| `tests/widgets_test.py` | Add tests for `_restore_generate_cards_button()` function; update existing tests that reference audio toggle outputs to include new elements. |

### Behavior Summary

1. User completes Phase 2 → both buttons hidden, cards displayed with media.
2. User changes **any** phase-2 parameter (language, audio toggle, image toggle, voice) → Generate Cards button becomes visible and interactive. Export button stays disabled.
3. User clicks **Generate Cards** → `generate_media_async()` runs with the new parameters, using existing `_phase1_texts` as source.
4. After Phase 2 completes again → buttons hidden again (same as before).

### Edge Cases Handled

- **Changing language after Phase 2:** Language dropdown already calls `_reset_to_idle()` which keeps cards visible and resets toggles to OFF. The new `.then()` restores the Generate Cards button so user can regenerate with the new language.
- **Toggling audio ON/OFF:** Audio toggle change already updates voice dropdown interactivity and CSS. Adding Generate Cards button restoration lets user re-generate with or without audio.
- **Voice change while audio is OFF:** Voice dropdown is disabled when audio is OFF, so this event won't fire. No issue.
- **Rapid parameter changes:** Gradio queues events sequentially; each `.then()` waits for the previous handler to complete. No race conditions.

### Testing

- Unit test: `_restore_generate_cards_button()` returns correct tuple of `(gr.Button(visible=True, interactive=True), gr.Button(visible=True, interactive=False))`.
- Integration test: Simulate audio toggle change → verify Generate Cards button becomes visible and interactive.
- Existing widget tests that reference `_reset_to_idle()` or audio toggle outputs must be updated to match new output counts.
