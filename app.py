#!/usr/bin/env python3
"""EuropaLex — Gradio Frontend Demo

Interactive flashcard generator UI with mock data.
No backend connection — visual preview only.

Run: uv sync && python app.py
"""

import logging

import gradio as gr

logger = logging.getLogger(__name__)
from core.engine import EnginePool, MiniCPMTextEngine
from core.types import CEFRLevel, EngineConfig
from frontend.ui.cards import render_card_html, generate_cards_html, generate_progress_html
from frontend.ui.widgets import create_toggle


# ─── Phase State ────────────────────────────────────────────────────

_phase1_texts: list[str] = []  # English texts from Phase 1, passed to Phase 2


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
    """Phase 1: Generate English text only using Nemotron (no translation).

    Yields (progress_html, card_output_html) tuples.
    Cards show English text with dashed placeholder back side.
    Phase 2 (translation + media) is deferred — stays as mock data.
    """
    # Load config and get engine
    try:
        config = EngineConfig.from_settings_yaml()
        pool = EnginePool.get(config)
        engine = pool.get_english_engine()

        cefr = CEFRLevel(cefr_level)
    except FileNotFoundError as e:
        logger.error("Phase 1 model not found: %s", e)
        yield generate_progress_html(0, f"\u26a0\ufe0f Model file missing: {e}"), (
            '<div style="color:#c44; padding:20px;">'
            '<strong>Model file not found.</strong><br>'
            f'{e}<br><br>'
            'Run <code>python models/download_models.py minicpm</code> to download MiniCPM5-1B, '
            'or check <code>configs/settings.yaml</code> for the correct path.'
            '</div>'
        )
        return
    except Exception as e:
        logger.error("Phase 1 setup failed: %s", e, exc_info=True)
        yield generate_progress_html(0, f"\u26a0\ufe0f Setup error: {e}"), (
            '<div style="color:#c44; padding:20px;">'
            f'<strong>Failed to initialize engine.</strong><br>{e}<br><br>'
            'Check <code>configs/settings.yaml</code> and run the smoke test: '
            '<code>python scripts/smoke_test.py</code>'
            '</div>'
        )
        return

    # Generate English text via Nemotron
    try:
        yield generate_progress_html(20, "Preparing MiniCPM5-1B generation..."), ""
        texts = engine.generate(
            texts=[],  # empty = generation mode (not translation)
            scenario=scenario,
            cefr_level=cefr,
            batch_size=batch_size,
            topic_description=scenario,  # user's free-form topic description
        )
    except Exception as e:
        logger.error("Phase 1 generation failed: %s", e, exc_info=True)
        err_detail = str(e)
        yield generate_progress_html(0, f"\u26a0\ufe0f Generation failed"), (
            '<div style="color:#c44; padding:20px;">'
            f'<strong>MiniCPM5-1B generation failed.</strong><br>'
            f'{err_detail}<br><br>'
            'Possible causes:<br>'
            '• llama-cpp-python not installed — run: <code>uv pip install llama-cpp-python</code><br>'
            '• Model file corrupted or incompatible format<br>'
            '• Insufficient VRAM (~1.1 GB required)<br><br>'
            'Check the terminal for full error output.'
            '</div>'
        )
        return

    # Store Phase 1 texts for Phase 2 (module-level state)
    global _phase1_texts
    _phase1_texts = list(texts.generated_texts)

    # Convert TextResult to card dicts for rendering
    cards = [
        {"text": t, "translation": "", "cefr_level": cefr, "topic_description": scenario}
        for t in texts.generated_texts
    ]

    yield generate_progress_html(60, "Generating text..."), ""
    yield generate_progress_html(100, "Text ready! Adjust media toggles and click Generate Cards."), generate_cards_html(cards, include_image=False, include_audio=False, placeholder_back=True)


def _progress_pct(translated_idx: int, total: int) -> tuple[float, str]:
    """Calculate progress percentage and label for per-sentence translation.

    Args:
        translated_idx: Index of the sentence just completed (0-based).
        total: Total number of sentences to translate.

    Returns:
        (percentage, label) tuple.
    """
    if total <= 1:
        return 100.0, "Translation complete!"
    pct = ((translated_idx + 1) / total) * 100
    remaining = total - (translated_idx + 1)
    if pct >= 100:
        return 100.0, "Translation complete!"
    return round(pct, 1), f"Translated {translated_idx + 1}/{total} — {remaining} remaining..."


def generate_media_async(
    scenario: str,
    cefr_level: str,
    batch_size: int,
    target_language: str = "Latvian",
):
    """Phase 2: Translate Phase 1 English text to Latvian via tiny-aya.

    Reads the English texts from _phase1_texts (set by Phase 1 handler),
    translates each sentence one-by-one, and yields progressive card updates
    so cards appear incrementally as translations complete.
    Images and audio toggles are not yet active — media fields remain empty.
    """
    if not _phase1_texts:
        yield generate_progress_html(0, "⚠️ Please generate text first."), (
            '<div style="color:#c44; padding:20px;">'
            'No Phase 1 text found. Generate English text first, then click "Generate Cards".'
            '</div>'
        )
        return

    try:
        config = EngineConfig.from_settings_yaml()
        pool = EnginePool.get(config)
        cefr = CEFRLevel(cefr_level)
    except FileNotFoundError as e:
        logger.error("Phase 2 model not found: %s", e)
        yield generate_progress_html(0, f"\u26a0\ufe0f Model file missing: {e}"), (
            '<div style="color:#c44; padding:20px;">'
            '<strong>Model file not found.</strong><br>'
            f'{e}<br><br>'
            'Run <code>python models/download_models.py tiny_aya</code> to download tiny-aya-water, '
            'or check <code>configs/settings.yaml</code> for the correct path.'
            '</div>'
        )
        return
    except Exception as e:
        logger.error("Phase 2 setup failed: %s", e, exc_info=True)
        yield generate_progress_html(0, f"\u26a0\ufe0f Setup error: {e}"), (
            '<div style="color:#c44; padding:20px;">'
            f'<strong>Failed to initialize engine.</strong><br>{e}<br><br>'
            'Check <code>configs/settings.yaml</code> and run the smoke test: '
            '<code>python scripts/smoke_test.py</code>'
            '</div>'
        )
        return

    yield generate_progress_html(10, "Preparing translation engine..."), ""

    # Get the translation engine (lazy-loads tiny-aya)
    try:
        translation_engine = pool.get_translation_engine()
    except Exception as e:
        logger.error("Phase 2 failed to get translation engine: %s", e, exc_info=True)
        err_detail = str(e)
        yield generate_progress_html(0, f"\u26a0\ufe0f Engine error: {err_detail}"), (
            '<div style="color:#c44; padding:20px;">'
            f'<strong>Failed to initialize translation engine.</strong><br>'
            f'{err_detail}<br><br>'
            'Check <code>configs/settings.yaml</code> for the model path.'
            '</div>'
        )
        return

    # Build cards one-by-one — each sentence translated individually
    cards: list[dict] = []
    total = len(_phase1_texts)

    for i, english_text in enumerate(_phase1_texts):
        try:
            translation = translation_engine._translate_single(
                english_text, cefr,
                topic_description=scenario,
                target_language=target_language,
            )
        except Exception as e:
            logger.error("Translation failed for sentence %d: %s", i, e, exc_info=True)
            # Fallback: use English text as translation
            translation = english_text

        cards.append({
            "text": english_text,
            "translation": translation,
            "cefr_level": cefr,
            "topic_description": scenario,
        })

        pct, label = _progress_pct(i, total)
        yield generate_progress_html(pct, label), generate_cards_html(
            cards, include_image=False, include_audio=False, placeholder_back=False
        )

    # Final yield with 100%
    if not cards:
        yield generate_progress_html(0, "\u26a0\ufe0f No translations produced."), (
            '<div style="color:#c44; padding:20px;">'
            '<strong>Translation failed.</strong><br>No translations were produced. '
            'Check the terminal for error details.'
            '</div>'
        )
    else:
        yield generate_progress_html(100, "Translation complete!"), generate_cards_html(
            cards, include_image=False, include_audio=False, placeholder_back=False
        )


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
                language_dropdown = gr.Dropdown(
                    label="Target Language",
                    choices=["Latvian", "Spanish", "French", "German", "Polish", "Italian", "Portuguese", "Finnish"],
                    value="Latvian",
                    elem_id="language-dropdown",
                )

            # Phase 1 button: Generate Text
            generate_text_btn = gr.Button("Generate Text", elem_id="generate-btn")

            # Card display area (below Generate Text)
            card_output = gr.HTML(label="Generated Cards")

            # Phase 2 controls: toggles + button (below cards)
            with gr.Row():
                images_toggle = create_toggle("🖼️ Images", value=False, elem_id="toggle-images")
            audio_toggle = create_toggle("🔊 Audio", value=False, elem_id="toggle-audio")

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

    def _handle_media_generation(scenario, cefr_level, batch_size, target_language):
        """Wrapper for generate_media_async that handles empty scenario and missing Phase 1 texts."""
        if not scenario.strip():
            yield generate_progress_html(0, "⚠️ Please enter a scenario or topic."), '<div style="color:#c44; padding:20px;">Please enter a scenario or topic to generate cards.</div>'
            return
        for result in generate_media_async(scenario, cefr_level, batch_size, target_language):
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
        inputs=[scenario_input, cefr_dropdown, batch_slider, language_dropdown],
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
    language_dropdown.change(_reset_to_idle, inputs=[], outputs=[generate_text_btn, images_toggle, audio_toggle, generate_cards_btn, phase_css])


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
