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


# ─── Generation Logic ──────────────────────────────────────────────

def generate_cards_async(
    scenario: str,
    cefr_level: str,
    batch_size: int,
    include_images: bool,
    include_audio: bool,
):
    """Generate flashcards with streaming progress updates.

    Yields (progress_html, card_output_html) tuples at each phase:
        1. Text generation → cards shown without media
        2. Image generation → cards updated with image placeholders
        3. Audio generation → cards updated with audio buttons

    Skips phases whose media is toggled off.
    """
    cards = MOCK_CARDS.get(cefr_level, MOCK_CARDS["B1"])
    selected = cards[:batch_size]

    if not selected:
        yield generate_progress_html(0, "No cards available"), '<div style="color:#8b7355; padding:20px;">No cards available for this level.</div>'
        return

    # Phase 1: Text generation (always runs)
    phase_cards_text_only = generate_cards_html(selected, include_image=False, include_audio=False)
    yield generate_progress_html(30, "Generating text..."), phase_cards_text_only

    # Phase 2: Image generation (if enabled)
    if include_images:
        phase_cards_with_images = generate_cards_html(selected, include_image=True, include_audio=False)
        yield generate_progress_html(80, "Generating images..."), phase_cards_with_images

    # Phase 3: Audio generation (if enabled)
    if include_audio:
        phase_cards_full = generate_cards_html(selected, include_image=include_images, include_audio=True)
        yield generate_progress_html(100, "Generation complete!"), phase_cards_full
    elif not include_images:
        # Both toggled off — just mark done
        yield generate_progress_html(100, "Generation complete!"), phase_cards_text_only
    else:
        # Images on, audio off — final state is images-only cards
        yield generate_progress_html(100, "Generation complete!"), phase_cards_with_images


# ─── Gradio UI Construction ──────────────────────────────────────

with gr.Blocks() as demo:
    # Inject CSS via a <style> tag rendered in an HTML block.
    # Note: the style tag is inside an inline div so Gradio doesn't escape it.
    gr.HTML("""<div id="europalex-styles" style="display:none;">
        /* Wood grain background applied to body via inline style below */
    </div>""")

    with gr.Row():
        # Left side: empty spacer
        gr.Column(scale=1)
        # Center: main app card (frosted glass on wood grain)
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

            # Media toggles row
            with gr.Row():
                images_toggle = create_toggle("🖼️ Images", value=True, elem_id="toggle-images")
                audio_toggle = create_toggle("🔊 Audio", value=True, elem_id="toggle-audio")

            generate_btn = gr.Button("Generate Cards", elem_id="generate-btn")

            # Progress bar (hidden until generation starts)
            progress_html = gr.HTML(label="Progress")

            card_output = gr.HTML(label="Generated Cards")

            with gr.Row():
                gr.Button(".apkg", interactive=False, elem_id="export-btn")
                gr.Button(".csv", interactive=False, elem_id="export-btn")
                gr.Button("Sync to Anki", interactive=False, elem_id="export-btn")
        # Right side: empty spacer
        gr.Column(scale=1)

    generate_btn.click(
        fn=generate_cards_async,
        inputs=[scenario_input, cefr_dropdown, batch_slider, images_toggle, audio_toggle],
        outputs=[progress_html, card_output],
    )


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
