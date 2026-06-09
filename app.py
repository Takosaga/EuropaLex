#!/usr/bin/env python3
"""EuropaLex — Gradio Frontend Demo

Interactive flashcard generator UI with mock data.
No backend connection — visual preview only.

Run: uv sync && python app.py
"""

import gradio as gr
from frontend.ui.cards import render_card_html, generate_cards_html, generate_progress_html
from frontend.ui.widgets import create_toggle

# ─── Mock Card Data ────────────────────────────────────────────────

MOCK_CARDS = {
    "A0": [
        {"front": "Es esmu bērns.", "back": "I am a child."},
        {"front": "Šī ir māja.", "back": "This is a house."},
        {"front": "Es mīlu savu ģimeni.", "back": "I love my family."},
    ],
    "A1": [
        {"front": "Labrīt!", "back": "Good morning!"},
        {"front": "Paldies.", "back": "Thank you."},
        {"front": "Vai tu runā angļu valodu?", "back": "Do you speak English?"},
    ],
    "A2": [
        {"front": "Es strādāju skolā.", "back": "I work at a school."},
        {"front": "Kas ir laika grāmata?", "back": "What is a calendar?"},
        {"front": "Es eju uz veikalu.", "back": "I am going to the store."},
    ],
    "B1": [
        {"front": "Es gribētu izdzert kafiju.", "back": "I would like to drink coffee."},
        {"front": "Vai jūs varat man palīdzēt?", "back": "Can you help me?"},
        {"front": "Cik daudz maksā šis?", "back": "How much does this cost?"},
    ],
    "B2": [
        {"front": "Es uzskatu, ka tas ir pareizi.", "back": "I believe that is correct."},
        {"front": "Vai jūs varat izskaidrot iemeslu?", "back": "Can you explain the reason?"},
        {"front": "Šis projekts prasa vairāk laika.", "back": "This project requires more time."},
    ],
    "C1": [
        {"front": "Es nevaru atturēties no domas, ka...", "back": "I can't help but think that..."},
        {"front": "Tas ir acīmredzami, taču...", "back": "It is obvious, however..."},
        {"front": "Vai jūs dalāties manā viedoklī?", "back": "Do you share my opinion?"},
    ],
    "C2": [
        {"front": "Es apgūstu latviešu valodu ar lielu aizrautību.", "back": "I am mastering the Latvian language with great enthusiasm."},
        {"front": "Šis ir sarežģīts jautājums.", "back": "This is a complex question."},
        {"front": "Es saprotu katru vārdu.", "back": "I understand every word."},
    ],
}


def transform_mock_cards(raw_cards: list[dict]) -> list[dict]:
    """Transform legacy mock card format to two-phase format.

    Legacy format: {"front": <Latvian>, "back": <English>}
    New format:    {"text": <English>, "translation": <Latvian>}

    For text-only phase, 'text' is displayed with placeholder back.
    After media generation, 'translation' is populated.
    """
    return [{"text": c["back"], "translation": c["front"]} for c in raw_cards]


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
        """After text generation, enable toggles and Generate Cards button."""
        return gr.Checkbox(interactive=True), gr.Checkbox(interactive=True), gr.Button(interactive=True)

    def _reset_to_idle():
        """Reset UI to idle state when user changes parameters.

        Only resets toggle/button interactivity — keeps cards visible
        so the user can regenerate without losing their work.
        """
        return (
            gr.Checkbox(interactive=False),
            gr.Checkbox(interactive=False),
            gr.Button(interactive=False, variant="secondary"),
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

    # Reset toggles and phase-2 button when user changes any input parameter
    scenario_input.change(_reset_to_idle, inputs=[], outputs=[images_toggle, audio_toggle, generate_cards_btn])
    cefr_dropdown.change(_reset_to_idle, inputs=[], outputs=[images_toggle, audio_toggle, generate_cards_btn])
    batch_slider.change(_reset_to_idle, inputs=[], outputs=[images_toggle, audio_toggle, generate_cards_btn])


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
