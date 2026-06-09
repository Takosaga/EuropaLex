#!/usr/bin/env python3
"""EuropaLex — Gradio Frontend Demo

Interactive flashcard generator UI with mock data.
No backend connection — visual preview only.

Run: uv sync && python app.py
"""

import gradio as gr
from pathlib import Path

from core.engine import EnginePool
from core.types import CEFRLevel, CardData
from frontend.ui.cards import render_card_html, generate_cards_html, generate_progress_html
from frontend.ui.widgets import create_toggle


def _get_pool():
    """Lazy-initialize the EnginePool singleton."""
    from core.types import EngineConfig
    config = EngineConfig.from_settings_yaml()
    return EnginePool.get(config)


def generate_text_async(
    scenario: str,
    cefr_level: str,
    batch_size: int,
):
    """Phase 1: Generate English text + translations using local models.

    Yields (progress_html, card_output_html) tuples.
    Cards show English text with dashed placeholder back side.
    """
    if not scenario.strip():
        yield generate_progress_html(0, "⚠️ Please enter a scenario or topic."), '<div style="color:#c44; padding:20px;">Please enter a scenario or topic to generate cards.</div>'
        return

    pool = _get_pool()
    cefr = CEFRLevel(cefr_level)

    # Step 1: Generate English sentences with Nemotron
    yield generate_progress_html(20, "Generating English text...")
    english_engine = pool.get_english_engine()
    english_result = english_engine.generate(
        texts=[], scenario=scenario, cefr_level=cefr, batch_size=batch_size
    )

    if not english_result.translations:
        yield generate_progress_html(0, "No text generated."), '<div style="color:#c44; padding:20px;">Model produced no output. Try a different scenario.</div>'
        return

    yield generate_progress_html(50, "Translating to target language...")

    # Step 2: Translate each sentence with TildeOpen
    cards: list[dict] = []
    translation_engine = pool.get_translation_engine()
    for eng_text in english_result.translations:
        trans_result = translation_engine.generate(
            texts=[eng_text], scenario="", cefr_level=cefr
        )
        if trans_result.translations:
            cards.append({
                "text": eng_text,
                "translation": trans_result.translations[0],
                "cefr_level": cefr,
            })

    if not cards:
        yield generate_progress_html(0, "No translations produced."), '<div style="color:#c44; padding:20px;">Model produced no translations.</div>'
        return

    # Render with placeholder back (Phase 1 state)
    phase_cards = generate_cards_html(cards, include_image=False, include_audio=False, placeholder_back=True)
    yield generate_progress_html(100, "Text ready! Adjust media toggles and click Generate Cards."), phase_cards


def generate_media_async(
    scenario: str,
    cefr_level: str,
    batch_size: int,
    include_images: bool,
    include_audio: bool,
):
    """Phase 2: Add audio and images to existing text cards.

    Re-generates text first (since we don't persist card state between phases in this version),
    then adds media.
    """
    if not scenario.strip():
        yield generate_progress_html(0, "⚠️ Please enter a scenario or topic."), '<div style="color:#c44; padding:20px;">Please enter a scenario or topic to generate cards.</div>'
        return

    pool = _get_pool()
    cefr = CEFRLevel(cefr_level)
    output_dir = Path(".local/media")

    # Re-generate text (same logic as Phase 1, but we'll add media)
    yield generate_progress_html(10, "Regenerating text with media...")
    english_engine = pool.get_english_engine()
    english_result = english_engine.generate(
        texts=[], scenario=scenario, cefr_level=cefr, batch_size=batch_size
    )

    if not english_result.translations:
        yield generate_progress_html(0, "No text generated."), '<div style="color:#c44; padding:20px;">Model produced no output.</div>'
        return

    translation_engine = pool.get_translation_engine()
    cards_data: list[CardData] = []
    for eng_text in english_result.translations:
        trans_result = translation_engine.generate(
            texts=[eng_text], scenario="", cefr_level=cefr
        )
        if trans_result.translations:
            cards_data.append(CardData(
                text=eng_text,
                translation=trans_result.translations[0],
                cefr_level=cefr,
            ))

    # Step 1: Generate audio if requested
    if include_audio and cards_data:
        yield generate_progress_html(40, "Generating audio...")
        tts_engine = pool.get_tts_engine()
        texts_to_synthesize = [c.text for c in cards_data]
        audio_result = tts_engine.synthesize(texts_to_synthesize, output_dir)
        for i, card in enumerate(cards_data):
            if i < len(audio_result.audio_paths):
                card.audio_path = audio_result.audio_paths[i]

    # Step 2: Generate images if requested
    if include_images and cards_data:
        yield generate_progress_html(70, "Generating images...")
        image_engine = pool.get_image_engine()
        prompts = [f"{c.translation}. Scene: {c.text}. Illustrative, educational style." for c in cards_data]
        image_result = image_engine.generate(prompts, output_dir)
        for i, card in enumerate(cards_data):
            if i < len(image_result.image_paths):
                card.image_path = image_result.image_paths[i]

    # Render with full media (no placeholder — translation is real)
    cards_html = generate_cards_html(
        [{"text": c.text, "translation": c.translation} for c in cards_data],
        include_image=include_images,
        include_audio=include_audio,
        placeholder_back=False,
    )
    yield generate_progress_html(100, "Generation complete!"), cards_html


# ─── Gradio UI Construction ──────────────────────────────────────

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
                images_toggle = create_toggle("🖼️ Images", value=True, elem_id="toggle-images")
                audio_toggle = create_toggle("🔊 Audio", value=True, elem_id="toggle-audio")

            generate_cards_btn = gr.Button("Generate Cards", elem_id="generate-cards-btn", variant="secondary")

            # Dynamic CSS block — toggled to disable phase-2 controls until text generation completes
            phase_css = gr.HTML(f"""<style id="phase-css">#toggle-images, #toggle-audio {{ opacity: 0.45; pointer-events: none; cursor: not-allowed; }} #generate-cards-btn {{ opacity: 0.45; pointer-events: none; cursor: not-allowed; }}</style>""")

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
            yield generate_progress_html(0, "⚠️ Please enter a scenario or topic."), '<div style="color:#c44; padding:20px;">Please enter a scenario or topic to generate cards.</div>'
            return
        for result in generate_text_async(scenario, cefr_level, batch_size):
            yield result

    def _handle_media_generation(scenario, cefr_level, batch_size, images_on, audio_on):
        """Wrapper for generate_media_async that handles empty scenario."""
        if not scenario.strip():
            yield generate_progress_html(0, "⚠️ Please enter a scenario or topic."), '<div style="color:#c44; padding:20px;">Please enter a scenario or topic to generate cards.</div>'
            return
        for result in generate_media_async(scenario, cefr_level, batch_size, images_on, audio_on):
            yield result

    def _enable_phase2():
        """After text generation, enable toggles and Generate Cards button by removing disabled CSS."""
        return gr.Checkbox(interactive=True), gr.Checkbox(interactive=True), gr.Button(interactive=True), ""

    def _reset_to_idle():
        """Reset UI to idle state when user changes parameters.

        Only resets toggle/button interactivity — keeps cards visible
        so the user can regenerate without losing their work.
        Also restores both buttons visibility (hidden by Phase 2).
        Re-applies disabled CSS to phase-2 controls.
        """
        return (
            gr.Button(visible=True, interactive=True),
            gr.Checkbox(interactive=False),
            gr.Checkbox(interactive=False),
            gr.Button(visible=True, interactive=False, variant="secondary"),
            """<style id="phase-css">#toggle-images, #toggle-audio { opacity: 0.45; pointer-events: none; cursor: not-allowed; } #generate-cards-btn { opacity: 0.45; pointer-events: none; cursor: not-allowed; }</style>""",
        )

    generate_text_btn.click(
        fn=_handle_text_generation,
        inputs=[scenario_input, cefr_dropdown, batch_slider],
        outputs=[progress_html, card_output],
    ).then(
        fn=_enable_phase2,
        inputs=[],
        outputs=[images_toggle, audio_toggle, generate_cards_btn, phase_css],
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

    # Reset toggles and both buttons when user changes any input parameter
    scenario_input.change(_reset_to_idle, inputs=[], outputs=[generate_text_btn, images_toggle, audio_toggle, generate_cards_btn, phase_css])
    cefr_dropdown.change(_reset_to_idle, inputs=[], outputs=[generate_text_btn, images_toggle, audio_toggle, generate_cards_btn, phase_css])
    batch_slider.change(_reset_to_idle, inputs=[], outputs=[generate_text_btn, images_toggle, audio_toggle, generate_cards_btn, phase_css])


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
