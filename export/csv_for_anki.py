"""EuropaLex CSV-for-Anki Export — creates an Anki-compatible zip with HTML media references.

Produces a zipped folder containing:
    {folder_name}/
        cards.csv                    (2 columns: Front, Back — HTML embedded)
        collection.media/            (media files following Anki convention)

Uses Anki's native text-file import mechanism with embedded media via
relative paths in <img> and <audio> tags.
"""

import csv
import html
import re
import shutil
from pathlib import Path

# ISO 639-1 language abbreviation mapping — mirrors csv_export.py exactly
_LANGUAGE_ABBREVS: dict[str, str] = {
    "Latvian": "LV",
    "Spanish": "ES",
    "French": "FR",
    "German": "DE",
    "Polish": "PL",
    "Italian": "IT",
    "Portuguese": "PT",
    "Finnish": "FI",
}

# Project root for resolving relative paths — mirrors csv_export.py
_PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _sanitize_folder_name(scenario: str) -> str:
    """Convert scenario text to a filesystem-safe folder name slug.

    Same implementation as csv_export._sanitize_folder_name for consistency.

    Args:
        scenario: Free-form scenario/topic string from the user.

    Returns:
        Sanitized slug suitable for use as a directory name.
    """
    slug = scenario.strip().lower()
    slug = re.sub(r'[^a-z0-9\s_]', '', slug)   # remove special chars
    slug = re.sub(r'\s+', '_', slug)             # spaces → underscores
    slug = re.sub(r'_+', '_', slug)              # collapse multiple underscores
    return slug.strip('_')


def _get_language_abbrev(language: str) -> str:
    """Return the ISO 639-1 abbreviation for a language name.

    Args:
        language: Language name (e.g., 'Latvian', 'Spanish').

    Returns:
        Two-letter ISO 639-1 code.

    Raises:
        ValueError: If the language is not in the mapping.
    """
    if language not in _LANGUAGE_ABBREVS:
        raise ValueError(
            f"Unknown language '{language}'. "
            f"Supported: {', '.join(sorted(_LANGUAGE_ABBREVS.keys()))}"
        )
    return _LANGUAGE_ABBREVS[language]


def _copy_media_file(
    src_path: str | None,
    dest_dir: Path,
    filename_prefix: str,
    card_index: int,
    ext: str,
) -> str | None:
    """Copy a media file to the export media directory and return its filename, or None.

    Args:
        src_path: Source file path or None.
        dest_dir: Destination media directory (collection.media/).
        filename_prefix: Filename prefix ({scenario}_{CEFR}_{LANG}).
        card_index: Zero-based card index for the filename suffix.
        ext: File extension including dot (e.g., '.wav', '.png').

    Returns:
        Bare media filename or None if skipped.
    """
    if not src_path or not Path(src_path).exists():
        return None
    media_filename = f"{filename_prefix}_{card_index}{ext}"
    shutil.copy2(src_path, str(dest_dir / media_filename))
    return media_filename


def _build_front_html(
    translation: str,
    audio_path: str | None,
    image_path: str | None,
    export_dir: Path,
    base_name: str,
    card_index: int,
) -> str:
    """Build the HTML string for the card front field.

    Format: <b>translation</b><br>[<img>]<br>[<audio>]
    Tags are omitted entirely if media paths are None/missing.

    Args:
        translation: Target-language text (will be HTML-escaped).
        audio_path: Path to TTS .wav file or None.
        image_path: Path to illustration .png file or None.
        export_dir: Export directory containing collection.media/.
        base_name: Filename prefix ({scenario}_{CEFR}_{LANG}).
        card_index: Zero-based card index.

    Returns:
        HTML string for the Front field.
    """
    media_dir = export_dir / "collection.media"
    parts = [f"<b>{html.escape(translation)}</b>"]

    if image_path:
        fname = _copy_media_file(image_path, media_dir, base_name, card_index, ".png")
        if fname:
            parts.append(f'<img src="collection.media/{fname}">')

    if audio_path:
        fname = _copy_media_file(audio_path, media_dir, base_name, card_index, ".wav")
        if fname:
            parts.append(f'<audio controls src="collection.media/{fname}"></audio>')

    return "<br>".join(parts)


def export_csv_for_anki(
    cards: list[dict],
    scenario: str,
    cefr_level: str,
    target_language: str,
) -> str:
    """Export cards as an Anki-compatible CSV zip with HTML media references.

    Args:
        cards: List of card dicts with keys: 'text', 'translation',
               'audio_path' (str or None), 'image_path' (str or None).
        scenario: Free-form scenario/topic string.
        cefr_level: CEFR level string (e.g., 'A2', 'B1').
        target_language: Target language name (e.g., 'Latvian').

    Returns:
        Absolute path to the generated .zip file.

    Raises:
        ValueError: If no cards provided or target_language not supported.
    """
    if not cards:
        raise ValueError("No cards provided for Anki CSV export")

    lang_abbrev = _get_language_abbrev(target_language)
    scenario_slug = _sanitize_folder_name(scenario)
    folder_name = f"{scenario_slug}_{cefr_level}_{lang_abbrev}"

    # Resolve output directory (same pattern as csv_export.py)
    export_base = _PROJECT_ROOT / ".local" / "models" / "output" / "export"
    export_base.mkdir(parents=True, exist_ok=True)

    export_dir = export_base / folder_name
    export_dir.mkdir(parents=True, exist_ok=True)

    media_dir = export_dir / "collection.media"
    media_dir.mkdir(parents=True, exist_ok=True)

    # Build CSV rows and copy media files
    csv_path = export_dir / "cards.csv"
    with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['Front', 'Back'])

        for i, card in enumerate(cards):
            base_name = f"{scenario_slug}_{cefr_level}_{lang_abbrev}"
            front_html = _build_front_html(
                translation=card.get("translation", ""),
                audio_path=card.get("audio_path"),
                image_path=card.get("image_path"),
                export_dir=export_dir,
                base_name=base_name,
                card_index=i,
            )
            back_text = card.get("text", "")
            writer.writerow([front_html, back_text])

    # Create zip archive
    zip_path = shutil.make_archive(
        str(export_base / folder_name),
        'zip',
        export_dir,
    )

    return str(zip_path)
