"""EuropaLex .apkg Generator — Creates Anki package files from card data.

Uses genanki for database structure and post-processes the generated zip
to inject media files (.wav, .png) with correct MD5-hashed filenames
and update the media JSON manifest.
"""

import hashlib
import html
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# ─── Model Definition ──────────────────────────────────────────────

MODEL_ID = 1607392319  # Hardcoded unique ID (30-bit unsigned int)
MODEL_NAME = "EuropaLex Flashcard"
FIELDS = [
    {"name": "Translation"},   # Front side: target language text
    {"name": "English"},       # Back side: English source text
    {"name": "Audio"},         # HTML audio tag for TTS
    {"name": "Image"},         # HTML img tag for illustration
]
TEMPLATE = {
    "name": "Card 1",
    "qfmt": "{{Translation}}\n{{Image}}\n{{Audio}}",   # front side
    "afmt": "{{FrontSide}}<hr id=answer>{{English}}",  # back side
}


def _create_model() -> "genanki.Model":
    """Create a genanki Model with EuropaLex field definitions.

    Returns:
        Configured genanki.Model instance.
    """
    import genanki
    return genanki.Model(
        model_id=MODEL_ID,
        name=MODEL_NAME,
        fields=FIELDS,
        templates=[TEMPLATE],
    )


def _extract_filename(path: str | None) -> str:
    """Extract bare filename from a path string, or return empty string.

    Args:
        path: File path string or None.

    Returns:
        Bare filename (e.g., 'hello_A2_LV_0.wav') or empty string.
    """
    if not path:
        return ""
    return Path(path).name


def _create_note(
    model: "genanki.Model",
    translation: str,
    english: str,
    audio_path: str | None = None,
    image_path: str | None = None,
) -> "genanki.Note":
    """Create a genanki Note with EuropaLex field mapping.

    Fields are HTML-escaped. Media references use original filenames
    (Anki resolves them to hashed files in the package).

    Args:
        model: The genanki.Model this note belongs to.
        translation: Target-language text (front side).
        english: English source text (back side).
        audio_path: Path to TTS .wav file or None.
        image_path: Path to illustration .png file or None.

    Returns:
        Configured genanki.Note instance.
    """
    import genanki

    # HTML-escape text fields
    translation_escaped = html.escape(translation) if translation else ""
    english_escaped = html.escape(english) if english else ""

    # Build audio field: <audio controls src="filename.wav"> or empty
    audio_filename = _extract_filename(audio_path)
    audio_field = (
        f'<audio controls src="{audio_filename}"></audio>'
        if audio_filename
        else ""
    )

    # Build image field: <img src="filename.png" style="max-width:100%"> or empty
    image_filename = _extract_filename(image_path)
    image_field = (
        f'<img src="{image_filename}" style="max-width:100%">'
        if image_filename
        else ""
    )

    return genanki.Note(
        model=model,
        fields=[translation_escaped, english_escaped, audio_field, image_field],
    )


def _create_package(*args, **kwargs):  # type: ignore[no-untyped-def]
    """Stub — replaced in Task 4."""
    raise NotImplementedError("_create_package not yet implemented")


def _inject_media(*args, **kwargs):  # type: ignore[no-untyped-def]
    """Stub — replaced in Task 5."""
    raise NotImplementedError("_inject_media not yet implemented")


def generate_apkg_package(*args, **kwargs):  # type: ignore[no-untyped-def]
    """Stub — replaced in Task 6."""
    raise NotImplementedError("generate_apkg_package not yet implemented")
