# EuropaLex Frontend UI Components
# Custom styled Gradio widget wrappers + full UI layout builder

import logging
import warnings

# Suppress Starlette deprecation warnings from Gradio internals
warnings.filterwarnings("ignore", category=DeprecationWarning, module="starlette")


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
    Export buttons remain VISIBLE but DISABLED until Phase 2 completes (when _current_cards is populated).

    Returns:
        Tuple of (images_toggle, audio_toggle, generate_cards_btn, voice_dropdown,
                  export_csv_btn, export_apkg_btn, export_file, export_apkg_file, phase_css) updates.
    """
    import gradio as gr
    return (
        gr.Checkbox(interactive=True, value=True),     # images_toggle
        gr.Checkbox(interactive=True, value=True),     # audio_toggle
        gr.Button(interactive=True),                    # generate_cards_btn
        gr.Dropdown(interactive=True),                  # voice_dropdown
        gr.Button(visible=True, interactive=False),     # export_csv_btn (disabled until Phase 2)
        gr.Button(visible=True, interactive=False),     # export_apkg_btn (disabled until Phase 2)
        gr.File(value=None, visible=False),             # export_file
        gr.File(value=None, visible=False),             # export_apkg_file
        "",                                              # phase_css
    )


def _reset_to_idle() -> tuple:
    """Reset UI to idle state when user changes parameters.

    Only resets toggle/button interactivity — keeps cards visible
    so the user can regenerate without losing their work.
    Also restores both buttons visibility (hidden by Phase 2).
    Re-applies disabled CSS to phase-2 controls.
    Keeps voice dropdown visible but disabled (it becomes interactive when audio is toggled ON after Phase 1).
    Explicitly sets value=False to prevent Gradio from resetting checkbox state on re-render.
    Keeps export buttons visible but disabled until Phase 2 completes.

    Returns:
        Tuple of (generate_text_btn, images_toggle, audio_toggle, generate_cards_btn,
                  voice_dropdown, phase_css, export_csv_btn, export_apkg_btn, export_file, export_apkg_file) updates.
    """
    import gradio as gr
    return (
        gr.Button(visible=True, interactive=True),          # generate_text_btn
        gr.Checkbox(interactive=False, value=False),       # images_toggle
        gr.Checkbox(interactive=False, value=False),       # audio_toggle
        gr.Button(visible=True, interactive=False, variant="secondary"),  # generate_cards_btn
        gr.Dropdown(visible=True, interactive=False),      # voice_dropdown
        """<style id="phase-css">#toggle-images, #toggle-audio { opacity: 0.45; pointer-events: none; cursor: not-allowed; } #language-dropdown, #voice-dropdown { opacity: 0.45; pointer-events: none; cursor: not-allowed; } #generate-cards-btn { opacity: 0.45; pointer-events: none; cursor: not-allowed; }</style>""",  # phase_css
        gr.Button(visible=True, interactive=False),       # export_csv_btn (always visible, disabled until Phase 2)
        gr.Button(visible=True, interactive=False),       # export_apkg_btn (always visible, disabled until Phase 2)
        gr.File(value=None, visible=False),                 # export_file
        gr.File(value=None, visible=False),                 # export_apkg_file
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


def _restore_generate_cards_button() -> tuple:
    """After a parameter change, restore the Generate Cards button so user can regenerate media.

    Called as a chained .then() handler after primary event handlers.
    Unhides the button and makes it interactive. Export buttons stay disabled.

    Returns:
        Tuple of (generate_cards_btn, export_csv_btn, export_apkg_btn) Gradio updates.
    """
    import gradio as gr
    return (
        gr.Button(visible=True, interactive=True),   # generate_cards_btn
        gr.Button(visible=True, interactive=False),  # export_csv_btn (disabled until Phase 2)
        gr.Button(visible=True, interactive=False),  # export_apkg_btn (disabled until Phase 2)
    )


def _restore_generate_cards_button_only() -> tuple:
    """Restore only the Generate Cards button visibility without disabling toggles.

    Used for language changes after Phase 2 has completed. Unlike _reset_to_idle(),
    this does NOT re-apply disabled CSS to toggles — they remain fully interactive.
    Does NOT restore the Generate Text button (only appears on scenario/CEFR/batch reset).

    Returns:
        Tuple of (generate_text_btn, generate_cards_btn, export_csv_btn, export_apkg_btn) Gradio updates.
    """
    import gradio as gr
    return (
        gr.Button(visible=False),                    # generate_text_btn (stays hidden)
        gr.Button(visible=True, interactive=True),   # generate_cards_btn (restore)
        gr.Button(visible=True, interactive=False),  # export_csv_btn (disabled until Phase 2)
        gr.Button(visible=True, interactive=False),  # export_apkg_btn (disabled until Phase 2)
    )


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
    import sys

    # Import business logic handlers INSIDE build_ui to avoid circular import
    from app import generate_text_async, generate_media_async

    # Reference to the running script module — always __main__ on HF Spaces,
    # never `import app` (which would load a second copy and lose shared state)
    _app_module = sys.modules.get('app', sys.modules['__main__'])

    from frontend.ui.cards import generate_cards_html, generate_progress_html

    # ─── CSS Block ────────────────────────────────────────────────
    with gr.Blocks() as demo:
        with gr.Row():
            gr.Column(scale=1)
            with gr.Column(scale=3, elem_id="app-card"):
                gr.HTML('<h2 style="color:#1a1a1a; font-family:sans-serif; margin-bottom:4px;">Europa Lex</h2>')
                gr.HTML('<p style="color:#666; font-size:0.8em; margin-top:-4px; margin-bottom:12px;">AI-powered flashcard generator — translate text into European languages, generate audio &amp; images, and export as CSV</p>')

                with gr.Row():
                    scenario_input = gr.Textbox(
                        label="Scenario or Topic",
                        placeholder="e.g., ordering coffee, family members, weather",
                        lines=1,
                        elem_id="scenario-input",
                    )
                    cefr_dropdown = gr.Dropdown(
                        label="CEFR Level",
                        choices=["A1", "A2", "B1", "B2"],
                        value="A2",
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
                        choices=[
                            "Bulgarian", "Croatian", "Czech", "Danish", "Dutch", "Estonian",
                            "Finnish", "French", "German", "Greek", "Hungarian", "Irish",
                            "Italian", "Latvian", "Lithuanian", "Maltese", "Polish",
                            "Portuguese", "Romanian", "Slovak", "Slovenian", "Spanish", "Swedish",
                        ],
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

                # Export area: CSV button + File download, APKG button + File download
                with gr.Row():
                    export_csv_btn = gr.Button(
                        "📥 Export CSV + Media",
                        variant="primary",
                        visible=True,
                        interactive=False,
                        elem_id="export-btn",
                    )
                    export_apkg_btn = gr.Button(
                        "📥 Export Anki Cards",
                        variant="primary",
                        visible=True,
                        interactive=False,
                        elem_id="export-apkg-btn",
                    )
                export_file = gr.File(
                    label="Download CSV", file_types=[".zip"], visible=False
                )
                export_apkg_file = gr.File(
                    label="Download Anki Cards", file_types=[".apkg"], visible=False
                )

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
            """Wrapper for generate_media_async that handles empty scenario and missing Phase 1 texts."""
            import logging
            logger = logging.getLogger(__name__)
            
            phase1_count = len(_app_module._phase1_state['texts'])
            logger.info("Phase 2 start: _phase1_state has %d items", phase1_count)
            
            if not _app_module._phase1_state['texts']:
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
            """After Phase 2 completes: hide generate buttons, enable export buttons.

            Export buttons are always visible but become interactive only after
            Phase 2 completes (when _current_cards is populated).
            """
            import gradio as gr
            # Clear persisted phase1 state so Phase 2 can't accidentally re-read stale data
            from app import _clear_phase1_state
            _clear_phase1_state()
            return (
                gr.Button(visible=False),        # generate_text_btn
                gr.Button(visible=False),       # generate_cards_btn
                gr.Button(visible=True, interactive=True),  # export_csv_btn (enable)
                gr.File(value=None, visible=False),  # export_file (cleared)
                gr.Button(visible=True, interactive=True),  # export_apkg_btn (enable)
                gr.File(value=None, visible=False),  # export_apkg_file (cleared)
            )

        generate_text_btn.click(
            fn=_handle_text_generation,
            inputs=[scenario_input, cefr_dropdown, batch_slider],
            outputs=[progress_html, card_output],
        ).then(
            fn=_enable_phase2,
            inputs=[],
            outputs=[images_toggle, audio_toggle, generate_cards_btn, voice_dropdown, export_csv_btn, export_apkg_btn, export_file, export_apkg_file, phase_css],
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
        ).then(
            fn=_restore_generate_cards_button,
            inputs=[],
            outputs=[generate_cards_btn, export_csv_btn, export_apkg_btn],
        )

        generate_cards_btn.click(
            fn=_handle_media_generation_v2,
            inputs=[scenario_input, cefr_dropdown, batch_slider, language_dropdown, audio_toggle, images_toggle, voice_dropdown],
            outputs=[progress_html, card_output],
        ).then(
            fn=_on_media_generation_complete,
            inputs=[],
            outputs=[generate_text_btn, generate_cards_btn, export_csv_btn, export_file, export_apkg_btn, export_apkg_file],
        )

        # Reset toggles and both buttons when user changes any input parameter
        scenario_input.change(_reset_to_idle, inputs=[], outputs=[generate_text_btn, images_toggle, audio_toggle, generate_cards_btn, voice_dropdown, phase_css, export_csv_btn, export_apkg_btn, export_file, export_apkg_file])
        cefr_dropdown.change(_reset_to_idle, inputs=[], outputs=[generate_text_btn, images_toggle, audio_toggle, generate_cards_btn, voice_dropdown, phase_css, export_csv_btn, export_apkg_btn, export_file, export_apkg_file])
        batch_slider.change(_reset_to_idle, inputs=[], outputs=[generate_text_btn, images_toggle, audio_toggle, generate_cards_btn, voice_dropdown, phase_css, export_csv_btn, export_apkg_btn, export_file, export_apkg_file])
        # Language change — only restore Generate Cards button (toggles stay interactive)
        language_dropdown.change(
            fn=_restore_generate_cards_button_only,
            inputs=[],
            outputs=[generate_text_btn, generate_cards_btn, export_csv_btn, export_apkg_btn],
        )

        # Image toggle change — restore Generate Cards button so user can regenerate with/without images
        images_toggle.change(
            fn=lambda: (gr.Button(visible=True, interactive=True), gr.Button(visible=True, interactive=False)),
            inputs=[],
            outputs=[generate_cards_btn, export_csv_btn],
        )

        # Voice dropdown change — restore Generate Cards button so user can regenerate with different voice
        voice_dropdown.change(
            fn=lambda: (gr.Button(visible=True, interactive=True), gr.Button(visible=True, interactive=False), gr.Button(visible=True, interactive=False)),
            inputs=[],
            outputs=[generate_cards_btn, export_csv_btn, export_apkg_btn],
        )

        # ─── Export Event Wiring ──────────────────────────────────────

        def _handle_export_csv_event(scenario: str, cefr_level: str, target_language: str):
            """Export current cards as CSV + media zip.

            Sets the generated zip file path as the value of export_file component,
            which Gradio renders as a downloadable file link (bypassing DownloadButton's
            FileResponse Content-Length bug with h11).
            """
            from frontend.ui.cards import generate_progress_html

            if not _app_module._current_cards:
                return generate_progress_html(0, "\u26a0\ufe0f No cards to export."), None, gr.File(visible=False)

            try:
                zip_path = _app_module._handle_export_csv(scenario, cefr_level, target_language)
                if zip_path is None:
                    return generate_progress_html(0, "\u26a0\ufe0f Export failed."), None, gr.File(visible=False)
                # Show the file for download — gr.File component renders it as a clickable link
                return generate_progress_html(100, "Export complete! Click the file below to download."), zip_path, gr.File(visible=True)
            except Exception as e:
                logger = logging.getLogger(__name__)
                logger.error("CSV export failed: %s", e, exc_info=True)
                return generate_progress_html(0, f"\u26a0\ufe0f Export failed: {e}"), None, gr.File(visible=False)

        # Export button click — generates zip and shows it in gr.File for download
        export_csv_btn.click(
            fn=_handle_export_csv_event,
            inputs=[scenario_input, cefr_dropdown, language_dropdown],
            outputs=[progress_html, export_file, export_file],
        )

        # ─── Anki .apkg Export Event Wiring ─────────────────────────────

        def _handle_export_csv_for_anki_event(scenario: str, cefr_level: str, target_language: str):
            """Export current cards as an Anki-compatible .apkg file via genanki.

            Sets the generated .apkg file path as the value of export_apkg_file component,
            which Gradio renders as a downloadable file link.
            """
            from frontend.ui.cards import generate_progress_html

            if not _app_module._current_cards:
                return generate_progress_html(0, "\u26a0\ufe0f No cards to export."), None, gr.File(visible=False)

            try:
                zip_path = _app_module._handle_export_csv_for_anki(scenario, cefr_level, target_language)
                if zip_path is None:
                    return generate_progress_html(0, "\u26a0\ufe0f Export failed."), None, gr.File(visible=False)
                # Show the file for download — gr.File component renders it as a clickable link
                return generate_progress_html(100, "Export complete! Click the file below to download."), zip_path, gr.File(visible=True)
            except Exception as e:
                logger = logging.getLogger(__name__)
                logger.error("Anki .apkg export failed: %s", e, exc_info=True)
                return generate_progress_html(0, f"\u26a0\ufe0f Export failed: {e}"), None, gr.File(visible=False)

        # Anki .apkg Export button click — generates apkg and shows it in gr.File for download
        export_apkg_btn.click(
            fn=_handle_export_csv_for_anki_event,
            inputs=[scenario_input, cefr_dropdown, language_dropdown],
            outputs=[progress_html, export_apkg_file, export_apkg_file],
        )

    return demo
