"""EuropaLex CSV Export — creates a zipped folder containing CSV + media files."""

import csv
import shutil
from pathlib import Path
from typing import Any

from export._constants import _PROJECT_ROOT, get_language_abbrev, sanitize_folder_name





def export_csv_zip(
    cards: list[dict[str, Any]],
    scenario: str,
    cefr_level: str,
    target_language: str,
) -> str:
    """Export cards as a zipped folder containing CSV + media files.

    Creates a folder under {models_dir}/output/export/ with the following flat structure:
        {folder_name}/
            cards.csv                          (CSV with 7 columns, one row per card)
            {scenario_slug}_{CEFR}_{LANG}_0.wav   (copied from TTS output)
            {scenario_slug}_{CEFR}_{LANG}_0.png   (copied from image generation)
        {folder_name}.zip                       (zipped archive of the above)

    CSV columns: scenario, cefr_level, target_language, english_text, translated_text,
                 audio_filename, image_filename

    Media filenames are bare filenames in the export folder (e.g., 'ordering_coffee_A2_LV_0.wav').
    Missing media files are silently skipped — CSV entries remain empty strings.

    Args:
        cards: List of card dicts with keys: 'text', 'translation',
               'audio_path' (str or None), 'image_path' (str or None).
        scenario: Free-form scenario/topic string.
        cefr_level: CEFR level string (e.g., 'A2', 'B1').
        target_language: Target language name (e.g., 'Latvian').

    Returns:
        Absolute path to the generated .zip file.

    Raises:
        ValueError: If target_language is not in the supported mapping.
        RuntimeError: If zip creation fails.
    """
    # Resolve output directory from project root
    export_base = _PROJECT_ROOT / ".local" / "models" / "output" / "export"
    export_base.mkdir(parents=True, exist_ok=True)

    # Build folder name
    scenario_slug = sanitize_folder_name(scenario)
    lang_abbrev = get_language_abbrev(target_language)
    folder_name = f"{scenario_slug}_{cefr_level}_{lang_abbrev}"
    export_dir = export_base / folder_name
    export_dir.mkdir(parents=True, exist_ok=True)

    # Copy media files and build CSV rows (flat folder — no subfolders)
    csv_path = export_dir / "cards.csv"
    with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile, quoting=csv.QUOTE_ALL)
        # Header row
        writer.writerow([
            'scenario', 'cefr_level', 'target_language',
            'english_text', 'translated_text',
            'audio_filename', 'image_filename'
        ])
        for i, card in enumerate(cards):
            audio_path = card.get('audio_path')
            image_path = card.get('image_path')

            # Build the common prefix: {scenario_slug}_{CEFR}_{LANG_ABBREV}
            base_name = f"{scenario_slug}_{cefr_level}_{lang_abbrev}"

            # Copy audio file if it exists — flat naming
            audio_filename = ''
            if audio_path and Path(audio_path).exists():
                audio_dst = export_dir / f"{base_name}_{i}.wav"
                shutil.copy2(audio_path, audio_dst)
                audio_filename = f"{base_name}_{i}.wav"

            # Copy image file if it exists — flat naming
            image_filename = ''
            if image_path and Path(image_path).exists():
                image_dst = export_dir / f"{base_name}_{i}.png"
                shutil.copy2(image_path, image_dst)
                image_filename = f"{base_name}_{i}.png"

            writer.writerow([
                scenario,
                cefr_level,
                target_language,
                card.get('text', ''),
                card.get('translation', ''),
                audio_filename,
                image_filename,
            ])

    # Create zip archive
    zip_path = shutil.make_archive(
        str(export_base / folder_name),
        'zip',
        export_dir,
    )

    return str(zip_path)
