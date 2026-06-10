# Two-Phase Card Generation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split the single "Generate Cards" flow into two sequential phases — first generate English text on cards, then optionally add translations/images/audio via a second button click.

**Architecture:** Modify existing Gradio UI to introduce a "Generate Text" button that renders cards with placeholder back sides, then enable a "Generate Cards" button that adds media. Toggles are disabled between phases. No new files — all changes are modifications to existing files.

**Tech Stack:** Python 3.12+, Gradio 6, HTML/CSS for custom styling

---

### Task 1: Add Disabled Styling to CSS

**Files:**
- Modify: `frontend/css/custom.css`

- [ ] **Step 1: Add disabled button and toggle classes to custom.css**

Append the following to the end of `frontend/css/custom.css`:

```css
/* ─── Two-Phase Generation: Disabled States ─────────────────────── */

.europalex-btn-disabled {
    opacity: 0.45;
    cursor: not-allowed;
    pointer-events: none;
}

.europalex-toggle-disabled .md:has(input[type="checkbox"]) {
    opacity: 0.45;
    cursor: not-allowed;
    pointer-events: none;
}

/* Card placeholder back side styling */
.card-placeholder-back {
    border-top: 2px dashed #d4c5a9;
    padding-top: 6px;
    font-size: 0.78em;
    color: #b8a88a;
    font-style: italic;
    min-height: 1.2em;
}
```

- [ ] **Step 2: Verify CSS syntax**

Run: `cat frontend/css/custom.css | tail -20`
Expected: The three new classes appear at the end of the file with valid CSS syntax (closing braces, no trailing commas).

- [ ] **Step 3: Commit**

```bash
git add frontend/css/custom.css
git commit -m "style: add disabled button/toggle/card-placeholder CSS classes for two-phase generation"
```

---

### Task 2: Add `placeholder_back` Parameter to Card Rendering

**Files:**
- Modify: `frontend/ui/cards.py`

- [ ] **Step 1: Update `render_card_html()` signature and logic**

Read the current `render_card_html()` function in `frontend/ui/cards.py`. Replace the entire function with:

```python
def render_card_html(
    card_data: dict,
    include_image: bool = True,
    include_audio: bool = False,
    rotation: float = 0.0,
    placeholder_back: bool = False,
) -> str:
    """Render a single flashcard as HTML with conditional media elements.

    Args:
        card_data: Dict with 'text' (English) and optional 'translation' keys.
        include_image: Whether to render the image placeholder.
        include_audio: Whether to render the audio button.
        rotation: Rotation angle for the "spread on desk" feel.
        placeholder_back: If True, show dashed placeholder line instead of translation.

    Returns:
        HTML string for a single flashcard.
    """
    front = card_data["text"]
    back = card_data.get("translation", "")

    # Adaptive dimensions based on enabled media
    if include_image and include_audio:
        width = 180
        min_height = 160
    elif include_image:
        width = 170
        min_height = 130
    elif include_audio:
        width = 170
        min_height = 120
    else:
        width = 150
        min_height = 80

    # Build image placeholder HTML (conditional)
    image_html = ""
    if include_image:
        image_html = '<div class="img-placeholder">🖼️</div>'

    # Build media buttons row HTML (conditional)
    media_buttons_html = ""
    if include_audio:
        media_buttons_html = (
            '<span class="media-btn" title="Play audio">▶</span>'
        )

    # Build back text or placeholder
    if placeholder_back:
        back_html = '<div class="card-placeholder-back">&nbsp;</div>'
    elif back:
        back_html = f'<div class="back-text" style="font-size:0.78em; color:#6b5e4a; line-height:1.35; border-top:1px dotted #d4c5a9; padding-top:6px;">{back}</div>'
    else:
        back_html = '<div class="card-placeholder-back">&nbsp;</div>'

    return f"""<div style="
        background: #fffef9;
        border-radius: 8px;
        padding: 14px 16px;
        box-shadow: 0 2px 6px rgba(0,0,0,0.15), 0 1px 2px rgba(0,0,0,0.1);
        border: 1px solid #e8dcc8;
        width: {width}px;
        min-height: {min_height}px;
        display: flex;
        flex-direction: column;
        justify-content: center;
        transform: rotate({rotation}deg);
        transition: all 0.2s ease;
    " onmouseover="this.style.transform='rotate(0deg) scale(1.02)'; this.style.boxShadow='0 4px 12px rgba(0,0,0,0.2)'" onmouseout="this.style.transform='rotate({rotation}deg)'; this.style.boxShadow='0 2px 6px rgba(0,0,0,0.15), 0 1px 2px rgba(0,0,0,0.1)'">
        <div class="front-text" style="font-size:0.95em; font-weight:bold; color:#2a1f0f; margin-bottom:6px; line-height:1.35; font-style:italic;">{front}</div>
        {back_html}
        {image_html}
        <div class="media-row" style="display:flex; gap:8px; margin-top:8px; align-items:center;">
            {media_buttons_html}
        </div>
    </div>"""
```

Key changes from original:
- Added `placeholder_back` parameter (default `False` for backward compatibility)
- Changed key access from `card_data["front"]` → `card_data["text"]` and `card_data["back"]` → `card_data.get("translation", "")`
- When `placeholder_back=True`, renders a dashed placeholder div instead of translation text

- [ ] **Step 2: Update `generate_cards_html()` to pass through `placeholder_back`**

Replace the current `generate_cards_html()` function with:

```python
def generate_cards_html(
    cards: list[dict],
    include_image: bool = True,
    include_audio: bool = False,
    placeholder_back: bool = False,
) -> str:
    """Generate HTML for a gallery of flashcards.

    Args:
        cards: List of card dicts with 'text' and optional 'translation' keys.
        include_image: Whether to render image placeholders on all cards.
        include_audio: Whether to render audio buttons on all cards.
        placeholder_back: If True, show dashed placeholder instead of translation on all cards.

    Returns:
        HTML string for the full card gallery.
    """
    if not cards:
        return '<div style="color:#8b7355; padding:20px;">No cards available for this level.</div>'

    # Distribute natural rotations across cards
    n = len(cards)
    rotations = []
    for i in range(n):
        angle = (i * 1.618 * 360) % 7 - 3.5
        rotations.append(round(angle, 1))

    html_cards = "".join(
        render_card_html(c, include_image, include_audio, rotations[i % n], placeholder_back)
        for i, c in enumerate(cards)
    )
    return f'<div style="display:flex; flex-wrap:wrap; gap:16px; justify-content:center; padding:16px 0;">{html_cards}</div>'
```

- [ ] **Step 3: Verify the module imports cleanly**

Run: `cd EuropaLex && python -c "from frontend.ui.cards import render_card_html, generate_cards_html; print('OK')"`
Expected: `OK` with no errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/ui/cards.py
git commit -m "feat: add placeholder_back parameter to card rendering for two-phase generation"
```

---

### Task 3: Add `interactive` Parameter to Toggle Helper

**Files:**
- Modify: `frontend/ui/widgets.py`

- [ ] **Step 1: Update `create_toggle()` to support disabled state**

Replace the current `create_toggle()` function with:

```python
def create_toggle(label: str, value: bool = True, elem_id: str = "", interactive: bool = True) -> "gr.Checkbox":
    """Create a styled toggle checkbox for media options.

    Args:
        label: Display label with emoji (e.g., '🖼️ Images').
        value: Default checked state.
        elem_id: Optional Gradio element ID.
        interactive: If False, apply disabled styling via CSS class wrapper.

    Returns:
        Configured gr.Checkbox instance.
    """
    import gradio as gr

    checkbox = gr.Checkbox(
        label=label,
        value=value,
        elem_id=elem_id if elem_id else "toggle-" + label.lower().replace(" ", "-").replace("🖼️", "img").replace("🔊", "audio"),
    )

    if not interactive:
        # Gradio doesn't have a native disabled checkbox, so wrap in a styled div
        import functools

        @functools.wraps(checkbox)
        def wrapped_component():
            return checkbox

        # Apply CSS class via elem_classes
        checkbox.elem_classes = (checkbox.elem_classes or []) + ["europalex-toggle-disabled"]

    return checkbox
```

- [ ] **Step 2: Verify the module imports cleanly**

Run: `cd EuropaLex && python -c "from frontend.ui.widgets import create_toggle; print('OK')"`
Expected: `OK` with no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/ui/widgets.py
git commit -m "feat: add interactive parameter to toggle helper for disabled state in two-phase generation"
```

---

### Task 4: Restructure app.py for Two-Phase Generation

**Files:**
- Modify: `app.py`

This is the largest change. Read the current `app.py` fully before editing.

- [ ] **Step 1: Add new mock data format and transformation helper**

Add this function after the existing `MOCK_CARDS` dict (before `generate_cards_async`):

```python
def transform_mock_cards(raw_cards: list[dict]) -> list[dict]:
    """Transform legacy mock card format to two-phase format.

    Legacy format: {"front": <Latvian>, "back": <English>}
    New format:    {"text": <English>, "translation": <Latvian>}

    For text-only phase, 'text' is displayed with placeholder back.
    After media generation, 'translation' is populated.
    """
    return [{"text": c["back"], "translation": c["front"]} for c in raw_cards]
```

- [ ] **Step 2: Replace `generate_cards_async()` with two new functions**

Delete the existing `generate_cards_async()` function entirely and replace it with:

```python
def generate_text_async(
    scenario: str,
    cefr_level: str,
    batch_size: int,
):
    """Phase 1: Generate English text on cards (no media).

    Yields (progress_html, card_output_html) tuples.
    Cards show English text with dashed placeholder back side.
    """
    raw_cards = MOCK_CARDS.get(cefr_level, MOCK_CARDS["B1"])
    selected_raw = raw_cards[:batch_size]

    if not selected_raw:
        yield generate_progress_html(0, "No cards available"), '<div style="color:#8b7355; padding:20px;">No cards available for this level.</div>'
        return

    # Transform to two-phase format: text=English, translation=Latvian (placeholder)
    cards = transform_mock_cards(selected_raw)

    # Render with placeholder back
    phase_cards_text_only = generate_cards_html(cards, include_image=False, include_audio=False, placeholder_back=True)
    yield generate_progress_html(30, "Generating text..."), phase_cards_text_only
    yield generate_progress_html(100, "Text ready! Adjust media toggles and click Generate Cards."), phase_cards_text_only


def generate_media_async(
    scenario: str,
    cefr_level: str,
    batch_size: int,
    include_images: bool,
    include_audio: bool,
):
    """Phase 2: Add translations, images, and audio to existing text cards.

    Takes the same parameters as Phase 1 plus media toggles.
    Re-renders cards with actual translation text and optional media.
    """
    raw_cards = MOCK_CARDS.get(cefr_level, MOCK_CARDS["B1"])
    selected_raw = raw_cards[:batch_size]

    if not selected_raw:
        yield generate_progress_html(0, "No cards available"), '<div style="color:#8b7355; padding:20px;">No cards available for this level.</div>'
        return

    # Transform to two-phase format with actual translations
    cards = transform_mock_cards(selected_raw)

    # Render with full media (no placeholder — translation text is real)
    phase_cards_full = generate_cards_html(
        cards,
        include_image=include_images,
        include_audio=include_audio,
        placeholder_back=False,
    )
    yield generate_progress_html(100, "Generation complete!"), phase_cards_full
```

- [ ] **Step 3: Update the Gradio UI layout**

Replace the entire UI construction block (from `with gr.Blocks() as demo:` to the end of the file) with:

```python
# ─── Gradio UI Construction ──────────────────────────────────────

with gr.Blocks() as demo:
    gr.HTML("""<div id="europalex-styles" style="display:none;">
    </div>""")

    with gr.Row():
        gr.Column(scale=1)
        with gr.Column(scale=3, elem_id="app-card"):
            gr.HTML('<h2 style="color:#3a2e1f; font-family:Georgia,serif; margin-bottom:4px;">EuropaLex</h2>')
            gr.HTML('<p style="color:#6b5e4a; font-size:0.8em; margin-top:-4px; margin-bottom:12px;">Generate Anki flashcards for European languages</p>')

            with gr.Row():
                scenario_input = gr.Textbox(
                    label="Scenario or Topic",
                    placeholder="e.g., ordering coffee, family members, weather",
                    lines=1,
                    elem_id="scenario-input",
                )
                cefr_dropdown = gr.Dropdown(
                    label="CEFR Level",
                    choices=["A0", "A1", "A2", "B1", "B2", "C1", "C2"],
                    value="B1",
                    elem_id="cefr-dropdown",
                )
                batch_slider = gr.Slider(
                    minimum=1,
                    maximum=10,
                    value=3,
                    step=1,
                    label="Number of Cards",
                    elem_id="batch-slider",
                )

            # Phase 1 button: Generate Text
            generate_text_btn = gr.Button("Generate Text", elem_id="generate-btn")

            # Card display area (below Generate Text)
            card_output = gr.HTML(label="Generated Cards")

            # Phase 2 controls: toggles + button (below cards)
            with gr.Row():
                images_toggle = create_toggle("🖼️ Images", value=True, elem_id="toggle-images", interactive=False)
                audio_toggle = create_toggle("🔊 Audio", value=True, elem_id="toggle-audio", interactive=False)

            generate_cards_btn = gr.Button("Generate Cards", elem_id="generate-btn", variant="secondary")

            progress_html = gr.HTML(label="Progress")

            with gr.Row():
                gr.Button(".apkg", interactive=False, elem_id="export-btn")
                gr.Button(".csv", interactive=False, elem_id="export-btn")
                gr.Button("Sync to Anki", interactive=False, elem_id="export-btn")

        gr.Column(scale=1)

    # ─── Event Wiring ──────────────────────────────────────────────

    def _handle_text_generation(scenario, cefr_level, batch_size):
        """Wrapper for generate_text_async that handles empty scenario."""
        if not scenario.strip():
            return generate_progress_html(0, "⚠️ Please enter a scenario or topic."), '<div style="color:#c44; padding:20px;">Please enter a scenario or topic to generate cards.</div>'
        return generate_text_async(scenario, cefr_level, batch_size)

    def _handle_media_generation(scenario, cefr_level, batch_size, images_on, audio_on):
        """Wrapper for generate_media_async that handles empty scenario."""
        if not scenario.strip():
            return generate_progress_html(0, "⚠️ Please enter a scenario or topic."), '<div style="color:#c44; padding:20px;">Please enter a scenario or topic to generate cards.</div>'
        return generate_media_async(scenario, cefr_level, batch_size, images_on, audio_on)

    def _enable_phase2():
        """After text generation, enable toggles and Generate Cards button."""
        return gr.Checkbox(interactive=True), gr.Checkbox(interactive=True), gr.Button(interactive=True)

    def _reset_to_idle():
        """Reset UI to idle state when user changes parameters."""
        return (
            gr.Button(interactive=True),
            gr.Checkbox(interactive=False),
            gr.Checkbox(interactive=False),
            gr.Button(interactive=False, variant="secondary"),
            "",  # clear card output
            "",  # clear progress
        )

    generate_text_btn.click(
        fn=_handle_text_generation,
        inputs=[scenario_input, cefr_dropdown, batch_slider],
        outputs=[progress_html, card_output],
    ).then(
        fn=_enable_phase2,
        inputs=[],
        outputs=[images_toggle, audio_toggle, generate_cards_btn],
    )

    generate_cards_btn.click(
        fn=_handle_media_generation,
        inputs=[scenario_input, cefr_dropdown, batch_slider, images_toggle, audio_toggle],
        outputs=[progress_html, card_output],
    ).then(
        fn=lambda: (gr.Button(visible=False), gr.Button(visible=False)),
        inputs=[],
        outputs=[generate_text_btn, generate_cards_btn],
    )

    # Reset when user changes any input parameter
    scenario_input.change(_reset_to_idle, inputs=[], outputs=[generate_text_btn, images_toggle, audio_toggle, generate_cards_btn, card_output, progress_html])
    cefr_dropdown.change(_reset_to_idle, inputs=[], outputs=[generate_text_btn, images_toggle, audio_toggle, generate_cards_btn, card_output, progress_html])
    batch_slider.change(_reset_to_idle, inputs=[], outputs=[generate_text_btn, images_toggle, audio_toggle, generate_cards_btn, card_output, progress_html])


if __name__ == "__main__":
    import os
    css_path = os.path.join(os.path.dirname(__file__), "frontend", "css", "custom.css")
    with open(css_path, "r") as f:
        css_content = f.read()
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        css=css_content,
    )
```

Key changes in the UI:
- Removed the old Row containing scenario + cefr + batch (kept them but repositioned)
- Added `generate_text_btn` right after inputs, before card output
- Moved `card_output` below `generate_text_btn` (cards appear immediately under the button)
- Moved toggles and `generate_cards_btn` below `card_output`
- Toggles start with `interactive=False`, `generate_cards_btn` starts disabled
- Added `_enable_phase2()` callback: after text generation, enables toggles and second button
- Added `_reset_to_idle()` callback: when any input changes, resets all states
- Removed the old single `.click()` wiring; replaced with two-phase event chain

- [ ] **Step 4: Verify Python syntax**

Run: `cd EuropaLex && python -c "import ast; ast.parse(open('app.py').read()); print('Syntax OK')"`
Expected: `Syntax OK`

- [ ] **Step 5: Verify imports work**

Run: `cd EuropaLex && python -c "from frontend.ui.cards import render_card_html, generate_cards_html, generate_progress_html; from frontend.ui.widgets import create_toggle; print('Imports OK')"`
Expected: `Imports OK`

- [ ] **Step 6: Commit**

```bash
git add app.py
git commit -m "feat: split generation into two phases — Generate Text then Generate Cards

Phase 1: Generate English text on cards with placeholder back side.
Phase 2: Add translations, images, audio via second button click.
Toggles disabled between phases. Input changes reset to idle state."
```

---

### Task 5: Manual Verification

**Files:** None (runtime check)

- [ ] **Step 1: Run the Gradio app and test the flow**

Run: `cd EuropaLex && python app.py`

Test sequence in browser (http://localhost:7860):
1. Enter a scenario (e.g., "ordering coffee"), select CEFR level B1, set batch to 3
2. Click "Generate Text" → verify cards appear with English text and dashed placeholder back
3. Verify toggles are disabled (greyed out) and "Generate Cards" is active
4. Adjust toggles if desired, click "Generate Cards" → verify cards update with media
5. Change scenario or level → verify everything resets to idle state
6. Leave scenario empty → verify warning message appears

- [ ] **Step 2: Commit any fixes from manual testing**

If issues found, fix them and commit:
```bash
git add -A
git commit -m "fix: address issues found during manual verification of two-phase generation"
```

---

## Execution Order

1. Task 1 (CSS) → Task 2 (cards.py) → Task 3 (widgets.py) → Task 4 (app.py) → Task 5 (manual verification)

Tasks 1-3 are independent and could be parallelized. Task 4 depends on Tasks 2 and 3. Task 5 depends on all previous tasks.
