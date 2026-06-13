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


# ─── Stub implementations (replaced in subsequent tasks) ──────────


def _create_note(*args, **kwargs):  # type: ignore[no-untyped-def]
    """Stub — replaced in Task 3."""
    raise NotImplementedError("_create_note not yet implemented")


def _create_package(*args, **kwargs):  # type: ignore[no-untyped-def]
    """Stub — replaced in Task 4."""
    raise NotImplementedError("_create_package not yet implemented")


def _inject_media(*args, **kwargs):  # type: ignore[no-untyped-def]
    """Stub — replaced in Task 5."""
    raise NotImplementedError("_inject_media not yet implemented")


def generate_apkg_package(*args, **kwargs):  # type: ignore[no-untyped-def]
    """Stub — replaced in Task 6."""
    raise NotImplementedError("generate_apkg_package not yet implemented")
