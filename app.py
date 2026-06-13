#!/usr/bin/env python3
"""EuropaLex — Gradio Frontend Demo

Interactive flashcard generator UI with mock data.
No backend connection — visual preview only.

Run: uv sync && python app.py
"""

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

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
        from core.engine import EnginePool, MiniCPMTextEngine
        from core.types import CEFRLevel, EngineConfig
        from frontend.ui.cards import generate_progress_html

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
            '<code>python tests/smoke_test.py</code>'
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
    from frontend.ui.cards import generate_cards_html

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
        from frontend.ui.cards import generate_progress_html
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
        from core.engine import EnginePool
        from core.types import CEFRLevel, EngineConfig
        from frontend.ui.cards import generate_progress_html, generate_cards_html

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
            '<code>python tests/smoke_test.py</code>'
            '</div>'
        )
        return

    yield generate_progress_html(10, "Preparing translation engine..."), ""

    # Get the translation engine (lazy-loads tiny-aya)
    try:
        from core.engine import LlamaCppTextEngine
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

    # Generate TTS audio for all translations if requested
    image_paths: list[str | None] = [None] * len(cards)
    tts_generated = False
    if include_audio and cards:
        yield generate_progress_html(70, "Generating audio..."), generate_cards_html(
            cards, include_image=include_images, include_audio=True, placeholder_back=False
        )
        try:
            from core.audio_gen import TTSEngine
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

    # Generate images for all translations if requested
    if include_images and cards:
        yield generate_progress_html(85, "Generating images..."), generate_cards_html(
            cards, include_image=True, include_audio=tts_generated, placeholder_back=False
        )
        try:
            from core.image_gen import ImageGenEngine
            img_engine = pool.get_image_engine()
            output_dir = Path(config.models_dir) / "output" / "images"
            # Build prompts from English text + CEFR level
            prompts = []
            for card in cards:
                prompt = (
                    f"Simple educational illustration with NO TEXT for language learning for the following text: {card['text']}. "
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
                final_label = "Translation, audio, and images complete!"
            else:
                final_label = "Translation and images complete!"
        else:
            final_label = "Translation and audio complete!" if tts_generated else "Translation complete!"
        # Always include generated media regardless of toggle state so previously
        # generated audio/images remain accessible after toggling off/on.
        yield generate_progress_html(100, final_label), generate_cards_html(
            cards, include_image=include_images, include_audio=tts_generated, placeholder_back=False
        )


if __name__ == "__main__":
    from frontend.ui.widgets import build_ui

    css_path = os.path.join(os.path.dirname(__file__), "frontend", "css", "custom.css")
    with open(css_path, "r") as f:
        css_content = f.read()

    # Register the project root as a static directory so generated audio/images are accessible
    # inside gr.HTML output via /gradio_api/file=<relative-path> URLs.
    project_root = Path(__file__).resolve().parent
    import gradio as gr
    gr.set_static_paths(paths=[project_root])

    app = build_ui()
    app.launch(
        server_name="0.0.0.0",
        server_port=7860,
        css=css_content,
    )
