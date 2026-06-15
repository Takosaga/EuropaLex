# Regenerate Cards on Parameter Change Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore the Generate Cards button visibility and interactivity when any phase-2 parameter changes after Phase 2 completes, enabling users to regenerate cards with new settings without re-running Phase 1.

**Architecture:** Add a `_restore_generate_cards_button()` helper function and chain it as `.then()` handlers on four existing events (language change, audio toggle, image toggle, voice dropdown). Each chain restores the Generate Cards button after the primary handler completes.

**Tech Stack:** Python 3.12+, Gradio 6, Pydantic, pytest

---

### Task 1: Add `_restore_generate_cards_button()` helper function to `widgets.py`

**Files:**
- Modify: `frontend/ui/widgets.py` (after `_enable_language_dropdown_on_audio()`, before `build_ui()`)

- [ ] **Step 1: Write the helper function**

Add this function right after `_enable_language_dropdown_on_audio()` (around line 120, before the `# ─── UI Layout Builder ─────────────────────────────────────` comment):

```python
def _restore_generate_cards_button() -> tuple:
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

- [ ] **Step 2: Verify syntax is correct**

Run: `python -c "from frontend.ui.widgets import _restore_generate_cards_button; print('OK')"`
Expected: `OK` with no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/ui/widgets.py
git commit -m "feat: add _restore_generate_cards_button helper function"
```

---

### Task 2: Update language dropdown event chain to restore Generate Cards button

**Files:**
- Modify: `frontend/ui/widgets.py` (in `build_ui()`, around the language dropdown event wiring)

- [ ] **Step 1: Add the language dropdown event chain**

In `build_ui()`, find this existing code block:

```python
        # Reset toggles and both buttons when user changes any input parameter
        scenario_input.change(_reset_to_idle, inputs=[], outputs=[generate_text_btn, images_toggle, audio_toggle, generate_cards_btn, voice_dropdown, phase_css, export_btn, export_file])
        cefr_dropdown.change(_reset_to_idle, inputs=[], outputs=[generate_text_btn, images_toggle, audio_toggle, generate_cards_btn, voice_dropdown, phase_css, export_btn, export_file])
        batch_slider.change(_reset_to_idle, inputs=[], outputs=[generate_text_btn, images_toggle, audio_toggle, generate_cards_btn, voice_dropdown, phase_css, export_btn, export_file])
        # Language change does NOT reset — user can switch languages freely after Phase 1
```

Add a new event handler for `language_dropdown.change` right before the comment (or replace the comment with actual code):

```python
        # Reset toggles and both buttons when user changes any input parameter
        scenario_input.change(_reset_to_idle, inputs=[], outputs=[generate_text_btn, images_toggle, audio_toggle, generate_cards_btn, voice_dropdown, phase_css, export_btn, export_file])
        cefr_dropdown.change(_reset_to_idle, inputs=[], outputs=[generate_text_btn, images_toggle, audio_toggle, generate_cards_btn, voice_dropdown, phase_css, export_btn, export_file])
        batch_slider.change(_reset_to_idle, inputs=[], outputs=[generate_text_btn, images_toggle, audio_toggle, generate_cards_btn, voice_dropdown, phase_css, export_btn, export_file])

        # Language change — reset toggles but restore Generate Cards button for regeneration
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

- [ ] **Step 2: Verify syntax is correct**

Run: `python -c "from frontend.ui.widgets import build_ui; print('OK')"`
Expected: `OK` with no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/ui/widgets.py
git commit -m "feat: add language dropdown change event chain to restore Generate Cards button"
```

---

### Task 3: Update audio toggle event chain to restore Generate Cards button

**Files:**
- Modify: `frontend/ui/widgets.py` (in `build_ui()`, around the audio toggle event wiring)

- [ ] **Step 1: Add `.then()` to the audio toggle event chain**

In `build_ui()`, find this existing code:

```python
        audio_toggle.change(
            fn=_on_audio_toggle_change,
            inputs=[audio_toggle],
            outputs=[voice_dropdown, phase_css],
        )
```

Replace it with (only add `.then()` — do NOT add `generate_cards_btn`/`export_btn` to the `.change()` outputs since `_on_audio_toggle_change` yields only a 2-tuple):

```python
        audio_toggle.change(
            fn=_on_audio_toggle_change,
            inputs=[audio_toggle],
            outputs=[voice_dropdown, phase_css],
        ).then(
            fn=_restore_generate_cards_button,
            inputs=[],
            outputs=[generate_cards_btn, export_btn],
        )
```

- [ ] **Step 2: Verify syntax is correct**

Run: `python -c "from frontend.ui.widgets import build_ui; print('OK')"`
Expected: `OK` with no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/ui/widgets.py
git commit -m "feat: chain _restore_generate_cards_button on audio toggle change"
```

---

### Task 4: Add image toggle event wire to restore Generate Cards button

**Files:**
- Modify: `frontend/ui/widgets.py` (in `build_ui()`, after the audio toggle event wiring)

- [ ] **Step 1: Add new image toggle event chain**

Right after the audio toggle `.then()` block, add:

```python
# Image toggle change — restore Generate Cards button so user can regenerate with/without images
images_toggle.change(
    fn=lambda: (gr.Button(visible=True, interactive=True), gr.Button(visible=True, interactive=False)),
    inputs=[],
    outputs=[generate_cards_btn, export_btn],
)
```

- [ ] **Step 2: Verify syntax is correct**

Run: `python -c "from frontend.ui.widgets import build_ui; print('OK')"`
Expected: `OK` with no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/ui/widgets.py
git commit -m "feat: wire image toggle change to restore Generate Cards button"
```

---

### Task 5: Add voice dropdown event wire to restore Generate Cards button

**Files:**
- Modify: `frontend/ui/widgets.py` (in `build_ui()`, after the image toggle event wiring)

- [ ] **Step 1: Add new voice dropdown event chain**

Right after the image toggle block, add:

```python
# Voice dropdown change — restore Generate Cards button so user can regenerate with different voice
voice_dropdown.change(
    fn=lambda: (gr.Button(visible=True, interactive=True), gr.Button(visible=True, interactive=False)),
    inputs=[],
    outputs=[generate_cards_btn, export_btn],
)
```

- [ ] **Step 2: Verify syntax is correct**

Run: `python -c "from frontend.ui.widgets import build_ui; print('OK')"`
Expected: `OK` with no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/ui/widgets.py
git commit -m "feat: add voice dropdown change event chain to restore Generate Cards button"
```

---

### Task 6: Write tests for `_restore_generate_cards_button()`

**Files:**
- Modify: `tests/widgets_test.py`

- [ ] **Step 1: Add test for `_restore_generate_cards_button()`**

Add this test at the end of `tests/widgets_test.py`:

```python
def test_restore_generate_cards_button_returns_tuple(_mock_gradio):
    """_restore_generate_cards_button() returns tuple of (Button, Button)."""
    from frontend.ui.widgets import _restore_generate_cards_button

    result = _restore_generate_cards_button()
    assert isinstance(result, tuple)
    assert len(result) == 2


def test_restore_generate_cards_button_makes_button_visible_interactive(_mock_gradio):
    """Generate Cards button becomes visible and interactive."""
    from frontend.ui.widgets import _restore_generate_cards_button

    result = _restore_generate_cards_button()
    btn_update = result[0]
    assert isinstance(btn_update, MagicMock)
    call_kwargs = btn_update.call_args[1] if btn_update.call_args else {}
    # The mock gr.Button was called with visible=True, interactive=True
    assert call_kwargs.get("visible") is True
    assert call_kwargs.get("interactive") is True


def test_restore_generate_cards_button_export_stays_disabled(_mock_gradio):
    """Export button stays visible but disabled."""
    from frontend.ui.widgets import _restore_generate_cards_button

    result = _restore_generate_cards_button()
    export_update = result[1]
    assert isinstance(export_update, MagicMock)
    call_kwargs = export_update.call_args[1] if export_update.call_args else {}
    assert call_kwargs.get("visible") is True
    assert call_kwargs.get("interactive") is False
```

- [ ] **Step 2: Run the new tests to verify they pass**

Run: `uv run pytest tests/widgets_test.py::test_restore_generate_cards_button_returns_tuple tests/widgets_test.py::test_restore_generate_cards_button_makes_button_visible_interactive tests/widgets_test.py::test_restore_generate_cards_button_export_stays_disabled -v`
Expected: All 3 tests PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/widgets_test.py
git commit -m "test: add tests for _restore_generate_cards_button()"
```

---

### Task 7: Update existing test `test_reset_to_idle_returns_tuple`

**Files:**
- Modify: `tests/widgets_test.py`

- [ ] **Step 1: Verify `_reset_to_idle()` still returns 8 elements**

The function was not changed, so this is a verification step. Run:

```bash
uv run pytest tests/widgets_test.py::test_reset_to_idle_returns_tuple -v
```

Expected: PASS (still returns 8 elements). No code changes needed.

---

### Task 8: Update existing test `test_enable_phase2_returns_tuple`

**Files:**
- Modify: `tests/widgets_test.py`

- [ ] **Step 1: Verify `_enable_phase2()` still returns 6 elements**

The function was not changed, so this is a verification step. Run:

```bash
uv run pytest tests/widgets_test.py::test_enable_phase2_returns_tuple -v
```

Expected: PASS (still returns 6 elements). No code changes needed.

---

### Task 9: Update existing test `test_enable_language_dropdown_on_audio_true`

**Files:**
- Modify: `tests/widgets_test.py`

- [ ] **Step 1: Verify `_enable_language_dropdown_on_audio(True)` still returns 2 elements**

The function was not changed, so this is a verification step. Run:

```bash
uv run pytest tests/widgets_test.py::test_enable_language_dropdown_on_audio_true -v
```

Expected: PASS (still returns 2 elements). No code changes needed.

---

### Task 10: Run full test suite to verify no regressions

**Files:**
- All test files

- [ ] **Step 1: Run the full pytest suite**

Run: `uv run pytest tests/ -v`
Expected: All tests PASS.

- [ ] **Step 2: Run smoke test**

Run: `uv run pytest tests/smoke_test.py -v`
Expected: All smoke tests PASS (imports, Pydantic models, Gradio app construction).

- [ ] **Step 3: Commit any fixes if needed, or final commit**

```bash
git add .
git commit -m "test: verify full test suite passes after parameter change feature"
```

---

### Task 11: Manual verification — start the Gradio app and test interactively

**Files:**
- None (manual testing)

- [ ] **Step 1: Start the app**

Run: `python app.py`
Expected: App launches on port 7860 without errors.

- [ ] **Step 2: Test the flow manually**

1. Enter a scenario (or use mock data if models not available)
2. Complete Phase 1 text generation — verify both buttons hide
3. Change target language — verify Generate Cards button reappears
4. Toggle Audio ON/OFF — verify Generate Cards button reappears
5. Toggle Images ON/OFF — verify Generate Cards button reappears
6. Click Generate Cards — verify it regenerates with new settings

- [ ] **Step 3: Final commit if all tests pass**

```bash
git add .
git commit -m "docs: mark regenerate cards plan complete"
```

---

## Self-Review Checklist

1. **Spec coverage:** All four events covered (language, audio toggle, image toggle, voice dropdown). `_restore_generate_cards_button()` helper function defined and tested. ✅
2. **Placeholder scan:** No "TBD", "TODO", or vague instructions. Every step has exact code and commands. ✅
3. **Type consistency:** All Gradio button updates use `gr.Button(visible=True, interactive=True/False)`. Return types match output expectations. ✅
4. **Test coverage:** New tests cover the helper function's return value and button states. Existing tests verified as unchanged. ✅
