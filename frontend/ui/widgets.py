# EuropaLex Frontend UI Components
# Custom styled Gradio widget wrappers + full UI layout builder


def create_toggle(label: str, value: bool = True, elem_id: str = "") -> "gr.Checkbox":
    """Create a styled toggle checkbox for media options.

    Args:
        label: Display label with emoji (e.g., '🖼️ Images').
        value: Default checked state.
        elem_id: Optional Gradio element ID.

    Returns:
        Configured gr.Checkbox instance.
    """
    import gradio as gr

    return gr.Checkbox(
        label=label,
        value=value,
        elem_id=elem_id if elem_id else "toggle-" + label.lower().replace(" ", "-").replace("🖼️", "img").replace("🔊", "audio"),
    )


def create_voice_dropdown(
    default_voice: str = "female, young adult",
) -> "gr.Dropdown":
    """Create a voice selection dropdown for TTS audio generation.

    Six presets mapped to OmniVoice instruct strings (gender × age).
    Ordered by gender first, then age from oldest to youngest.
    Visible by default; disabled via CSS until Audio toggle is ON.

    Args:
        default_voice: Default OmniVoice instruct string.

    Returns:
        Configured gr.Dropdown with 6 voice presets.
    """
    import gradio as gr

    choices = [
        "Female — Middle-Aged",
        "Female — Young Adult",
        "Female — Teenager",
        "Male — Middle-Aged",
        "Male — Young Adult",
        "Male — Teenager",
    ]

    return gr.Dropdown(
        label="Voice",
        choices=choices,
        value=default_voice,
        elem_id="voice-dropdown",
        allow_custom_value=True,
        visible=True,
    )


# ─── Voice Mapping ────────────────────────────────────────────────

# Mapping from voice dropdown display labels to OmniVoice instruct strings
_VOICE_MAP: dict[str, str] = {
    "Female — Middle-Aged": "female, middle-aged",
    "Female — Young Adult": "female, young adult",
    "Female — Teenager": "female, teenager",
    "Male — Middle-Aged": "male, middle-aged",
    "Male — Young Adult": "male, young adult",
    "Male — Teenager": "male, teenager",
}


# ─── UI State Helpers ─────────────────────────────────────────────

def _enable_phase2() -> tuple:
    """After text generation, enable toggles, dropdowns and Generate Cards button by removing disabled CSS.

    Both Audio and Images toggles default to ON after Phase 1. Voice dropdown becomes interactive — it becomes visible when audio toggle is turned ON (via audio_toggle.change).
    Explicitly sets value=True to prevent Gradio from resetting checkbox state on re-render.

    Returns:
        Tuple of (images_toggle, audio_toggle, generate_cards_btn, voice_dropdown, phase_css) updates.
    """
    import gradio as gr
    return (
        gr.Checkbox(interactive=True, value=True),
        gr.Checkbox(interactive=True, value=True),
        gr.Button(interactive=True),
        gr.Dropdown(interactive=True),
        "",
    )


def _reset_to_idle() -> tuple:
    """Reset UI to idle state when user changes parameters.

    Only resets toggle/button interactivity — keeps cards visible
    so the user can regenerate without losing their work.
    Also restores both buttons visibility (hidden by Phase 2).
    Re-applies disabled CSS to phase-2 controls.
    Keeps voice dropdown visible but disabled (it becomes interactive when audio is toggled ON after Phase 1).
    Explicitly sets value=False to prevent Gradio from resetting checkbox state on re-render.

    Returns:
        Tuple of (generate_text_btn, images_toggle, audio_toggle, generate_cards_btn, voice_dropdown, phase_css) updates.
    """
    import gradio as gr
    return (
        gr.Button(visible=True, interactive=True),
        gr.Checkbox(interactive=False, value=False),
        gr.Checkbox(interactive=False, value=False),
        gr.Button(visible=True, interactive=False, variant="secondary"),
        gr.Dropdown(visible=True, interactive=False),
        """<style id="phase-css">#toggle-images, #toggle-audio { opacity: 0.45; pointer-events: none; cursor: not-allowed; } #language-dropdown, #voice-dropdown { opacity: 0.45; pointer-events: none; cursor: not-allowed; } #generate-cards-btn { opacity: 0.45; pointer-events: none; cursor: not-allowed; }</style>""",
    )


def _enable_language_dropdown_on_audio(is_checked: bool) -> tuple:
    """Update CSS and voice dropdown interactivity when audio toggle changes.

    Voice dropdown is always visible — toggling audio ON makes it interactive,
    toggling OFF disables it (but keeps it visible).

    Args:
        is_checked: Whether the audio toggle is currently checked.

    Returns:
        Tuple of (voice_dropdown_update, phase_css_html) updates.
    """
    import gradio as gr
    if is_checked:
        # Audio ON: remove disabled CSS, make voice dropdown interactive
        return gr.Dropdown(interactive=True), ""
    else:
        # Audio OFF: apply disabled CSS to voice dropdown only (not generate button)
        return gr.Dropdown(interactive=False), """<style id="phase-css">#voice-dropdown { opacity: 0.45; pointer-events: none; cursor: not-allowed; }</style>"""


# ─── UI Layout Builder ───────────────────────────────────────────

def build_ui() -> "gr.Blocks":
    """Construct the entire Gradio Blocks layout and return it.

    This function replaces the inline `with gr.Blocks() as demo:` block in app.py.
    It creates all widgets, assembles the layout, wires event handlers, and returns
    the configured `demo` object ready for `.launch()`.

    IMPORTANT: Imports from app.py happen INSIDE this function (not at module level)
    to avoid circular imports. app.py does NOT import from widgets.py at module level
    (only inside __main__), so the import chain is safe:
      import widgets → build_ui() body runs → imports from app → app has no widget deps.

    _phase1_texts is accessed via the _app_module reference — shared mutable state between
    Phase 1 (generate_text_async sets it) and Phase 2 (_handle_media_generation_v2 reads it).
    We use module-level access (not `from app import _phase1_texts`) because rebinding
    `_phase1_texts = [...]` in app.py would not update a `from-import` binding.

    Returns:
        Configured gr.Blocks instance with all events wired.
    """
    import gradio as gr

    # Import business logic handlers INSIDE build_ui to avoid circular import
    from app import generate_text_async, generate_media_async
    import app as _app_module  # access _phase1_texts via module ref (rebinding in app.py won't break the reference)

    from frontend.ui.cards import generate_cards_html, generate_progress_html

    # ─── CSS Block ────────────────────────────────────────────────
    with gr.Blocks() as demo:
        gr.HTML("""<div id="europalex-styles" style="display:none;">
        </div>""")

        with gr.Row():
            gr.Column(scale=1)
            with gr.Column(scale=3, elem_id="app-card"):
                gr.HTML('<h2 style="color:#1a1a1a; font-family:sans-serif; margin-bottom:4px;">Europa Lex</h2>')
                gr.HTML('<p style="color:#666; font-size:0.8em; margin-top:-4px; margin-bottom:12px;">AI-powered flashcard generator — translate text into European languages, generate audio &amp; images, and export Anki decks</p>')

                with gr.Row():
                    scenario_input = gr.Textbox(
                        label="Scenario or Topic",
                        placeholder="e.g., ordering coffee, family members, weather",
                        lines=1,
                        elem_id="scenario-input",
                    )
                    cefr_dropdown = gr.Dropdown(
                        label="CEFR Level",
                        choices=["A0", "A1", "A2", "B1", "B2"],
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

                # Phase 2 controls: language, toggles + button (below cards)
                with gr.Row():
                    language_dropdown = gr.Dropdown(
                        label="Target Language",
                        choices=["Latvian", "Spanish", "French", "German", "Polish", "Italian", "Portuguese", "Finnish"],
                        value="Latvian",
                        elem_id="language-dropdown",
                    )
                with gr.Row():
                    audio_toggle = create_toggle("🔊 Audio", value=True, elem_id="toggle-audio")
                    images_toggle = create_toggle("🖼️ Images", value=True, elem_id="toggle-images")

                voice_dropdown = create_voice_dropdown()  # visible but disabled via CSS until Phase 2 + audio ON

                generate_cards_btn = gr.Button("Generate Cards", elem_id="generate-cards-btn", variant="secondary")

                # Dynamic CSS block — toggled to disable phase-2 controls until text generation completes
                phase_css = gr.HTML("""<style id="phase-css">#toggle-images, #toggle-audio { opacity: 0.45; pointer-events: none; cursor: not-allowed; } #language-dropdown, #voice-dropdown { opacity: 0.45; pointer-events: none; cursor: not-allowed; }</style>""")

                progress_html = gr.HTML(label="Progress")

                with gr.Row():
                    gr.Button(".apkg", interactive=False, elem_id="export-btn")
                    gr.Button(".csv", interactive=False, elem_id="export-btn")
                    gr.Button("Sync to Anki", interactive=False, elem_id="export-btn")

            gr.Column(scale=1)

        # ─── Event Wiring ──────────────────────────────────────────────

        def _handle_text_generation(scenario: str, cefr_level: str, batch_size: int):
            """Wrapper for generate_text_async that handles empty scenario."""
            if not scenario.strip():
                yield generate_progress_html(0, "⚠️ Please enter a scenario or topic."), '<div style="color:#c44; padding:20px;">Please enter a scenario or topic to generate cards.</div>'
                return
            for result in generate_text_async(scenario, cefr_level, batch_size):
                yield result

        def _handle_media_generation_v2(scenario: str, cefr_level: str, batch_size: int, target_language: str, include_audio: bool, include_images: bool, voice: str):
            """Wrapper for generate_media_async that handles empty scenario and missing Phase 1 texts.

            Reads _phase1_texts from app module (via module ref to survive rebinding).
            """
            if not _app_module._phase1_texts:
                yield generate_progress_html(0, "⚠️ Please generate text first."), (
                    '<div style="color:#c44; padding:20px;">'
                    'No Phase 1 text found. Generate English text first, then click "Generate Cards".'
                    '</div>'
                )
                return

            if not scenario.strip():
                yield generate_progress_html(0, "⚠️ Please enter a scenario or topic."), '<div style="color:#c44; padding:20px;">Please enter a scenario or topic to generate cards.</div>'
                return

            instruct = _VOICE_MAP.get(voice, voice)
            for result in generate_media_async(scenario, cefr_level, batch_size, target_language, include_audio, include_images, instruct):
                yield result

        def _on_media_generation_complete():
            """Hide both buttons during media generation."""
            import gradio as gr
            return (gr.Button(visible=False), gr.Button(visible=False))

        generate_text_btn.click(
            fn=_handle_text_generation,
            inputs=[scenario_input, cefr_dropdown, batch_slider],
            outputs=[progress_html, card_output],
        ).then(
            fn=_enable_phase2,
            inputs=[],
            outputs=[images_toggle, audio_toggle, generate_cards_btn, voice_dropdown, phase_css],
        )

        # When audio toggle changes: show/hide voice dropdown and manage disabled CSS
        def _on_audio_toggle_change(is_checked: bool):
            """Handle audio toggle change: update voice dropdown + CSS.

            Yields a single tuple (dropdown_update, css_html) so Gradio's
            generator handler sees one yield with 2 values matching the
            [voice_dropdown, phase_css] outputs.
            """
            yield _enable_language_dropdown_on_audio(is_checked)

        audio_toggle.change(
            fn=_on_audio_toggle_change,
            inputs=[audio_toggle],
            outputs=[voice_dropdown, phase_css],
        )

        generate_cards_btn.click(
            fn=_handle_media_generation_v2,
            inputs=[scenario_input, cefr_dropdown, batch_slider, language_dropdown, audio_toggle, images_toggle, voice_dropdown],
            outputs=[progress_html, card_output],
        ).then(
            fn=_on_media_generation_complete,
            inputs=[],
            outputs=[generate_text_btn, generate_cards_btn],
        )

        # Reset toggles and both buttons when user changes any input parameter
        scenario_input.change(_reset_to_idle, inputs=[], outputs=[generate_text_btn, images_toggle, audio_toggle, generate_cards_btn, voice_dropdown, phase_css])
        cefr_dropdown.change(_reset_to_idle, inputs=[], outputs=[generate_text_btn, images_toggle, audio_toggle, generate_cards_btn, phase_css])
        batch_slider.change(_reset_to_idle, inputs=[], outputs=[generate_text_btn, images_toggle, audio_toggle, generate_cards_btn, voice_dropdown, phase_css])
        # Language change does NOT reset — user can switch languages freely after Phase 1

    return demo
