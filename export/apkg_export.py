"""EuropaLex .apkg Export — creates a proper Anki package via genanki.

Two-phase approach:
    Phase 1: Build CSV + media folder (matching working_anki_example/cards.csv format)
    Phase 2: Package with genanki into .apkg file

Produces: .local/models/output/export/{scenario_slug}_{CEFR}_{LANG}.apkg
"""

import csv
import re
import random
import shutil
from pathlib import Path

import genanki

from export._constants import _PROJECT_ROOT, get_language_abbrev, sanitize_folder_name





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
) -> tuple[str, str]:
    """Build the HTML/markup strings for the card front fields.

    Returns both Image markup and Audio markup as a tuple.

    Args:
        translation: Target-language text (will be HTML-escaped).
        audio_path: Path to TTS .wav file or None.
        image_path: Path to illustration .png file or None.
        export_dir: Export directory containing collection.media/.
        base_name: Filename prefix ({scenario}_{CEFR}_{LANG}).
        card_index: Zero-based card index.

    Returns:
        Tuple of (image_markup, audio_markup) strings.
        image_markup: '<img src="{filename}">' or empty string
        audio_markup: '[sound:{filename}]' or empty string
    """
    media_dir = export_dir / "collection.media"
    media_dir.mkdir(parents=True, exist_ok=True)

    image_markup = ""
    if image_path:
        fname = _copy_media_file(image_path, media_dir, base_name, card_index, ".png")
        if fname:
            image_markup = f'<img src="collection.media/{fname}">'

    audio_markup = ""
    if audio_path:
        fname = _copy_media_file(audio_path, media_dir, base_name, card_index, ".wav")
        if fname:
            audio_markup = f"[sound:collection.media/{fname}]"

    return image_markup, audio_markup


# Card template and CSS from create_anki_deck.py reference script
FRONT_TEMPLATE = """
<div class="card-front">
  {{#Image}}<div class="media-image">{{Image}}</div>{{/Image}}
  <div class="target-text">{{TargetText}}</div>
  {{#Audio}}<div class="audio">{{Audio}}</div>{{/Audio}}
</div>
"""

BACK_TEMPLATE = """
{{FrontSide}}
<hr class="divider">
<div class="card-back">
  <div class="english-text">{{EnglishText}}</div>
</div>
"""

CSS = """
.card {
  font-family: 'Segoe UI', Arial, sans-serif;
  text-align: center;
  color: #1a1a1a;
  background: #fafafa;
  padding: 20px;
  max-width: 500px;
  margin: 0 auto;
}

.media-image img {
  max-width: 280px;
  max-height: 280px;
  border-radius: 12px;
  margin-bottom: 16px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.15);
}

.target-text {
  font-size: 2em;
  font-weight: 700;
  color: #2c3e50;
  margin: 12px 0;
  letter-spacing: 0.02em;
}

.audio {
  margin: 10px 0;
}

.divider {
  border: none;
  border-top: 2px solid #e0e0e0;
  margin: 20px auto;
  width: 60%;
}

.english-text {
  font-size: 1.4em;
  color: #555;
  font-style: italic;
  margin-top: 10px;
}
"""


def stable_id(seed: str) -> int:
    """Generate a stable numeric ID from a string seed."""
    rng = random.Random(seed)
    return rng.randint(1_000_000_000, 9_999_999_999)


def export_csv_for_anki(
    cards: list[dict],
    scenario: str,
    cefr_level: str,
    target_language: str,
) -> str:
    """Export cards as a proper Anki .apkg package via genanki.

    Two-phase approach:
        Phase 1: Build CSV + media folder (matching working_anki_example/cards.csv format)
        Phase 2: Package with genanki into .apkg file

    Args:
        cards: List of card dicts with keys: 'text', 'translation',
               'audio_path' (str or None), 'image_path' (str or None).
        scenario: Free-form scenario/topic string.
        cefr_level: CEFR level string (e.g., 'A2', 'B1').
        target_language: Target language name (e.g., 'Latvian').

    Returns:
        Absolute path to the generated .apkg file.

    Raises:
        ValueError: If no cards provided or target_language not supported.
    """
    if not cards:
        raise ValueError("No cards provided for Anki export")

    lang_abbrev = get_language_abbrev(target_language)
    scenario_slug = sanitize_folder_name(scenario)
    folder_name = f"{scenario_slug}_{cefr_level}_{lang_abbrev}"

    # Resolve output directory (same pattern as csv_export.py)
    export_base = _PROJECT_ROOT / ".local" / "models" / "output" / "export"
    export_base.mkdir(parents=True, exist_ok=True)

    export_dir = export_base / folder_name
    export_dir.mkdir(parents=True, exist_ok=True)

    media_dir = export_dir / "collection.media"
    media_dir.mkdir(parents=True, exist_ok=True)

    # ── Phase 1: Build CSV + media folder ──────────────────────────────

    csv_path = export_dir / "cards.csv"
    with open(csv_path, 'w', newline='', encoding='utf-8-sig') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['Front', 'Audio', 'Image', 'Back'])

        for i, card in enumerate(cards):
            base_name = f"{scenario_slug}_{cefr_level}_{lang_abbrev}"
            translation = card.get("translation", "")
            image_markup, audio_markup = _build_front_html(
                translation=translation,
                audio_path=card.get("audio_path"),
                image_path=card.get("image_path"),
                export_dir=export_dir,
                base_name=base_name,
                card_index=i,
            )
            back_text = card.get("text", "")
            writer.writerow([translation, audio_markup, image_markup, back_text])

    # ── Phase 2: Package with genanki ───────────────────────────────────

    model = genanki.Model(
        model_id=stable_id(folder_name + "_model"),
        name="Language Card (Text + Image + Audio)",
        fields=[
            {"name": "TargetText"},
            {"name": "EnglishText"},
            {"name": "Image"},
            {"name": "Audio"},
        ],
        templates=[
            {
                "name": "Card 1",
                "qfmt": FRONT_TEMPLATE,
                "afmt": BACK_TEMPLATE,
            }
        ],
        css=CSS,
    )

    deck = genanki.Deck(
        deck_id=stable_id(folder_name),
        name="EuropaLex Flashcards",
    )

    media_files = []
    card_count = 0

    # Read CSV back (same logic as create_anki_deck.py)
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        csv_lines = [l for l in f if not l.strip().startswith("#")]

    reader = csv.DictReader(csv_lines)
    reader.fieldnames = [h.strip().lower() for h in reader.fieldnames]

    for i, row in enumerate(reader, start=2):
        target = row.get("front", "").strip()
        english = row.get("back", "").strip()
        img_raw = row.get("image", "").strip()
        aud_raw = row.get("audio", "").strip()

        if not target or not english:
            continue

        # Extract bare filename from image markup: <img src="collection.media/foo.png">
        img_fn = ""
        if img_raw:
            match = re.search(r'src=["\']collection\.media/([^"\']+)["\']', img_raw)
            if match:
                img_fn = match.group(1)

        # Extract bare filename from audio markup: [sound:collection.media/foo.wav]
        aud_fn = ""
        if aud_raw:
            match = re.search(r'\[sound:collection\.media/([^\]]+)\]', aud_raw)
            if match:
                aud_fn = match.group(1)

        # Build image field with bare filename
        img_field = ""
        if img_fn:
            img_path = media_dir / img_fn
            if img_path.exists():
                img_field = f'<img src="{img_fn}">'
                media_files.append(img_path)

        # Build audio field with bare filename
        aud_field = ""
        if aud_fn:
            aud_path = media_dir / aud_fn
            if aud_path.exists():
                aud_field = f"[sound:{aud_fn}]"
                media_files.append(aud_path)

        note = genanki.Note(
            model=model,
            fields=[target, english, img_field, aud_field],
        )
        deck.add_note(note)
        card_count += 1

    if card_count == 0:
        raise ValueError("No valid cards found after processing")

    # Package and save
    package = genanki.Package(deck)
    package.media_files = list(dict.fromkeys(media_files))   # deduplicate, preserve order
    apkg_path = str(export_base / f"{folder_name}.apkg")
    package.write_to_file(apkg_path)

    return apkg_path
