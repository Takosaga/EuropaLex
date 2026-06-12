#!/usr/bin/env python3
"""EuropaLex — Gradio Frontend Demo

Interactive flashcard generator UI with mock data.
No backend connection — visual preview only.

Run: uv sync && python app.py
"""

import logging
import os
from pathlib import Path

import gradio as gr

logger = logging.getLogger(__name__)
from core.engine import EnginePool, MiniCPMTextEngine
from core.types import CEFRLevel, EngineConfig
from frontend.ui.cards import render_card_html, generate_cards_html, generate_progress_html
from frontend.ui.widgets import create_toggle, create_voice_dropdown


# ─── Phase State ────────────────────────────────────────────────────

_phase1_texts: list[str] = []  # English texts from Phase 1, passed to Phase 2

# Mapping from voice dropdown display labels to OmniVoice instruct strings
_VOICE_MAP: dict[str, str] = {
    "Female — Middle-Aged": "female, middle-aged",
    "Female — Young Adult": "female, young adult",
    "Female — Teenager": "female, teenager",
    "Male — Middle-Aged": "male, middle-aged",
    "Male — Young Adult": "male, young adult",
    "Male — Teenager": "male, teenager",
}


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


def _progress_pct(
    translated_idx: int,
    total: int,
    start_pct: float = 15.0,
    end_pct: float = 70.0,
) -> tuple[float, str]:
    """Calculate progress percentage for translation within a given range.

    Args:
        translated_idx: Index of the sentence just completed (0-based).
        total: Total number of sentences to translate.
        start_pct: Starting percentage for this phase (default 15% after preparation).
        end_pct: Ending percentage for this phase (default 70% before next phase).

    Returns:
        (percentage, label) tuple.
    """
    if total <= 1:
        return end_pct, "Translation complete!"
    pct = start_pct + ((translated_idx + 1) / total) * (end_pct - start_pct)
    remaining = total - (translated_idx + 1)
    if pct >= end_pct:
        return end_pct, "Translation complete!"
    return round(pct, 1), f"Translated {translated_idx + 1}/{total} — {remaining} remaining..."


def generate_media_async(
    scenario: str,
    cefr_level: str,
    batch_size: int,
    target_language: str = "Latvian",
    include_audio: bool = False,
    include_images: bool = False,
    voice: str = "female, young adult",
):
    """Phase 2: Translate Phase 1 English text and optionally generate TTS audio.

    Reads the English texts from _phase1_texts (set by Phase 1 handler),
    translates each sentence one-by-one via tiny-aya, optionally generates
    TTS audio for all translations via OmniVoice (voice design mode), and
    yields progressive card updates so cards appear incrementally.
    """
    global _phase1_texts

    if not _phase1_texts:
        yield generate_progress_html(0, "⚠️ Please generate text first."), (
            '<div style="color:#c44; padding:20px;">'
            'No Phase 1 text found. Generate English text first, then click "Generate Cards".'
            '</div>'
        )
        return

    # Save Phase 1 texts for this generation pass. Keep _phase1_texts intact so
    # the user can change language and regenerate media without re-generating text.
    _current_texts = list(_phase1_texts)

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

    for i, english_text in enumerate(_current_texts):
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

        pct, label = _progress_pct(i, total, start_pct=15.0, end_pct=70.0)
        yield generate_progress_html(pct, label), generate_cards_html(
            cards, include_image=include_images, include_audio=include_audio, placeholder_back=False
        )

    # Generate images for all translations if requested
    image_paths: list[str | None] = [None] * len(cards)
    tts_generated = False
    if include_images and cards:
        yield generate_progress_html(70, "Generating images..."), generate_cards_html(
            cards, include_image=True, include_audio=tts_generated, placeholder_back=False
        )
        try:
            img_engine = pool.get_image_engine()
            output_dir = Path(config.models_dir) / "output" / "images"
            # Build prompts from English text + CEFR level
            prompts = []
            for card in cards:
                prompt = (
                    f"Simple educational illustration for language learning: {card['text']}. "
                    f"Level: {cefr.value}. No text in image."
                )
                prompts.append(prompt)
            image_result = img_engine.generate(prompts, output_dir)
            image_paths = image_result.image_paths
            # Attach image paths to cards
            for i, path in enumerate(image_paths):
                if path is not None:
                    cards[i]["image_path"] = path
        except Exception as e:
            logger.error("Image generation failed: %s", e, exc_info=True)
            # Cards remain without images — user can retry

    # Generate TTS audio for all translations if requested
    # Note: always include generated media in final output regardless of toggle state,
    # so previously generated audio/images remain accessible after toggling off.
    if include_audio and cards:
        yield generate_progress_html(85, "Generating audio..."), generate_cards_html(
            cards, include_image=include_images, include_audio=True, placeholder_back=False
        )
        try:
            tts_engine = pool.get_tts_engine()
            output_dir = Path(config.models_dir) / "output" / "audio"
            translations_list = [c["translation"] for c in cards]
            audio_result = tts_engine.synthesize(translations_list, output_dir, language=target_language, instruct=voice)
            audio_paths = audio_result.audio_paths

            # Attach audio paths to cards
            for i, path in enumerate(audio_paths):
                if path is not None:
                    cards[i]["audio_path"] = path
            tts_generated = True
        except Exception as e:
            logger.error("TTS generation failed: %s", e, exc_info=True)
            # Cards remain without audio — user can retry
            tts_generated = False

    # Final yield with 100%
    if not cards:
        yield generate_progress_html(0, "\u26a0\ufe0f No translations produced."), (
            '<div style="color:#c44; padding:20px;">'
            '<strong>Translation failed.</strong><br>No translations were produced. '
            'Check the terminal for error details.'
            '</div>'
        )
    else:
        if include_images:
            if tts_generated:
                final_label = "Translation, images, and audio complete!"
            else:
                final_label = "Translation and images complete!"
        else:
            final_label = "Translation and audio complete!" if tts_generated else "Translation complete!"
        # Always include generated media regardless of toggle state so previously
        # generated audio/images remain accessible after toggling off/on.
        yield generate_progress_html(100, final_label), generate_cards_html(
            cards, include_image=include_images, include_audio=tts_generated, placeholder_back=False
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
            phase_css = gr.HTML(f"""<style id="phase-css">#toggle-images, #toggle-audio {{ opacity: 0.45; pointer-events: none; cursor: not-allowed; }} #language-dropdown, #voice-dropdown {{ opacity: 0.45; pointer-events: none; cursor: not-allowed; }}</style>""")

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

    def _enable_phase2():
        """After text generation, enable toggles, dropdowns and Generate Cards button by removing disabled CSS.

        Both Audio and Images toggles default to ON after Phase 1. Voice dropdown becomes interactive — it becomes visible when audio toggle is turned ON (via audio_toggle.change).
        Explicitly sets value=True to prevent Gradio from resetting checkbox state on re-render.
        """
        return (
            gr.Checkbox(interactive=True, value=True),
            gr.Checkbox(interactive=True, value=True),
            gr.Button(interactive=True),
            gr.Dropdown(interactive=True),
            "",
        )

    def _reset_to_idle():
        """Reset UI to idle state when user changes parameters.

        Only resets toggle/button interactivity — keeps cards visible
        so the user can regenerate without losing their work.
        Also restores both buttons visibility (hidden by Phase 2).
        Re-applies disabled CSS to phase-2 controls.
        Keeps voice dropdown visible but disabled (it becomes interactive when audio is toggled ON after Phase 1).
        Explicitly sets value=False to prevent Gradio from resetting checkbox state on re-render.
        """
        return (
            gr.Button(visible=True, interactive=True),
            gr.Checkbox(interactive=False, value=False),
            gr.Checkbox(interactive=False, value=False),
            gr.Button(visible=True, interactive=False, variant="secondary"),
            gr.Dropdown(visible=True, interactive=False),
            """<style id="phase-css">#toggle-images, #toggle-audio { opacity: 0.45; pointer-events: none; cursor: not-allowed; } #language-dropdown, #voice-dropdown { opacity: 0.45; pointer-events: none; cursor: not-allowed; } #generate-cards-btn { opacity: 0.45; pointer-events: none; cursor: not-allowed; }</style>""",
        )

    def _enable_language_dropdown_on_audio(is_checked):
        """Update CSS and voice dropdown interactivity when audio toggle changes.

        Voice dropdown is always visible — toggling audio ON makes it interactive,
        toggling OFF disables it (but keeps it visible).
        """
        if is_checked:
            # Audio ON: remove disabled CSS, make voice dropdown interactive
            return gr.Dropdown(interactive=True), ""
        else:
            # Audio OFF: apply disabled CSS to voice dropdown only (not generate button)
            return gr.Dropdown(interactive=False), """<style id="phase-css">#voice-dropdown { opacity: 0.45; pointer-events: none; cursor: not-allowed; }</style>"""

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
    def _handle_media_generation_v2(scenario, cefr_level, batch_size, target_language, include_audio, include_images, voice):
        """Wrapper for generate_media_async that handles empty scenario and missing Phase 1 texts."""
        if not scenario.strip():
            yield generate_progress_html(0, "⚠️ Please enter a scenario or topic."), '<div style="color:#c44; padding:20px;">Please enter a scenario or topic to generate cards.</div>'
            return
        instruct = _VOICE_MAP.get(voice, voice)
        for result in generate_media_async(scenario, cefr_level, batch_size, target_language, include_audio, include_images, instruct):
            yield result

    audio_toggle.change(
        fn=_enable_language_dropdown_on_audio,
        inputs=[audio_toggle],
        outputs=[voice_dropdown, phase_css],
    )

    generate_cards_btn.click(
        fn=_handle_media_generation_v2,
        inputs=[scenario_input, cefr_dropdown, batch_slider, language_dropdown, audio_toggle, images_toggle, voice_dropdown],
        outputs=[progress_html, card_output],
    ).then(
        fn=lambda: (gr.Button(visible=False), gr.Button(visible=False)),
        inputs=[],
        outputs=[generate_text_btn, generate_cards_btn],
    )

    # Reset toggles and both buttons when user changes any input parameter
    scenario_input.change(_reset_to_idle, inputs=[], outputs=[generate_text_btn, images_toggle, audio_toggle, generate_cards_btn, voice_dropdown, phase_css])
    cefr_dropdown.change(_reset_to_idle, inputs=[], outputs=[generate_text_btn, images_toggle, audio_toggle, generate_cards_btn, phase_css])
    batch_slider.change(_reset_to_idle, inputs=[], outputs=[generate_text_btn, images_toggle, audio_toggle, generate_cards_btn, voice_dropdown, phase_css])
    # Language change does NOT reset — user can switch languages freely after Phase 1


if __name__ == "__main__":
    import os
    css_path = os.path.join(os.path.dirname(__file__), "frontend", "css", "custom.css")
    with open(css_path, "r") as f:
        css_content = f.read()

    # Register the project root as a static directory so generated audio/images are accessible
    # inside gr.HTML output via /gradio_api/file=<relative-path> URLs.
    project_root = Path(__file__).resolve().parent
    gr.set_static_paths(paths=[project_root])

    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        css=css_content,
    )
