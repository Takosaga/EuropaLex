#!/usr/bin/env python3
"""EuropaLex — Gradio Frontend Demo

Interactive flashcard generator UI with mock data.
No backend connection — visual preview only.

Run: uv sync && python app.py
"""

import gradio as gr

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


# ─── Card Rendering Helper ────────────────────────────────────────

def render_card_html(card_data: dict) -> str:
    """Render a single flashcard as HTML."""
    front = card_data["front"]
    back = card_data["back"]
    return f"""
    <div class="flashcard">
        <div class="front-text">{front}</div>
        <div class="back-text">{back}</div>
        <div class="img-placeholder">🖼️</div>
        <div class="media-row">
            <span class="media-btn" title="Audio (demo)">▶</span>
            <span class="media-btn" title="Image (demo)">🖼</span>
        </div>
    </div>
    """


def generate_cards(scenario: str, cefr_level: str, batch_size: int) -> str:
    """Generate flashcards from mock data based on user input."""
    cards = MOCK_CARDS.get(cefr_level, MOCK_CARDS["B1"])
    selected = cards[:batch_size]

    if not selected:
        return '<div style="color:#8b7355; padding:20px;">No cards available for this level.</div>'

    html_cards = "".join(render_card_html(c) for c in selected)
    return f'<div class="flashcard-gallery">{html_cards}</div>'


# ─── Gradio UI Construction ──────────────────────────────────────

CSS_PATH = "frontend/css/custom.css"

with gr.Blocks(css=CSS_PATH, theme=gr.themes.Default()) as demo:
    # Main container for frosted glass effect
    with gr.Column(elem_classes="main-app-container"):
        gr.HTML('<h2 style="color:#3a2e1f; font-family:Georgia,serif; margin-bottom:4px;">EuropaLex</h2>')
        gr.HTML('<p style="color:#6b5e4a; font-size:0.8em; margin-top:-4px; margin-bottom:12px;">Generate Anki flashcards for European languages</p>')

        # ── Input Panel ──
        with gr.Row(elem_classes="input-panel"):
            scenario_input = gr.Textbox(
                label="Scenario or Topic",
                placeholder="e.g., ordering coffee, family members, weather",
                lines=1,
            )
            cefr_dropdown = gr.Dropdown(
                label="CEFR Level",
                choices=["A0", "A1", "A2", "B1", "B2", "C1", "C2"],
                value="B1",
            )
            batch_slider = gr.Slider(
                minimum=1,
                maximum=10,
                value=3,
                step=1,
                label="Number of Cards",
            )

        generate_btn = gr.Button("Generate Cards", elem_classes="generate-btn")

        # ── Card Gallery (output) ──
        card_output = gr.HTML(label="Generated Cards")

        # ── Export Bar ──
        with gr.Row(elem_classes="export-bar"):
            gr.Button(".apkg", interactive=False, elem_classes="export-btn", variant="secondary")
            gr.Button(".csv", interactive=False, elem_classes="export-btn", variant="secondary")
            gr.Button("Sync to Anki", interactive=False, elem_classes="export-btn", variant="secondary")

    # ── Wire up Generate button ──
    generate_btn.click(
        fn=generate_cards,
        inputs=[scenario_input, cefr_dropdown, batch_slider],
        outputs=card_output,
    )


if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860)
