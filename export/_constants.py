"""Shared constants for EuropaLex export modules."""

import re
from pathlib import Path

# Project root for resolving relative paths.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent

import re

# ISO 639-1 language abbreviation mapping — kept in sync with all export targets.
_LANGUAGE_ABBREVS: dict[str, str] = {
    "Bulgarian": "BG",
    "Croatian": "HR",
    "Czech": "CS",
    "Danish": "DA",
    "Dutch": "NL",
    "Estonian": "ET",
    "Finnish": "FI",
    "French": "FR",
    "German": "DE",
    "Greek": "EL",
    "Hungarian": "HU",
    "Irish": "GA",
    "Italian": "IT",
    "Latvian": "LV",
    "Lithuanian": "LT",
    "Maltese": "MT",
    "Polish": "PL",
    "Portuguese": "PT",
    "Romanian": "RO",
    "Slovak": "SK",
    "Slovenian": "SL",
    "Spanish": "ES",
    "Swedish": "SV",
}


def get_language_abbrev(language: str) -> str:
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


def sanitize_folder_name(scenario: str) -> str:
    """Convert scenario text to a filesystem-safe folder name slug.

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
