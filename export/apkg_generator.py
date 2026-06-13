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


def _sanitize_folder_name(scenario: str) -> str:
    """Convert scenario text to a filesystem-safe folder name slug.

    Lowercase, remove special characters (keep alphanumeric, spaces, underscores),
    replace spaces with underscores, collapse multiple spaces, strip leading/trailing underscores.

    Args:
        scenario: Free-form scenario string.

    Returns:
        Slug suitable for use as a folder or deck name.
    """
    import re
    slug = scenario.lower()
    slug = re.sub(r'[^a-z0-9_ ]', '', slug)
    slug = re.sub(r'\s+', '_', slug)
    slug = slug.strip('_')
    return slug


def _get_language_abbrev(language: str) -> str:
    """Return the ISO 639-1 abbreviation for a language name.

    Args:
        language: Language name (e.g., 'Latvian', 'Spanish').

    Returns:
        Two-letter ISO 639-1 code.

    Raises:
        ValueError: If the language is not in the supported mapping.
    """
    _LANGUAGE_ABBREVS = {
        "Latvian": "LV",
        "Spanish": "ES",
        "French": "FR",
        "German": "DE",
        "Polish": "PL",
        "Italian": "IT",
        "Portuguese": "PT",
        "Finnish": "FI",
    }
    if language not in _LANGUAGE_ABBREVS:
        raise ValueError(
            f"Unknown language '{language}'. "
            f"Supported: {', '.join(sorted(_LANGUAGE_ABBREVS.keys()))}"
        )
    return _LANGUAGE_ABBREVS[language]


def _create_package(
    notes: list["genanki.Note"],
    scenario: str,
    cefr_level: str,
    target_language: str,
) -> str:
    """Create a genanki Package (.apkg) from notes and return its path.

    Args:
        notes: List of genanki.Note instances.
        scenario: Free-form scenario/topic string (used in deck name).
        cefr_level: CEFR level string (e.g., 'A2', 'B1').
        target_language: Target language name (e.g., 'Latvian').

    Returns:
        Absolute path to the generated .apkg file.
    """
    import genanki
    import tempfile
    import uuid

    # Build deck name using same convention as CSV export
    scenario_slug = _sanitize_folder_name(scenario)
    lang_abbrev = _get_language_abbrev(target_language)
    deck_name = f"{scenario_slug}_{cefr_level}_{lang_abbrev}"

    deck = genanki.Deck(
        deck_id=int(uuid.uuid4().hex[:8], 16),
        name=deck_name,
    )

    for note in notes:
        deck.add_note(note)

    # Write to temp dir — caller decides where to save
    with tempfile.NamedTemporaryFile(suffix='.apkg', delete=False) as f:
        pkg = genanki.Package(deck)
        pkg.write_to_file(f.name)
        return f.name


def _inject_media(
    apkg_path: str,
    cards: list[dict],
) -> None:
    """Inject media files (.wav, .png) into an existing .apkg zip.

    For each unique audio/image path in cards:
      1. Compute MD5 hash of file content (Anki's media naming convention)
      2. Write the file into the zip under the hashed name
      3. Update the media JSON manifest: {hash.ext} → {original_filename.ext}

    Deduplicates by content hash — same file injected only once.
    Skips files that don't exist on disk (logged as warning).

    Args:
        apkg_path: Path to the .apkg zip file generated by genanki.
        cards: List of card dicts with 'audio_path' and 'image_path' keys.
    """
    import zipfile

    # Collect unique media files to inject (dedup by absolute path)
    seen_paths = set()
    media_files = []  # list of (source_path, original_filename, ext)

    for card in cards:
        for path_key in ('audio_path', 'image_path'):
            src = card.get(path_key)
            if not src or not Path(src).exists():
                continue
            abs_src = str(Path(src).resolve())
            if abs_src in seen_paths:
                continue
            seen_paths.add(abs_src)

            ext = Path(src).suffix.lower()
            if ext not in ('.wav', '.png'):
                logger.warning("Skipping unsupported media type: %s", src)
                continue

            original_filename = Path(src).name
            media_files.append((abs_src, original_filename, ext))

    # Read existing media manifest
    with zipfile.ZipFile(apkg_path, 'r') as zin:
        media_json = json.loads(zin.read('media'))

    # Inject each unique file
    for src_path, original_filename, ext in media_files:
        content = Path(src_path).read_bytes()
        media_hash = hashlib.md5(content, usedforsecurity=False).hexdigest()
        zip_entry = f"{media_hash}{ext}"

        # Skip if already injected (same content hash)
        if zip_entry in media_json:
            continue

        # Write into zip with hashed name
        with zipfile.ZipFile(apkg_path, 'a') as zout:
            zout.writestr(zip_entry, content)

        # Update manifest: hash → original filename (already includes extension)
        media_json[zip_entry] = original_filename

    # Write updated media manifest back
    with zipfile.ZipFile(apkg_path, 'a') as zout:
        zout.writestr('media', json.dumps(media_json))


def generate_apkg_package(
    cards: list[dict],
    scenario: str,
    cefr_level: str,
    target_language: str,
) -> str:
    """Generate an Anki package (.apkg) with embedded media.

    Creates a genanki note model, builds notes from card data, generates the
    base .apkg zip, then injects audio/image files with correct hashed names
    and updates the media manifest.

    Args:
        cards: List of card dicts with keys: 'text', 'translation',
               'audio_path' (str or None), 'image_path' (str or None).
        scenario: Free-form scenario/topic string.
        cefr_level: CEFR level string (e.g., 'A2', 'B1').
        target_language: Target language name (e.g., 'Latvian').

    Returns:
        Absolute path to the generated .apkg file.

    Raises:
        ValueError: If no cards provided.
        RuntimeError: If zip generation fails.
    """
    if not cards:
        raise ValueError("No cards provided for APKG export")

    # Step 1: Create model and notes
    model = _create_model()
    notes = []
    for card in cards:
        note = _create_note(
            model=model,
            translation=card.get("translation", ""),
            english=card.get("text", ""),
            audio_path=card.get("audio_path"),
            image_path=card.get("image_path"),
        )
        notes.append(note)

    # Step 2: Create base package (genanki handles database + zip structure)
    pkg_path = _create_package(notes, scenario, cefr_level, target_language)

    try:
        # Step 3: Inject media files
        _inject_media(pkg_path, cards)
    except Exception as e:
        logger.warning("Media injection failed, returning text-only .apkg: %s", e)
        # Return the text-only package — user still gets a usable .apkg

    return pkg_path
