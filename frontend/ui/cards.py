# EuropaLex Card Display Components
# Styled card widgets for front/back text + media

import math
import os
from pathlib import Path

# Project root directory — used to build Gradio-served URLs
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def _build_audio_url(audio_path: str) -> str:
    """Convert an absolute audio file path to a Gradio static-file URL.

    The Gradio app registers the project root via ``gr.set_static_paths()``
    (see ``app.py``). This function strips the project-root prefix so the resulting
    URL resolves correctly via Gradio's ``/gradio_api/file=`` route.

    Appends a cache-busting query parameter so regenerated audio files are not
    served from browser cache under the same filename.

    Args:
        audio_path: Absolute filesystem path to the .wav file.

    Returns:
        URL string like ``/gradio_api/file=.local/models/output/audio/audio_0.wav?t=1234567890``.
    """
    import time
    try:
        rel = Path(audio_path).relative_to(_PROJECT_ROOT)
    except ValueError:
        # Path is outside project root — fall back to absolute path
        return audio_path
    return f"/gradio_api/file={rel}?t={int(time.time())}".replace(os.sep, '/')


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
    # Normal mode: translation on front, English on back
    # Phase 1 (placeholder_back=True): English on front, placeholder on back
    if placeholder_back:
        front = card_data["text"]
        back = ""
    else:
        front = card_data.get("translation", "")
        back = card_data["text"]

    # Adaptive dimensions based on enabled media
    if include_image and include_audio:
        width = 190
        min_height = 350
    elif include_image:
        width = 180
        min_height = 310
    elif include_audio:
        width = 180
        min_height = 270
    else:
        width = 160
        min_height = 90

    # Build image box (conditional, for front side)
    image_box = ""
    if include_image:
        image_path = card_data.get("image_path")
        if image_path and Path(image_path).exists():
            try:
                rel = Path(image_path).relative_to(_PROJECT_ROOT)
                img_url = f"/gradio_api/file={rel}".replace(os.sep, '/')
                image_box = (
                    '<div class="media-box media-box-image">'
                    f'<img src="{img_url}" alt="Illustration" style="width:100%; border-radius:4px;">'
                    '</div>'
                )
            except ValueError:
                image_box = '<div class="media-box media-box-image">🖼️</div>'
        else:
            image_box = '<div class="media-box media-box-image img-placeholder">🖼️</div>'

    # Build audio box (conditional, for front side)
    audio_box = ""
    if include_audio:
        audio_path = card_data.get("audio_path")
        if audio_path and Path(audio_path).exists():
            audio_url = _build_audio_url(audio_path)
            audio_box = (
                '<div class="media-box media-box-audio">'
                f'<audio controls preload="none" style="width:100%; height:32px;">'
                f'<source src="{audio_url}" type="audio/wav">'
                '</audio></div>'
            )
        else:
            audio_box = '<div class="media-box media-box-audio"><span class="media-btn" title="Generating audio...">▶</span></div>'

    # Build front media boxes (only in normal mode — not Phase 1)
    if placeholder_back:
        front_media_boxes = ""
    else:
        parts = []
        if image_box:
            parts.append(image_box)
        if audio_box:
            parts.append(audio_box)
        front_media_boxes = '<div class="media-boxes-row">' + ''.join(parts) + '</div>'

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
        overflow: hidden;
    " onmouseover="this.style.transform='rotate(0deg) scale(1.02)'; this.style.boxShadow='0 4px 12px rgba(0,0,0,0.2)'" onmouseout="this.style.transform='rotate({rotation}deg)'; this.style.boxShadow='0 2px 6px rgba(0,0,0,0.15), 0 1px 2px rgba(0,0,0,0.1)'">
        <div class="front-text" style="font-size:0.95em; font-weight:bold; color:#2a1f0f; margin-bottom:6px; line-height:1.35; font-style:italic;">{front}</div>
        {front_media_boxes}
        {back_html}
    </div>"""


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


def generate_progress_html(percent: float, phase_label: str) -> str:
    """Generate HTML for the progress bar.

    Args:
        percent: Progress percentage (0–100).
        phase_label: Description of current phase (e.g., "Generating text...").

    Returns:
        HTML string for the progress indicator.
    """
    if percent <= 0:
        return ""

    # Color based on completion
    if percent >= 100:
        bar_color = "#7a5c3a"
        status_style = 'color:#2a6e2a; font-weight:bold;'
    elif percent > 60:
        bar_color = "#8a6c4a"
        status_style = 'color:#6b5e4a;'
    else:
        bar_color = "#a0845c"
        status_style = 'color:#6b5e4a;'

    return f"""<div style="margin-top:12px; padding:8px 12px;">
        <div style="
            width: 100%;
            height: 18px;
            background: #f0e8d6;
            border-radius: 9px;
            overflow: hidden;
            box-shadow: inset 0 1px 3px rgba(0,0,0,0.1);
        ">
            <div style="
                width: {percent}%;
                height: 100%;
                background: linear-gradient(135deg, {bar_color}, #6b4f2e);
                border-radius: 9px;
                transition: width 0.3s ease;
            "></div>
        </div>
        <div style="
            font-size: 0.8em;
            color: #6b5e4a;
            margin-top: 4px;
            text-align: center;
            {status_style}
        ">{phase_label}</div>
    </div>"""
